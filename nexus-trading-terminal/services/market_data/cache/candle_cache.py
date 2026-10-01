"""Incremental candle cache.

Holds the most recent frame per (provider, symbol, timeframe). On refresh it
asks the provider only for the bars that can have changed since the last
fetch and merges them in, which keeps API usage low for live providers.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import pandas as pd

from market_data.models import CandleSeries, Timeframe

DEFAULT_TTL: dict[Timeframe, float] = {
    Timeframe.M1: 5,
    Timeframe.M5: 10,
    Timeframe.M15: 15,
    Timeframe.M30: 20,
    Timeframe.H1: 30,
    Timeframe.H4: 60,
    Timeframe.D1: 120,
    Timeframe.W1: 300,
}
MAX_CACHED_BARS = 5000


@dataclass
class _Entry:
    series: CandleSeries
    fetched_mono: float
    fetched_wall: float


class CandleCache:
    def __init__(self, ttl: dict[Timeframe, float] | None = None, ttl_multiplier: float = 1.0):
        self._ttl = {tf: v * ttl_multiplier for tf, v in (ttl or DEFAULT_TTL).items()}
        self._entries: dict[tuple[str, str, Timeframe], _Entry] = {}
        self._locks: dict[tuple[str, str, Timeframe], asyncio.Lock] = {}
        self.hits = 0
        self.misses = 0

    def _lock(self, key: tuple[str, str, Timeframe]) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def get(
        self,
        provider: str,
        symbol: str,
        timeframe: Timeframe,
        limit: int,
        fetch: Callable[[int], Awaitable[CandleSeries]],
        incremental: bool = True,
    ) -> CandleSeries:
        key = (provider, symbol, timeframe)
        async with self._lock(key):
            entry = self._entries.get(key)
            now_mono = time.monotonic()
            if (
                entry
                and now_mono - entry.fetched_mono < self._ttl[timeframe]
                and len(entry.series.df) >= limit
            ):
                self.hits += 1
                return _tail(entry.series, limit)
            self.misses += 1
            if entry and incremental and len(entry.series.df) >= limit:
                elapsed = time.time() - entry.fetched_wall
                n_new = int(elapsed // timeframe.seconds) + 3
                if n_new < limit:
                    fresh = await fetch(n_new)
                    merged = pd.concat([entry.series.df, fresh.df])
                    merged = (
                        merged[~merged.index.duplicated(keep="last")].sort_index().iloc[-MAX_CACHED_BARS:]
                    )
                    series = CandleSeries(
                        symbol=fresh.symbol,
                        timeframe=fresh.timeframe,
                        provider=fresh.provider,
                        is_demo=fresh.is_demo,
                        df=merged,
                        fetched_at=fresh.fetched_at,
                        last_bar_complete=fresh.last_bar_complete,
                        volume_available=fresh.volume_available,
                    )
                    self._entries[key] = _Entry(series, now_mono, time.time())
                    return _tail(series, limit)
            series = await fetch(limit)
            self._entries[key] = _Entry(series, now_mono, time.time())
            return _tail(series, limit)

    def invalidate(self, provider: str | None = None) -> None:
        if provider is None:
            self._entries.clear()
            return
        for key in [k for k in self._entries if k[0] == provider]:
            del self._entries[key]

    def stats(self) -> dict[str, int]:
        return {"entries": len(self._entries), "hits": self.hits, "misses": self.misses}


def _tail(series: CandleSeries, limit: int) -> CandleSeries:
    if len(series.df) <= limit:
        return series
    return CandleSeries(
        symbol=series.symbol,
        timeframe=series.timeframe,
        provider=series.provider,
        is_demo=series.is_demo,
        df=series.df.iloc[-limit:],
        fetched_at=series.fetched_at,
        last_bar_complete=series.last_bar_complete,
        volume_available=series.volume_available,
    )

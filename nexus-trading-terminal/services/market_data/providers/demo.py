"""DEMO MODE market data provider.

Serves deterministic synthetic prices from `DemoPriceModel`. Everything it
returns is tagged provider="demo" and is_demo=True. It never claims to be live.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from market_data.assets import DEFAULT_CATALOG, AssetCatalog
from market_data.models import AssetSpec, CandleSeries, MarketStatus, ProviderHealth, Quote, Timeframe
from market_data.providers.base import MarketDataError, MarketDataProvider
from market_data.providers.demo_model import EPOCH, DemoPriceModel
from market_data.sessions import is_open

MAX_DEMO_BARS = 200_000


class DemoMarketDataProvider(MarketDataProvider):
    name = "demo"
    is_demo = True

    def __init__(self, catalog: AssetCatalog | None = None, clock: Callable[[], datetime] | None = None):
        self.catalog = catalog or DEFAULT_CATALOG
        self._clock = clock or (lambda: datetime.now(UTC))
        self._models: dict[str, DemoPriceModel] = {}

    def model(self, symbol: str) -> DemoPriceModel:
        spec = self._spec(symbol)
        m = self._models.get(spec.symbol)
        if m is None:
            m = DemoPriceModel(spec)
            self._models[spec.symbol] = m
        return m

    def _spec(self, symbol: str) -> AssetSpec:
        try:
            return self.catalog.get(symbol)
        except KeyError as exc:
            raise MarketDataError("INVALID_SYMBOL", f"Unknown symbol '{symbol}'") from exc

    def now(self) -> datetime:
        return self._clock()

    def quote_sync(self, symbol: str, at: datetime | None = None) -> Quote:
        spec = self._spec(symbol)
        m = self.model(spec.symbol)
        now = at or self.now()
        price = m.price_at(now)
        ref = m.price_at(now - timedelta(hours=24))
        half = m.spread_at(now) / 2.0
        open_, _ = is_open(spec.session, now)
        return Quote(
            symbol=spec.symbol,
            bid=spec.round_price(price - half),
            ask=spec.round_price(price + half),
            price=spec.round_price(price),
            timestamp=now,
            provider=self.name,
            is_demo=True,
            change_24h=spec.round_price(price - ref),
            change_pct_24h=round((price / ref - 1.0) * 100.0, 3) if ref else None,
            market_open=open_,
        )

    async def get_quote(self, symbol: str) -> Quote:
        return self.quote_sync(symbol)

    def candles_sync(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 500,
        end: datetime | None = None,
        start: datetime | None = None,
    ) -> CandleSeries:
        spec = self._spec(symbol)
        now = self.now()
        end = min(end or now, now)
        if start is not None and start < EPOCH:
            start = EPOCH
        if start is not None:
            est_bars = (end - start).total_seconds() / timeframe.seconds
            if est_bars > MAX_DEMO_BARS:
                raise MarketDataError(
                    "INSUFFICIENT_DATA",
                    f"Requested range is too large ({int(est_bars)} bars); narrow the date range",
                )
        df, complete = self.model(spec.symbol).candles(timeframe, end, limit, start=start, now=now)
        for col in ("open", "high", "low", "close"):
            df[col] = df[col].round(spec.price_precision + 2)
        return CandleSeries(
            symbol=spec.symbol,
            timeframe=timeframe,
            provider=self.name,
            is_demo=True,
            df=df,
            fetched_at=now,
            last_bar_complete=complete,
            volume_available=True,
        )

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 500,
        end: datetime | None = None,
        start: datetime | None = None,
    ) -> CandleSeries:
        heavy = start is not None or timeframe in (Timeframe.W1, Timeframe.D1) or limit > 2000
        if heavy:
            return await asyncio.to_thread(self.candles_sync, symbol, timeframe, limit, end, start)
        return self.candles_sync(symbol, timeframe, limit, end, start)

    async def get_assets(self) -> list[AssetSpec]:
        return self.catalog.all()

    async def get_market_status(self, symbol: str) -> MarketStatus:
        spec = self._spec(symbol)
        now = self.now()
        open_, reason = is_open(spec.session, now)
        return MarketStatus(
            symbol=spec.symbol, is_open=open_, session=spec.session, reason=reason, checked_at=now
        )

    async def validate(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            status="DEMO",
            is_demo=True,
            detail="Deterministic synthetic data (DEMO MODE). Not real market prices.",
        )

    def history_start(self) -> datetime:
        return EPOCH

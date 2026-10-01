"""Twelve Data market data provider (LIVE data, requires MARKET_DATA_API_KEY).

Docs: https://twelvedata.com/docs  (endpoints used: /quote, /time_series)

Twelve Data does not publish bid/ask on its standard quote endpoint, so the
quote's spread is the instrument's configured typical spread and is flagged
`spread_is_estimate=True`. FX pairs carry no volume; candles are returned with
`volume_available=False` and the quant engine neutralises volume factors.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pandas as pd

from market_data.assets import DEFAULT_CATALOG, AssetCatalog
from market_data.models import AssetSpec, CandleSeries, MarketStatus, ProviderHealth, Quote, Timeframe
from market_data.normalization.normalize import frame_from_records
from market_data.providers.base import MarketDataError, MarketDataProvider
from market_data.sessions import is_open

BASE_URL = "https://api.twelvedata.com"

INTERVALS: dict[Timeframe, str] = {
    Timeframe.M1: "1min",
    Timeframe.M5: "5min",
    Timeframe.M15: "15min",
    Timeframe.M30: "30min",
    Timeframe.H1: "1h",
    Timeframe.H4: "4h",
    Timeframe.D1: "1day",
    Timeframe.W1: "1week",
}
MAX_OUTPUTSIZE = 5000


class TwelveDataProvider(MarketDataProvider):
    name = "twelvedata"
    is_demo = False

    def __init__(self, api_key: str, catalog: AssetCatalog | None = None, timeout: float = 10.0,
                 client: httpx.AsyncClient | None = None, clock: Callable[[], datetime] | None = None):
        if not api_key:
            raise ValueError("TwelveDataProvider requires an API key")
        self._api_key = api_key
        self.catalog = catalog or DEFAULT_CATALOG
        self._client = client or httpx.AsyncClient(base_url=BASE_URL, timeout=timeout)
        self._clock = clock or (lambda: datetime.now(UTC))

    def _symbol(self, spec: AssetSpec) -> str:
        mapped = spec.provider_symbols.get(self.name)
        if not mapped:
            raise MarketDataError("DATA_PROVIDER_UNAVAILABLE", f"No Twelve Data symbol mapping for {spec.symbol}")
        return mapped

    def _spec(self, symbol: str) -> AssetSpec:
        try:
            return self.catalog.get(symbol)
        except KeyError as exc:
            raise MarketDataError("INVALID_SYMBOL", f"Unknown symbol '{symbol}'") from exc

    async def _get(self, path: str, params: dict[str, str | int]) -> dict:
        query = {**params, "apikey": self._api_key}
        try:
            resp = await self._client.get(path, params=query)
        except httpx.HTTPError as exc:
            raise MarketDataError("DATA_PROVIDER_UNAVAILABLE", f"Twelve Data request failed: {type(exc).__name__}") from exc
        if resp.status_code != 200:
            raise MarketDataError("DATA_PROVIDER_UNAVAILABLE", f"Twelve Data HTTP {resp.status_code}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise MarketDataError("INVALID_MARKET_DATA", "Twelve Data returned non-JSON response") from exc
        if isinstance(payload, dict) and payload.get("status") == "error":
            raise MarketDataError("DATA_PROVIDER_UNAVAILABLE", f"Twelve Data error: {payload.get('message', 'unknown')}")
        return payload

    async def get_quote(self, symbol: str) -> Quote:
        spec = self._spec(symbol)
        payload = await self._get("/quote", {"symbol": self._symbol(spec)})
        return self._parse_quote(spec, payload)

    def _parse_quote(self, spec: AssetSpec, payload: dict) -> Quote:
        try:
            price = float(payload["close"])
            prev = float(payload.get("previous_close") or 0) or None
            ts_raw = payload.get("last_quote_at") or payload.get("timestamp")
            ts = datetime.fromtimestamp(int(ts_raw), tz=UTC) if ts_raw else self._clock()
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataError("INVALID_MARKET_DATA", f"Malformed Twelve Data quote for {spec.symbol}") from exc
        if price <= 0:
            raise MarketDataError("INVALID_MARKET_DATA", f"Non-positive price for {spec.symbol}")
        half = spec.typical_spread / 2.0
        open_flag = payload.get("is_market_open")
        market_open = bool(open_flag) if open_flag is not None else is_open(spec.session, self._clock())[0]
        return Quote(
            symbol=spec.symbol, bid=spec.round_price(price - half), ask=spec.round_price(price + half),
            price=spec.round_price(price), timestamp=ts, provider=self.name, is_demo=False,
            change_24h=spec.round_price(price - prev) if prev else None,
            change_pct_24h=round((price / prev - 1) * 100, 3) if prev else None,
            market_open=market_open, spread_is_estimate=True,
        )

    async def get_candles(self, symbol: str, timeframe: Timeframe, limit: int = 500,
                          end: datetime | None = None, start: datetime | None = None) -> CandleSeries:
        spec = self._spec(symbol)
        params: dict[str, str | int] = {
            "symbol": self._symbol(spec), "interval": INTERVALS[timeframe], "timezone": "UTC",
            "order": "ASC", "outputsize": min(max(limit, 1), MAX_OUTPUTSIZE),
        }
        if start is not None:
            params["start_date"] = start.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        if end is not None:
            params["end_date"] = end.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        payload = await self._get("/time_series", params)
        values = payload.get("values")
        if not isinstance(values, list) or not values:
            raise MarketDataError("INSUFFICIENT_DATA", f"Twelve Data returned no candles for {spec.symbol}")
        records = [
            {"timestamp": v.get("datetime"), "open": v.get("open"), "high": v.get("high"), "low": v.get("low"),
             "close": v.get("close"), "volume": v.get("volume")}
            for v in values
        ]
        df = frame_from_records(records)
        volume_available = bool(df["volume"].notna().any() and (df["volume"].fillna(0) > 0).any())
        df["volume"] = df["volume"].fillna(0.0)
        now = self._clock()
        last_open = df.index[-1].to_pydatetime() if len(df) else now
        complete = last_open + pd.Timedelta(seconds=timeframe.seconds).to_pytimedelta() <= now
        return CandleSeries(symbol=spec.symbol, timeframe=timeframe, provider=self.name, is_demo=False, df=df,
                            fetched_at=now, last_bar_complete=complete, volume_available=volume_available)

    async def get_assets(self) -> list[AssetSpec]:
        return [a for a in self.catalog.all() if self.name in a.provider_symbols]

    async def get_market_status(self, symbol: str) -> MarketStatus:
        spec = self._spec(symbol)
        now = self._clock()
        open_, reason = is_open(spec.session, now)
        return MarketStatus(symbol=spec.symbol, is_open=open_, session=spec.session,
                            reason=f"{reason} (session-rule approximation)", checked_at=now)

    async def validate(self) -> ProviderHealth:
        probe = self.catalog.all()[0]
        started = time.perf_counter()
        try:
            quote = await self.get_quote(probe.symbol)
        except MarketDataError as exc:
            return ProviderHealth(provider=self.name, status="ERROR", is_demo=False, detail=exc.message)
        latency = (time.perf_counter() - started) * 1000
        return ProviderHealth(provider=self.name, status="CONNECTED", is_demo=False, latency_ms=round(latency, 1),
                              detail=f"Validated with {quote.symbol} quote")

    async def close(self) -> None:
        await self._client.aclose()

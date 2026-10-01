"""Market data manager: chooses DEMO or LIVE data and never mixes them silently.

* Starts in DEMO MODE. If a live provider is configured, it is validated with
  a real request; only on success does the mode switch to LIVE.
* A live provider that fails later is reported as DISCONNECTED and its
  requests raise DATA_PROVIDER_UNAVAILABLE - the manager does not quietly
  substitute demo prices for live ones.
"""

from __future__ import annotations

import logging
from datetime import datetime

from market_data.assets import AssetCatalog
from market_data.cache.candle_cache import CandleCache
from market_data.models import CandleSeries, ProviderHealth, Quote, Timeframe
from market_data.normalization.validation import DataQualityReport, validate_series
from market_data.providers.base import MarketDataError, MarketDataProvider
from market_data.providers.demo import DemoMarketDataProvider
from market_data.providers.twelvedata import TwelveDataProvider

logger = logging.getLogger("nexus.market")


class MarketDataManager:
    def __init__(
        self,
        catalog: AssetCatalog,
        provider_name: str = "demo",
        api_key: str | None = None,
        ttl_multiplier: float = 1.0,
        demo: DemoMarketDataProvider | None = None,
    ):
        self.catalog = catalog
        self.demo = demo or DemoMarketDataProvider(catalog)
        self.live: MarketDataProvider | None = None
        self.configured_name = provider_name
        self.health = ProviderHealth(
            provider="demo",
            status="DEMO",
            is_demo=True,
            detail="Demo market data active (no live provider configured)",
        )
        if provider_name == "twelvedata" and api_key:
            self.live = TwelveDataProvider(api_key, catalog)
        elif provider_name not in ("demo", "", None):
            self.health.detail = (
                f"Market data provider '{provider_name}' is not configured (missing API key or unsupported)"
            )
        self.mode = "DEMO"
        self.cache = CandleCache(ttl_multiplier=ttl_multiplier)
        self._live_failures = 0

    @property
    def active(self) -> MarketDataProvider:
        return self.live if self.mode == "LIVE" and self.live is not None else self.demo

    @property
    def is_demo(self) -> bool:
        return self.active.is_demo

    async def init(self) -> None:
        if self.live is None:
            return
        health = await self.live.validate()
        if health.status == "CONNECTED":
            self.mode = "LIVE"
            self.health = health
            logger.info(
                "market_data_live", extra={"event": "market_data_live", "data": {"provider": self.live.name}}
            )
        else:
            self.mode = "DEMO"
            self.health = ProviderHealth(
                provider=self.live.name,
                status="ERROR",
                is_demo=True,
                detail=f"Live provider failed validation ({health.detail}); DEMO data retained",
            )
            logger.warning(
                "market_data_validation_failed",
                extra={"event": "market_data_validation_failed", "data": {"detail": health.detail}},
            )

    async def revalidate(self) -> ProviderHealth:
        if self.live is None:
            return self.health
        health = await self.live.validate()
        if self.mode == "LIVE":
            self.health = (
                health
                if health.status == "CONNECTED"
                else ProviderHealth(
                    provider=self.live.name, status="DISCONNECTED", is_demo=False, detail=health.detail
                )
            )
        elif health.status == "CONNECTED":
            # Switching DEMO -> LIVE requires a restart so demo and live data are never mixed in one session.
            self.health = ProviderHealth(
                provider=self.live.name,
                status="ERROR",
                is_demo=True,
                detail="Live provider now validates; restart the API to switch from DEMO to LIVE",
            )
        return self.health

    def _record(self, ok: bool, err: MarketDataError | None = None) -> None:
        if self.mode != "LIVE" or self.live is None:
            return
        if ok:
            self._live_failures = 0
            if self.health.status != "CONNECTED":
                self.health = ProviderHealth(
                    provider=self.live.name, status="CONNECTED", is_demo=False, detail="Recovered"
                )
        else:
            self._live_failures += 1
            if self._live_failures >= 3:
                self.health = ProviderHealth(
                    provider=self.live.name,
                    status="DISCONNECTED",
                    is_demo=False,
                    detail=err.message if err else "Repeated failures",
                )

    async def quote(self, symbol: str) -> Quote:
        try:
            q = await self.active.get_quote(symbol)
            self._record(True)
            return q
        except MarketDataError as exc:
            self._record(False, exc)
            raise

    async def candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 500,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> CandleSeries:
        spec = self.catalog.get(symbol)
        provider = self.active
        try:
            if start is not None or end is not None:
                series = await provider.get_candles(spec.symbol, timeframe, limit, end=end, start=start)
            else:
                series = await self.cache.get(
                    provider.name,
                    spec.symbol,
                    timeframe,
                    limit,
                    lambda n: provider.get_candles(spec.symbol, timeframe, n),
                    incremental=not provider.is_demo,
                )
            self._record(True)
            return series
        except MarketDataError as exc:
            self._record(False, exc)
            raise

    async def validated(
        self, symbol: str, timeframe: Timeframe, limit: int = 500
    ) -> tuple[CandleSeries, DataQualityReport]:
        series = await self.candles(symbol, timeframe, limit)
        return validate_series(series, self.catalog.get(symbol), self._now())

    def _now(self) -> datetime:
        from datetime import UTC

        return self.demo.now() if self.mode == "DEMO" else datetime.now(UTC)

    def now(self) -> datetime:
        return self._now()

    def status(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "provider": self.active.name,
            "configured_provider": self.configured_name,
            "health": self.health.model_dump(mode="json"),
            "cache": self.cache.stats(),
        }

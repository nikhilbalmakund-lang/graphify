"""Market data provider abstraction.

Every provider returns provenance-tagged objects (provider name + demo flag)
so the rest of the system can always tell DEMO data from LIVE data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd

from market_data.models import AssetSpec, CandleSeries, MarketStatus, ProviderHealth, Quote, Timeframe


class MarketDataError(Exception):
    """Raised when a provider cannot return valid data."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class MarketDataProvider(ABC):
    name: str = "abstract"
    is_demo: bool = False

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote: ...

    @abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 500,
        end: datetime | None = None,
        start: datetime | None = None,
    ) -> CandleSeries: ...

    async def get_volume(self, symbol: str, timeframe: Timeframe, limit: int = 200) -> pd.Series:
        series = await self.get_candles(symbol, timeframe, limit)
        return series.df["volume"]

    @abstractmethod
    async def get_assets(self) -> list[AssetSpec]: ...

    @abstractmethod
    async def get_market_status(self, symbol: str) -> MarketStatus: ...

    @abstractmethod
    async def validate(self) -> ProviderHealth:
        """Check connectivity/credentials by fetching real data. Never raises."""

    async def close(self) -> None:  # pragma: no cover - optional hook
        return None

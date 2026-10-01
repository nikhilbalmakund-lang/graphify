"""Core market data domain types shared by every service package.

These types intentionally carry provenance (provider, demo flag, timestamps)
so that DEMO data can never be confused with LIVE data downstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

import pandas as pd
from pydantic import BaseModel, Field


class AssetClass(StrEnum):
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"
    INDICES = "INDICES"
    COMMODITIES = "COMMODITIES"


class SessionType(StrEnum):
    """Trading-hours template used to decide whether a market is open."""

    FX = "FX"  # Sun 21:00 UTC -> Fri 21:00 UTC, no daily break
    CFD = "CFD"  # FX hours plus a daily 21:00-22:00 UTC maintenance break (Mon-Thu)
    CRYPTO = "CRYPTO"  # 24/7


class DataMode(StrEnum):
    LIVE = "LIVE"
    DEMO = "DEMO"
    IMPORTED = "IMPORTED"


class Timeframe(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1H"
    H4 = "4H"
    D1 = "1D"
    W1 = "1W"

    @property
    def seconds(self) -> int:
        return _TF_SECONDS[self]

    @property
    def minutes(self) -> int:
        return _TF_SECONDS[self] // 60

    @property
    def pandas_rule(self) -> str:
        return _TF_RULE[self]

    @property
    def is_intraday(self) -> bool:
        return self.seconds < 86_400

    @classmethod
    def parse(cls, value: str) -> Timeframe:
        """Accept canonical values plus common aliases (1h, 4h, 1d, 1w, 60m...)."""
        v = value.strip()
        aliases = {
            "1h": "1H",
            "60m": "1H",
            "4h": "4H",
            "240m": "4H",
            "1d": "1D",
            "d": "1D",
            "1w": "1W",
            "w": "1W",
            "1min": "1m",
            "5min": "5m",
            "15min": "15m",
            "30min": "30m",
        }
        v = aliases.get(v.lower(), v) if v not in cls._value2member_map_ else v
        try:
            return cls(v)
        except ValueError as exc:
            raise ValueError(f"Unsupported timeframe '{value}'") from exc


_TF_SECONDS: dict[Timeframe, int] = {
    Timeframe.M1: 60,
    Timeframe.M5: 300,
    Timeframe.M15: 900,
    Timeframe.M30: 1800,
    Timeframe.H1: 3600,
    Timeframe.H4: 14_400,
    Timeframe.D1: 86_400,
    Timeframe.W1: 604_800,
}

_TF_RULE: dict[Timeframe, str] = {
    Timeframe.M1: "1min",
    Timeframe.M5: "5min",
    Timeframe.M15: "15min",
    Timeframe.M30: "30min",
    Timeframe.H1: "1h",
    Timeframe.H4: "4h",
    Timeframe.D1: "1D",
    Timeframe.W1: "W-MON",
}

ANALYSIS_TIMEFRAMES: tuple[Timeframe, ...] = (
    Timeframe.M1,
    Timeframe.M5,
    Timeframe.M15,
    Timeframe.M30,
    Timeframe.H1,
    Timeframe.H4,
    Timeframe.D1,
)


class AssetSpec(BaseModel):
    """Instrument specification. Contract math (pip value, sizing) relies on it."""

    symbol: str
    name: str
    asset_class: AssetClass
    session: SessionType
    base: str
    quote: str = "USD"
    currencies: list[str] = Field(
        default_factory=list, description="Currencies whose macro events affect this asset"
    )
    price_precision: int = 2
    tick_size: float = 0.01
    pip_size: float = 0.01
    contract_size: float = 1.0
    min_lot: float = 0.01
    lot_step: float = 0.01
    max_lot: float = 100.0
    max_leverage: float = 20.0
    typical_spread: float = 0.0
    commission_per_lot: float = 0.0
    commission_pct: float = 0.0
    # DEMO MODE ONLY: parameters for the deterministic synthetic price model.
    demo_anchor_price: float = 1.0
    demo_daily_vol: float = 0.01
    demo_base_volume: float = 1000.0
    provider_symbols: dict[str, str] = Field(default_factory=dict)

    def round_price(self, price: float) -> float:
        return round(price, self.price_precision)

    def value_per_point(self, lots: float = 1.0) -> float:
        """Account-currency (USD) value of a 1.0 price move for `lots` lots.

        For USD-quoted instruments this is contract_size * lots. For USD-base
        pairs (e.g. USDJPY) callers must divide by the current price; see
        `risk.sizing.pnl_in_account_ccy`.
        """
        return self.contract_size * lots


class Quote(BaseModel):
    symbol: str
    bid: float
    ask: float
    price: float
    timestamp: datetime
    provider: str
    is_demo: bool
    change_24h: float | None = None
    change_pct_24h: float | None = None
    market_open: bool = True
    spread_is_estimate: bool = False

    @property
    def spread(self) -> float:
        return self.ask - self.bid


class MarketStatus(BaseModel):
    symbol: str
    is_open: bool
    session: SessionType
    reason: str
    checked_at: datetime


class ProviderHealth(BaseModel):
    provider: str
    status: str  # CONNECTED | DEMO | DISCONNECTED | ERROR | NOT_CONFIGURED
    is_demo: bool
    detail: str = ""
    latency_ms: float | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


@dataclass
class CandleSeries:
    """A provenance-tagged OHLCV frame.

    `df` has a tz-aware UTC DatetimeIndex (bar open time) and the columns
    open/high/low/close/volume. The final bar may be in progress when
    `last_bar_complete` is False.
    """

    symbol: str
    timeframe: Timeframe
    provider: str
    is_demo: bool
    df: pd.DataFrame
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_bar_complete: bool = False
    volume_available: bool = True

    @property
    def mode(self) -> DataMode:
        if self.provider.startswith("csv"):
            return DataMode.IMPORTED
        return DataMode.DEMO if self.is_demo else DataMode.LIVE

    def __len__(self) -> int:
        return len(self.df)

    @property
    def last_close(self) -> float:
        return float(self.df["close"].iloc[-1])

    @property
    def last_timestamp(self) -> datetime:
        ts = self.df.index[-1]
        return ts.to_pydatetime()

    def closed_bars(self) -> pd.DataFrame:
        """Bars that are fully closed (drops the in-progress bar if any)."""
        if self.last_bar_complete or len(self.df) == 0:
            return self.df
        return self.df.iloc[:-1]

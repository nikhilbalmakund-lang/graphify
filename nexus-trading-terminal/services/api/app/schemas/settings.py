"""Runtime (database-stored) settings categories. Secrets are NOT stored here."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from market_data.assets import DEFAULT_SYMBOLS
from quant.signals.models import ScoringWeights, SignalConfig
from risk.engine import RiskConfig


class SignalSettings(BaseModel):
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    min_score: float = Field(62.0, ge=0, le=100)
    min_score_margin: float = Field(6.0, ge=0, le=50)
    min_rr: float = Field(1.5, ge=0.5, le=10)
    max_spread_atr: float = Field(0.15, gt=0, le=2)
    max_vol_percentile: float = Field(97.0, ge=50, le=100)
    news_blackout_before_min: int = Field(45, ge=0, le=720)
    news_blackout_after_min: int = Field(15, ge=0, le=720)
    require_market_open: bool = True
    block_on_mtf_contradiction: bool = True
    min_historical_samples: int = Field(5, ge=0, le=500)
    min_historical_expectancy: float | None = None
    expiry_bars: int = Field(8, ge=1, le=100)
    exit_plan: list[float] = Field(default_factory=lambda: [0.5, 0.3, 0.2])

    def to_config(self) -> SignalConfig:
        return SignalConfig(**self.model_dump())


class AISettings(BaseModel):
    enabled_in_pipeline: bool = True
    block_on_low_agreement: bool = True
    require_ai_review: bool = False
    auto_briefings: bool = True
    ai_news_sentiment: bool = True
    max_calls_per_day: int = Field(200, ge=0, le=100_000)
    cache_minutes: int = Field(30, ge=0, le=1440)


class MarketSettings(BaseModel):
    default_assets: list[str] = Field(default_factory=lambda: list(DEFAULT_SYMBOLS))
    default_timeframe: Literal["1m", "5m", "15m", "30m", "1H", "4H", "1D"] = "15m"
    auto_scan: bool = True

    @field_validator("default_assets")
    @classmethod
    def _known(cls, v: list[str]) -> list[str]:
        unknown = [s for s in v if s.upper() not in DEFAULT_SYMBOLS]
        if unknown:
            raise ValueError(f"Unknown symbols: {unknown}")
        if not v:
            raise ValueError("At least one asset is required")
        return [s.upper() for s in v]


class PaperSettings(BaseModel):
    auto_execute_signals: bool = False
    slippage_bps: float = Field(1.0, ge=0, le=50)
    move_stop_to_breakeven: bool = True
    starting_balance: float = Field(100_000.0, ge=100, le=100_000_000)
    require_stop_loss: bool = True


class AppearanceSettings(BaseModel):
    accent: Literal["cyan", "purple", "emerald", "amber"] = "cyan"
    density: Literal["compact", "comfortable"] = "compact"
    reduce_motion: bool = False
    show_right_panel: bool = True


class NotificationSettings(BaseModel):
    browser_enabled: bool = False
    new_signal: bool = True
    signal_invalidated: bool = True
    target_reached: bool = True
    stop_reached: bool = True
    economic_event: bool = True
    risk_limit: bool = True
    data_disconnection: bool = True


class DataSettings(BaseModel):
    retention_days: int | None = Field(None, ge=7, le=3650, description="None = never delete automatically")
    retain_no_trade_days: int | None = Field(None, ge=1, le=3650)


class LiveTradingSettings(BaseModel):
    ui_switch_on: bool = False


CATEGORIES: dict[str, type[BaseModel]] = {
    "risk": RiskConfig,
    "signals": SignalSettings,
    "ai": AISettings,
    "markets": MarketSettings,
    "paper": PaperSettings,
    "appearance": AppearanceSettings,
    "notifications": NotificationSettings,
    "data": DataSettings,
    "live_trading": LiveTradingSettings,
}

SECRET_KEYS = (
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "MARKET_DATA_API_KEY",
    "NEWS_API_KEY",
    "ECONOMIC_CALENDAR_API_KEY",
    "BROKER_API_KEY",
    "BROKER_API_SECRET",
)
PROVIDER_KEYS = (
    "MARKET_DATA_PROVIDER",
    "NEWS_PROVIDER",
    "ECONOMIC_CALENDAR_PROVIDER",
    "CLAUDE_MODEL_FAST",
    "CLAUDE_MODEL_STRONG",
    "GEMINI_MODEL_FAST",
    "GEMINI_MODEL_STRONG",
)


class SecretsUpdate(BaseModel):
    values: dict[str, str | None] = Field(description="Keys to set; null or empty string clears a key")

    @field_validator("values")
    @classmethod
    def _allowed(cls, v: dict[str, str | None]) -> dict[str, str | None]:
        bad = [k for k in v if k not in SECRET_KEYS + PROVIDER_KEYS]
        if bad:
            raise ValueError(f"Unsupported keys: {bad}")
        for k, val in v.items():
            if val is not None and (len(val) > 500 or "\n" in val or "\r" in val):
                raise ValueError(f"Invalid value for {k}")
        return v


class SecretStatus(BaseModel):
    key: str
    configured: bool
    hint: str | None = Field(None, description="Last 4 characters only; the full key is never returned")

"""Signal-engine data structures."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from market_data.normalization.validation import DataQualityReport
from quant.features.feature_set import FeatureSnapshot
from quant.mtf.alignment import MTFAnalysis
from quant.regime.detector import RegimeResult
from quant.structure.engine import StructureSnapshot

SIGNAL_ENGINE_VERSION = "1.0.0"


class Direction(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"

    @property
    def sign(self) -> int:
        return {Direction.LONG: 1, Direction.SHORT: -1, Direction.NO_TRADE: 0}[self]


class EntryType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    ZONE = "ZONE"


class ScoringWeights(BaseModel):
    """Points available per factor. Normalised to a 100-point scale."""

    trend: float = 20
    structure: float = 20
    momentum: float = 15
    volume_vwap: float = 10
    liquidity: float = 10
    volatility: float = 10
    macro: float = 10
    sentiment: float = 5

    @model_validator(mode="after")
    def _non_negative(self) -> ScoringWeights:
        vals = self.model_dump()
        if any(v < 0 for v in vals.values()):
            raise ValueError("Scoring weights must be non-negative")
        if sum(vals.values()) <= 0:
            raise ValueError("At least one scoring weight must be positive")
        return self

    def normalised(self) -> dict[str, float]:
        vals = self.model_dump()
        total = sum(vals.values())
        return {k: v * 100.0 / total for k, v in vals.items()}


class SignalConfig(BaseModel):
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    min_score: float = 62.0
    min_score_margin: float = 6.0
    min_rr: float = 1.5
    max_spread_atr: float = 0.15
    max_vol_percentile: float = 97.0
    news_blackout_before_min: int = 45
    news_blackout_after_min: int = 15
    require_market_open: bool = True
    min_data_quality: float = 0.6
    block_on_mtf_contradiction: bool = True
    min_historical_samples: int = 5
    min_historical_expectancy: float | None = None
    expiry_bars: int = 8
    stop_buffer_atr: float = 0.25
    min_stop_atr: float = 0.5
    max_stop_atr: float = 4.0
    exit_plan: list[float] = Field(default_factory=lambda: [0.5, 0.3, 0.2])
    swing_left: int = 3
    swing_right: int = 3

    @model_validator(mode="after")
    def _check(self) -> SignalConfig:
        if abs(sum(self.exit_plan) - 1.0) > 1e-6 or len(self.exit_plan) != 3:
            raise ValueError("exit_plan must contain three allocations summing to 1.0")
        if not 0 <= self.min_score <= 100:
            raise ValueError("min_score must be within 0..100")
        return self


class MacroContext(BaseModel):
    """Cross-asset context relevant to one instrument. bias > 0 supports LONG."""

    available: bool = False
    bias: float = 0.0
    usd_basket_change_pct: float | None = None
    risk_sentiment: float | None = None
    notes_for_long: list[str] = Field(default_factory=list)
    notes_for_short: list[str] = Field(default_factory=list)


class SentimentContext(BaseModel):
    available: bool = False
    score: float = 0.0  # [-1, 1]
    articles: int = 0
    is_demo: bool = True
    source: str = ""


class EventRisk(BaseModel):
    available: bool = False
    is_demo: bool = True
    next_high_impact_minutes: float | None = None
    next_high_impact_event: str | None = None
    recent_high_impact_minutes: float | None = None
    in_blackout: bool = False
    detail: str = ""


class HistoricalEvidence(BaseModel):
    sample_size: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float | None = None
    avg_r: float | None = None
    expectancy: float | None = None
    max_drawdown_r: float | None = None
    sample_label: str = "NONE"  # NONE | INSUFFICIENT | SMALL | MODERATE | LARGE
    is_demo: bool = True
    notes: list[str] = Field(default_factory=list)


class SignalContext(BaseModel):
    symbol: str
    timeframe: str
    timestamp: str
    price: float
    bid: float
    ask: float
    spread_is_estimate: bool = False
    is_demo: bool = True
    provider: str = "demo"
    market_open: bool = True
    features: FeatureSnapshot
    structure: StructureSnapshot
    regime: RegimeResult
    mtf: MTFAnalysis
    data_quality: DataQualityReport
    macro: MacroContext = Field(default_factory=MacroContext)
    sentiment: SentimentContext = Field(default_factory=SentimentContext)
    events: EventRisk = Field(default_factory=EventRisk)
    ensemble: dict | None = None
    price_precision: int = 5


class ScoreComponent(BaseModel):
    name: str
    weight: float
    points: float
    raw: float  # directional sub-score in [-1, 1]
    notes_for: list[str] = Field(default_factory=list)
    notes_against: list[str] = Field(default_factory=list)


class TargetLevel(BaseModel):
    label: str
    price: float
    rr: float
    basis: str
    allocation: float


class LevelPlan(BaseModel):
    entry_type: EntryType
    entry_price: float
    entry_zone_low: float | None = None
    entry_zone_high: float | None = None
    stop: float
    invalidation_level: float
    invalidation_text: str
    stop_basis: str
    targets: list[TargetLevel]
    risk_distance: float
    reward_distance: float
    rr: float  # to the final target
    effective_rr: float  # weighted by the exit plan
    risk_atr: float


class FilterResult(BaseModel):
    name: str
    passed: bool
    blocking: bool = True
    detail: str = ""
    value: float | str | None = None
    threshold: float | str | None = None


class SignalCandidate(BaseModel):
    symbol: str
    timeframe: str
    timestamp: str
    price: float
    direction: Direction
    proposed_direction: Direction
    score: float
    score_long: float
    score_short: float
    components: list[ScoreComponent]
    mtf_adjustment: float = 0.0
    levels: LevelPlan | None = None
    regime: str
    regime_clarity: float = 0.0
    supporting_factors: list[str] = Field(default_factory=list)
    opposing_factors: list[str] = Field(default_factory=list)
    filters: list[FilterResult] = Field(default_factory=list)
    no_trade_reasons: list[str] = Field(default_factory=list)
    evidence: HistoricalEvidence | None = None
    expiry_bars: int = 8
    expires_at: str | None = None
    is_demo: bool = True
    provider: str = "demo"
    signal_engine_version: str = SIGNAL_ENGINE_VERSION
    feature_version: str = ""

    def component_points(self) -> dict[str, float]:
        return {c.name: round(c.points, 2) for c in self.components}

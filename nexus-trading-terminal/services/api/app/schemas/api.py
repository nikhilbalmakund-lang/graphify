"""Request and response schemas for the REST API (also drive the OpenAPI document)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backtesting.engine.engine import BacktestConfig
from backtesting.validation.walk_forward import WalkForwardConfig
from market_data.normalization.validation import DataQualityReport
from paper_trading.broker.base import Account, Fill, Order, Position

TimeframeStr = Literal["1m", "5m", "15m", "30m", "1H", "4H", "1D", "1W"]
AnalysisTimeframe = Literal["1m", "5m", "15m", "30m", "1H", "4H", "1D"]


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ModeMeta(BaseModel):
    mode: str = Field(description="LIVE or DEMO market data")
    provider: str
    is_demo: bool


class AssetOut(BaseModel):
    symbol: str
    name: str
    asset_class: str
    session: str
    price_precision: int
    pip_size: float
    contract_size: float
    min_lot: float
    lot_step: float
    max_leverage: float
    typical_spread: float
    currencies: list[str]
    market_open: bool
    market_status: str


class CandlesOut(BaseModel):
    symbol: str
    timeframe: str
    bars: list[list[float]] = Field(description="[unix_seconds, open, high, low, close, volume]")
    last_bar_complete: bool
    volume_available: bool
    data_quality: DataQualityReport
    price_precision: int
    mode: str
    provider: str
    is_demo: bool


class TargetOut(BaseModel):
    label: str
    price: float
    rr: float
    basis: str
    allocation: float


class SignalOutcomeOut(BaseModel):
    status: str
    filled: bool
    fill_time: str | None = None
    fill_price: float | None = None
    exit_time: str | None = None
    exit_reason: str | None = None
    r_multiple: float | None = None
    mfe_r: float | None = None
    mae_r: float | None = None
    tp_hits: list[str] = Field(default_factory=list)
    resolved: bool
    updated_at: str


class SignalOut(BaseModel):
    id: str
    symbol: str
    timeframe: str
    created_at: str
    bar_time: str
    direction: str
    proposed_direction: str
    status: str
    score: float = Field(description="SIGNAL SCORE 0-100: rules-based quality score, NOT a probability")
    score_long: float
    score_short: float
    regime: str
    price: float
    entry_type: str | None
    entry_price: float | None
    entry_zone_low: float | None
    entry_zone_high: float | None
    stop: float | None
    invalidation_level: float | None
    invalidation_text: str | None
    targets: list[TargetOut]
    rr: float | None
    effective_rr: float | None
    expires_at: str | None
    expiry_bars: int
    supporting: list[str]
    opposing: list[str]
    no_trade_reasons: list[str]
    components: list[dict[str, Any]]
    mtf_adjustment: float
    filters: list[dict[str, Any]]
    evidence: dict[str, Any] | None
    ai_summary: dict[str, Any] | None
    risk_decision: dict[str, Any] | None
    calibrated_probability: float | None = Field(
        description="Shown only when a validated calibrated model exists"
    )
    ensemble: dict[str, Any] | None
    data_mode: str
    provider: str
    is_demo: bool
    source: str
    versions: dict[str, Any]
    outcome: SignalOutcomeOut | None = None


class AIAnalysisOut(BaseModel):
    role: str
    provider: str
    model: str | None
    prompt_name: str | None
    prompt_version: str | None
    prompt_date: str | None
    settings: dict[str, Any]
    status: str
    output: dict[str, Any] | None
    validation: dict[str, Any] | None
    error: str | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    latency_ms: float | None
    created_at: str


class SignalDetailOut(SignalOut):
    analysis: dict[str, Any] | None = None
    ai_analyses: list[AIAnalysisOut] = Field(default_factory=list)


class GenerateSignalIn(BaseModel):
    symbol: str = Field(min_length=2, max_length=20)
    timeframe: AnalysisTimeframe = "15m"
    use_ai: bool | None = Field(
        None, description="true forces the AI stage, false skips it, null follows settings"
    )
    force: bool = False


class NewsOut(BaseModel):
    id: str
    headline: str
    summary: str | None
    source: str
    url: str | None = Field(description="Original source URL; null for DEMO items (never fabricated)")
    published_at: str
    symbols: list[str]
    countries: list[str]
    sentiment: str | None
    sentiment_source: str | None
    sentiment_rationale: str | None
    importance: str
    provider: str
    is_demo: bool


class EventOut(BaseModel):
    id: str
    event: str
    currency: str
    country: str
    time: str
    impact: str
    previous: str | None
    forecast: str | None
    actual: str | None
    source: str
    provider: str
    is_demo: bool
    minutes_until: float


class JournalOut(BaseModel):
    id: str
    entry_type: str
    symbol: str
    timeframe: str | None
    direction: str
    strategy: str | None
    regime: str | None
    signal_score: float | None
    entry_time: str
    exit_time: str | None
    entry_price: float | None
    exit_price: float | None
    stop: float | None
    lots: float | None
    fees: float
    slippage: float
    pnl: float | None
    r_multiple: float | None
    duration_seconds: float | None
    mfe_r: float | None
    mae_r: float | None
    result: str
    ai_reasoning: dict[str, Any] | None
    notes: str | None
    tags: list[str]
    signal_id: str | None
    position_id: str | None
    is_demo: bool


class ManualTradeIn(BaseModel):
    symbol: str
    direction: Literal["LONG", "SHORT"]
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: float = Field(gt=0)
    exit_price: float | None = Field(None, gt=0)
    stop: float | None = Field(None, gt=0)
    lots: float | None = Field(None, gt=0)
    fees: float = Field(0.0, ge=0)
    strategy: str | None = Field(None, max_length=60)
    regime: str | None = Field(None, max_length=24)
    notes: str | None = Field(None, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class JournalPatchIn(BaseModel):
    notes: str | None = Field(None, max_length=5000)
    tags: list[str] | None = Field(None, max_length=20)


class PaperOverviewOut(BaseModel):
    label: str = "PAPER TRADING - SIMULATED"
    account: Account
    positions: list[Position]
    closed_positions: list[Position]
    orders: list[Order]
    fills: list[Fill]
    risk: dict[str, Any]
    is_demo_prices: bool


class KillSwitchIn(BaseModel):
    active: bool


class BacktestIn(BacktestConfig):
    data_source: str = Field("provider", description="'provider' or 'imported:<batch>'")


class WalkForwardIn(WalkForwardConfig):
    data_source: str = "provider"


class ChatTurnIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurnIn] = Field(default_factory=list, max_length=20)


class SymbolTimeframeIn(BaseModel):
    symbol: str = Field(min_length=2, max_length=20)
    timeframe: AnalysisTimeframe = "1H"


class HistoryQueryIn(SymbolTimeframeIn):
    k: int = Field(50, ge=10, le=100)


class LiveSwitchIn(BaseModel):
    on: bool


class NotificationOut(BaseModel):
    id: int
    ts: str
    type: str
    title: str
    body: str
    severity: str
    symbol: str | None
    signal_id: str | None
    is_demo: bool
    read: bool


class NotificationsReadIn(BaseModel):
    ids: list[int] | None = None


class AlertOut(BaseModel):
    id: str
    type: str
    symbol: str | None
    condition: dict[str, Any]
    enabled: bool
    note: str | None
    cooldown_minutes: int
    last_triggered_at: str | None
    created_at: str


class AlertToggleIn(BaseModel):
    enabled: bool


class ComponentStatus(BaseModel):
    name: str
    status: str = Field(description="CONNECTED | DEMO | DISCONNECTED | ERROR | NOT_CONFIGURED | OK")
    detail: str = ""
    provider: str | None = None
    latency_ms: float | None = None


class SystemStatusOut(BaseModel):
    app_name: str
    version: str
    mode: str
    trading_mode: str = "PAPER"
    live_trading: dict[str, Any]
    components: list[ComponentStatus]
    versions: dict[str, str]
    background: dict[str, Any]
    memory: dict[str, Any]
    server_time: str

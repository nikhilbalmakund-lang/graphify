"""All persistent tables.

Every market-derived row carries provenance (provider, is_demo) and every
analytical row carries the versions that produced it (feature version, signal
engine version, strategy version, prompt version, model version).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UTCDateTime, utcnow

__all__ = [
    "AICall",
    "Alert",
    "AppSetting",
    "Backtest",
    "BacktestTrade",
    "Briefing",
    "EconomicEvent",
    "HistoricalSetup",
    "MarketAsset",
    "MarketCandle",
    "MarketFeature",
    "MarketRegime",
    "ModelVersion",
    "NewsItem",
    "Notification",
    "PaperAccount",
    "PaperFill",
    "PaperOrder",
    "PaperPosition",
    "PortfolioSnapshot",
    "Signal",
    "SignalAIAnalysis",
    "SignalFeature",
    "SignalOutcome",
    "Strategy",
    "StrategyRegimeStat",
    "SystemEvent",
    "TradeJournal",
]


def _ts() -> Mapped[datetime]:
    return mapped_column(UTCDateTime(), default=utcnow, nullable=False)


# ------------------------------------------------------------------ market
class MarketAsset(Base):
    __tablename__ = "market_assets"
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    asset_class: Mapped[str] = mapped_column(String(20), index=True)
    session: Mapped[str] = mapped_column(String(10))
    spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts()


class MarketCandle(Base):
    __tablename__ = "market_candles"
    __table_args__ = (
        UniqueConstraint("provider", "symbol", "timeframe", "ts", name="uq_candle"),
        Index("ix_candle_lookup", "symbol", "timeframe", "ts"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str] = mapped_column(String(4))
    ts: Mapped[datetime] = mapped_column(UTCDateTime())
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    provider: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(20))  # seed | import | provider
    is_demo: Mapped[bool] = mapped_column(Boolean, index=True)
    batch: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = _ts()


class MarketFeature(Base):
    __tablename__ = "market_features"
    __table_args__ = (Index("ix_feature_lookup", "symbol", "timeframe", "ts"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str] = mapped_column(String(4))
    ts: Mapped[datetime] = mapped_column(UTCDateTime())
    feature_version: Mapped[str] = mapped_column(String(16))
    features: Mapped[dict[str, Any]] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String(40))
    is_demo: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = _ts()


class MarketRegime(Base):
    __tablename__ = "market_regimes"
    __table_args__ = (Index("ix_regime_lookup", "symbol", "timeframe", "ts"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str] = mapped_column(String(4))
    ts: Mapped[datetime] = mapped_column(UTCDateTime())
    regime: Mapped[str] = mapped_column(String(24), index=True)
    clarity: Mapped[float] = mapped_column(Float)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    version: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(40))
    is_demo: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = _ts()


# ----------------------------------------------------------------- signals
class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signal_symbol_time", "symbol", "created_at"),
        Index("ix_signal_status", "status"),
        Index("ix_signal_dedupe", "symbol", "timeframe", "bar_time"),
    )
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str] = mapped_column(String(4), index=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()
    bar_time: Mapped[datetime] = mapped_column(UTCDateTime())
    direction: Mapped[str] = mapped_column(String(10), index=True)
    proposed_direction: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20))
    score: Mapped[float] = mapped_column(Float, index=True)
    score_long: Mapped[float] = mapped_column(Float)
    score_short: Mapped[float] = mapped_column(Float)
    regime: Mapped[str] = mapped_column(String(24))
    price: Mapped[float] = mapped_column(Float)
    entry_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_zone_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_zone_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop: Mapped[float | None] = mapped_column(Float, nullable=True)
    invalidation_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    invalidation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    targets: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    rr: Mapped[float | None] = mapped_column(Float, nullable=True)
    effective_rr: Mapped[float | None] = mapped_column(Float, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    expiry_bars: Mapped[int] = mapped_column(Integer, default=8)
    supporting: Mapped[list[str]] = mapped_column(JSON, default=list)
    opposing: Mapped[list[str]] = mapped_column(JSON, default=list)
    no_trade_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    filters: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    components: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    mtf_adjustment: Mapped[float] = mapped_column(Float, default=0.0)
    ensemble: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ai_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    risk_decision: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    calibrated_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_mode: Mapped[str] = mapped_column(String(10))
    provider: Mapped[str] = mapped_column(String(40))
    is_demo: Mapped[bool] = mapped_column(Boolean, index=True)
    source: Mapped[str] = mapped_column(String(20), default="pipeline")
    signal_engine_version: Mapped[str] = mapped_column(String(16))
    feature_version: Mapped[str] = mapped_column(String(16))
    risk_engine_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    strategy_versions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    prompt_versions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    model_versions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)


class SignalFeature(Base):
    __tablename__ = "signal_features"
    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True)
    feature_version: Mapped[str] = mapped_column(String(16))
    features: Mapped[dict[str, Any]] = mapped_column(JSON)
    vector: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    structure: Mapped[dict[str, Any]] = mapped_column(JSON)
    mtf: Mapped[dict[str, Any]] = mapped_column(JSON)
    regime: Mapped[dict[str, Any]] = mapped_column(JSON)
    data_quality: Mapped[dict[str, Any]] = mapped_column(JSON)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SignalAIAnalysis(Base):
    __tablename__ = "signal_ai_analysis"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30))  # claude_analyst | gemini_analyst | critic | consensus
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    prompt_date: Mapped[str | None] = mapped_column(String(16), nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20))
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = _ts()


class SignalOutcome(Base):
    __tablename__ = "signal_outcomes"
    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    filled: Mapped[bool] = mapped_column(Boolean, default=False)
    fill_time: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fill_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_time: Mapped[str | None] = mapped_column(String(40), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    mfe_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp_hits: Mapped[list[str]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(20), default="tracker")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = _ts()


class HistoricalSetup(Base):
    __tablename__ = "historical_setups"
    __table_args__ = (Index("ix_setup_lookup", "symbol", "timeframe", "direction", "is_demo"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str] = mapped_column(String(4))
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    direction: Mapped[str] = mapped_column(String(10))
    score: Mapped[float] = mapped_column(Float)
    regime: Mapped[str] = mapped_column(String(24))
    asset_class: Mapped[str] = mapped_column(String(20))
    vector: Mapped[list[float]] = mapped_column(JSON)
    entry_type: Mapped[str] = mapped_column(String(10))
    entry: Mapped[float] = mapped_column(Float)
    stop: Mapped[float] = mapped_column(Float)
    effective_rr: Mapped[float] = mapped_column(Float)
    outcome_status: Mapped[str] = mapped_column(String(20), index=True)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    bars_held: Mapped[int] = mapped_column(Integer, default=0)
    mfe_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp1_before_sl: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean)
    provider: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(30))
    feature_version: Mapped[str] = mapped_column(String(16))
    signal_engine_version: Mapped[str] = mapped_column(String(16))
    signal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = _ts()


# -------------------------------------------------------- news / calendar
class NewsItem(Base):
    __tablename__ = "news"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_news"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(200))
    headline: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(120))
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    symbols: Mapped[list[str]] = mapped_column(JSON, default=list)
    countries: Mapped[list[str]] = mapped_column(JSON, default=list)
    sentiment: Mapped[str | None] = mapped_column(String(12), nullable=True)
    sentiment_source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sentiment_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance: Mapped[str] = mapped_column(String(8), default="MEDIUM")
    provider: Mapped[str] = mapped_column(String(40))
    is_demo: Mapped[bool] = mapped_column(Boolean)
    data_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    fetched_at: Mapped[datetime] = _ts()


class EconomicEvent(Base):
    __tablename__ = "economic_events"
    __table_args__ = (UniqueConstraint("provider", "external_id", name="uq_event"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(200))
    event: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(8), index=True)
    country: Mapped[str] = mapped_column(String(60))
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    impact: Mapped[str] = mapped_column(String(8), index=True)
    previous: Mapped[str | None] = mapped_column(String(40), nullable=True)
    forecast: Mapped[str | None] = mapped_column(String(40), nullable=True)
    actual: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str] = mapped_column(String(120))
    provider: Mapped[str] = mapped_column(String(40))
    is_demo: Mapped[bool] = mapped_column(Boolean)
    fetched_at: Mapped[datetime] = _ts()


# ------------------------------------------------------------------ paper
class PaperAccount(Base):
    __tablename__ = "paper_accounts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    __table_args__ = (Index("ix_pos_account_status", "account_id", "status"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("paper_accounts.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(10))
    opened_at: Mapped[datetime] = mapped_column(UTCDateTime())
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    strategy: Mapped[str | None] = mapped_column(String(60), nullable=True)
    signal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class PaperOrder(Base):
    __tablename__ = "paper_orders"
    __table_args__ = (Index("ix_order_account_status", "account_id", "status"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("paper_accounts.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class PaperFill(Base):
    __tablename__ = "paper_fills"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("paper_accounts.id", ondelete="CASCADE"), index=True)
    position_id: Mapped[str] = mapped_column(String(40), index=True)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime())
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (Index("ix_snapshot_account_ts", "account_id", "ts"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("paper_accounts.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(UTCDateTime())
    balance: Mapped[float] = mapped_column(Float)
    equity: Mapped[float] = mapped_column(Float)
    margin_used: Mapped[float] = mapped_column(Float)
    unrealized_pnl: Mapped[float] = mapped_column(Float)
    open_positions: Mapped[int] = mapped_column(Integer)
    drawdown: Mapped[float] = mapped_column(Float)
    is_demo_prices: Mapped[bool] = mapped_column(Boolean)


# ---------------------------------------------------------------- journal
class TradeJournal(Base):
    __tablename__ = "trade_journal"
    __table_args__ = (Index("ix_journal_symbol_time", "symbol", "entry_time"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    entry_type: Mapped[str] = mapped_column(String(16), index=True)  # SIGNAL | PAPER_TRADE | MANUAL_TRADE
    symbol: Mapped[str] = mapped_column(String(20))
    timeframe: Mapped[str | None] = mapped_column(String(4), nullable=True)
    direction: Mapped[str] = mapped_column(String(10))
    strategy: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    regime: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    signal_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_time: Mapped[datetime] = mapped_column(UTCDateTime())
    exit_time: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop: Mapped[float | None] = mapped_column(Float, nullable=True)
    lots: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    slippage: Mapped[float] = mapped_column(Float, default=0.0)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    mfe_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[str] = mapped_column(
        String(12), index=True
    )  # OPEN | WIN | LOSS | BREAKEVEN | NO_TRADE | EXPIRED
    ai_reasoning: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    signal_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    position_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()


# ------------------------------------------------------------- strategies
class Strategy(Base):
    __tablename__ = "strategies"
    name: Mapped[str] = mapped_column(String(60), primary_key=True)
    version: Mapped[str] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSON)
    regimes: Mapped[list[str]] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = _ts()


class StrategyRegimeStat(Base):
    __tablename__ = "strategy_regime_stats"
    __table_args__ = (UniqueConstraint("strategy", "regime", "source", "is_demo", name="uq_strategy_regime"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy: Mapped[str] = mapped_column(String(60), index=True)
    regime: Mapped[str] = mapped_column(String(24))
    source: Mapped[str] = mapped_column(String(20))  # BACKTEST | PAPER
    is_demo: Mapped[bool] = mapped_column(Boolean)
    trades: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    sum_r: Mapped[float] = mapped_column(Float, default=0.0)
    sum_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = _ts()


class Backtest(Base):
    __tablename__ = "backtests"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # BACKTEST | WALK_FORWARD
    strategy: Mapped[str] = mapped_column(String(60), index=True)
    strategy_version: Mapped[str] = mapped_column(String(16))
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    timeframe: Mapped[str] = mapped_column(String(4))
    params: Mapped[dict[str, Any]] = mapped_column(JSON)
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(12))
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean)
    provider: Mapped[str] = mapped_column(String(40))
    data_label: Mapped[str] = mapped_column(String(120))
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine_version: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = _ts()
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[str] = mapped_column(ForeignKey("backtests.id", ondelete="CASCADE"), index=True)
    trade_no: Mapped[int] = mapped_column(Integer)
    direction: Mapped[str] = mapped_column(String(6))
    entry_time: Mapped[datetime] = mapped_column(UTCDateTime())
    exit_time: Mapped[datetime] = mapped_column(UTCDateTime())
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float] = mapped_column(Float)
    lots: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float] = mapped_column(Float)
    pnl_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float] = mapped_column(Float)
    exit_reason: Mapped[str] = mapped_column(String(20))
    regime: Mapped[str | None] = mapped_column(String(24), nullable=True)
    bars_held: Mapped[int] = mapped_column(Integer)
    mfe_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae_r: Mapped[float | None] = mapped_column(Float, nullable=True)


# ------------------------------------------------------------- AI / models
class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("kind", "provider", "model", "version", name="uq_model_version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20))  # AI | ML | SIGNAL_ENGINE | STRATEGY | PROMPT
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(40))
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    first_used_at: Mapped[datetime] = _ts()
    last_used_at: Mapped[datetime] = _ts()
    uses: Mapped[int] = mapped_column(Integer, default=0)


class AICall(Base):
    __tablename__ = "ai_calls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    provider: Mapped[str] = mapped_column(String(20), index=True)
    model: Mapped[str] = mapped_column(String(80))
    task: Mapped[str] = mapped_column(String(30))
    prompt_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    signal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Briefing(Base):
    __tablename__ = "briefings"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    session: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = _ts()
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    is_ai: Mapped[bool] = mapped_column(Boolean)
    is_demo_data: Mapped[bool] = mapped_column(Boolean)
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    prompt_version: Mapped[str | None] = mapped_column(String(16), nullable=True)


# ---------------------------------------------------------- system / misc
class SystemEvent(Base):
    __tablename__ = "system_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    severity: Mapped[str] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    signal_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = _ts()


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    type: Mapped[str] = mapped_column(String(30))
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    condition: Mapped[dict[str, Any]] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_triggered_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = _ts()


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(10))
    symbol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    signal_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)

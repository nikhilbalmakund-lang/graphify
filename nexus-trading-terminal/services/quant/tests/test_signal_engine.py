from datetime import UTC, datetime

import pytest

from market_data.assets import DEFAULT_CATALOG
from market_data.models import Timeframe
from market_data.normalization.validation import IssueSeverity, validate_series
from market_data.providers.demo import DemoMarketDataProvider
from quant.signals.context import analyze_series, build_context, mtf_from_bundles
from quant.signals.engine import SignalEngine
from quant.signals.levels import build_levels
from quant.signals.models import (
    Direction,
    EventRisk,
    HistoricalEvidence,
    ScoringWeights,
    SignalConfig,
)

NOW = datetime(2026, 10, 1, 14, 30, 27, tzinfo=UTC)


def make_ctx(symbol="XAUUSD", tf=Timeframe.M15, **overrides):
    p = DemoMarketDataProvider(clock=lambda: NOW)
    spec = DEFAULT_CATALOG.get(symbol)
    s = p.candles_sync(symbol, tf, 500)
    clean, rep = validate_series(s, spec, NOW)
    b = analyze_series(clean.df, tf)
    bundles = {tf: b, Timeframe.H1: analyze_series(p.candles_sync(symbol, Timeframe.H1, 300).df, Timeframe.H1),
               Timeframe.H4: analyze_series(p.candles_sync(symbol, Timeframe.H4, 300).df, Timeframe.H4)}
    q = p.quote_sync(symbol)
    kwargs = dict(symbol=symbol, spec=spec, bundle=b, t=-1, mtf=mtf_from_bundles(bundles), data_quality=rep,
                  bid=q.bid, ask=q.ask, market_open=q.market_open)
    kwargs.update(overrides)
    return build_context(**kwargs)


@pytest.mark.parametrize("symbol", DEFAULT_CATALOG.symbols())
def test_scores_are_bounded_and_components_stored(symbol):
    cand = SignalEngine().evaluate(make_ctx(symbol))
    assert 0 <= cand.score <= 100 and 0 <= cand.score_long <= 100 and 0 <= cand.score_short <= 100
    names = {c.name for c in cand.components}
    assert names == {"trend", "structure", "momentum", "volume_vwap", "liquidity", "volatility", "macro", "sentiment"}
    assert sum(c.weight for c in cand.components) == pytest.approx(100.0)
    assert all(0 <= c.points <= c.weight + 1e-9 for c in cand.components)
    if cand.direction == Direction.NO_TRADE:
        assert cand.no_trade_reasons
    else:
        assert not cand.no_trade_reasons and cand.levels is not None
        assert all(f.passed for f in cand.filters if f.blocking)


@pytest.mark.parametrize("symbol", DEFAULT_CATALOG.symbols())
def test_levels_are_structural_and_consistent(symbol):
    ctx = make_ctx(symbol)
    for d in (1, -1):
        plan, reason = build_levels(ctx, d, SignalConfig())
        if plan is None:
            assert reason
            continue
        if d > 0:
            assert plan.stop < plan.invalidation_level <= plan.entry_price
            assert all(t.price > plan.entry_price for t in plan.targets)
        else:
            assert plan.stop > plan.invalidation_level >= plan.entry_price
            assert all(t.price < plan.entry_price for t in plan.targets)
        assert [t.label for t in plan.targets] == ["TP1", "TP2", "TP3"]
        assert plan.targets[0].rr >= 1.0 - 1e-6
        assert all(t.basis.startswith(("STRUCTURE", "R-MULTIPLE")) for t in plan.targets)
        assert plan.effective_rr == pytest.approx(sum(t.rr * t.allocation for t in plan.targets), abs=0.02)


def test_no_structural_levels_means_no_stop():
    ctx = make_ctx()
    ctx = ctx.model_copy(update={"structure": ctx.structure.model_copy(update={
        "last_swing_low": None, "last_swing_high": None, "supports": [], "resistances": []})})
    plan, reason = build_levels(ctx, 1, SignalConfig())
    assert plan is None and "invalidation" in reason.lower()


def test_score_is_not_enough_filters_block():
    cfg = SignalConfig(min_score=0, min_score_margin=0, min_rr=0, max_stop_atr=100, max_spread_atr=10,
                       max_vol_percentile=100, block_on_mtf_contradiction=False)
    ctx = make_ctx()
    base = SignalEngine(cfg).evaluate(ctx)
    closed = SignalEngine(cfg).evaluate(ctx.model_copy(update={"market_open": False}))
    assert closed.direction == Direction.NO_TRADE and any("Market hours" in r for r in closed.no_trade_reasons)
    event = EventRisk(available=True, is_demo=True, next_high_impact_minutes=20, next_high_impact_event="US CPI")
    news = SignalEngine(cfg).evaluate(ctx.model_copy(update={"events": event}))
    assert news.direction == Direction.NO_TRADE and any("News risk" in r for r in news.no_trade_reasons)
    if base.levels is not None:
        assert base.direction != Direction.NO_TRADE


def test_bad_data_forces_no_trade():
    ctx = make_ctx()
    dq = ctx.data_quality.model_copy(deep=True)
    dq.add("STALE_MARKET_DATA", IssueSeverity.CRITICAL, 0, "stale")
    dq.is_stale = True
    cand = SignalEngine(SignalConfig(min_score=0)).evaluate(ctx.model_copy(update={"data_quality": dq}))
    assert cand.direction == Direction.NO_TRADE
    assert any("Stale data" in r or "Data quality" in r for r in cand.no_trade_reasons)


def test_finalize_requires_historical_evidence():
    cfg = SignalConfig(min_score=0, min_score_margin=0, min_rr=0, max_stop_atr=100, max_spread_atr=10,
                       max_vol_percentile=100, block_on_mtf_contradiction=False, min_historical_samples=10)
    eng = SignalEngine(cfg)
    cand = eng.evaluate(make_ctx())
    small = HistoricalEvidence(sample_size=4, sample_label="INSUFFICIENT")
    out = eng.finalize(cand, small)
    assert out.direction == Direction.NO_TRADE
    assert any("Historical evidence" in r for r in out.no_trade_reasons)
    assert any("small" in o.lower() for o in out.opposing_factors)
    big = HistoricalEvidence(sample_size=60, sample_label="MODERATE", expectancy=0.2, win_rate=0.5, avg_r=0.2)
    out2 = eng.finalize(cand, big)
    assert out2.direction == cand.direction


def test_scoring_weights_configurable_and_validated():
    w = ScoringWeights(trend=40, structure=40, momentum=20, volume_vwap=0, liquidity=0, volatility=0, macro=0, sentiment=0)
    assert w.normalised()["trend"] == pytest.approx(40)
    cand = SignalEngine(SignalConfig(weights=w)).evaluate(make_ctx())
    assert {c.name: c.weight for c in cand.components}["macro"] == 0
    with pytest.raises(ValueError):
        ScoringWeights(trend=-1)
    with pytest.raises(ValueError):
        SignalConfig(exit_plan=[0.5, 0.5, 0.5])

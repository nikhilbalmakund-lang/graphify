from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from backtesting.engine.engine import Backtester, BacktestConfig
from backtesting.metrics.metrics import TradeLike, compute_metrics, losing_periods
from backtesting.strategies.base import BarView, LookAheadError, SeriesData, Strategy, StrategyVote
from backtesting.strategies.ensemble import StrategyPerf, combine_votes
from backtesting.strategies.library import REGISTRY, create
from backtesting.validation.walk_forward import WalkForwardConfig, run_walk_forward
from market_data.assets import DEFAULT_CATALOG
from market_data.models import AssetSpec, AssetClass, SessionType, Timeframe
from market_data.providers.demo import DemoMarketDataProvider
from quant.signals.models import Direction

NOW = datetime(2026, 10, 1, 14, 30, 27, tzinfo=UTC)
SPEC = AssetSpec(symbol="TEST", name="Test", asset_class=AssetClass.CRYPTO, session=SessionType.CRYPTO, base="TST",
                 quote="USD", contract_size=1, min_lot=1, lot_step=1, max_lot=1_000_000, typical_spread=0.0)


def bars(rows):
    idx = pd.date_range("2025-01-01", periods=len(rows), freq="1h", tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=100.0)


class OneShot(Strategy):
    """Goes long once at bar `at` with a fixed stop/target (test helper)."""

    name = "OneShot"
    defaults = {"at": 1, "stop": 95.0, "target": 110.0, "direction": 1}
    min_bars = 0

    def analyze(self, v: BarView) -> StrategyVote:
        if v.t != self.params["at"]:
            return self._none()
        d = Direction.LONG if self.params["direction"] > 0 else Direction.SHORT
        return self._vote(d, 1.0, self.params["stop"], self.params["target"], ["test"])


def run(rows, cfg_kw=None, **params):
    data = SeriesData(bars(rows), Timeframe.H1)
    kw = {"slippage_bps": 0, "partial_exit_r": None, "max_daily_loss": None, **(cfg_kw or {})}
    cfg = BacktestConfig(symbol="TEST", timeframe="1H", strategy="OneShot", **kw)
    return Backtester(data, SPEC, cfg, is_demo=False, provider="test").run(OneShot(**params))


FLAT = [100, 100.5, 99.5, 100]


def test_market_order_fills_next_open_and_hits_target():
    rows = [FLAT, FLAT, [101, 112, 100, 111], [111, 111, 110, 110]]
    res = run(rows)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.entry_price == pytest.approx(101.0)  # next bar open, zero spread/slippage
    assert t.exit_reason == "TARGET" and t.exit_price == pytest.approx(110.0)
    risk = (101 - 95) * t.lots
    assert t.pnl == pytest.approx((110 - 101) * t.lots)
    assert t.pnl_r == pytest.approx(t.pnl / risk)


def test_stop_and_target_in_same_bar_assumes_stop_first():
    rows = [FLAT, FLAT, [100, 115, 90, 100], FLAT]
    t = run(rows).trades[0]
    assert t.exit_reason == "STOP" and t.exit_price == pytest.approx(95.0)


def test_gap_through_stop_fills_at_open_not_stop():
    rows = [FLAT, FLAT, [100, 101, 99, 100], [90, 91, 88, 89], FLAT]
    t = run(rows).trades[0]
    assert t.exit_reason == "STOP" and t.exit_price == pytest.approx(90.0)
    assert t.pnl_r < -1.0


def test_spread_slippage_and_commission_are_charged():
    rows = [FLAT, FLAT, [101, 112, 100, 111], FLAT]
    data = SeriesData(bars(rows), Timeframe.H1)
    cfg = BacktestConfig(symbol="TEST", timeframe="1H", strategy="OneShot", spread=0.2, slippage_bps=10,
                         commission_per_lot=1.0, partial_exit_r=None, max_daily_loss=None)
    t = Backtester(data, SPEC, cfg).run(OneShot()).trades[0]
    assert t.entry_price == pytest.approx(101 + 0.1 + 101 * 0.001)
    assert t.exit_price == pytest.approx(110 - 0.1 - 110 * 0.001)
    assert t.fees == pytest.approx(2 * t.lots * 1.0)
    assert t.slippage_cost > 0


def test_partial_exit_and_breakeven_stop():
    rows = [FLAT, FLAT, [100, 106.5, 100, 106], [106, 106.5, 99, 100], FLAT]
    res = run(rows, cfg_kw={"partial_exit_r": 1.0, "partial_fraction": 0.5})
    t = res.trades[0]
    reasons = [p.reason for p in t.partial_exits]
    assert reasons == ["PARTIAL_TP", "BREAKEVEN_STOP"]
    assert t.partial_exits[0].price == pytest.approx(105.0)  # entry 100 + 1R (R = 5)
    assert t.pnl > 0


def test_short_trade_mirror():
    rows = [FLAT, FLAT, [99, 100, 88, 89], FLAT]
    t = run(rows, stop=105.0, target=90.0, direction=-1).trades[0]
    assert t.direction == "SHORT" and t.exit_reason == "TARGET" and t.pnl > 0


def test_bar_view_blocks_lookahead():
    data = SeriesData(bars([FLAT] * 10), Timeframe.H1)
    v = BarView(data, 5)
    assert v.get("close") == 100
    with pytest.raises(LookAheadError):
        v.get("close", 1)


@pytest.fixture(scope="module")
def demo_series():
    p = DemoMarketDataProvider(clock=lambda: NOW)
    s = p.candles_sync("XAUUSD", Timeframe.H1, start=NOW - timedelta(days=200), end=NOW)
    return s.closed_bars()


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_strategies_have_no_lookahead(demo_series, name):
    full = SeriesData(demo_series, Timeframe.H1, higher=Timeframe.H4)
    cut = 2500
    part = SeriesData(demo_series.iloc[: cut + 1], Timeframe.H1, higher=Timeframe.H4)
    strat = create(name)
    for t in range(cut - 200, cut + 1, 7):
        a, b = strat.vote(BarView(full, t)), strat.vote(BarView(part, t))
        assert a.direction == b.direction and a.stop == pytest.approx(b.stop) and a.target == pytest.approx(b.target)


def test_backtest_prefix_consistency(demo_series):
    """Trades closed before a cutoff must be identical whether or not later data exists."""
    spec = DEFAULT_CATALOG.get("XAUUSD")
    cfg = BacktestConfig(symbol="XAUUSD", timeframe="1H", strategy="MarketStructure")
    full = Backtester(SeriesData(demo_series, Timeframe.H1), spec, cfg).run(create("MarketStructure"))
    cut = demo_series.index[3000]
    part = Backtester(SeriesData(demo_series.loc[:cut], Timeframe.H1), spec, cfg).run(create("MarketStructure"))
    early_full = [(t.entry_time, t.exit_time, t.pnl) for t in full.trades if t.exit_time < cut - pd.Timedelta(hours=2)]
    early_part = [(t.entry_time, t.exit_time, t.pnl) for t in part.trades if t.exit_time < cut - pd.Timedelta(hours=2)]
    assert early_full == early_part and len(early_full) > 3


def test_demo_backtests_are_labelled(demo_series):
    spec = DEFAULT_CATALOG.get("XAUUSD")
    res = Backtester(SeriesData(demo_series, Timeframe.H1), spec,
                     BacktestConfig(symbol="XAUUSD", timeframe="1H", strategy="Breakout")).run(create("Breakout"))
    assert res.is_demo and "DEMO" in res.data_label and any("DEMO DATA" in w for w in res.warnings)
    assert res.equity_curve and res.drawdown_curve


def test_metrics_known_values():
    t0 = datetime(2025, 1, 1, tzinfo=UTC)
    pnls = [100, -50, -50, 200, -50]
    trades = [TradeLike(pnl=p, pnl_r=p / 50, entry_time=t0, exit_time=t0, bars_held=2, regime="RANGING" if i % 2 else "TRENDING_BULLISH")
              for i, p in enumerate(pnls)]
    eq = pd.Series(np.cumsum([10_000] + pnls), index=pd.date_range("2025-01-01", periods=6, freq="7D", tz="UTC"), dtype=float)
    b = compute_metrics(trades, eq, [True, False, True, False, True, False])
    m = b.metrics
    assert m.total_trades == 5 and m.wins == 2 and m.losses == 3
    assert m.win_rate == pytest.approx(0.4)
    assert m.profit_factor == pytest.approx(300 / 150)
    assert m.expectancy == pytest.approx(30.0)
    assert m.longest_losing_streak == 2
    assert m.largest_loss == -50 and m.largest_win == 200
    assert m.exposure_pct == pytest.approx(50.0)
    assert m.max_drawdown_abs == pytest.approx(100.0)
    assert {r.regime for r in b.by_regime} == {"RANGING", "TRENDING_BULLISH"}
    assert sum(b.r_distribution.values()) == 5


def test_losing_periods_are_reported():
    eq = pd.Series([100, 110, 90, 95, 112, 100, 98], index=pd.date_range("2025-01-01", periods=7, freq="D", tz="UTC"), dtype=float)
    lp = losing_periods(eq)
    assert lp[0].depth_pct == pytest.approx(18.18, abs=0.01) and lp[0].recovered
    assert any(not p.recovered for p in lp)


def test_ensemble_rules():
    def v(name, d, s=1.0, app=True):
        return StrategyVote(strategy=name, version="1", direction=d, strength=s, applicable=app)
    agree = combine_votes([v("A", Direction.LONG), v("B", Direction.LONG), v("C", Direction.NO_TRADE)], "TRENDING_BULLISH")
    assert agree.net_direction == Direction.LONG and agree.agreement == 1.0 and not agree.conflict
    conflict = combine_votes([v("A", Direction.LONG), v("B", Direction.SHORT)], "RANGING")
    assert conflict.net_direction == Direction.NO_TRADE and conflict.conflict
    none = combine_votes([v("A", Direction.NO_TRADE)], "RANGING")
    assert none.net_direction == Direction.NO_TRADE
    perf = {("A", "RANGING"): StrategyPerf(trades=50, expectancy_r=-0.2)}
    weighted = combine_votes([v("A", Direction.LONG), v("B", Direction.SHORT, 0.5, app=True)], "RANGING", perf)
    assert weighted.long_weight == pytest.approx(0.6)


def test_walk_forward_segments_are_sequential(demo_series):
    spec = DEFAULT_CATALOG.get("XAUUSD")
    data = SeriesData(demo_series, Timeframe.H1, higher=Timeframe.H4)
    cfg = WalkForwardConfig(backtest=BacktestConfig(symbol="XAUUSD", timeframe="1H", strategy="Breakout"),
                            train_bars=1200, validation_bars=300, test_bars=300, max_windows=3,
                            param_grid=[{"squeeze_pct": 40.0, "min_rr": 1.5}, {"squeeze_pct": 55.0, "min_rr": 2.0}])
    wf = run_walk_forward(data, spec, cfg)
    assert len(wf.windows) == 3
    for w in wf.windows:
        assert w.train.end < w.validation.start <= w.validation.end < w.test.start
        assert w.candidates_evaluated == 2
    assert wf.windows[1].test.start > wf.windows[0].test.start
    assert all(wf.windows[0].test.start <= str(t.entry_time.isoformat()).replace("T", " ") for t in wf.oos_trades) or wf.oos_trades == []
    assert "DEMO" in wf.data_label

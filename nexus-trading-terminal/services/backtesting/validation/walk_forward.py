"""Walk-forward validation: TRAIN -> VALIDATION -> TEST, then roll forward.

For every window:
1. Each parameter combination is backtested on the TRAIN segment only.
2. The best combination by the objective (expectancy in R scaled by sqrt(n),
   requiring a minimum trade count) is selected using TRAIN data only.
3. That single choice is evaluated on VALIDATION (degradation check) and on
   the untouched TEST segment (out-of-sample).
The window then rolls forward by the TEST length. Indicators are computed on
the whole series once (they are causal), so segments get warm-up history
from earlier bars only - never from later bars.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from backtesting.engine.engine import BacktestConfig, Backtester, BacktestResult, BacktestTrade
from backtesting.metrics.metrics import Metrics, MetricsBundle, compute_metrics
from backtesting.strategies.base import SeriesData
from backtesting.strategies.library import create
from backtesting.validation.overfitting import OverfitReport, assess_overfitting
from market_data.models import AssetSpec

MIN_TRADES_FOR_SELECTION = 5


class WalkForwardConfig(BaseModel):
    backtest: BacktestConfig
    train_bars: int = Field(2000, ge=200)
    validation_bars: int = Field(500, ge=50)
    test_bars: int = Field(500, ge=50)
    max_windows: int = Field(8, ge=1, le=50)
    param_grid: list[dict[str, Any]] | None = None


class SegmentSummary(BaseModel):
    start: str
    end: str
    bars: int
    metrics: Metrics


class WindowResult(BaseModel):
    window: int
    chosen_params: dict[str, Any]
    train: SegmentSummary
    validation: SegmentSummary
    test: SegmentSummary
    candidates_evaluated: int
    grid_scores: list[dict[str, Any]] = Field(default_factory=list)


class WalkForwardResult(BaseModel):
    strategy: str
    symbol: str
    timeframe: str
    is_demo: bool
    data_label: str
    windows: list[WindowResult]
    oos_trades: list[BacktestTrade]
    oos_metrics: MetricsBundle
    oos_equity_curve: list[tuple[str, float]]
    overfitting: OverfitReport
    warnings: list[str] = Field(default_factory=list)


def objective(m: Metrics) -> float:
    if m.total_trades < MIN_TRADES_FOR_SELECTION or m.expectancy_r is None:
        return -math.inf
    return m.expectancy_r * math.sqrt(m.total_trades)


def _segment(res: BacktestResult, idx: pd.DatetimeIndex, lo: int, hi: int) -> SegmentSummary:
    return SegmentSummary(start=str(idx[lo]), end=str(idx[hi - 1]), bars=hi - lo, metrics=res.metrics.metrics)


def run_walk_forward(
    data: SeriesData, spec: AssetSpec, cfg: WalkForwardConfig, provider: str = "demo", is_demo: bool = True
) -> WalkForwardResult:
    bt_cfg = cfg.backtest
    n = len(data)
    idx = data.df.index
    grid = cfg.param_grid or create(bt_cfg.strategy).param_combinations()
    win_len = cfg.train_bars + cfg.validation_bars + cfg.test_bars
    warmup = create(bt_cfg.strategy).min_bars
    first = warmup
    windows: list[WindowResult] = []
    oos_trades: list[BacktestTrade] = []
    oos_equity: list[pd.Series] = []
    equity = bt_cfg.initial_capital
    warnings: list[str] = []
    w = 0
    while first + win_len <= n and w < cfg.max_windows:
        tr = (first, first + cfg.train_bars)
        va = (tr[1], tr[1] + cfg.validation_bars)
        te = (va[1], va[1] + cfg.test_bars)
        scored = []
        for params in grid:
            res = Backtester(data, spec, bt_cfg, provider, is_demo).run(
                create(bt_cfg.strategy, **params), trade_window=tr
            )
            scored.append((objective(res.metrics.metrics), params, res))
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_params, best_train = scored[0]
        val_res = Backtester(data, spec, bt_cfg, provider, is_demo).run(
            create(bt_cfg.strategy, **best_params), trade_window=va
        )
        test_res = Backtester(data, spec, bt_cfg, provider, is_demo).run(
            create(bt_cfg.strategy, **best_params), trade_window=te, start_equity=equity
        )
        equity = test_res.metrics.metrics.end_equity or equity
        oos_trades.extend(test_res.trades)
        oos_equity.append(
            pd.Series(
                [v for _, v in test_res.equity_curve],
                index=pd.DatetimeIndex([k for k, _ in test_res.equity_curve]),
            )
        )
        windows.append(
            WindowResult(
                window=w + 1,
                chosen_params=best_params,
                train=_segment(best_train, idx, *tr),
                validation=_segment(val_res, idx, *va),
                test=_segment(test_res, idx, *te),
                candidates_evaluated=len(grid),
                grid_scores=[
                    {
                        "params": p,
                        "objective": (None if not np.isfinite(s) else round(s, 4)),
                        "expectancy_r": r.metrics.metrics.expectancy_r,
                        "trades": r.metrics.metrics.total_trades,
                    }
                    for s, p, r in scored
                ],
            )
        )
        if not np.isfinite(best_score):
            warnings.append(
                f"Window {w + 1}: no parameter set produced {MIN_TRADES_FOR_SELECTION}+ training trades"
            )
        first += cfg.test_bars
        w += 1

    if not windows:
        raise ValueError(
            f"Not enough data for one walk-forward window: need {win_len + warmup} bars, have {n}"
        )
    eq = pd.concat(oos_equity) if oos_equity else pd.Series(dtype="float64")
    eq = eq[~eq.index.duplicated(keep="last")]
    oos = compute_metrics(oos_trades, eq)
    report = assess_overfitting(windows, oos.metrics, len(grid))
    if is_demo:
        warnings.append("DEMO DATA: walk-forward results are computed on synthetic prices")
    return WalkForwardResult(
        strategy=bt_cfg.strategy,
        symbol=bt_cfg.symbol,
        timeframe=bt_cfg.timeframe,
        is_demo=is_demo,
        data_label="DEMO WALK-FORWARD (synthetic data)"
        if is_demo
        else f"WALK-FORWARD ({provider} historical data)",
        windows=windows,
        oos_trades=oos_trades,
        oos_metrics=oos,
        oos_equity_curve=[(str(k), round(float(v), 2)) for k, v in eq.items()],
        overfitting=report,
        warnings=warnings,
    )

"""Overfitting / robustness diagnostics for walk-forward results.

Flags (each with a plain-language explanation):
* TOO_FEW_TRADES          - out-of-sample trade count below 30
* EXTREME_OPTIMIZATION    - many parameter combinations relative to trades
* TRAIN_TEST_GAP          - in-sample edge collapses out of sample
* POOR_OUT_OF_SAMPLE      - out-of-sample expectancy <= 0 or profit factor < 1
* PARAMETER_SENSITIVITY   - the chosen parameters sit on an isolated peak
* UNSTABLE_RESULTS        - chosen parameters / window results vary widely
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel, Field

from backtesting.metrics.metrics import Metrics

if TYPE_CHECKING:
    from backtesting.validation.walk_forward import WindowResult


class OverfitFlag(BaseModel):
    code: str
    severity: str  # WARNING | CRITICAL
    detail: str


class OverfitReport(BaseModel):
    suspicious: bool
    flags: list[OverfitFlag] = Field(default_factory=list)
    summary: str


def assess_overfitting(windows: list[WindowResult], oos: Metrics, grid_size: int) -> OverfitReport:
    flags: list[OverfitFlag] = []
    if oos.total_trades < 30:
        flags.append(OverfitFlag(code="TOO_FEW_TRADES", severity="WARNING",
                                 detail=f"Only {oos.total_trades} out-of-sample trades; at least 30 are needed for meaningful statistics"))
    train_trades = sum(w.train.metrics.total_trades for w in windows)
    if grid_size > 1 and train_trades and grid_size > train_trades / 5:
        flags.append(OverfitFlag(code="EXTREME_OPTIMIZATION", severity="WARNING",
                                 detail=f"{grid_size} parameter combinations tested against {train_trades} training trades"))
    tr_r = [w.train.metrics.expectancy_r for w in windows if w.train.metrics.expectancy_r is not None]
    te_r = [w.test.metrics.expectancy_r for w in windows if w.test.metrics.expectancy_r is not None]
    if tr_r and te_r:
        gap = float(np.mean(tr_r) - np.mean(te_r))
        if gap > 0.3:
            flags.append(OverfitFlag(code="TRAIN_TEST_GAP", severity="CRITICAL",
                                     detail=f"Average expectancy falls by {gap:.2f}R from training to test windows"))
    if oos.total_trades > 0 and ((oos.expectancy_r is not None and oos.expectancy_r <= 0) or (oos.profit_factor is not None and oos.profit_factor < 1)):
        flags.append(OverfitFlag(code="POOR_OUT_OF_SAMPLE", severity="CRITICAL",
                                 detail=f"Out-of-sample expectancy {oos.expectancy_r}R, profit factor {oos.profit_factor}"))
    sens = []
    for w in windows:
        vals = [g["objective"] for g in w.grid_scores if g["objective"] is not None]
        if len(vals) >= 3:
            best, med, sd = max(vals), float(np.median(vals)), float(np.std(vals))
            if sd > 0 and best - med > 2 * sd:
                sens.append(w.window)
    if sens:
        flags.append(OverfitFlag(code="PARAMETER_SENSITIVITY", severity="WARNING",
                                 detail=f"Chosen parameters are an isolated peak in windows {sens}"))
    distinct = {tuple(sorted(w.chosen_params.items())) for w in windows}
    if len(windows) >= 3 and len(distinct) >= max(3, int(0.75 * len(windows))):
        flags.append(OverfitFlag(code="UNSTABLE_RESULTS", severity="WARNING",
                                 detail=f"Optimal parameters changed in {len(distinct)} of {len(windows)} windows"))
    if len(te_r) >= 3:
        m, s = float(np.mean(te_r)), float(np.std(te_r))
        if s > abs(m) * 2 and s > 0.2:
            flags.append(OverfitFlag(code="UNSTABLE_RESULTS", severity="WARNING",
                                     detail=f"Test-window expectancy varies widely (mean {m:.2f}R, sd {s:.2f}R)"))
    critical = any(f.severity == "CRITICAL" for f in flags)
    summary = ("Suspicious: results are unlikely to generalise" if critical
               else "Some robustness warnings" if flags else "No overfitting flags raised (this is not proof of an edge)")
    return OverfitReport(suspicious=critical or len(flags) >= 3, flags=flags, summary=summary)

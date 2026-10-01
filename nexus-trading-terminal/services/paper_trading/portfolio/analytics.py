"""Portfolio and performance analytics over closed paper positions / journal rows."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime

import numpy as np
from pydantic import BaseModel, Field


class ClosedTrade(BaseModel):
    closed_at: datetime
    symbol: str
    strategy: str | None = None
    regime: str | None = None
    pnl: float
    r_multiple: float | None = None


class PeriodPnl(BaseModel):
    period: str
    pnl: float
    trades: int


class GroupStats(BaseModel):
    key: str
    trades: int
    pnl: float
    win_rate: float | None
    expectancy_r: float | None


class PerformanceReport(BaseModel):
    trades: int
    win_rate: float | None
    expectancy: float | None
    expectancy_r: float | None
    total_pnl: float
    max_drawdown: float
    daily: list[PeriodPnl] = Field(default_factory=list)
    weekly: list[PeriodPnl] = Field(default_factory=list)
    monthly: list[PeriodPnl] = Field(default_factory=list)
    by_strategy: list[GroupStats] = Field(default_factory=list)
    by_asset: list[GroupStats] = Field(default_factory=list)
    by_regime: list[GroupStats] = Field(default_factory=list)
    r_distribution: dict[str, int] = Field(default_factory=dict)
    sample_note: str = ""


def _period(trades: list[ClosedTrade], fmt: str) -> list[PeriodPnl]:
    agg: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        agg[t.closed_at.strftime(fmt)].append(t.pnl)
    return [PeriodPnl(period=k, pnl=round(sum(v), 2), trades=len(v)) for k, v in sorted(agg.items())]


def _group(trades: list[ClosedTrade], key: str) -> list[GroupStats]:
    agg: dict[str, list[ClosedTrade]] = defaultdict(list)
    for t in trades:
        agg[getattr(t, key) or "UNSPECIFIED"].append(t)
    out = []
    for k, items in sorted(agg.items()):
        rs = [i.r_multiple for i in items if i.r_multiple is not None]
        out.append(
            GroupStats(
                key=k,
                trades=len(items),
                pnl=round(sum(i.pnl for i in items), 2),
                win_rate=round(sum(1 for i in items if i.pnl > 0) / len(items), 4),
                expectancy_r=round(float(np.mean(rs)), 3) if rs else None,
            )
        )
    return out


def performance_report(rows: Iterable[ClosedTrade]) -> PerformanceReport:
    trades = sorted(rows, key=lambda t: t.closed_at)
    pnls = [t.pnl for t in trades]
    rs = [t.r_multiple for t in trades if t.r_multiple is not None]
    cum = np.cumsum(pnls) if pnls else np.array([0.0])
    dd = float(np.max(np.maximum.accumulate(np.concatenate([[0.0], cum])) - np.concatenate([[0.0], cum])))
    dist: dict[str, int] = {}
    if rs:
        edges = [-np.inf, -1.5, -1, -0.5, 0, 0.5, 1, 2, 3, np.inf]
        labels = [
            "<-1.5R",
            "-1.5..-1R",
            "-1..-0.5R",
            "-0.5..0R",
            "0..0.5R",
            "0.5..1R",
            "1..2R",
            "2..3R",
            ">3R",
        ]
        counts, _ = np.histogram(rs, bins=edges)
        dist = {lbl: int(c) for lbl, c in zip(labels, counts, strict=True)}
    n = len(trades)
    note = (
        "No closed trades yet"
        if n == 0
        else (f"Small sample ({n} trades): statistics are not reliable" if n < 30 else f"{n} trades")
    )
    return PerformanceReport(
        trades=n,
        win_rate=round(sum(1 for p in pnls if p > 0) / n, 4) if n else None,
        expectancy=round(float(np.mean(pnls)), 2) if n else None,
        expectancy_r=round(float(np.mean(rs)), 3) if rs else None,
        total_pnl=round(float(sum(pnls)), 2),
        max_drawdown=round(dd, 2),
        daily=_period(trades, "%Y-%m-%d"),
        weekly=_period(trades, "%G-W%V"),
        monthly=_period(trades, "%Y-%m"),
        by_strategy=_group(trades, "strategy"),
        by_asset=_group(trades, "symbol"),
        by_regime=_group(trades, "regime"),
        r_distribution=dist,
        sample_note=note,
    )

"""Performance metrics for backtests, walk-forward tests and paper trading.

All statistics are computed from realised trades and the bar-by-bar equity
curve. Nothing is smoothed and losing periods are reported explicitly.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class TradeLike(BaseModel):
    pnl: float
    pnl_r: float | None = None
    entry_time: datetime
    exit_time: datetime
    bars_held: int = 0
    regime: str | None = None


class Metrics(BaseModel):
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    win_rate: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None  # account currency per trade
    expectancy_r: float | None = None
    average_r: float | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_abs: float = 0.0
    sharpe: float | None = None
    sortino: float | None = None
    cagr_pct: float | None = None
    volatility_pct: float | None = None
    exposure_pct: float | None = None
    largest_win: float | None = None
    largest_loss: float | None = None
    longest_losing_streak: int = 0
    longest_winning_streak: int = 0
    avg_bars_held: float | None = None
    start_equity: float = 0.0
    end_equity: float = 0.0
    years: float | None = None


class LosingPeriod(BaseModel):
    start: str
    trough: str
    end: str | None
    depth_pct: float
    duration_bars: int
    recovered: bool


class RegimeStats(BaseModel):
    regime: str
    trades: int
    win_rate: float | None
    average_r: float | None
    profit_factor: float | None
    net_profit: float


class MetricsBundle(BaseModel):
    metrics: Metrics
    monthly_returns: dict[str, float] = Field(default_factory=dict)
    losing_periods: list[LosingPeriod] = Field(default_factory=list)
    by_regime: list[RegimeStats] = Field(default_factory=list)
    r_distribution: dict[str, int] = Field(default_factory=dict)


def _streaks(values: Sequence[float]) -> tuple[int, int]:
    lose = win = cur_l = cur_w = 0
    for v in values:
        if v < 0:
            cur_l += 1
            cur_w = 0
        elif v > 0:
            cur_w += 1
            cur_l = 0
        else:
            cur_l = cur_w = 0
        lose, win = max(lose, cur_l), max(win, cur_w)
    return lose, win


def drawdown_series(equity: pd.Series) -> pd.Series:
    peak = equity.cummax()
    return (equity / peak - 1.0).fillna(0.0)


def losing_periods(equity: pd.Series, min_depth: float = 0.02, limit: int = 10) -> list[LosingPeriod]:
    if equity.empty:
        return []
    dd = drawdown_series(equity).to_numpy()
    idx = equity.index
    periods: list[LosingPeriod] = []
    i, n = 0, len(dd)
    while i < n:
        if dd[i] < 0:
            start = i - 1 if i > 0 else 0
            j = i
            trough = i
            while j < n and dd[j] < 0:
                if dd[j] < dd[trough]:
                    trough = j
                j += 1
            depth = -float(dd[trough])
            if depth >= min_depth:
                periods.append(
                    LosingPeriod(
                        start=str(idx[start]),
                        trough=str(idx[trough]),
                        end=str(idx[j]) if j < n else None,
                        depth_pct=round(depth * 100, 2),
                        duration_bars=j - start,
                        recovered=j < n,
                    )
                )
            i = j
        else:
            i += 1
    periods.sort(key=lambda p: -p.depth_pct)
    return periods[:limit]


def compute_metrics(
    trades: Sequence[TradeLike], equity: pd.Series, in_market: Sequence[bool] | None = None
) -> MetricsBundle:
    m = Metrics()
    if len(equity):
        m.start_equity = float(equity.iloc[0])
        m.end_equity = float(equity.iloc[-1])
        m.net_profit = round(m.end_equity - m.start_equity, 2)
        m.total_return_pct = round((m.end_equity / m.start_equity - 1) * 100, 3) if m.start_equity else 0.0
        dd = drawdown_series(equity)
        m.max_drawdown_pct = round(-float(dd.min()) * 100, 3)
        m.max_drawdown_abs = round(float((equity.cummax() - equity).max()), 2)
        span_days = (equity.index[-1] - equity.index[0]).total_seconds() / 86_400 if len(equity) > 1 else 0
        if span_days > 0:
            years = span_days / 365.25
            m.years = round(years, 4)
            rets = equity.pct_change().dropna()
            bars_per_year = len(rets) / years if years > 0 else 0
            if len(rets) > 2 and rets.std() > 0 and bars_per_year > 0:
                m.sharpe = round(float(rets.mean() / rets.std() * math.sqrt(bars_per_year)), 3)
                m.volatility_pct = round(float(rets.std() * math.sqrt(bars_per_year) * 100), 3)
                downside = rets[rets < 0]
                if len(downside) > 1 and downside.std() > 0:
                    m.sortino = round(float(rets.mean() / downside.std() * math.sqrt(bars_per_year)), 3)
            if m.start_equity > 0 and m.end_equity > 0 and years >= 0.05:
                m.cagr_pct = round(((m.end_equity / m.start_equity) ** (1 / years) - 1) * 100, 3)
    if in_market is not None and len(in_market):
        m.exposure_pct = round(100.0 * float(np.mean(np.asarray(in_market, dtype=float))), 2)

    pnls = [t.pnl for t in trades]
    m.total_trades = len(pnls)
    if pnls:
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        m.wins, m.losses, m.breakeven = len(wins), len(losses), len(pnls) - len(wins) - len(losses)
        m.win_rate = round(len(wins) / len(pnls), 4)
        m.gross_profit = round(sum(wins), 2)
        m.gross_loss = round(sum(losses), 2)
        m.profit_factor = round(m.gross_profit / -m.gross_loss, 3) if m.gross_loss < 0 else None
        m.expectancy = round(float(np.mean(pnls)), 2)
        m.avg_win = round(float(np.mean(wins)), 2) if wins else None
        m.avg_loss = round(float(np.mean(losses)), 2) if losses else None
        m.largest_win = round(max(pnls), 2)
        m.largest_loss = round(min(pnls), 2)
        m.longest_losing_streak, m.longest_winning_streak = _streaks(pnls)
        rs = [t.pnl_r for t in trades if t.pnl_r is not None]
        if rs:
            m.average_r = round(float(np.mean(rs)), 3)
            m.expectancy_r = m.average_r
        m.avg_bars_held = round(float(np.mean([t.bars_held for t in trades])), 2)

    monthly: dict[str, float] = {}
    if len(equity) > 1:
        month_end = equity.groupby(equity.index.strftime("%Y-%m")).last()
        prev = m.start_equity
        for k, v in month_end.items():
            monthly[str(k)] = round((float(v) / prev - 1) * 100, 3) if prev else 0.0
            prev = float(v)

    by_regime: list[RegimeStats] = []
    regimes = sorted({t.regime for t in trades if t.regime})
    for rg in regimes:
        sub = [t for t in trades if t.regime == rg]
        sp = [t.pnl for t in sub]
        gl = -sum(p for p in sp if p < 0)
        rr = [t.pnl_r for t in sub if t.pnl_r is not None]
        by_regime.append(
            RegimeStats(
                regime=rg,
                trades=len(sub),
                win_rate=round(sum(1 for p in sp if p > 0) / len(sp), 4),
                average_r=round(float(np.mean(rr)), 3) if rr else None,
                profit_factor=round(sum(p for p in sp if p > 0) / gl, 3) if gl > 0 else None,
                net_profit=round(sum(sp), 2),
            )
        )

    dist: dict[str, int] = {}
    edges = [-np.inf, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 3, np.inf]
    labels = [
        "<-2R",
        "-2..-1.5R",
        "-1.5..-1R",
        "-1..-0.5R",
        "-0.5..0R",
        "0..0.5R",
        "0.5..1R",
        "1..1.5R",
        "1.5..2R",
        "2..3R",
        ">3R",
    ]
    rs_all = [t.pnl_r for t in trades if t.pnl_r is not None]
    if rs_all:
        counts, _ = np.histogram(rs_all, bins=edges)
        dist = {lbl: int(c) for lbl, c in zip(labels, counts, strict=True)}
    return MetricsBundle(
        metrics=m,
        monthly_returns=monthly,
        losing_periods=losing_periods(equity),
        by_regime=by_regime,
        r_distribution=dist,
    )

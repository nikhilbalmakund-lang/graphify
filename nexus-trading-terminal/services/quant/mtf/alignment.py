"""Multi-timeframe (MTF) analysis.

For each timeframe we summarise trend, momentum, structure, volatility, VWAP
relationship and key levels, then combine them into a weighted alignment in
[-1, 1]. The signal engine converts alignment into a bounded score adjustment
with fixed, documented rules (see `MTFAnalysis.adjustment_for`).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from market_data.models import Timeframe

TF_WEIGHTS: dict[Timeframe, float] = {
    Timeframe.M1: 0.05,
    Timeframe.M5: 0.07,
    Timeframe.M15: 0.11,
    Timeframe.M30: 0.12,
    Timeframe.H1: 0.18,
    Timeframe.H4: 0.22,
    Timeframe.D1: 0.25,
}
MAX_BONUS = 5.0
MAX_PENALTY = 10.0


class TimeframeView(BaseModel):
    timeframe: str
    available: bool = True
    note: str = ""
    close: float | None = None
    trend: str = "NEUTRAL"
    direction_value: float = 0.0  # [-1, 1]
    trend_score: float | None = None
    momentum_score: float | None = None
    structure_trend: str = "NEUTRAL"
    regime: str | None = None
    atr_pct: float | None = None
    vol_percentile: float | None = None
    rsi14: float | None = None
    vwap_relation: str = "UNAVAILABLE"
    nearest_support: float | None = None
    nearest_resistance: float | None = None


def direction_value(trend_score: float | None, structure_trend: str) -> float:
    ts = 0.0 if trend_score is None or math.isnan(trend_score) else trend_score
    st = {"BULLISH": 1.0, "BEARISH": -1.0}.get(structure_trend, 0.0)
    return float(np.clip(0.6 * math.tanh(ts / 35.0) + 0.4 * st, -1.0, 1.0))


def label_for(value: float) -> str:
    if value >= 0.3:
        return "BULLISH"
    if value <= -0.3:
        return "BEARISH"
    return "NEUTRAL"


class MTFAnalysis(BaseModel):
    views: list[TimeframeView] = Field(default_factory=list)
    alignment: float = 0.0
    bullish_weight: float = 0.0
    bearish_weight: float = 0.0
    dominant: str = "NEUTRAL"
    summary: str = ""

    def view(self, tf: Timeframe) -> TimeframeView | None:
        return next((v for v in self.views if v.timeframe == tf.value), None)

    def higher_than(self, tf: Timeframe) -> list[TimeframeView]:
        return [v for v in self.views if v.available and Timeframe(v.timeframe).seconds > tf.seconds]

    def adjustment_for(self, direction: int, primary: Timeframe) -> tuple[float, bool, list[str], list[str]]:
        """Score adjustment in [-MAX_PENALTY, +MAX_BONUS] for a direction on the primary timeframe.

        Rules:
        * support = weighted share of higher timeframes agreeing with the direction
        * oppose  = weighted share of higher timeframes disagreeing
        * adjustment = +5 * support - 10 * oppose   (penalties weigh double)
        * contradiction = the two heaviest higher timeframes both oppose
        """
        higher = self.higher_than(primary)
        if not higher:
            return 0.0, False, [], []
        weights = {v.timeframe: TF_WEIGHTS[Timeframe(v.timeframe)] for v in higher}
        total = sum(weights.values())
        support = sum(weights[v.timeframe] * max(0.0, direction * v.direction_value) for v in higher) / total
        oppose = sum(weights[v.timeframe] * max(0.0, -direction * v.direction_value) for v in higher) / total
        adj = round(MAX_BONUS * support - MAX_PENALTY * oppose, 2)
        heaviest = sorted(higher, key=lambda v: weights[v.timeframe], reverse=True)[:2]
        opp_label = "BEARISH" if direction > 0 else "BULLISH"
        same_label = "BULLISH" if direction > 0 else "BEARISH"
        contradiction = len(heaviest) == 2 and all(v.trend == opp_label for v in heaviest)
        pros = [f"{v.timeframe} trend {v.trend.lower()}" for v in higher if v.trend == same_label]
        cons = [f"{v.timeframe} trend {v.trend.lower()}" for v in higher if v.trend == opp_label]
        return adj, contradiction, pros, cons


def build_view(
    timeframe: Timeframe,
    frame: pd.DataFrame | None,
    structure_trend: str = "NEUTRAL",
    regime: str | None = None,
    supports: list[float] | None = None,
    resistances: list[float] | None = None,
    note: str = "",
) -> TimeframeView:
    if frame is None or len(frame) == 0:
        return TimeframeView(timeframe=timeframe.value, available=False, note=note or "No data")
    row = frame.iloc[-1]

    def g(col: str) -> float | None:
        v = row.get(col)
        if v is None:
            return None
        fv = float(v)
        return None if math.isnan(fv) else round(fv, 6)

    ts = g("trend_score")
    if ts is None:
        return TimeframeView(
            timeframe=timeframe.value, available=False, note=note or "Insufficient bars for indicators"
        )
    dv = direction_value(ts, structure_trend)
    vwap = g("vwap")
    close = g("close")
    vrel = "UNAVAILABLE" if vwap is None or close is None else ("ABOVE" if close >= vwap else "BELOW")
    return TimeframeView(
        timeframe=timeframe.value,
        close=close,
        trend=label_for(dv),
        direction_value=round(dv, 4),
        trend_score=ts,
        momentum_score=g("momentum_score"),
        structure_trend=structure_trend,
        regime=regime,
        atr_pct=g("atr_pct"),
        vol_percentile=g("vol_percentile"),
        rsi14=g("rsi14"),
        vwap_relation=vrel,
        nearest_support=supports[0] if supports else None,
        nearest_resistance=resistances[0] if resistances else None,
        note=note,
    )


def combine(views: list[TimeframeView]) -> MTFAnalysis:
    avail = [v for v in views if v.available]
    if not avail:
        return MTFAnalysis(views=views, summary="No timeframe data available")
    w = {v.timeframe: TF_WEIGHTS.get(Timeframe(v.timeframe), 0.1) for v in avail}
    total = sum(w.values())
    alignment = sum(w[v.timeframe] * v.direction_value for v in avail) / total
    bull = sum(w[v.timeframe] for v in avail if v.trend == "BULLISH") / total
    bear = sum(w[v.timeframe] for v in avail if v.trend == "BEARISH") / total
    dominant = label_for(alignment)
    parts = [
        f"{v.timeframe}: {v.trend.lower()}"
        for v in sorted(avail, key=lambda v: -Timeframe(v.timeframe).seconds)
    ]
    return MTFAnalysis(
        views=views,
        alignment=round(alignment, 4),
        bullish_weight=round(bull, 4),
        bearish_weight=round(bear, 4),
        dominant=dominant,
        summary=", ".join(parts),
    )


def resample_ohlcv(df: pd.DataFrame, timeframe: Timeframe) -> pd.DataFrame:
    """Aggregate a finer OHLCV frame to a coarser timeframe (bar open-time labels)."""
    rule_kwargs: dict[str, object]
    if timeframe == Timeframe.W1:
        rule_kwargs = {"rule": "7D", "origin": pd.Timestamp("2022-01-03", tz="UTC")}  # Monday-anchored weeks
    elif timeframe == Timeframe.D1:
        rule_kwargs = {"rule": "1D"}  # UTC calendar days
    else:
        rule_kwargs = {"rule": timeframe.pandas_rule, "origin": "epoch"}
    out = df.resample(label="left", closed="left", **rule_kwargs).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return out.dropna(subset=["open"])


def closed_htf_bars(df: pd.DataFrame, base: Timeframe, higher: Timeframe, t: int) -> pd.DataFrame:
    """Higher-timeframe bars that were fully closed at the close of base bar t (no look-ahead)."""
    upto = df.iloc[: t + 1]
    htf = resample_ohlcv(upto, higher)
    if len(htf) == 0:
        return htf
    bar_close_time = upto.index[-1] + pd.Timedelta(seconds=base.seconds)
    span = pd.Timedelta(days=7) if higher == Timeframe.W1 else pd.Timedelta(seconds=higher.seconds)
    return htf[htf.index + span <= bar_close_time]

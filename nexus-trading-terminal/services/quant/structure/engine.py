"""Market structure engine.

Objective definitions (all causal - a swing is only "known" once confirmed):

* Swing high at bar i: high[i] is strictly greater than the `left` previous
  highs and >= the `right` following highs. It is confirmed at bar i+right.
  Swing lows mirror this. Consecutive same-type swings are merged keeping the
  more extreme one, so highs and lows alternate.
* HH / LH: a swing high above / below the previous swing high. HL / LL for lows.
* Structure trend: BULLISH after HH+HL, BEARISH after LH+LL, else NEUTRAL.
* Break of Structure (BOS): a close beyond the last swing extreme in the
  direction of the prevailing structure (continuation).
* Change of Character (CHoCH): a close beyond the last swing extreme against
  the prevailing structure (first sign of reversal).
* Support / resistance: clusters of confirmed swing prices within 0.35 ATR.
* Range: prior-20-bar range <= 6 ATR, efficiency ratio < 0.30, ADX < 22.
* Breakout: close beyond the prior 20-bar high/low by > 0.1 ATR.
* Retest: after a breakout, price returns within 0.3 ATR of the broken level
  and closes back on the breakout side.

HEURISTIC concepts (labelled as such in every output):
* Liquidity sweep: wick beyond the last unbroken swing extreme with the close
  back inside. This is a price pattern; it does not reveal actual orders.
* Liquidity zones: equal highs/lows clusters and prior-day high/low, where
  stop orders are *commonly assumed* to rest. Ordinary OHLC data cannot see
  real order flow, so these are hypotheses, not observations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from pydantic import BaseModel, Field

HEURISTIC_NOTE = (
    "Liquidity sweeps and liquidity zones are heuristic price patterns derived from OHLC candles. "
    "They do not observe real orders or institutional positioning."
)

TREND_CODE = {1: "BULLISH", -1: "BEARISH", 0: "NEUTRAL"}
EV_NONE, EV_BOS_UP, EV_BOS_DOWN, EV_CHOCH_UP, EV_CHOCH_DOWN = 0, 1, 2, 3, 4
EVENT_NAMES = {EV_BOS_UP: ("BOS", "BULLISH"), EV_BOS_DOWN: ("BOS", "BEARISH"),
               EV_CHOCH_UP: ("CHOCH", "BULLISH"), EV_CHOCH_DOWN: ("CHOCH", "BEARISH")}


@dataclass
class Swing:
    index: int
    confirmed_at: int
    price: float
    kind: str  # HIGH | LOW
    label: str = ""  # HH | LH | HL | LL | "" (first of its kind)


@dataclass
class StructureStates:
    """Per-bar causal structure state for a whole series."""

    trend: np.ndarray  # int8: 1 / -1 / 0
    last_high: np.ndarray  # price of last confirmed swing high (alternating list)
    last_low: np.ndarray
    event: np.ndarray  # event code occurring at this bar
    sweep: np.ndarray  # 1 bullish sweep (of lows), -1 bearish sweep (of highs), 0 none
    sweep_level: np.ndarray
    swings: list[Swing] = field(default_factory=list)  # alternating swing list known at the last bar


def find_pivots(high: np.ndarray, low: np.ndarray, left: int = 3, right: int = 3) -> list[Swing]:
    n = len(high)
    out: list[Swing] = []
    if n < left + right + 1:
        return out
    w = left + right + 1
    hw = sliding_window_view(high, w)
    lw = sliding_window_view(low, w)
    centre_h = hw[:, left]
    centre_l = lw[:, left]
    is_high = (centre_h > hw[:, :left].max(axis=1)) & (centre_h >= hw[:, left + 1:].max(axis=1))
    is_low = (centre_l < lw[:, :left].min(axis=1)) & (centre_l <= lw[:, left + 1:].min(axis=1))
    for j in np.nonzero(is_high | is_low)[0]:
        i = int(j + left)
        if is_high[j]:
            out.append(Swing(index=i, confirmed_at=i + right, price=float(high[i]), kind="HIGH"))
        if is_low[j]:
            out.append(Swing(index=i, confirmed_at=i + right, price=float(low[i]), kind="LOW"))
    out.sort(key=lambda s: (s.confirmed_at, s.index))
    return out


def _add_swing(alt: list[Swing], s: Swing) -> bool:
    """Append to the alternating list (merge same-type runs). Returns True if list changed."""
    if alt and alt[-1].kind == s.kind:
        last = alt[-1]
        more_extreme = s.price > last.price if s.kind == "HIGH" else s.price < last.price
        if not more_extreme:
            return False
        alt.pop()
    prev_same = next((x for x in reversed(alt) if x.kind == s.kind), None)
    if prev_same is None:
        s.label = ""
    elif s.kind == "HIGH":
        s.label = "HH" if s.price > prev_same.price else "LH"
    else:
        s.label = "HL" if s.price > prev_same.price else "LL"
    alt.append(s)
    return True


def compute_structure_states(df: pd.DataFrame, left: int = 3, right: int = 3) -> StructureStates:
    high = df["high"].to_numpy(dtype="float64")
    low = df["low"].to_numpy(dtype="float64")
    close = df["close"].to_numpy(dtype="float64")
    n = len(df)
    pivots = find_pivots(high, low, left, right)
    trend = np.zeros(n, dtype=np.int8)
    last_high = np.full(n, np.nan)
    last_low = np.full(n, np.nan)
    event = np.zeros(n, dtype=np.int8)
    sweep = np.zeros(n, dtype=np.int8)
    sweep_level = np.full(n, np.nan)

    alt: list[Swing] = []
    p = 0
    state = 0
    ref_high = np.nan
    ref_low = np.nan
    high_broken = True
    low_broken = True
    for t in range(n):
        changed = False
        while p < len(pivots) and pivots[p].confirmed_at <= t:
            s = Swing(**pivots[p].__dict__)
            if _add_swing(alt, s):
                changed = True
            p += 1
        if changed:
            last_h = next((x for x in reversed(alt) if x.kind == "HIGH"), None)
            last_l = next((x for x in reversed(alt) if x.kind == "LOW"), None)
            if last_h is not None and last_h.price != ref_high:
                ref_high, high_broken = last_h.price, False
            if last_l is not None and last_l.price != ref_low:
                ref_low, low_broken = last_l.price, False
            labels_h = [x.label for x in alt if x.kind == "HIGH"][-1:]
            labels_l = [x.label for x in alt if x.kind == "LOW"][-1:]
            if labels_h == ["HH"] and labels_l == ["HL"]:
                state = 1
            elif labels_h == ["LH"] and labels_l == ["LL"]:
                state = -1
        # Breaks are evaluated on closes; sweeps on wicks that close back inside.
        if not high_broken and not np.isnan(ref_high):
            if close[t] > ref_high:
                event[t] = EV_CHOCH_UP if state == -1 else EV_BOS_UP
                state = 1
                high_broken = True
            elif high[t] > ref_high:
                sweep[t] = -1
                sweep_level[t] = ref_high
        if not low_broken and not np.isnan(ref_low):
            if close[t] < ref_low:
                event[t] = EV_CHOCH_DOWN if state == 1 else EV_BOS_DOWN
                state = -1
                low_broken = True
            elif low[t] < ref_low and sweep[t] == 0:
                sweep[t] = 1
                sweep_level[t] = ref_low
        trend[t] = state
        last_high[t] = ref_high
        last_low[t] = ref_low
    return StructureStates(trend=trend, last_high=last_high, last_low=last_low, event=event, sweep=sweep,
                           sweep_level=sweep_level, swings=alt)


# --------------------------------------------------------------------- snapshot
class Level(BaseModel):
    price: float
    kind: str  # SUPPORT | RESISTANCE
    touches: int
    last_touch: str
    strength: float
    distance_atr: float | None = None


class LiquidityZone(BaseModel):
    kind: str  # EQUAL_HIGHS | EQUAL_LOWS | PRIOR_DAY_HIGH | PRIOR_DAY_LOW
    price: float
    touches: int = 1
    heuristic: bool = True
    note: str = ""


class StructureEvent(BaseModel):
    type: str  # BOS | CHOCH
    direction: str  # BULLISH | BEARISH
    level: float | None
    timestamp: str
    bars_ago: int


class BreakoutInfo(BaseModel):
    direction: str
    level: float
    timestamp: str
    bars_ago: int
    retested: bool = False
    retest_bars_ago: int | None = None
    failed: bool = False


class SweepInfo(BaseModel):
    direction: str  # BULLISH (swept lows) | BEARISH (swept highs)
    level: float
    timestamp: str
    bars_ago: int
    heuristic: bool = True


class RangeInfo(BaseModel):
    is_range: bool
    high: float | None = None
    low: float | None = None
    height_atr: float | None = None


class SwingPoint(BaseModel):
    timestamp: str
    price: float
    kind: str
    label: str


class StructureSnapshot(BaseModel):
    trend: str
    last_swing_high: SwingPoint | None = None
    last_swing_low: SwingPoint | None = None
    recent_labels: list[str] = Field(default_factory=list)
    last_event: StructureEvent | None = None
    supports: list[Level] = Field(default_factory=list)
    resistances: list[Level] = Field(default_factory=list)
    range: RangeInfo
    breakout: BreakoutInfo | None = None
    sweep: SweepInfo | None = None
    liquidity_zones: list[LiquidityZone] = Field(default_factory=list)
    swings: list[SwingPoint] = Field(default_factory=list)
    heuristic_note: str = HEURISTIC_NOTE


def cluster_levels(swings: list[Swing], index: pd.DatetimeIndex, price: float, atr: float,
                   t: int, max_levels: int = 4) -> tuple[list[Level], list[Level]]:
    if not swings or atr <= 0 or np.isnan(atr):
        return [], []
    tol = 0.35 * atr
    pts = sorted(swings, key=lambda s: s.price)
    clusters: list[list[Swing]] = []
    for s in pts:
        if clusters and s.price - np.mean([c.price for c in clusters[-1]]) <= tol:
            clusters[-1].append(s)
        else:
            clusters.append([s])
    supports, resistances = [], []
    for c in clusters:
        lvl = float(np.mean([s.price for s in c]))
        last_bar = max(s.index for s in c)
        recency = max(0.0, 1.0 - (t - last_bar) / 300.0)
        strength = round(len(c) + recency, 3)
        level = Level(price=lvl, kind="SUPPORT" if lvl < price else "RESISTANCE", touches=len(c),
                      last_touch=index[last_bar].isoformat(), strength=strength,
                      distance_atr=round((lvl - price) / atr, 3))
        (supports if lvl < price else resistances).append(level)
    supports.sort(key=lambda lv: price - lv.price)
    resistances.sort(key=lambda lv: lv.price - price)
    return supports[:max_levels], resistances[:max_levels]


def liquidity_zones(swings: list[Swing], df: pd.DataFrame, atr: float, t: int, intraday: bool) -> list[LiquidityZone]:
    zones: list[LiquidityZone] = []
    if atr > 0 and not np.isnan(atr):
        tol = 0.15 * atr
        for kind, label in (("HIGH", "EQUAL_HIGHS"), ("LOW", "EQUAL_LOWS")):
            pts = sorted([s for s in swings if s.kind == kind][-12:], key=lambda s: s.price)
            group: list[Swing] = []
            for s in pts + [None]:  # type: ignore[list-item]
                if s is not None and group and s.price - group[-1].price <= tol:
                    group.append(s)
                    continue
                if len(group) >= 2:
                    zones.append(LiquidityZone(kind=label, price=float(np.mean([g.price for g in group])), touches=len(group),
                                               note="Equal swing extremes; stops are commonly assumed to rest beyond them (heuristic)"))
                group = [s] if s is not None else []
    if intraday and t > 0:
        idx = df.index[: t + 1]
        day = idx[-1].floor("D")
        prev = df.iloc[: t + 1][(idx < day) & (idx >= day - pd.Timedelta(days=4))]
        if len(prev):
            last_day = prev.index[-1].floor("D")
            pd_bars = prev[prev.index >= last_day]
            zones.append(LiquidityZone(kind="PRIOR_DAY_HIGH", price=float(pd_bars["high"].max()), heuristic=False,
                                       note="Prior session high (objective level)"))
            zones.append(LiquidityZone(kind="PRIOR_DAY_LOW", price=float(pd_bars["low"].min()), heuristic=False,
                                       note="Prior session low (objective level)"))
    return zones


def _point(s: Swing, index: pd.DatetimeIndex) -> SwingPoint:
    return SwingPoint(timestamp=index[s.index].isoformat(), price=s.price, kind=s.kind, label=s.label)


def analyze_structure(df: pd.DataFrame, features: pd.DataFrame, intraday: bool = True, left: int = 3,
                      right: int = 3, states: StructureStates | None = None, t: int | None = None) -> StructureSnapshot:
    """Structure snapshot at bar t (default: last bar) using only data <= t."""
    n = len(df)
    t = n - 1 if t is None else t
    if states is None or t != n - 1:
        sub = df.iloc[: t + 1]
        states = compute_structure_states(sub, left, right)
    index = df.index
    price = float(df["close"].iloc[t])
    atr = float(features["atr14"].iloc[t]) if not np.isnan(features["atr14"].iloc[t]) else float("nan")
    swings = [s for s in states.swings if s.confirmed_at <= t]
    last_h = next((s for s in reversed(swings) if s.kind == "HIGH"), None)
    last_l = next((s for s in reversed(swings) if s.kind == "LOW"), None)

    last_event = None
    ev_idx = np.nonzero(states.event[: t + 1])[0]
    if len(ev_idx):
        e = int(ev_idx[-1])
        typ, direction = EVENT_NAMES[int(states.event[e])]
        lvl = states.last_high[e] if direction == "BULLISH" else states.last_low[e]
        last_event = StructureEvent(type=typ, direction=direction, level=None if np.isnan(lvl) else float(lvl),
                                    timestamp=index[e].isoformat(), bars_ago=t - e)

    lookback_swings = [s for s in swings if s.index >= t - 300]
    supports, resistances = cluster_levels(lookback_swings, index, price, atr, t)

    rng = RangeInfo(is_range=False)
    r_atr = features["range20_atr"].iloc[t]
    er = features["er20"].iloc[t]
    adx_v = features["adx"].iloc[t]
    if not any(np.isnan(v) for v in (r_atr, er, adx_v)):
        rng = RangeInfo(is_range=bool(r_atr <= 6.0 and er < 0.30 and adx_v < 22.0),
                        high=float(features["prior_high20"].iloc[t]), low=float(features["prior_low20"].iloc[t]),
                        height_atr=round(float(r_atr), 3))

    breakout = _breakout(df, features, t)
    sweep = None
    sw_idx = np.nonzero(states.sweep[max(0, t - 5): t + 1])[0]
    if len(sw_idx):
        j = int(sw_idx[-1]) + max(0, t - 5)
        sweep = SweepInfo(direction="BULLISH" if states.sweep[j] == 1 else "BEARISH", level=float(states.sweep_level[j]),
                          timestamp=index[j].isoformat(), bars_ago=t - j)

    labels = [s.label for s in swings[-6:] if s.label]
    return StructureSnapshot(
        trend=TREND_CODE[int(states.trend[t])],
        last_swing_high=_point(last_h, index) if last_h else None,
        last_swing_low=_point(last_l, index) if last_l else None,
        recent_labels=labels,
        last_event=last_event,
        supports=supports,
        resistances=resistances,
        range=rng,
        breakout=breakout,
        sweep=sweep,
        liquidity_zones=liquidity_zones(lookback_swings, df, atr, t, intraday),
        swings=[_point(s, index) for s in swings[-24:]],
    )


def _breakout(df: pd.DataFrame, features: pd.DataFrame, t: int, lookback: int = 10) -> BreakoutInfo | None:
    close = df["close"].to_numpy()
    low = df["low"].to_numpy()
    high = df["high"].to_numpy()
    atr = features["atr14"].to_numpy()
    ph = features["prior_high20"].to_numpy()
    pl = features["prior_low20"].to_numpy()
    for b in range(t, max(t - lookback, 20) - 1, -1):
        if np.isnan(atr[b]) or np.isnan(ph[b]):
            continue
        direction = None
        if close[b] > ph[b] + 0.1 * atr[b]:
            direction, level = "BULLISH", float(ph[b])
        elif close[b] < pl[b] - 0.1 * atr[b]:
            direction, level = "BEARISH", float(pl[b])
        if direction is None:
            continue
        info = BreakoutInfo(direction=direction, level=level, timestamp=df.index[b].isoformat(), bars_ago=t - b)
        for j in range(b + 1, t + 1):
            a = atr[j] if not np.isnan(atr[j]) else atr[b]
            if direction == "BULLISH":
                if close[j] < level - 0.3 * a:
                    info.failed = True
                    break
                if low[j] <= level + 0.3 * a and close[j] > level and not info.retested:
                    info.retested, info.retest_bars_ago = True, t - j
            else:
                if close[j] > level + 0.3 * a:
                    info.failed = True
                    break
                if high[j] >= level - 0.3 * a and close[j] < level and not info.retested:
                    info.retested, info.retest_bars_ago = True, t - j
        return info
    return None

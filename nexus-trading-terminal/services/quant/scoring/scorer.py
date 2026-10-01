"""Signal scoring.

Each factor yields a directional sub-score s in [-1, 1] for a candidate
direction D (+1 long, -1 short). Points = weight * (s + 1) / 2, so a neutral
factor earns half its weight, a fully supportive factor earns all of it and a
fully opposing factor earns nothing. The total (0-100) is a SIGNAL SCORE -
a rules-based measure of setup quality, NOT a probability of success.
"""

from __future__ import annotations

import math

import numpy as np

from quant.signals.models import MacroContext, ScoreComponent, ScoringWeights, SignalContext


def _clip(x: float) -> float:
    return float(np.clip(x, -1.0, 1.0))


def _f(v: float | None, default: float = 0.0) -> float:
    return default if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def _side(d: int) -> str:
    return "bullish" if d > 0 else "bearish"


def score_trend(ctx: SignalContext, d: int) -> tuple[float, list[str], list[str]]:
    ts = _f(ctx.features.trend_score)
    alignment = ctx.mtf.alignment if ctx.mtf.views else ts / 100.0
    s = 0.5 * d * float(np.clip(ts / 60.0, -1, 1)) + 0.5 * d * alignment
    pros, cons = [], []
    label = ctx.features.trend
    if (label == "BULLISH" and d > 0) or (label == "BEARISH" and d < 0):
        pros.append(f"{ctx.timeframe} trend {label.lower()} (trend score {ts:.0f})")
    elif label != "NEUTRAL":
        cons.append(f"{ctx.timeframe} trend {label.lower()} (trend score {ts:.0f})")
    for v in ctx.mtf.views:
        if not v.available or v.timeframe == ctx.timeframe:
            continue
        if v.trend == ("BULLISH" if d > 0 else "BEARISH"):
            pros.append(f"{v.timeframe} trend {v.trend.lower()}")
        elif v.trend == ("BEARISH" if d > 0 else "BULLISH"):
            cons.append(f"{v.timeframe} trend {v.trend.lower()}")
    return _clip(s), pros, cons


def score_structure(ctx: SignalContext, d: int) -> tuple[float, list[str], list[str]]:
    st = ctx.structure
    code = {"BULLISH": 1, "BEARISH": -1}.get(st.trend, 0)
    s = 0.45 * d * code
    pros, cons = [], []
    if code == d:
        pros.append(
            f"{ctx.timeframe} structure {st.trend.lower()} ({', '.join(st.recent_labels[-2:]) or 'swings'})"
        )
    elif code == -d:
        cons.append(f"{ctx.timeframe} structure {st.trend.lower()}")
    ev = st.last_event
    if ev and ev.bars_ago <= 30:
        ev_dir = 1 if ev.direction == "BULLISH" else -1
        name = "Break of structure" if ev.type == "BOS" else "Change of character"
        if ev_dir == d:
            s += 0.30 if ev.type == "BOS" else 0.25
            pros.append(f"{name} {ev.direction.lower()} {ev.bars_ago} bars ago")
        else:
            s -= 0.35
            cons.append(f"{name} {ev.direction.lower()} {ev.bars_ago} bars ago")
    br = st.breakout
    if br and not br.failed and br.bars_ago <= 10:
        br_dir = 1 if br.direction == "BULLISH" else -1
        if br_dir == d:
            s += 0.20 + (0.10 if br.retested else 0.0)
            pros.append(
                f"{br.direction.capitalize()} breakout of {br.level:.{ctx.price_precision}f}"
                + (" with retest" if br.retested else "")
            )
        else:
            s -= 0.30
            cons.append(f"{br.direction.capitalize()} breakout of {br.level:.{ctx.price_precision}f}")
    elif br and br.failed and br.bars_ago <= 10:
        br_dir = 1 if br.direction == "BULLISH" else -1
        if br_dir == d:
            s -= 0.15
            cons.append(f"Recent {br.direction.lower()} breakout failed")
    return _clip(s), pros, cons


def score_momentum(ctx: SignalContext, d: int) -> tuple[float, list[str], list[str]]:
    f = ctx.features
    m = _f(f.momentum_score)
    s = d * m / 100.0
    pros, cons = [], []
    if d * m > 15:
        pros.append(f"Momentum {_side(d)} (score {m:.0f}, RSI {_f(f.rsi14):.0f})")
    elif d * m < -15:
        cons.append(f"Momentum against the setup (score {m:.0f})")
    rsi = f.rsi14
    if rsi is not None:
        if d > 0 and rsi > 75:
            s -= 0.35
            cons.append(f"RSI {rsi:.0f}: overextended for a long entry")
        elif d < 0 and rsi < 25:
            s -= 0.35
            cons.append(f"RSI {rsi:.0f}: overextended for a short entry")
    if f.macd_hist is not None and f.macd_hist * d > 0:
        pros.append("MACD histogram " + ("positive" if d > 0 else "negative"))
    return _clip(s), pros, cons


def score_volume_vwap(ctx: SignalContext, d: int) -> tuple[float, list[str], list[str]]:
    f = ctx.features
    if not f.volume_available or f.vwap is None:
        return 0.0, [], ["Volume/VWAP unavailable from this data feed (factor neutral)"]
    pros, cons = [], []
    dist = _f(f.dist_vwap_atr)
    s = 0.5 * d * math.tanh(dist)
    if dist * d > 0.05:
        pros.append(f"Price {'above' if d > 0 else 'below'} VWAP ({_f(f.dist_vwap_pct):+.2f}%)")
    elif dist * d < -0.05:
        cons.append(f"Price {'below' if d > 0 else 'above'} VWAP ({_f(f.dist_vwap_pct):+.2f}%)")
    vr = _f(f.volume_ratio, 1.0)
    r1 = _f(f.ret1)
    if vr > 1.2 and r1 * d > 0:
        s += 0.3
        pros.append(f"Volume {vr:.1f}x average on a {_side(d)} bar")
    elif vr > 1.2 and r1 * d < 0:
        s -= 0.3
        cons.append(f"Volume {vr:.1f}x average on a counter-direction bar")
    obv = _f(f.obv_slope10)
    s += 0.2 * d * math.tanh(obv * 5.0)
    if obv * d > 0.05:
        pros.append("OBV rising" if d > 0 else "OBV falling")
    return _clip(s), pros, cons


def score_liquidity(ctx: SignalContext, d: int) -> tuple[float, list[str], list[str]]:
    st = ctx.structure
    atr = _f(ctx.features.atr14)
    s = 0.0
    pros, cons = [], []
    prec = ctx.price_precision
    if st.sweep and st.sweep.bars_ago <= 5:
        sw_dir = 1 if st.sweep.direction == "BULLISH" else -1
        side = "Sell-side (lows)" if sw_dir > 0 else "Buy-side (highs)"
        if sw_dir == d:
            s += 0.5
            pros.append(f"{side} liquidity sweep at {st.sweep.level:.{prec}f} (heuristic)")
        else:
            s -= 0.4
            cons.append(f"{side} liquidity sweep at {st.sweep.level:.{prec}f} (heuristic)")
    if atr > 0:
        blockers = st.resistances if d > 0 else st.supports
        if blockers:
            dist = abs(blockers[0].price - ctx.price) / atr
            name = "Resistance" if d > 0 else "Support"
            if dist < 1.0:
                s -= 0.4
                cons.append(f"{name} {blockers[0].price:.{prec}f} only {dist:.1f} ATR away")
            elif dist >= 2.0:
                s += 0.3
                pros.append(f"{dist:.1f} ATR of room to {name.lower()} {blockers[0].price:.{prec}f}")
        else:
            s += 0.2
            pros.append("No mapped opposing level nearby")
        pools = [
            z
            for z in st.liquidity_zones
            if z.kind in (("EQUAL_HIGHS", "PRIOR_DAY_HIGH") if d > 0 else ("EQUAL_LOWS", "PRIOR_DAY_LOW"))
        ]
        for z in pools:
            gap = (z.price - ctx.price) * d / atr
            if 0.5 <= gap <= 3.0:
                s += 0.1
                pros.append(
                    f"{z.kind.replace('_', ' ').title()} at {z.price:.{prec}f} as a potential objective"
                    + (" (heuristic)" if z.heuristic else "")
                )
                break
    return _clip(s), pros, cons


def score_volatility(ctx: SignalContext, d: int) -> tuple[float, list[str], list[str]]:
    vp = ctx.features.vol_percentile
    if vp is None:
        return 0.0, [], ["Volatility percentile unavailable (insufficient history)"]
    if 25 <= vp <= 80:
        return 0.6, [f"Volatility in a workable range ({vp:.0f}th percentile)"], []
    if 80 < vp <= 92:
        return 0.1, [], [f"Elevated volatility ({vp:.0f}th percentile)"]
    if vp > 92:
        return -0.7, [], [f"Extreme volatility ({vp:.0f}th percentile)"]
    if vp < 10:
        return -0.4, [], [f"Very low volatility ({vp:.0f}th percentile): limited movement"]
    return 0.0, [], []


def score_macro(ctx: SignalContext, d: int) -> tuple[float, list[str], list[str]]:
    m: MacroContext = ctx.macro
    s = 0.0
    pros: list[str] = []
    cons: list[str] = []
    if m.available:
        s = d * m.bias
        pros += m.notes_for_long if d > 0 else m.notes_for_short
        cons += m.notes_for_short if d > 0 else m.notes_for_long
    ev = ctx.events
    if ev.available and ev.next_high_impact_minutes is not None and 0 <= ev.next_high_impact_minutes <= 120:
        s -= 0.5
        cons.append(
            f"High-impact event in {int(ev.next_high_impact_minutes)} min: {ev.next_high_impact_event}"
        )
    return _clip(s), pros, cons


def score_sentiment(ctx: SignalContext, d: int) -> tuple[float, list[str], list[str]]:
    sent = ctx.sentiment
    if not sent.available or sent.articles == 0:
        return 0.0, [], []
    weight = min(1.0, sent.articles / 3.0)
    s = d * sent.score * weight
    label = "demo " if sent.is_demo else ""
    if s > 0.1:
        return _clip(s), [f"News sentiment supportive ({label}{sent.articles} items, {sent.score:+.2f})"], []
    if s < -0.1:
        return _clip(s), [], [f"News sentiment opposing ({label}{sent.articles} items, {sent.score:+.2f})"]
    return _clip(s), [], []


SCORERS = {
    "trend": score_trend,
    "structure": score_structure,
    "momentum": score_momentum,
    "volume_vwap": score_volume_vwap,
    "liquidity": score_liquidity,
    "volatility": score_volatility,
    "macro": score_macro,
    "sentiment": score_sentiment,
}


def score_direction(
    ctx: SignalContext, d: int, weights: ScoringWeights
) -> tuple[float, list[ScoreComponent], float]:
    """Return (total score, components, mtf adjustment) for direction d."""
    from market_data.models import Timeframe  # local import avoids a cycle at module import

    norm = weights.normalised()
    comps: list[ScoreComponent] = []
    for name, fn in SCORERS.items():
        raw, pros, cons = fn(ctx, d)
        pts = norm[name] * (raw + 1.0) / 2.0
        comps.append(
            ScoreComponent(
                name=name,
                weight=round(norm[name], 3),
                points=round(pts, 3),
                raw=round(raw, 4),
                notes_for=pros,
                notes_against=cons,
            )
        )
    adj, _, _, _ = ctx.mtf.adjustment_for(d, Timeframe.parse(ctx.timeframe))
    total = float(np.clip(sum(c.points for c in comps) + adj, 0.0, 100.0))
    return round(total, 2), comps, adj

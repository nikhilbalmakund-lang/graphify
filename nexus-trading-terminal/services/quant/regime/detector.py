"""Market regime detection from measurable features (no AI involved).

Regimes: TRENDING_BULLISH, TRENDING_BEARISH, RANGING, BREAKOUT,
HIGH_VOLATILITY, LOW_VOLATILITY, MEAN_REVERSION, UNCERTAIN.

Each bar gets one *primary* regime chosen by a fixed priority, plus a list of
secondary flags. `clarity` (0-1) measures how decisively the rules fired; it
is a rule margin, NOT a probability.
"""

from __future__ import annotations

from enum import StrEnum

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

REGIME_VERSION = "1.0.0"


class Regime(StrEnum):
    TRENDING_BULLISH = "TRENDING_BULLISH"
    TRENDING_BEARISH = "TRENDING_BEARISH"
    RANGING = "RANGING"
    BREAKOUT = "BREAKOUT"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    MEAN_REVERSION = "MEAN_REVERSION"
    UNCERTAIN = "UNCERTAIN"


REGIME_CODES = list(Regime)


class RegimeThresholds(BaseModel):
    trend_adx: float = 22.0
    trend_score: float = 35.0
    trend_er: float = 0.30
    range_adx: float = 20.0
    range_er: float = 0.25
    range_trend_score: float = 25.0
    high_vol_pct: float = 90.0
    low_vol_pct: float = 12.0
    low_bbw_pct: float = 20.0
    mean_rev_autocorr: float = -0.08
    breakout_atr: float = 0.10


class RegimeResult(BaseModel):
    regime: Regime
    clarity: float
    flags: list[Regime] = Field(default_factory=list)
    evidence: dict[str, float | None] = Field(default_factory=dict)
    explanation: str = ""
    version: str = REGIME_VERSION


def _arr(f: pd.DataFrame, col: str) -> np.ndarray:
    return f[col].to_numpy(dtype="float64")


def classify_frame(f: pd.DataFrame, th: RegimeThresholds | None = None) -> pd.DataFrame:
    """Vectorised regime classification for every bar of an indicator frame."""
    th = th or RegimeThresholds()
    adx, ts, er = _arr(f, "adx"), _arr(f, "trend_score"), _arr(f, "er20")
    volp, bbwp, ac = _arr(f, "vol_percentile"), _arr(f, "bb_width_percentile"), _arr(f, "autocorr50")
    close, atr = _arr(f, "close"), _arr(f, "atr14")
    ph, pl = _arr(f, "prior_high20"), _arr(f, "prior_low20")
    n = len(f)
    with np.errstate(invalid="ignore"):
        brk_up = close > ph + th.breakout_atr * atr
        brk_dn = close < pl - th.breakout_atr * atr
        breakout = (brk_up | brk_dn) & (np.nan_to_num(volp, nan=50.0) >= 40)
        trending_strength = (
            np.clip((adx - th.trend_adx) / 15.0, -1, 1) * 0.4
            + np.clip((np.abs(ts) - th.trend_score) / 40.0, -1, 1) * 0.4
            + np.clip((er - th.trend_er) / 0.3, -1, 1) * 0.2
        )
        trending = (adx >= th.trend_adx) & (np.abs(ts) >= th.trend_score) & (er >= th.trend_er * 0.8)
        ranging = (adx < th.range_adx) & (er < th.range_er) & (np.abs(ts) < th.range_trend_score)
        mean_rev = ranging & (ac <= th.mean_rev_autocorr)
        high_vol = volp >= th.high_vol_pct
        low_vol = (volp <= th.low_vol_pct) & (bbwp <= th.low_bbw_pct)

    regime = np.full(n, Regime.UNCERTAIN.value, dtype=object)
    clarity = np.zeros(n)
    valid = ~(np.isnan(adx) | np.isnan(ts) | np.isnan(er) | np.isnan(volp))
    for i in range(n):
        if not valid[i]:
            continue
        if breakout[i]:
            regime[i] = Regime.BREAKOUT.value
            dist = (close[i] - ph[i]) if brk_up[i] else (pl[i] - close[i])
            clarity[i] = float(np.clip(dist / (atr[i] or 1) / 1.0, 0.2, 1.0))
        elif high_vol[i]:
            regime[i] = Regime.HIGH_VOLATILITY.value
            clarity[i] = float(np.clip((volp[i] - th.high_vol_pct) / 10.0 + 0.4, 0.2, 1.0))
        elif trending[i]:
            regime[i] = (Regime.TRENDING_BULLISH if ts[i] > 0 else Regime.TRENDING_BEARISH).value
            clarity[i] = float(np.clip(0.5 + trending_strength[i], 0.2, 1.0))
        elif mean_rev[i]:
            regime[i] = Regime.MEAN_REVERSION.value
            clarity[i] = float(np.clip(0.4 + (th.mean_rev_autocorr - ac[i]) * 3, 0.2, 1.0))
        elif ranging[i]:
            regime[i] = Regime.RANGING.value
            clarity[i] = float(np.clip(0.4 + (th.range_adx - adx[i]) / 20.0 + (th.range_er - er[i]), 0.2, 1.0))
        elif low_vol[i]:
            regime[i] = Regime.LOW_VOLATILITY.value
            clarity[i] = float(np.clip(0.4 + (th.low_vol_pct - volp[i]) / 20.0, 0.2, 1.0))
        else:
            clarity[i] = 0.0
    out = pd.DataFrame({"regime": regime, "clarity": clarity}, index=f.index)
    out["flag_high_vol"] = high_vol
    out["flag_low_vol"] = low_vol
    out["flag_trending"] = trending
    out["flag_ranging"] = ranging
    out["flag_mean_reversion"] = mean_rev
    out["flag_breakout"] = breakout
    return out


def detect_regime(f: pd.DataFrame, i: int = -1, th: RegimeThresholds | None = None,
                  classified: pd.DataFrame | None = None) -> RegimeResult:
    pos = len(f) + i if i < 0 else i
    # Classification is row-wise (features already carry their own lookback).
    row = classified.iloc[pos] if classified is not None else classify_frame(f.iloc[[pos]], th).iloc[0]
    frow = f.iloc[pos]
    flags: list[Regime] = []
    for col, reg in (("flag_high_vol", Regime.HIGH_VOLATILITY), ("flag_low_vol", Regime.LOW_VOLATILITY),
                     ("flag_ranging", Regime.RANGING), ("flag_mean_reversion", Regime.MEAN_REVERSION),
                     ("flag_breakout", Regime.BREAKOUT)):
        if bool(row[col]) and reg.value != row["regime"]:
            flags.append(reg)
    if bool(row["flag_trending"]) and not str(row["regime"]).startswith("TRENDING"):
        flags.append(Regime.TRENDING_BULLISH if (frow["trend_score"] or 0) > 0 else Regime.TRENDING_BEARISH)

    def g(col: str) -> float | None:
        v = frow.get(col)
        return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), 4)

    evidence = {k: g(k) for k in ("adx", "trend_score", "er20", "vol_percentile", "bb_width_percentile", "autocorr50", "atr_pct")}
    regime = Regime(row["regime"])
    return RegimeResult(regime=regime, clarity=round(float(row["clarity"]), 3), flags=flags, evidence=evidence,
                        explanation=_explain(regime, evidence))


def _explain(regime: Regime, e: dict[str, float | None]) -> str:
    def fmt(k: str, d: int = 1) -> str:
        v = e.get(k)
        return "n/a" if v is None else f"{v:.{d}f}"

    base = f"ADX {fmt('adx')}, trend score {fmt('trend_score')}, efficiency {fmt('er20', 2)}, volatility percentile {fmt('vol_percentile', 0)}"
    reasons = {
        Regime.TRENDING_BULLISH: "Directional trend up: strong ADX, positive trend score and efficient price path",
        Regime.TRENDING_BEARISH: "Directional trend down: strong ADX, negative trend score and efficient price path",
        Regime.RANGING: "Low ADX and inefficient price path: price is rotating inside a range",
        Regime.MEAN_REVERSION: "Range conditions with negative return autocorrelation (moves tend to reverse)",
        Regime.BREAKOUT: "Close beyond the prior 20-bar extreme by more than 0.1 ATR",
        Regime.HIGH_VOLATILITY: "ATR% in the top decile of its trailing distribution",
        Regime.LOW_VOLATILITY: "ATR% and Bollinger width near the bottom of their trailing distributions",
        Regime.UNCERTAIN: "No regime rule fired decisively (mixed or insufficient evidence)",
    }
    return f"{reasons[regime]}. {base}."

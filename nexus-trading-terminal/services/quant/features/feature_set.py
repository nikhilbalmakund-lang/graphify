"""Versioned feature computation.

`compute_indicator_frame` produces every indicator and derived feature for a
whole OHLCV frame in one vectorised, causal pass. `snapshot_at` reads a single
bar into a typed `FeatureSnapshot`. Live analysis, backtests, walk-forward
tests and the historical setup memory all use the same functions, so a
feature means the same thing everywhere.

Bump FEATURE_VERSION whenever a definition changes.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from pydantic import BaseModel

from market_data.models import Timeframe
from quant.indicators import core as ind

FEATURE_VERSION = "1.0.0"
MIN_BARS = 60


def compute_indicator_frame(
    df: pd.DataFrame, timeframe: Timeframe, volume_available: bool = True
) -> pd.DataFrame:
    """All indicators + derived features for every bar (causal)."""
    close = df["close"].astype("float64")
    c: dict[str, pd.Series] = {
        "close": close,
        "high": df["high"],
        "low": df["low"],
        "open": df["open"],
        "sma20": ind.sma(close, 20),
        "sma50": ind.sma(close, 50),
        "ema9": ind.ema(close, 9),
        "ema20": ind.ema(close, 20),
        "ema50": ind.ema(close, 50),
        "ema200": ind.ema(close, 200),
        "rsi14": ind.rsi(close, 14),
    }
    for frame in (ind.macd(close), ind.adx(df, 14), ind.bollinger(close, 20, 2.0), ind.stochastic(df)):
        c.update({k: frame[k] for k in frame.columns})
    atr = ind.atr(df, 14)
    c["atr14"] = atr
    c["cci20"] = ind.cci(df, 20)
    c["roc10"] = ind.roc(close, 10)
    c["er20"] = ind.efficiency_ratio(close, 20)
    logp = np.log(close)
    logret = logp.diff()
    c["ret1"] = logret
    c["ret5"] = logp.diff(5)
    c["ret20"] = logp.diff(20)
    c["realized_vol20"] = logret.rolling(20, min_periods=20).std()
    c["autocorr50"] = ind.rolling_autocorr(logret, 50, 1)

    nan = pd.Series(np.nan, index=df.index)
    if volume_available:
        vol = df["volume"].astype("float64")
        vol_sma = ind.sma(vol, 20)
        obv = ind.obv(close, vol)
        c.update(
            {
                "volume": vol,
                "volume_sma20": vol_sma,
                "volume_ratio": vol / vol_sma.replace(0.0, np.nan),
                "obv": obv,
                "obv_slope10": ind.linear_slope(obv, 10) / vol_sma.replace(0.0, np.nan),
                "vwap": ind.vwap(df, "D") if timeframe.is_intraday else ind.vwap(df, rolling_bars=20),
            }
        )
    else:
        c.update({k: nan for k in ("volume", "volume_sma20", "volume_ratio", "obv", "obv_slope10", "vwap")})

    atr_pct = atr / close * 100.0
    c["atr_pct"] = atr_pct
    c["vol_percentile"] = ind.rolling_percentile(atr_pct, 250, 50)
    c["bb_width_percentile"] = ind.rolling_percentile(c["bb_width"], 250, 50)
    vwap = c["vwap"]
    c["dist_vwap_pct"] = (close / vwap - 1.0) * 100.0
    c["dist_vwap_atr"] = (close - vwap) / atr
    c["dist_ema20_pct"] = (close / c["ema20"] - 1.0) * 100.0
    c["dist_ema50_pct"] = (close / c["ema50"] - 1.0) * 100.0
    c["dist_ema200_pct"] = (close / c["ema200"] - 1.0) * 100.0
    c["dist_ema50_atr"] = (close - c["ema50"]) / atr
    c["ema50_slope_atr"] = ind.linear_slope(c["ema50"], 10) * 10.0 / atr
    # Prior-window extremes (exclude the current bar) for breakout logic.
    c["prior_high20"] = df["high"].shift(1).rolling(20, min_periods=20).max()
    c["prior_low20"] = df["low"].shift(1).rolling(20, min_periods=20).min()
    c["range20_atr"] = (c["prior_high20"] - c["prior_low20"]) / atr
    f = pd.DataFrame(c, index=df.index)
    f["trend_score"] = _trend_score(f)
    f["momentum_score"] = _momentum_score(f)
    return f


def _trend_score(f: pd.DataFrame) -> pd.Series:
    """Directional trend strength in [-100, 100] (positive = bullish)."""
    atr = f["atr14"].replace(0.0, np.nan)
    c1 = np.tanh((f["close"] - f["ema50"]) / atr / 2.0)
    c2 = np.tanh((f["ema20"] - f["ema50"]) / atr)
    c3 = np.tanh(f["ema50_slope_atr"])
    di_sum = (f["plus_di"] + f["minus_di"]).replace(0.0, np.nan)
    c4 = ((f["plus_di"] - f["minus_di"]) / di_sum) * np.minimum(f["adx"] / 25.0, 1.0)
    return (100.0 * (0.25 * c1 + 0.25 * c2 + 0.25 * c3 + 0.25 * c4)).clip(-100, 100)


def _momentum_score(f: pd.DataFrame) -> pd.Series:
    """Momentum in [-100, 100] combining RSI, MACD histogram and ROC."""
    atr = f["atr14"].replace(0.0, np.nan)
    c1 = (f["rsi14"] - 50.0) / 50.0
    c2 = np.tanh(f["macd_hist"] / (0.25 * atr))
    roc_scale = (f["atr_pct"] * math.sqrt(10)).replace(0.0, np.nan)
    c3 = np.tanh(f["roc10"] / roc_scale)
    return (100.0 * (0.35 * c1 + 0.35 * c2 + 0.30 * c3)).clip(-100, 100)


def classify_trend(trend_score: float | None, threshold: float = 20.0) -> str:
    if trend_score is None or (isinstance(trend_score, float) and math.isnan(trend_score)):
        return "NEUTRAL"
    if trend_score >= threshold:
        return "BULLISH"
    if trend_score <= -threshold:
        return "BEARISH"
    return "NEUTRAL"


class FeatureSnapshot(BaseModel):
    """Features at one bar. None means 'not computable' (warm-up / no volume)."""

    feature_version: str = FEATURE_VERSION
    timestamp: str
    close: float
    sma20: float | None = None
    sma50: float | None = None
    ema9: float | None = None
    ema20: float | None = None
    ema50: float | None = None
    ema200: float | None = None
    rsi14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
    atr14: float | None = None
    atr_pct: float | None = None
    adx: float | None = None
    plus_di: float | None = None
    minus_di: float | None = None
    bb_upper: float | None = None
    bb_mid: float | None = None
    bb_lower: float | None = None
    bb_width: float | None = None
    bb_pct_b: float | None = None
    stoch_k: float | None = None
    stoch_d: float | None = None
    cci20: float | None = None
    roc10: float | None = None
    er20: float | None = None
    obv: float | None = None
    obv_slope10: float | None = None
    volume: float | None = None
    volume_sma20: float | None = None
    volume_ratio: float | None = None
    vwap: float | None = None
    dist_vwap_pct: float | None = None
    dist_vwap_atr: float | None = None
    dist_ema20_pct: float | None = None
    dist_ema50_pct: float | None = None
    dist_ema200_pct: float | None = None
    dist_ema50_atr: float | None = None
    ema50_slope_atr: float | None = None
    vol_percentile: float | None = None
    bb_width_percentile: float | None = None
    realized_vol20: float | None = None
    autocorr50: float | None = None
    ret1: float | None = None
    ret5: float | None = None
    ret20: float | None = None
    trend_score: float | None = None
    momentum_score: float | None = None
    prior_high20: float | None = None
    prior_low20: float | None = None
    range20_atr: float | None = None
    volume_available: bool = True
    bars_available: int = 0

    @property
    def trend(self) -> str:
        return classify_trend(self.trend_score)

    @property
    def vwap_relation(self) -> str:
        if self.vwap is None:
            return "UNAVAILABLE"
        return "ABOVE" if self.close >= self.vwap else "BELOW"


_SNAPSHOT_FIELDS = [
    name
    for name in FeatureSnapshot.model_fields
    if name not in {"feature_version", "timestamp", "close", "volume_available", "bars_available"}
]


def _clean(v: object) -> float | None:
    if v is None:
        return None
    try:
        fv = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if math.isnan(fv) or math.isinf(fv) else fv


def snapshot_at(frame: pd.DataFrame, i: int = -1, volume_available: bool = True) -> FeatureSnapshot:
    row = frame.iloc[i]
    idx = frame.index[i]
    values = {name: _clean(row.get(name)) for name in _SNAPSHOT_FIELDS}
    pos = i if i >= 0 else len(frame) + i
    return FeatureSnapshot(
        timestamp=pd.Timestamp(idx).isoformat(),
        close=float(row["close"]),
        volume_available=volume_available,
        bars_available=pos + 1,
        **values,
    )


# Compact numeric vector used for historical similarity search (order matters; versioned).
SIMILARITY_FEATURES: list[str] = [
    "trend_score",
    "momentum_score",
    "rsi14",
    "adx",
    "vol_percentile",
    "bb_width_percentile",
    "dist_ema50_atr",
    "er20",
    "autocorr50",
    "bb_pct_b",
]
SIMILARITY_SCALE: dict[str, float] = {
    "trend_score": 100.0,
    "momentum_score": 100.0,
    "rsi14": 50.0,
    "adx": 25.0,
    "vol_percentile": 50.0,
    "bb_width_percentile": 50.0,
    "dist_ema50_atr": 3.0,
    "er20": 0.5,
    "autocorr50": 0.3,
    "bb_pct_b": 1.0,
}


def similarity_vector(snapshot: FeatureSnapshot) -> list[float] | None:
    out = []
    for name in SIMILARITY_FEATURES:
        v = getattr(snapshot, name)
        if v is None:
            return None
        out.append(round(float(v) / SIMILARITY_SCALE[name], 6))
    return out

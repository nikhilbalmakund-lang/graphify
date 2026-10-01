import math

import numpy as np
import pandas as pd
import pytest

from market_data.models import Timeframe
from quant.features.feature_set import FEATURE_VERSION, compute_indicator_frame, similarity_vector, snapshot_at
from quant.indicators import core as ind


def ohlcv(n=300, seed=1, drift=0.0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(drift + 0.01 * rng.standard_normal(n)))
    open_ = np.concatenate([[100], close[:-1]])
    high = np.maximum(open_, close) * (1 + 0.003 * np.abs(rng.standard_normal(n)))
    low = np.minimum(open_, close) * (1 - 0.003 * np.abs(rng.standard_normal(n)))
    vol = rng.integers(100, 1000, n).astype(float)
    idx = pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx)


def ref_wilder(x, n):
    out = np.full(len(x), np.nan)
    vals = []
    avg = None
    for i, v in enumerate(x):
        if np.isnan(v):
            continue
        vals.append(v)
        if avg is None:
            avg = v
        else:
            avg = avg + (v - avg) / n
        if len(vals) >= n:
            out[i] = avg
    return out


def test_sma_and_ema_match_reference():
    s = pd.Series(np.arange(1, 31, dtype=float))
    assert ind.sma(s, 5).iloc[4] == pytest.approx(3.0)
    assert math.isnan(ind.sma(s, 5).iloc[3])
    alpha = 2 / (10 + 1)
    ema = s.iloc[0]
    for v in s.iloc[1:]:
        ema = alpha * v + (1 - alpha) * ema
    assert ind.ema(s, 10).iloc[-1] == pytest.approx(ema)


def test_rsi_matches_wilder_reference():
    df = ohlcv()
    delta = df["close"].diff().to_numpy()
    gain = np.where(np.isnan(delta), np.nan, np.clip(delta, 0, None))
    loss = np.where(np.isnan(delta), np.nan, np.clip(-delta, 0, None))
    ag, al = ref_wilder(gain, 14), ref_wilder(loss, 14)
    ref = 100 - 100 / (1 + ag / al)
    got = ind.rsi(df["close"], 14).to_numpy()
    mask = ~np.isnan(ref)
    assert np.allclose(got[mask], ref[mask])
    assert np.all((got[mask] >= 0) & (got[mask] <= 100))


def test_rsi_edge_cases():
    up = pd.Series(np.arange(1, 40, dtype=float))
    assert ind.rsi(up, 14).iloc[-1] == pytest.approx(100.0)
    flat = pd.Series(np.full(40, 5.0))
    assert ind.rsi(flat, 14).iloc[-1] == pytest.approx(50.0)


def test_atr_matches_reference():
    df = ohlcv()
    tr = np.maximum.reduce([
        (df["high"] - df["low"]).to_numpy(),
        np.abs(df["high"] - df["close"].shift(1)).to_numpy(),
        np.abs(df["low"] - df["close"].shift(1)).to_numpy(),
    ])
    tr[0] = df["high"].iloc[0] - df["low"].iloc[0]
    ref = ref_wilder(tr, 14)
    got = ind.atr(df, 14).to_numpy()
    mask = ~np.isnan(ref)
    assert np.allclose(got[mask], ref[mask])


def test_macd_bollinger_stoch_cci_obv_relationships():
    df = ohlcv()
    m = ind.macd(df["close"])
    assert np.allclose((m["macd"] - m["macd_signal"]).dropna(), m["macd_hist"].dropna())
    bb = ind.bollinger(df["close"])
    valid = bb.dropna()
    assert (valid["bb_upper"] >= valid["bb_mid"]).all() and (valid["bb_lower"] <= valid["bb_mid"]).all()
    st = ind.stochastic(df).dropna()
    assert ((st >= 0) & (st <= 100)).all().all()
    cci = ind.cci(df, 20)
    tp = (df["high"] + df["low"] + df["close"]) / 3
    w = tp.iloc[-20:]
    expected = (tp.iloc[-1] - w.mean()) / (0.015 * np.mean(np.abs(w - w.mean())))
    assert cci.iloc[-1] == pytest.approx(expected)
    obv = ind.obv(df["close"], df["volume"])
    step = np.sign(df["close"].diff().fillna(0)) * df["volume"]
    assert obv.iloc[-1] == pytest.approx(step.sum())


def test_adx_bounds_and_trend_detection():
    trend = ohlcv(drift=0.004)
    a = ind.adx(trend).dropna()
    assert ((a["adx"] >= 0) & (a["adx"] <= 100)).all()
    assert a["plus_di"].iloc[-50:].mean() > a["minus_di"].iloc[-50:].mean()


def test_vwap_resets_daily_and_handles_missing_volume():
    df = ohlcv(n=200)
    v = ind.vwap(df, "D")
    first_of_day = df.index.floor("D") != df.index.floor("D").to_series().shift(1).to_numpy()
    tp = (df["high"] + df["low"] + df["close"]) / 3
    assert np.allclose(v[first_of_day], tp[first_of_day])
    no_vol = df.assign(volume=0.0)
    assert ind.vwap(no_vol).isna().all()


def test_indicators_are_causal():
    df = ohlcv(n=400)
    full = compute_indicator_frame(df, Timeframe.M15)
    part = compute_indicator_frame(df.iloc[:300], Timeframe.M15)
    cols = ["ema20", "rsi14", "atr14", "adx", "macd_hist", "bb_width", "vol_percentile", "trend_score", "momentum_score", "vwap"]
    a = full[cols].iloc[:300].to_numpy()
    b = part[cols].to_numpy()
    assert np.allclose(a, b, equal_nan=True)


def test_percentile_rank():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    out = ind.rolling_percentile(s, 5, 1)
    assert out.iloc[-1] == pytest.approx(90.0)  # 4 below + half of itself out of 5
    assert out.iloc[0] == pytest.approx(50.0)


def test_feature_snapshot_and_similarity_vector():
    df = ohlcv(n=400)
    f = compute_indicator_frame(df, Timeframe.M15)
    snap = snapshot_at(f)
    assert snap.feature_version == FEATURE_VERSION
    assert -100 <= snap.trend_score <= 100 and -100 <= snap.momentum_score <= 100
    assert snap.atr_pct > 0
    vec = similarity_vector(snap)
    assert vec is not None and len(vec) == 10
    early = snapshot_at(f, 10)
    assert early.ema200 is None and similarity_vector(early) is None

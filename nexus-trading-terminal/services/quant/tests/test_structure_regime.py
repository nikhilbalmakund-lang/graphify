import numpy as np
import pandas as pd

from market_data.models import Timeframe
from quant.features.feature_set import compute_indicator_frame
from quant.mtf.alignment import TimeframeView, closed_htf_bars, combine, resample_ohlcv
from quant.regime.detector import Regime, classify_frame, detect_regime
from quant.structure.engine import EV_BOS_UP, EV_CHOCH_DOWN, analyze_structure, compute_structure_states, find_pivots


def frame_from_path(path, freq="1h"):
    path = np.asarray(path, dtype=float)
    open_ = np.concatenate([[path[0]], path[:-1]])
    high = np.maximum(open_, path) + 0.05
    low = np.minimum(open_, path) - 0.05
    idx = pd.date_range("2025-01-06", periods=len(path), freq=freq, tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": path, "volume": 100.0}, index=idx)


def zigzag(points, steps=6):
    out = []
    for a, b in zip(points[:-1], points[1:], strict=True):
        out.extend(np.linspace(a, b, steps, endpoint=False))
    out.append(points[-1])
    return out


def test_pivots_are_confirmed_after_right_bars():
    df = frame_from_path(zigzag([100, 110, 105, 115, 108]))
    piv = find_pivots(df["high"].to_numpy(), df["low"].to_numpy(), 3, 3)
    assert piv, "expected pivots"
    assert all(p.confirmed_at == p.index + 3 for p in piv)


def test_uptrend_structure_labels_and_bos():
    df = frame_from_path(zigzag([100, 110, 105, 115, 110, 120, 114, 126]))
    states = compute_structure_states(df)
    labels = [s.label for s in states.swings if s.label]
    assert "HH" in labels and "HL" in labels
    assert states.trend[-1] == 1
    assert (states.event == EV_BOS_UP).any()


def test_change_of_character_on_break_of_last_higher_low():
    df = frame_from_path(zigzag([100, 110, 105, 115, 110, 120, 113, 100]))
    states = compute_structure_states(df)
    assert (states.event == EV_CHOCH_DOWN).any()
    assert states.trend[-1] == -1


def test_structure_snapshot_levels_and_heuristic_labels():
    df = frame_from_path(zigzag([100, 110, 104, 110, 104, 110, 104, 107], steps=8))
    f = compute_indicator_frame(df, Timeframe.H1)
    snap = analyze_structure(df, f)
    assert snap.resistances and abs(snap.resistances[0].price - 110.05) < 0.6
    assert snap.supports and snap.supports[0].touches >= 2
    assert "heuristic" in snap.heuristic_note.lower()
    assert any(z.kind == "EQUAL_HIGHS" and z.heuristic for z in snap.liquidity_zones)


def test_structure_is_causal():
    df = frame_from_path(zigzag([100, 110, 105, 115, 110, 120, 113, 100, 108, 96]))
    full = compute_structure_states(df)
    part = compute_structure_states(df.iloc[:40])
    assert np.array_equal(full.trend[:40], part.trend)
    assert np.array_equal(full.event[:40], part.event)


def test_regime_trending_and_ranging():
    rng = np.random.default_rng(3)
    up = 100 + np.cumsum(0.25 + 0.1 * rng.standard_normal(400))
    f_up = compute_indicator_frame(frame_from_path(up), Timeframe.H1)
    assert detect_regime(f_up).regime in (Regime.TRENDING_BULLISH, Regime.BREAKOUT)
    t = np.arange(400)
    flat = 100 + 1.5 * np.sin(t / 3.0) + 0.2 * rng.standard_normal(400)
    f_flat = compute_indicator_frame(frame_from_path(flat), Timeframe.H1)
    res = detect_regime(f_flat)
    assert res.regime in (Regime.RANGING, Regime.MEAN_REVERSION, Regime.LOW_VOLATILITY)
    assert 0 <= res.clarity <= 1
    cls = classify_frame(f_flat)
    assert set(cls["regime"].unique()) <= {r.value for r in Regime}


def test_regime_uncertain_with_insufficient_data():
    f = compute_indicator_frame(frame_from_path(np.linspace(100, 101, 30)), Timeframe.H1)
    assert detect_regime(f).regime == Regime.UNCERTAIN


def test_mtf_alignment_and_adjustment_rules():
    views = [
        TimeframeView(timeframe="15m", trend="BULLISH", direction_value=0.8),
        TimeframeView(timeframe="1H", trend="BULLISH", direction_value=0.7),
        TimeframeView(timeframe="4H", trend="BEARISH", direction_value=-0.6),
        TimeframeView(timeframe="1D", trend="BEARISH", direction_value=-0.9),
    ]
    mtf = combine(views)
    assert -1 <= mtf.alignment <= 1
    adj_long, contradiction, pros, cons = mtf.adjustment_for(1, Timeframe.M15)
    assert contradiction and adj_long < 0 and "4H trend bearish" in cons
    adj_short, contra_short, _, _ = mtf.adjustment_for(-1, Timeframe.M15)
    assert not contra_short and adj_short > adj_long
    assert -10 <= adj_long <= 5 and -10 <= adj_short <= 5


def test_closed_htf_bars_have_no_lookahead():
    df = frame_from_path(np.linspace(100, 120, 24 * 10), freq="1h")
    t = 30  # bar 30 = day 2, 06:00
    htf = closed_htf_bars(df, Timeframe.H1, Timeframe.H4, t)
    close_time = df.index[t] + pd.Timedelta(hours=1)
    assert (htf.index + pd.Timedelta(hours=4) <= close_time).all()
    full = resample_ohlcv(df, Timeframe.H4)
    assert len(full) > len(htf)

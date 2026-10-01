from datetime import UTC, datetime, timedelta
from itertools import pairwise

import numpy as np
import pandas as pd
import pytest

from market_data.assets import DEFAULT_CATALOG
from market_data.models import Timeframe
from market_data.providers.demo import DemoMarketDataProvider
from quant.ml.calibration import SetupProbabilityModel, expected_calibration_error
from quant.ml.memory import (
    SetupOutcome,
    SetupRecord,
    build_setup_memory,
    evidence_from,
    find_similar,
    sample_label,
    summarize_conditions,
)
from quant.signals.outcome_sim import simulate_plan

NOW = datetime(2026, 10, 1, 14, 30, 27, tzinfo=UTC)


def fut(rows):
    idx = pd.date_range("2025-01-01", periods=len(rows), freq="1h", tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


TARGETS = [("TP1", 102.0, 0.5), ("TP2", 104.0, 0.3), ("TP3", 106.0, 0.2)]


def test_outcome_partial_then_breakeven():
    out = simulate_plan(
        fut([[100, 101, 99.5, 100.5], [100.5, 102.5, 100.2, 102], [102, 102.1, 99.5, 100]]),
        1,
        "MARKET",
        100,
        99,
        TARGETS,
    )
    assert out.resolved and out.status == "WIN" and out.tp_hits == ["TP1"]
    assert out.r_multiple == pytest.approx(0.5 * 2.0)  # half off at 2R, rest stopped at breakeven
    assert out.tp1_before_sl is True and out.exit_reason == "BREAKEVEN_STOP"


def test_outcome_stop_first_when_same_bar():
    out = simulate_plan(fut([[100, 103, 98, 100]]), 1, "MARKET", 100, 99, TARGETS)
    assert out.status == "LOSS" and out.r_multiple == pytest.approx(-1.0) and out.tp1_before_sl is False


def test_outcome_all_targets_short_and_expiry_and_invalidation():
    rows = [[100, 100.2, 93, 94]]
    out = simulate_plan(
        fut(rows), -1, "MARKET", 100, 101, [("TP1", 98, 0.5), ("TP2", 96, 0.3), ("TP3", 94, 0.2)]
    )
    assert out.status == "WIN" and out.r_multiple == pytest.approx(0.5 * 2 + 0.3 * 4 + 0.2 * 6)
    exp = simulate_plan(
        fut([[105, 106, 104, 105]] * 8), 1, "ZONE", 100, 98, TARGETS, zone=(99.5, 100.5), expiry_bars=8
    )
    assert exp.status == "EXPIRED" and not exp.filled
    inv = simulate_plan(
        fut([[101, 101, 97, 97.5]]), 1, "ZONE", 99, 97, TARGETS, invalidation_level=98, zone=(98.8, 99.2)
    )
    assert inv.status == "INVALIDATED"
    pending = simulate_plan(
        fut([[105, 106, 104, 105]] * 2), 1, "ZONE", 100, 98, TARGETS, zone=(99.5, 100.5), expiry_bars=8
    )
    assert pending.status == "PENDING" and not pending.resolved


@pytest.fixture(scope="module")
def records():
    p = DemoMarketDataProvider(clock=lambda: NOW)
    s = p.candles_sync("XAUUSD", Timeframe.H1, start=NOW - timedelta(days=200), end=NOW).closed_bars()
    return build_setup_memory(
        s, Timeframe.H1, DEFAULT_CATALOG.get("XAUUSD"), provider="demo", is_demo=True, step=3
    )


def test_memory_is_deterministic_and_non_overlapping(records):
    assert len(records) > 50
    assert all(r.is_demo and r.vector and r.direction in ("LONG", "SHORT") for r in records)
    ts = [pd.Timestamp(r.timestamp) for r in records]
    assert ts == sorted(ts)
    filled = [r for r in records if r.filled]
    for a, b in pairwise(filled):
        exit_bar = pd.Timestamp(a.timestamp) + pd.Timedelta(hours=a.outcome.bars_held)
        assert pd.Timestamp(b.timestamp) >= exit_bar


def test_similarity_and_evidence_labels(records):
    q = records[-1]
    pool = [r for r in records[:-1] if r.direction == q.direction]
    matches = find_similar(q.vector, q.regime, pool, k=20)
    assert matches == sorted(matches, key=lambda m: m.distance)
    ev = evidence_from(matches, True)
    assert ev.sample_size <= 20 and ev.is_demo
    assert ev.sample_label == sample_label(ev.sample_size)
    assert any("DEMO" in n for n in ev.notes)
    tiny = evidence_from(matches[:4], True)
    assert tiny.sample_label == "INSUFFICIENT" and any("too small" in n for n in tiny.notes)
    summary = summarize_conditions(find_similar(q.vector, q.regime, pool, k=50), True)
    assert summary.sample_size <= 50 and summary.caveats


def _synthetic(n, informative, seed=0):
    rng = np.random.default_rng(seed)
    recs = []
    for i in range(n):
        v = rng.standard_normal(10).round(4).tolist()
        p = 1 / (1 + np.exp(-2.5 * v[0])) if informative else 0.4
        win = bool(rng.random() < p)
        recs.append(
            SetupRecord(
                symbol="X",
                timeframe="1H",
                timestamp=f"2025-01-01T00:00:00+00:00#{i:06d}",
                direction="LONG",
                score=60,
                regime="RANGING",
                asset_class="FOREX",
                vector=v,
                entry_type="MARKET",
                entry=1,
                stop=0.9,
                effective_rr=2,
                outcome=SetupOutcome(
                    status="WIN" if win else "LOSS", r_multiple=1.0 if win else -1.0, tp1_before_sl=win
                ),
                is_demo=True,
                provider="test",
            )
        )
    return recs


def test_calibration_gate():
    small = SetupProbabilityModel()
    assert small.fit(_synthetic(100, True), "DEMO").status == "INSUFFICIENT_DATA"
    assert small.predict([0.0] * 10, "LONG", 60, 2, "RANGING", "FOREX") is None
    good = SetupProbabilityModel()
    rep = good.fit(_synthetic(3000, True, 1), "DEMO")
    assert rep.status == "CALIBRATED", rep.reasons
    assert rep.ece <= 0.05 and rep.brier_skill > 0 and rep.n_test >= 100
    hi = good.predict([2.0] + [0.0] * 9, "LONG", 60, 2, "RANGING", "FOREX")
    lo = good.predict([-2.0] + [0.0] * 9, "LONG", 60, 2, "RANGING", "FOREX")
    assert hi is not None and lo is not None and hi > lo
    noise = SetupProbabilityModel()
    rep2 = noise.fit(_synthetic(3000, False, 2), "DEMO")
    assert rep2.status == "NOT_CALIBRATED"
    assert noise.predict([0.0] * 10, "LONG", 60, 2, "RANGING", "FOREX") is None


def test_ece_perfect_calibration():
    p = np.array([0.2] * 50 + [0.8] * 50)
    y = np.array([1] * 10 + [0] * 40 + [1] * 40 + [0] * 10)
    ece, bins = expected_calibration_error(p, y)
    assert ece == pytest.approx(0.0, abs=1e-9) and sum(b.count for b in bins) == 100

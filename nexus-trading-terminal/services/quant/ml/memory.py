"""Historical setup memory.

Building: walk a historical series bar by bar (causally), let the signal
engine propose a plan wherever the score is at least `min_score` with a valid
structural stop, then label the plan with what the FOLLOWING candles did
(`simulate_plan`). Setups do not overlap: after a filled setup the walk
resumes at its exit, so samples are not counted twice.

Querying: nearest neighbours in the versioned similarity feature space, same
symbol / timeframe / direction, preferring the same regime. Evidence always
states its sample size and labels small samples as unreliable.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from market_data.models import AssetSpec, Timeframe
from market_data.normalization.validation import DataQualityReport
from quant.features.feature_set import FEATURE_VERSION, similarity_vector
from quant.signals.context import HIGHER_TIMEFRAMES, PrecomputedMTF, analyze_series, build_context
from quant.signals.engine import SignalEngine
from quant.signals.models import SIGNAL_ENGINE_VERSION, HistoricalEvidence
from quant.signals.outcome_sim import simulate_plan

WARMUP_BARS = 250
REGIME_PENALTY = 0.5
DEFAULT_MAX_DISTANCE = 2.0


class SetupOutcome(BaseModel):
    status: str
    r_multiple: float | None = None
    exit_reason: str | None = None
    bars_held: int = 0
    mfe_r: float = 0.0
    mae_r: float = 0.0
    tp1_before_sl: bool | None = None


class SetupRecord(BaseModel):
    symbol: str
    timeframe: str
    timestamp: str
    direction: str
    score: float
    regime: str
    asset_class: str
    vector: list[float]
    entry_type: str
    entry: float
    stop: float
    effective_rr: float
    outcome: SetupOutcome
    is_demo: bool
    provider: str
    source: str = "HISTORICAL_BUILD"
    feature_version: str = FEATURE_VERSION
    signal_engine_version: str = SIGNAL_ENGINE_VERSION

    @property
    def filled(self) -> bool:
        return self.outcome.status in ("WIN", "LOSS", "BREAKEVEN") and self.outcome.r_multiple is not None


def build_setup_memory(
    df: pd.DataFrame,
    timeframe: Timeframe,
    spec: AssetSpec,
    *,
    provider: str,
    is_demo: bool,
    engine: SignalEngine | None = None,
    step: int = 2,
    min_score: float = 55.0,
    max_hold_bars: int = 96,
    volume_available: bool = True,
) -> list[SetupRecord]:
    engine = engine or SignalEngine()
    cfg = engine.config
    n = len(df)
    if n < WARMUP_BARS + 20:
        return []
    bundle = analyze_series(df, timeframe, volume_available, cfg.swing_left, cfg.swing_right)
    mtf = PrecomputedMTF(df, timeframe, HIGHER_TIMEFRAMES[timeframe][:2], volume_available)
    dq = DataQualityReport(
        symbol=spec.symbol, timeframe=timeframe.value, provider=provider, is_demo=is_demo, bars=n
    )
    records: list[SetupRecord] = []
    t = WARMUP_BARS
    while t < n - 2:
        ctx = build_context(
            symbol=spec.symbol,
            spec=spec,
            bundle=bundle,
            t=t,
            mtf=mtf.at(t),
            data_quality=dq,
            market_open=True,
            is_demo=is_demo,
            provider=provider,
        )
        cand = engine.evaluate(ctx)
        lv = cand.levels
        if lv is None or cand.score < min_score or lv.effective_rr < cfg.min_rr:
            t += step
            continue
        snap = ctx.features
        vec = similarity_vector(snap)
        if vec is None:
            t += step
            continue
        d = cand.proposed_direction.sign
        future = df.iloc[t + 1 : t + 1 + cfg.expiry_bars + max_hold_bars]
        zone = (
            (lv.entry_zone_low, lv.entry_zone_high)
            if lv.entry_zone_low is not None and lv.entry_zone_high is not None
            else None
        )
        out = simulate_plan(
            future,
            d,
            lv.entry_type.value,
            lv.entry_price,
            lv.stop,
            [(tp.label, tp.price, tp.allocation) for tp in lv.targets],
            invalidation_level=lv.invalidation_level,
            zone=zone,
            expiry_bars=cfg.expiry_bars,
            max_hold_bars=max_hold_bars,
            spread=spec.typical_spread,
        )
        if not out.resolved:
            break  # remaining setups cannot be labelled yet
        records.append(
            SetupRecord(
                symbol=spec.symbol,
                timeframe=timeframe.value,
                timestamp=cand.timestamp,
                direction=cand.proposed_direction.value,
                score=cand.score,
                regime=cand.regime,
                asset_class=spec.asset_class.value,
                vector=vec,
                entry_type=lv.entry_type.value,
                entry=lv.entry_price,
                stop=lv.stop,
                effective_rr=lv.effective_rr,
                outcome=SetupOutcome(
                    status=out.status,
                    r_multiple=out.r_multiple,
                    exit_reason=out.exit_reason,
                    bars_held=out.bars_held,
                    mfe_r=out.mfe_r,
                    mae_r=out.mae_r,
                    tp1_before_sl=out.tp1_before_sl,
                ),
                is_demo=is_demo,
                provider=provider,
            )
        )
        if out.filled and out.fill_index is not None:
            t = t + 1 + out.fill_index + max(out.bars_held, 1)
        else:
            t += step
    return records


def sample_label(n: int) -> str:
    if n == 0:
        return "NONE"
    if n < 10:
        return "INSUFFICIENT"
    if n < 30:
        return "SMALL"
    if n < 100:
        return "MODERATE"
    return "LARGE"


class SimilarMatch(BaseModel):
    record: SetupRecord
    distance: float


def find_similar(
    vector: list[float],
    regime: str,
    candidates: Iterable[SetupRecord],
    k: int = 50,
    max_distance: float = DEFAULT_MAX_DISTANCE,
) -> list[SimilarMatch]:
    q = np.asarray(vector, dtype="float64")
    scored: list[SimilarMatch] = []
    for rec in candidates:
        v = np.asarray(rec.vector, dtype="float64")
        if v.shape != q.shape:
            continue
        dist = float(np.linalg.norm(v - q)) + (0.0 if rec.regime == regime else REGIME_PENALTY)
        if dist <= max_distance:
            scored.append(SimilarMatch(record=rec, distance=round(dist, 4)))
    scored.sort(key=lambda m: m.distance)
    return scored[:k]


def evidence_from(matches: list[SimilarMatch], is_demo: bool) -> HistoricalEvidence:
    filled = sorted([m.record for m in matches if m.record.filled], key=lambda r: r.timestamp)
    unfilled = len(matches) - len(filled)
    rs = [r.outcome.r_multiple for r in filled if r.outcome.r_multiple is not None]
    n = len(rs)
    label = sample_label(n)
    notes = [
        f"{n} filled similar setups ({unfilled} similar setups never triggered or were invalidated before entry)"
    ]
    if label in ("INSUFFICIENT", "SMALL"):
        notes.append(f"Sample of {n} is too small for reliable statistics; treat as anecdotal")
    if is_demo:
        notes.append("Evidence derived from DEMO (synthetic) data")
    if n == 0:
        return HistoricalEvidence(sample_size=0, sample_label=label, is_demo=is_demo, notes=notes)
    arr = np.asarray(rs)
    cum = np.cumsum(arr)
    peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))
    dd = float(np.max(peak - np.concatenate([[0.0], cum])))
    wins = int((arr > 0.05).sum())
    losses = int((arr < -0.05).sum())
    return HistoricalEvidence(
        sample_size=n,
        wins=wins,
        losses=losses,
        win_rate=round(wins / n, 4),
        avg_r=round(float(arr.mean()), 4),
        expectancy=round(float(arr.mean()), 4),
        max_drawdown_r=round(dd, 3),
        sample_label=label,
        is_demo=is_demo,
        notes=notes,
    )


class ConditionsSummary(BaseModel):
    sample_size: int
    sample_label: str
    outcomes: dict[str, int] = Field(default_factory=dict)
    average_r: float | None = None
    median_r: float | None = None
    r_quantiles: dict[str, float] = Field(default_factory=dict)
    regimes: dict[str, int] = Field(default_factory=dict)
    directions: dict[str, int] = Field(default_factory=dict)
    first: str | None = None
    last: str | None = None
    caveats: list[str] = Field(default_factory=list)


def summarize_conditions(matches: list[SimilarMatch], is_demo: bool) -> ConditionsSummary:
    """'What happened the last N times conditions looked like this?'"""
    recs = [m.record for m in matches]
    rs = [r.outcome.r_multiple for r in recs if r.outcome.r_multiple is not None]
    outcomes: dict[str, int] = {}
    regimes: dict[str, int] = {}
    directions: dict[str, int] = {}
    for r in recs:
        outcomes[r.outcome.status] = outcomes.get(r.outcome.status, 0) + 1
        regimes[r.regime] = regimes.get(r.regime, 0) + 1
        directions[r.direction] = directions.get(r.direction, 0) + 1
    caveats = [
        "Similarity is measured on technical features only; macro and news context are not matched",
        "Past outcomes do not guarantee future results",
    ]
    if len(rs) < 30:
        caveats.insert(0, f"Only {len(rs)} resolved outcomes: do not generalise")
    if is_demo:
        caveats.append("DEMO data: synthetic history")
    q = {}
    if rs:
        for name, p in (("p10", 10), ("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90)):
            q[name] = round(float(np.percentile(rs, p)), 3)
    ts = sorted(r.timestamp for r in recs)
    return ConditionsSummary(
        sample_size=len(rs),
        sample_label=sample_label(len(rs)),
        outcomes=outcomes,
        average_r=round(float(np.mean(rs)), 3) if rs else None,
        median_r=round(float(np.median(rs)), 3) if rs else None,
        r_quantiles=q,
        regimes=regimes,
        directions=directions,
        first=ts[0] if ts else None,
        last=ts[-1] if ts else None,
        caveats=caveats,
    )


def nan_to_none(x: float | None) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else x

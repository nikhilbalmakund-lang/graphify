"""Deterministic signal engine: LONG / SHORT / NO_TRADE.

evaluate() scores both directions, picks the stronger, builds an objective
entry/stop/target plan and runs every filter. finalize() adds historical
evidence. NO_TRADE is a normal, frequent outcome.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from market_data.models import Timeframe
from quant.features.feature_set import FEATURE_VERSION
from quant.scoring.scorer import score_direction
from quant.signals.filters import evidence_filter, run_filters
from quant.signals.levels import build_levels
from quant.signals.models import (
    SIGNAL_ENGINE_VERSION,
    Direction,
    HistoricalEvidence,
    SignalCandidate,
    SignalConfig,
    SignalContext,
)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


class SignalEngine:
    version = SIGNAL_ENGINE_VERSION

    def __init__(self, config: SignalConfig | None = None):
        self.config = config or SignalConfig()

    def evaluate(self, ctx: SignalContext) -> SignalCandidate:
        cfg = self.config
        long_score, long_comps, long_adj = score_direction(ctx, 1, cfg.weights)
        short_score, short_comps, short_adj = score_direction(ctx, -1, cfg.weights)
        d = 1 if long_score >= short_score else -1
        best, comps, adj = (
            (long_score, long_comps, long_adj) if d > 0 else (short_score, short_comps, short_adj)
        )
        proposed = Direction.LONG if d > 0 else Direction.SHORT

        levels, level_reason = build_levels(ctx, d, cfg)
        filters = run_filters(ctx, d, levels, cfg)

        reasons: list[str] = []
        if best < cfg.min_score:
            reasons.append(f"Signal score {best:.1f}/100 is below the minimum of {cfg.min_score:.1f}")
        if abs(long_score - short_score) < cfg.min_score_margin:
            reasons.append(f"Long and short cases too similar ({long_score:.0f} vs {short_score:.0f})")
        if levels is None:
            reasons.append(level_reason)
        for fr in filters:
            if fr.blocking and not fr.passed:
                reasons.append(f"{fr.name.replace('_', ' ').capitalize()}: {fr.detail}")
        ens = ctx.ensemble or {}
        if (
            ens.get("net_direction") in ("LONG", "SHORT")
            and ens.get("net_direction") != proposed.value
            and ens.get("agreement", 0) >= 0.5
        ):
            reasons.append(
                f"Strategy ensemble leans {ens['net_direction']} (agreement {ens['agreement']:.0%})"
            )

        pros = _dedupe([n for c in comps for n in c.notes_for])
        cons = _dedupe([n for c in comps for n in c.notes_against])
        if ens.get("conflict"):
            cons.append("Strategy ensemble has conflicting votes")
        if ens.get("supporting"):
            pros.append("Strategies agreeing: " + ", ".join(ens["supporting"]))

        tf = Timeframe.parse(ctx.timeframe)
        ts = datetime.fromisoformat(ctx.timestamp)
        expires = ts + timedelta(seconds=tf.seconds * cfg.expiry_bars)
        return SignalCandidate(
            symbol=ctx.symbol,
            timeframe=ctx.timeframe,
            timestamp=ctx.timestamp,
            price=ctx.price,
            direction=Direction.NO_TRADE if reasons else proposed,
            proposed_direction=proposed,
            score=best,
            score_long=long_score,
            score_short=short_score,
            components=comps,
            mtf_adjustment=adj,
            levels=levels,
            regime=ctx.regime.regime.value,
            regime_clarity=ctx.regime.clarity,
            supporting_factors=pros,
            opposing_factors=cons,
            filters=filters,
            no_trade_reasons=reasons,
            expiry_bars=cfg.expiry_bars,
            expires_at=expires.isoformat(),
            is_demo=ctx.is_demo,
            provider=ctx.provider,
            signal_engine_version=SIGNAL_ENGINE_VERSION,
            feature_version=FEATURE_VERSION,
        )

    def finalize(self, cand: SignalCandidate, evidence: HistoricalEvidence | None) -> SignalCandidate:
        cand = cand.model_copy(deep=True)
        fr = evidence_filter(evidence, self.config)
        cand.filters = [f for f in cand.filters if f.name != "historical_evidence"] + [fr]
        cand.evidence = evidence
        if evidence is not None and evidence.sample_size > 0:
            note = (
                f"{evidence.sample_size} similar historical setups ({evidence.sample_label.lower()} sample)"
                + (" [DEMO data]" if evidence.is_demo else "")
            )
            if (
                evidence.expectancy is not None
                and evidence.expectancy > 0
                and evidence.sample_label in ("MODERATE", "LARGE")
            ):
                cand.supporting_factors.append(note + f": expectancy {evidence.expectancy:+.2f}R")
            elif evidence.expectancy is not None and evidence.expectancy < 0:
                cand.opposing_factors.append(note + f": expectancy {evidence.expectancy:+.2f}R")
            if evidence.sample_label in ("INSUFFICIENT", "SMALL"):
                cand.opposing_factors.append(
                    f"Historical sample is small (n={evidence.sample_size}); statistics are unreliable"
                )
        if fr.blocking and not fr.passed:
            cand.no_trade_reasons.append(f"Historical evidence: {fr.detail}")
            cand.direction = Direction.NO_TRADE
        return cand

"""Signal filters. Any failing *blocking* filter turns the signal into NO_TRADE.

A high score alone never produces a signal.
"""

from __future__ import annotations

from market_data.models import Timeframe
from quant.signals.models import FilterResult, HistoricalEvidence, LevelPlan, SignalConfig, SignalContext


def run_filters(
    ctx: SignalContext, d: int, levels: LevelPlan | None, cfg: SignalConfig
) -> list[FilterResult]:
    out: list[FilterResult] = []
    f = ctx.features
    dq = ctx.data_quality

    out.append(
        FilterResult(
            name="data_quality",
            passed=dq.usable and dq.quality_score >= cfg.min_data_quality,
            detail=("Data quality OK" if dq.usable else f"Unusable data: {', '.join(dq.critical_codes)}")
            + f" (score {dq.quality_score:.2f})",
            value=dq.quality_score,
            threshold=cfg.min_data_quality,
        )
    )
    out.append(
        FilterResult(
            name="stale_data",
            passed=not dq.is_stale,
            detail="Data is current"
            if not dq.is_stale
            else f"Last bar is {dq.last_bar_age_seconds:.0f}s old",
            value=dq.last_bar_age_seconds,
        )
    )
    if cfg.require_market_open:
        out.append(
            FilterResult(
                name="market_hours",
                passed=ctx.market_open,
                detail="Market open" if ctx.market_open else "Market closed",
            )
        )

    if levels is not None:
        out.append(
            FilterResult(
                name="min_risk_reward",
                passed=levels.effective_rr >= cfg.min_rr,
                detail=f"Planned R:R {levels.effective_rr:.2f} (exit-plan weighted)",
                value=levels.effective_rr,
                threshold=cfg.min_rr,
            )
        )
        out.append(
            FilterResult(
                name="max_stop_distance",
                passed=levels.risk_atr <= cfg.max_stop_atr,
                detail=f"Stop distance {levels.risk_atr:.2f} ATR",
                value=levels.risk_atr,
                threshold=cfg.max_stop_atr,
            )
        )
    else:
        out.append(FilterResult(name="levels", passed=False, detail="No objective entry/stop/target plan"))

    atr = f.atr14 or 0.0
    spread = max(ctx.ask - ctx.bid, 0.0)
    if atr > 0:
        ratio = spread / atr
        note = " (estimated spread)" if ctx.spread_is_estimate else ""
        out.append(
            FilterResult(
                name="max_spread",
                passed=ratio <= cfg.max_spread_atr,
                detail=f"Spread {ratio:.3f} ATR{note}",
                value=round(ratio, 4),
                threshold=cfg.max_spread_atr,
            )
        )

    vp = f.vol_percentile
    out.append(
        FilterResult(
            name="max_volatility",
            passed=vp is None or vp <= cfg.max_vol_percentile,
            detail="Volatility percentile unavailable" if vp is None else f"Volatility {vp:.0f}th percentile",
            value=vp,
            threshold=cfg.max_vol_percentile,
            blocking=vp is not None,
        )
    )

    ev = ctx.events
    if ev.available:
        blocked = False
        detail = "No high-impact event in the blackout window"
        if (
            ev.next_high_impact_minutes is not None
            and 0 <= ev.next_high_impact_minutes <= cfg.news_blackout_before_min
        ):
            blocked = True
            detail = f"{ev.next_high_impact_event} in {int(ev.next_high_impact_minutes)} min"
        if (
            ev.recent_high_impact_minutes is not None
            and 0 <= ev.recent_high_impact_minutes <= cfg.news_blackout_after_min
        ):
            blocked = True
            detail = f"High-impact event released {int(ev.recent_high_impact_minutes)} min ago"
        out.append(
            FilterResult(
                name="news_risk",
                passed=not blocked,
                detail=detail + (" [DEMO calendar]" if ev.is_demo else ""),
            )
        )
    else:
        out.append(
            FilterResult(
                name="news_risk",
                passed=True,
                blocking=False,
                detail="Economic calendar unavailable: news risk not assessed",
            )
        )

    if cfg.block_on_mtf_contradiction:
        _, contradiction, _, cons = ctx.mtf.adjustment_for(d, Timeframe.parse(ctx.timeframe))
        out.append(
            FilterResult(
                name="mtf_contradiction",
                passed=not contradiction,
                detail="Higher timeframes do not contradict"
                if not contradiction
                else "Higher timeframes oppose: " + ", ".join(cons),
            )
        )
    return out


def evidence_filter(evidence: HistoricalEvidence | None, cfg: SignalConfig) -> FilterResult:
    if cfg.min_historical_samples <= 0:
        return FilterResult(
            name="historical_evidence",
            passed=True,
            blocking=False,
            detail="Historical evidence filter disabled",
        )
    if evidence is None:
        return FilterResult(
            name="historical_evidence",
            passed=False,
            detail="Historical setup memory unavailable",
            value=0,
            threshold=cfg.min_historical_samples,
        )
    if evidence.sample_size < cfg.min_historical_samples:
        return FilterResult(
            name="historical_evidence",
            passed=False,
            detail=f"Only {evidence.sample_size} similar historical setups (minimum {cfg.min_historical_samples})",
            value=evidence.sample_size,
            threshold=cfg.min_historical_samples,
        )
    if cfg.min_historical_expectancy is not None and (
        evidence.expectancy is None or evidence.expectancy < cfg.min_historical_expectancy
    ):
        return FilterResult(
            name="historical_evidence",
            passed=False,
            detail=f"Historical expectancy {evidence.expectancy}R below {cfg.min_historical_expectancy}R",
            value=evidence.expectancy,
            threshold=cfg.min_historical_expectancy,
        )
    return FilterResult(
        name="historical_evidence",
        passed=True,
        detail=f"{evidence.sample_size} similar setups ({evidence.sample_label.lower()} sample)",
        value=evidence.sample_size,
        threshold=cfg.min_historical_samples,
    )

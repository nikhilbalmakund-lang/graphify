"""The signal pipeline and signal lifecycle tracking.

MARKET DATA -> DATA VALIDATION -> QUANT ANALYSIS -> MARKET REGIME -> SIGNAL ENGINE
-> CLAUDE + GEMINI -> DISAGREEMENT ANALYSIS -> AI CRITIC -> HISTORICAL MATCHING
-> RISK ENGINE -> FINAL SIGNAL

The deterministic engine decides; AI can only downgrade a candidate to
NO_TRADE; the risk engine has the final veto.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from ai.orchestration.analysts import AIReview, AIReviewOrchestrator
from app.core.cache import CacheBackend
from app.core.database import Database, utcnow
from app.core.errors import NexusError
from app.core.logging import signal_id_var
from app.models import (
    AICall,
    ModelVersion,
    Signal,
    SignalAIAnalysis,
    SignalFeature,
    SignalOutcome,
    StrategyRegimeStat,
)
from app.services.audit_service import AI_ERROR, SIGNAL_GENERATED, SIGNAL_REJECTED, AuditService
from app.services.content_service import ContentService
from app.services.market_service import MarketService
from app.services.memory_service import MemoryService
from app.services.trading_service import JournalService, PaperService
from app.websocket.manager import ConnectionManager
from backtesting.strategies.base import BarView, SeriesData
from backtesting.strategies.ensemble import StrategyPerf, run_ensemble
from backtesting.strategies.library import REGISTRY, create
from market_data.models import Timeframe
from quant.features.feature_set import FEATURE_VERSION, similarity_vector
from quant.signals.context import HIGHER_TIMEFRAMES, build_context
from quant.signals.engine import SignalEngine
from quant.signals.models import SIGNAL_ENGINE_VERSION, Direction, SignalCandidate
from quant.signals.outcome_sim import simulate_plan
from risk.engine import RISK_ENGINE_VERSION

logger = logging.getLogger("nexus.signals")
TRACKABLE = ("ACTIVE", "TRIGGERED", "TP1_HIT", "TP2_HIT")
RESOLVED_STATUS = {"WIN": "TARGET_HIT", "LOSS": "STOPPED", "BREAKEVEN": "BREAKEVEN"}


def _round(x: Any, n: int = 6) -> Any:
    return round(x, n) if isinstance(x, float) else x


class SignalService:
    def __init__(
        self,
        db: Database,
        market: MarketService,
        content: ContentService,
        memory: MemoryService,
        paper: PaperService,
        journal: JournalService,
        audit: AuditService,
        ws: ConnectionManager,
        settings: Any,
        cache: CacheBackend,
        ai_orchestrator: Any,
        ai_configured: Any,
    ):
        self.db = db
        self.market = market
        self.content = content
        self.memory = memory
        self.paper = paper
        self.journal = journal
        self.audit = audit
        self.ws = ws
        self.settings = settings
        self.cache = cache
        self.ai_orchestrator = ai_orchestrator  # callable -> AIReviewOrchestrator
        self.ai_configured = ai_configured  # callable -> bool
        self.strategies = [create(n) for n in REGISTRY]

    def engine(self) -> SignalEngine:
        return SignalEngine(self.settings.get("signals").to_config())

    # ------------------------------------------------------------ pipeline
    async def generate(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        use_ai: bool | None = None,
        source: str = "manual",
        force: bool = False,
    ) -> dict[str, Any]:
        spec = self.market.spec(symbol)
        bundle, series, report = await self.market.bundle(spec.symbol, timeframe)
        if len(bundle.df) < 260:
            raise NexusError(
                "INSUFFICIENT_DATA",
                f"Need at least 260 closed {timeframe.value} bars for {spec.symbol}; have {len(bundle.df)}",
            )
        bar_time = bundle.df.index[-1].to_pydatetime()
        if not force:
            existing = await self._existing(spec.symbol, timeframe.value, bar_time)
            if existing is not None and (use_ai is not True or existing.ai_summary):
                return await self.detail(existing.id)
            if source == "scanner":
                # Automated scans never stack a new setup on top of one that is still open.
                open_sig = await self._open_signal(spec.symbol, timeframe.value)
                if open_sig is not None:
                    return await self.detail(open_sig.id)

        engine = self.engine()
        cfg = engine.config
        quote = await self.market.quote(spec.symbol)
        mtf = await self.market.mtf(spec.symbol, timeframe)
        macro = await self.market.macro_context(spec.symbol)
        sentiment = await self.content.sentiment(spec.symbol)
        events = await self.content.event_risk(spec.symbol)
        perf = await self._strategy_perf()
        higher = HIGHER_TIMEFRAMES[timeframe][0] if HIGHER_TIMEFRAMES[timeframe] else None
        htf_view = mtf.view(higher) if higher else None
        sd = SeriesData.from_precomputed(
            bundle.df,
            timeframe,
            bundle.frame,
            bundle.states,
            bundle.regimes,
            bundle.volume_available,
            htf_view.trend_score if htf_view and htf_view.available else None,
        )
        ensemble = run_ensemble(self.strategies, BarView(sd, len(sd) - 1), perf)
        ctx = build_context(
            symbol=spec.symbol,
            spec=spec,
            bundle=bundle,
            t=-1,
            mtf=mtf,
            data_quality=report,
            bid=quote.bid,
            ask=quote.ask,
            market_open=quote.market_open,
            is_demo=series.is_demo,
            provider=series.provider,
            spread_is_estimate=quote.spread_is_estimate,
            macro=macro,
            sentiment=sentiment,
            events=events,
            ensemble=ensemble.as_context(),
        )
        cand = engine.evaluate(ctx)
        vector = similarity_vector(ctx.features)
        evidence = await self.memory.lookup(
            spec.symbol, timeframe.value, cand.proposed_direction.value, vector, cand.regime, series.is_demo
        )
        cand = engine.finalize(cand, evidence)
        prob = None
        if cand.levels is not None:
            prob = self.memory.probability(
                vector,
                cand.proposed_direction.value,
                cand.score,
                cand.levels.effective_rr,
                cand.regime,
                spec.asset_class.value,
                series.is_demo,
            )

        status = "ACTIVE" if cand.direction != Direction.NO_TRADE else "NO_TRADE"
        quant_direction = cand.direction.value
        signal_id = f"sig_{uuid.uuid4().hex[:16]}"
        signal_id_var.set(signal_id)
        review: AIReview | None = None
        ai_note: str | None = None
        want_ai = (
            use_ai
            if use_ai is not None
            else (self.settings.get("ai").enabled_in_pipeline and cand.direction != Direction.NO_TRADE)
        )
        if want_ai and self.ai_configured():
            if await self._ai_budget_left():
                payload = await self._ai_payload(ctx, cand, evidence, spec.symbol)
                review = await self._review(payload, quant_direction, cfg.min_rr)
                if review.downgrade_to_no_trade and cand.direction != Direction.NO_TRADE:
                    cand.direction = Direction.NO_TRADE
                    cand.no_trade_reasons += [f"AI review: {r}" for r in review.reasons]
                    status = "AI_REJECTED"
            else:
                ai_note = "AI daily call budget reached; AI review skipped"
        elif want_ai:
            ai_note = "AI review unavailable: no AI provider configured"

        risk_decision = None
        if cand.direction != Direction.NO_TRADE and cand.levels is not None:
            risk_decision = await self.paper.risk_check(
                spec.symbol,
                cand.direction.sign,
                cand.levels.entry_price,
                cand.levels.stop,
                effective_rr=cand.levels.effective_rr,
                requested_lots=None,
                source="signal",
                signal_id=signal_id,
            )
            if not risk_decision.approved:
                cand.direction = Direction.NO_TRADE
                cand.no_trade_reasons += [f"Risk engine: {r}" for r in risk_decision.reasons]
                status = "RISK_REJECTED"

        row = await self._persist(
            signal_id,
            status,
            cand,
            ctx,
            report,
            evidence,
            ensemble,
            review,
            risk_decision,
            prob,
            source,
            bar_time,
            series.is_demo,
            series.provider,
            ai_note,
        )
        await self._after_create(row, cand, review, status)
        return await self.detail(row.id)

    async def _existing(self, symbol: str, timeframe: str, bar_time: datetime) -> Signal | None:
        async with self.db.session() as s:
            return await s.scalar(
                select(Signal)
                .where(Signal.symbol == symbol, Signal.timeframe == timeframe, Signal.bar_time == bar_time)
                .order_by(Signal.created_at.desc())
                .limit(1)
            )

    async def _open_signal(self, symbol: str, timeframe: str) -> Signal | None:
        """Latest still-open (not yet resolved) signal for this instrument and timeframe."""
        async with self.db.session() as s:
            return await s.scalar(
                select(Signal)
                .where(Signal.symbol == symbol, Signal.timeframe == timeframe, Signal.status.in_(TRACKABLE))
                .order_by(Signal.created_at.desc())
                .limit(1)
            )

    async def _strategy_perf(self) -> dict[tuple[str, str], StrategyPerf]:
        is_demo = self.market.market.is_demo
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(StrategyRegimeStat).where(
                        StrategyRegimeStat.is_demo == is_demo, StrategyRegimeStat.source == "BACKTEST"
                    )
                )
            ).scalars()
            return {
                (r.strategy, r.regime): StrategyPerf(
                    trades=r.trades, expectancy_r=(r.sum_r / r.trades) if r.trades else None
                )
                for r in rows
            }

    async def _ai_budget_left(self) -> bool:
        limit = self.settings.get("ai").max_calls_per_day
        start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        async with self.db.session() as s:
            used = await s.scalar(
                select(func.count())
                .select_from(AICall)
                .where(AICall.created_at >= start, AICall.cached.is_(False))
            )
        return (used or 0) < limit

    async def _ai_payload(
        self, ctx: Any, cand: SignalCandidate, evidence: Any, symbol: str
    ) -> dict[str, Any]:
        f = ctx.features
        feats = {
            k: _round(getattr(f, k))
            for k in (
                "close",
                "ema20",
                "ema50",
                "ema200",
                "rsi14",
                "macd_hist",
                "atr14",
                "atr_pct",
                "adx",
                "bb_upper",
                "bb_lower",
                "vwap",
                "dist_vwap_pct",
                "volume_ratio",
                "vol_percentile",
                "trend_score",
                "momentum_score",
                "stoch_k",
                "cci20",
            )
        }
        st = ctx.structure
        news = [
            {
                "headline": n.headline,
                "source": n.source,
                "sentiment": n.sentiment,
                "published_at": n.published_at.isoformat(),
                "is_demo": n.is_demo,
            }
            for n in (await self.content.list_news(symbol, 5))
        ]
        upcoming = self.content.events_payload(await self.content.list_events(hours_back=2, hours_ahead=48))
        spec = self.market.spec(symbol)
        upcoming = [e for e in upcoming if e["currency"] in spec.currencies][:6]
        return {
            "symbol": symbol,
            "timeframe": ctx.timeframe,
            "timestamp": ctx.timestamp,
            "price": ctx.price,
            "is_demo": ctx.is_demo,
            "data_mode": "DEMO" if ctx.is_demo else "LIVE",
            "note": "signal score is a rules-based quality score (0-100), not a probability",
            "multi_timeframe": [
                {
                    k: getattr(v, k)
                    for k in (
                        "timeframe",
                        "trend",
                        "trend_score",
                        "momentum_score",
                        "structure_trend",
                        "regime",
                        "vwap_relation",
                        "atr_pct",
                        "rsi14",
                    )
                }
                for v in ctx.mtf.views
                if v.available
            ],
            "structure": {
                "trend": st.trend,
                "recent_labels": st.recent_labels,
                "last_event": st.last_event.model_dump() if st.last_event else None,
                "last_swing_high": st.last_swing_high.model_dump() if st.last_swing_high else None,
                "last_swing_low": st.last_swing_low.model_dump() if st.last_swing_low else None,
                "supports": [{"price": lv.price, "touches": lv.touches} for lv in st.supports[:3]],
                "resistances": [{"price": lv.price, "touches": lv.touches} for lv in st.resistances[:3]],
                "range": st.range.model_dump(),
                "breakout": st.breakout.model_dump() if st.breakout else None,
                "liquidity_sweep_heuristic": st.sweep.model_dump() if st.sweep else None,
                "liquidity_zones_heuristic": [z.model_dump() for z in st.liquidity_zones[:4]],
            },
            "features": feats,
            "regime": ctx.regime.model_dump(mode="json"),
            "events": {**ctx.events.model_dump(), "upcoming": upcoming},
            "news": news,
            "sentiment": ctx.sentiment.model_dump(),
            "macro": ctx.macro.model_dump(),
            "quant": {
                "direction": cand.direction.value,
                "proposed_direction": cand.proposed_direction.value,
                "score": cand.score,
                "components": cand.component_points(),
                "mtf_adjustment": cand.mtf_adjustment,
                "levels": cand.levels.model_dump(mode="json") if cand.levels else None,
                "failed_filters": [fr.model_dump() for fr in cand.filters if not fr.passed],
                "supporting": cand.supporting_factors,
                "opposing": cand.opposing_factors,
            },
            "historical_evidence": evidence.model_dump() if evidence else None,
            "data_quality": {
                "usable": ctx.data_quality.usable,
                "quality_score": ctx.data_quality.quality_score,
                "issues": [i.code for i in ctx.data_quality.issues],
            },
        }

    async def _review(self, payload: dict[str, Any], quant_direction: str, min_rr: float) -> AIReview:
        orch: AIReviewOrchestrator = self.ai_orchestrator()
        key = (
            "ai_review:"
            + hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        )
        ttl = self.settings.get("ai").cache_minutes * 60
        if ttl:
            hit = await self.cache.get(key)
            if hit:
                review = AIReview.model_validate(hit)
                await self._log_usage(review, None, cached=True)
                return review
        review = await orch.review(payload, quant_direction, min_rr)
        if ttl:
            await self.cache.set(key, review.model_dump(mode="json"), ttl)
        return review

    async def _log_usage(self, review: AIReview, signal_id: str | None, cached: bool = False) -> None:
        async with self.db.session() as s:
            for u in review.usages():
                s.add(
                    AICall(
                        created_at=utcnow(),
                        provider=u.provider,
                        model=u.model,
                        task=u.task,
                        prompt_name=u.prompt_name,
                        prompt_version=u.prompt_version,
                        input_tokens=None if cached else u.input_tokens,
                        output_tokens=None if cached else u.output_tokens,
                        cost_usd=0.0 if cached else u.cost_usd,
                        latency_ms=None if cached else u.latency_ms,
                        success=True,
                        cached=cached,
                        signal_id=signal_id,
                    )
                )
            for o in (review.claude, review.gemini):
                if o.status in ("ERROR", "INVALID_OUTPUT"):
                    s.add(
                        AICall(
                            created_at=utcnow(),
                            provider=o.provider,
                            model=o.model or "unknown",
                            task="signal_analysis",
                            prompt_name="signal_analysis",
                            success=False,
                            error_code=o.error_code,
                            cached=cached,
                            signal_id=signal_id,
                        )
                    )

    async def _persist(
        self,
        signal_id: str,
        status: str,
        cand: SignalCandidate,
        ctx: Any,
        report: Any,
        evidence: Any,
        ensemble: Any,
        review: AIReview | None,
        risk: Any,
        prob: float | None,
        source: str,
        bar_time: datetime,
        is_demo: bool,
        provider: str,
        ai_note: str | None,
    ) -> Signal:
        lv = cand.levels
        ai_summary = None
        prompt_versions: dict[str, str] = {}
        model_versions: dict[str, str] = {}
        if review is not None:
            ai_summary = {
                "agreement": review.consensus.agreement.value,
                "directions": review.consensus.directions,
                "critic": review.critic.verdict.value if review.critic.verdict else None,
                "critic_reasons": review.critic.reasons[:8],
                "downgraded": review.downgrade_to_no_trade,
                "reasons": review.reasons,
                "notes": review.consensus.notes,
                "claude_status": review.claude.status,
                "gemini_status": review.gemini.status,
            }
            for o in (review.claude, review.gemini):
                if o.prompt:
                    prompt_versions[o.provider] = (
                        f"{o.prompt.get('prompt_name')}@{o.prompt.get('prompt_version')}"
                    )
                if o.model:
                    model_versions[o.provider] = o.model
            if review.critic.ai_model:
                model_versions[f"critic:{review.critic.ai_provider}"] = review.critic.ai_model
        elif ai_note:
            ai_summary = {"agreement": "UNAVAILABLE", "note": ai_note}
        tf = Timeframe.parse(cand.timeframe)
        row = Signal(
            id=signal_id,
            symbol=cand.symbol,
            timeframe=cand.timeframe,
            created_at=utcnow(),
            updated_at=utcnow(),
            bar_time=bar_time,
            direction=cand.direction.value,
            proposed_direction=cand.proposed_direction.value,
            status=status,
            score=cand.score,
            score_long=cand.score_long,
            score_short=cand.score_short,
            regime=cand.regime,
            price=cand.price,
            entry_type=lv.entry_type.value if lv else None,
            entry_price=lv.entry_price if lv else None,
            entry_zone_low=lv.entry_zone_low if lv else None,
            entry_zone_high=lv.entry_zone_high if lv else None,
            stop=lv.stop if lv else None,
            invalidation_level=lv.invalidation_level if lv else None,
            invalidation_text=lv.invalidation_text if lv else None,
            targets=[t.model_dump() for t in lv.targets] if lv else [],
            rr=lv.rr if lv else None,
            effective_rr=lv.effective_rr if lv else None,
            expires_at=bar_time + timedelta(seconds=tf.seconds * (cand.expiry_bars + 1)),
            expiry_bars=cand.expiry_bars,
            supporting=cand.supporting_factors,
            opposing=cand.opposing_factors,
            no_trade_reasons=cand.no_trade_reasons,
            filters=[f.model_dump() for f in cand.filters],
            components=[c.model_dump() for c in cand.components],
            mtf_adjustment=cand.mtf_adjustment,
            ensemble=ensemble.model_dump(mode="json"),
            evidence=evidence.model_dump() if evidence else None,
            ai_summary=ai_summary,
            risk_decision=risk.model_dump(mode="json") if risk is not None else None,
            calibrated_probability=prob,
            data_mode="DEMO" if is_demo else "LIVE",
            provider=provider,
            is_demo=is_demo,
            source=source,
            signal_engine_version=SIGNAL_ENGINE_VERSION,
            feature_version=FEATURE_VERSION,
            risk_engine_version=RISK_ENGINE_VERSION if risk is not None else None,
            strategy_versions={s.name: s.version for s in self.strategies},
            prompt_versions=prompt_versions,
            model_versions=model_versions,
        )
        async with self.db.session() as s:
            s.add(row)
            await s.flush()
            s.add(
                SignalFeature(
                    signal_id=signal_id,
                    feature_version=FEATURE_VERSION,
                    features=ctx.features.model_dump(),
                    vector=similarity_vector(ctx.features),
                    structure=ctx.structure.model_dump(mode="json"),
                    mtf=ctx.mtf.model_dump(mode="json"),
                    regime=ctx.regime.model_dump(mode="json"),
                    data_quality=report.model_dump(mode="json"),
                    context={
                        "macro": ctx.macro.model_dump(),
                        "sentiment": ctx.sentiment.model_dump(),
                        "events": ctx.events.model_dump(),
                    },
                )
            )
            s.add(
                SignalOutcome(
                    signal_id=signal_id,
                    status=status if status == "ACTIVE" else "NOT_TRACKED",
                    filled=False,
                    updated_at=utcnow(),
                )
            )
            if review is not None:
                for role, o in (("claude_analyst", review.claude), ("gemini_analyst", review.gemini)):
                    s.add(
                        SignalAIAnalysis(
                            signal_id=signal_id,
                            role=role,
                            provider=o.provider,
                            model=o.model,
                            prompt_name=o.prompt.get("prompt_name"),
                            prompt_version=o.prompt.get("prompt_version"),
                            prompt_date=o.prompt.get("prompt_date"),
                            settings=o.settings,
                            status=o.status,
                            output=o.analysis,
                            validation=o.validation.model_dump() if o.validation else None,
                            error=o.error,
                            input_tokens=o.usage.input_tokens if o.usage else None,
                            output_tokens=o.usage.output_tokens if o.usage else None,
                            cost_usd=o.usage.cost_usd if o.usage else None,
                            latency_ms=o.usage.latency_ms if o.usage else None,
                            created_at=utcnow(),
                        )
                    )
                c = review.critic
                s.add(
                    SignalAIAnalysis(
                        signal_id=signal_id,
                        role="critic",
                        provider=c.ai_provider or "deterministic",
                        model=c.ai_model,
                        prompt_name=c.prompt.get("prompt_name"),
                        prompt_version=c.prompt.get("prompt_version"),
                        prompt_date=c.prompt.get("prompt_date"),
                        settings={},
                        status=c.status,
                        output=c.model_dump(mode="json", exclude={"usage"}),
                        error=c.ai_error,
                        input_tokens=c.usage.input_tokens if c.usage else None,
                        output_tokens=c.usage.output_tokens if c.usage else None,
                        cost_usd=c.usage.cost_usd if c.usage else None,
                        created_at=utcnow(),
                    )
                )
                s.add(
                    SignalAIAnalysis(
                        signal_id=signal_id,
                        role="consensus",
                        provider="engine",
                        status="OK",
                        output=review.consensus.model_dump(mode="json"),
                        created_at=utcnow(),
                    )
                )
                for prov, model in model_versions.items():
                    await self._touch_model(
                        s, "AI", prov.split(":")[-1], model, prompt_versions.get(prov.split(":")[-1], "n/a")
                    )
        if review is not None:
            await self._log_usage(review, signal_id)
        return row

    @staticmethod
    async def _touch_model(s: Any, kind: str, provider: str, model: str, version: str) -> None:
        row = await s.scalar(
            select(ModelVersion).where(
                ModelVersion.kind == kind,
                ModelVersion.provider == provider,
                ModelVersion.model == model,
                ModelVersion.version == version,
            )
        )
        if row is None:
            s.add(
                ModelVersion(
                    kind=kind,
                    provider=provider,
                    model=model,
                    version=version,
                    config={},
                    first_used_at=utcnow(),
                    last_used_at=utcnow(),
                    uses=1,
                )
            )
        else:
            row.uses += 1
            row.last_used_at = utcnow()

    async def _after_create(
        self, row: Signal, cand: SignalCandidate, review: AIReview | None, status: str
    ) -> None:
        if status == "ACTIVE":
            await self.audit.record(
                SIGNAL_GENERATED,
                f"{row.direction} {row.symbol} {row.timeframe} score {row.score:.0f}",
                details={"score": row.score, "rr": row.effective_rr, "mode": row.data_mode},
                signal_id=row.id,
            )
            await self.journal.add(
                entry_type="SIGNAL",
                symbol=row.symbol,
                timeframe=row.timeframe,
                direction=row.direction,
                strategy="SignalEngine",
                regime=row.regime,
                signal_score=row.score,
                entry_time=row.created_at,
                entry_price=row.entry_price,
                stop=row.stop,
                result="OPEN",
                ai_reasoning=row.ai_summary,
                signal_id=row.id,
                is_demo=row.is_demo,
                tags=["SIGNAL"],
            )
            if self.settings.get("notifications").new_signal:
                await self.audit.notify(
                    "NEW_SIGNAL",
                    f"{row.direction} {row.symbol} ({row.timeframe}) - signal score {row.score:.0f}/100",
                    f"Entry {row.entry_price}, stop {row.stop}, planned R:R {row.effective_rr}"
                    + (" [DEMO]" if row.is_demo else ""),
                    symbol=row.symbol,
                    signal_id=row.id,
                    is_demo=row.is_demo,
                )
            if self.settings.get("paper").auto_execute_signals:
                try:
                    await self.paper.execute_signal(row)
                except NexusError as exc:
                    await self.audit.record(
                        SIGNAL_REJECTED,
                        f"Auto paper execution skipped: {exc.message}",
                        severity="WARNING",
                        signal_id=row.id,
                    )
        elif cand.proposed_direction != Direction.NO_TRADE and status in ("AI_REJECTED", "RISK_REJECTED"):
            await self.audit.record(
                SIGNAL_REJECTED,
                f"{row.symbol} {row.proposed_direction} rejected ({status})",
                severity="INFO",
                details={"reasons": row.no_trade_reasons[-5:]},
                signal_id=row.id,
            )
        if review is not None:
            for o in (review.claude, review.gemini):
                if o.status in ("ERROR", "INVALID_OUTPUT"):
                    await self.audit.record(
                        AI_ERROR,
                        f"{o.analyst}: {o.error}",
                        severity="WARNING",
                        details={"code": o.error_code},
                        signal_id=row.id,
                    )
        await self.ws.broadcast("signals", {"event": "NEW", "signal": self.summary(row)})

    # --------------------------------------------------------------- reads
    @staticmethod
    def summary(r: Signal) -> dict[str, Any]:
        return {
            "id": r.id,
            "symbol": r.symbol,
            "timeframe": r.timeframe,
            "created_at": r.created_at.isoformat(),
            "bar_time": r.bar_time.isoformat(),
            "direction": r.direction,
            "proposed_direction": r.proposed_direction,
            "status": r.status,
            "score": r.score,
            "score_long": r.score_long,
            "score_short": r.score_short,
            "regime": r.regime,
            "price": r.price,
            "entry_type": r.entry_type,
            "entry_price": r.entry_price,
            "entry_zone_low": r.entry_zone_low,
            "entry_zone_high": r.entry_zone_high,
            "stop": r.stop,
            "invalidation_level": r.invalidation_level,
            "invalidation_text": r.invalidation_text,
            "targets": r.targets,
            "rr": r.rr,
            "effective_rr": r.effective_rr,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "expiry_bars": r.expiry_bars,
            "supporting": r.supporting,
            "opposing": r.opposing,
            "no_trade_reasons": r.no_trade_reasons,
            "components": r.components,
            "mtf_adjustment": r.mtf_adjustment,
            "filters": r.filters,
            "evidence": r.evidence,
            "ai_summary": r.ai_summary,
            "risk_decision": r.risk_decision,
            "calibrated_probability": r.calibrated_probability,
            "ensemble": r.ensemble,
            "data_mode": r.data_mode,
            "provider": r.provider,
            "is_demo": r.is_demo,
            "source": r.source,
            "versions": {
                "signal_engine": r.signal_engine_version,
                "features": r.feature_version,
                "risk_engine": r.risk_engine_version,
                "strategies": r.strategy_versions,
                "prompts": r.prompt_versions,
                "models": r.model_versions,
            },
        }

    async def query(
        self,
        *,
        status: str | None = None,
        symbol: str | None = None,
        direction: str | None = None,
        active_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            q = select(Signal).order_by(Signal.created_at.desc()).limit(min(limit, 1000))
            if status:
                q = q.where(Signal.status == status)
            if active_only:
                q = q.where(Signal.status.in_(TRACKABLE))
            if symbol:
                q = q.where(Signal.symbol == symbol)
            if direction:
                q = q.where(Signal.direction == direction)
            rows = list((await s.execute(q)).scalars())
            outcomes = (
                {
                    o.signal_id: o
                    for o in (
                        await s.execute(
                            select(SignalOutcome).where(SignalOutcome.signal_id.in_([r.id for r in rows]))
                        )
                    ).scalars()
                }
                if rows
                else {}
            )
        out = []
        for r in rows:
            d = self.summary(r)
            o = outcomes.get(r.id)
            d["outcome"] = self._outcome(o)
            out.append(d)
        return out

    @staticmethod
    def _outcome(o: SignalOutcome | None) -> dict[str, Any] | None:
        if o is None:
            return None
        return {
            "status": o.status,
            "filled": o.filled,
            "fill_time": o.fill_time,
            "fill_price": o.fill_price,
            "exit_time": o.exit_time,
            "exit_reason": o.exit_reason,
            "r_multiple": o.r_multiple,
            "mfe_r": o.mfe_r,
            "mae_r": o.mae_r,
            "tp_hits": o.tp_hits,
            "resolved": o.resolved,
            "updated_at": o.updated_at.isoformat(),
        }

    async def detail(self, signal_id: str) -> dict[str, Any]:
        async with self.db.session() as s:
            r = await s.get(Signal, signal_id)
            if r is None:
                raise NexusError("NOT_FOUND", f"Signal {signal_id} not found")
            feat = await s.get(SignalFeature, signal_id)
            outcome = await s.get(SignalOutcome, signal_id)
            ai_rows = list(
                (
                    await s.execute(select(SignalAIAnalysis).where(SignalAIAnalysis.signal_id == signal_id))
                ).scalars()
            )
        d = self.summary(r)
        d["outcome"] = self._outcome(outcome)
        d["analysis"] = (
            {
                "features": feat.features,
                "structure": feat.structure,
                "mtf": feat.mtf,
                "regime": feat.regime,
                "data_quality": feat.data_quality,
                "context": feat.context,
            }
            if feat
            else None
        )
        d["ai_analyses"] = [
            {
                "role": a.role,
                "provider": a.provider,
                "model": a.model,
                "prompt_name": a.prompt_name,
                "prompt_version": a.prompt_version,
                "prompt_date": a.prompt_date,
                "settings": a.settings,
                "status": a.status,
                "output": a.output,
                "validation": a.validation,
                "error": a.error,
                "input_tokens": a.input_tokens,
                "output_tokens": a.output_tokens,
                "cost_usd": a.cost_usd,
                "latency_ms": a.latency_ms,
                "created_at": a.created_at.isoformat(),
            }
            for a in ai_rows
        ]
        return d

    async def get_row(self, signal_id: str) -> Signal:
        async with self.db.session() as s:
            r = await s.get(Signal, signal_id)
        if r is None:
            raise NexusError("NOT_FOUND", f"Signal {signal_id} not found")
        return r

    async def latest_scores(self) -> dict[str, float]:
        async with self.db.session() as s:
            sub = (
                select(Signal.symbol, func.max(Signal.created_at).label("m"))
                .group_by(Signal.symbol)
                .subquery()
            )
            rows = (
                await s.execute(
                    select(Signal).join(sub, (Signal.symbol == sub.c.symbol) & (Signal.created_at == sub.c.m))
                )
            ).scalars()
            return {r.symbol: r.score for r in rows}

    # ------------------------------------------------------------- tracker
    async def track(self) -> int:
        """Update active signals from the candles that followed them."""
        async with self.db.session() as s:
            rows = list((await s.execute(select(Signal).where(Signal.status.in_(TRACKABLE)))).scalars())
        changed = 0
        for sig in rows:
            try:
                changed += await self._track_one(sig)
            except NexusError:
                continue
            except Exception:
                logger.exception(
                    "signal_track_failed", extra={"event": "signal_track_failed", "signal_id": sig.id}
                )
        return changed

    async def _track_one(self, sig: Signal) -> int:
        tf = Timeframe.parse(sig.timeframe)
        series = await self.market.market.candles(sig.symbol, tf, 600)
        df = series.closed_bars()
        future = df[df.index > sig.bar_time]
        if future.empty:
            return 0
        d = 1 if sig.direction == "LONG" else -1
        zone = (
            (sig.entry_zone_low, sig.entry_zone_high)
            if sig.entry_zone_low is not None and sig.entry_zone_high is not None
            else None
        )
        spec = self.market.spec(sig.symbol)
        out = simulate_plan(
            future,
            d,
            sig.entry_type or "MARKET",
            sig.entry_price or sig.price,
            sig.stop or sig.price,
            [(t["label"], t["price"], t["allocation"]) for t in sig.targets],
            invalidation_level=sig.invalidation_level,
            zone=zone,
            expiry_bars=sig.expiry_bars,
            max_hold_bars=96,
            spread=spec.typical_spread,
        )
        if out.status == "PENDING":
            new_status = "ACTIVE"
        elif out.status == "ACTIVE":
            new_status = (
                "TP2_HIT" if "TP2" in out.tp_hits else "TP1_HIT" if "TP1" in out.tp_hits else "TRIGGERED"
            )
        elif out.status in RESOLVED_STATUS:
            new_status = RESOLVED_STATUS[out.status]
        else:
            new_status = out.status  # EXPIRED | INVALIDATED
        if new_status == sig.status:
            return 0
        async with self.db.session() as s:
            row = await s.get(Signal, sig.id)
            oc = await s.get(SignalOutcome, sig.id)
            if row is None:
                return 0
            row.status, row.updated_at = new_status, utcnow()
            if oc is None:
                oc = SignalOutcome(signal_id=sig.id, status=new_status)
                s.add(oc)
            oc.status, oc.filled, oc.fill_time, oc.fill_price = (
                new_status,
                out.filled,
                out.fill_time,
                out.fill_price,
            )
            oc.exit_time, oc.exit_reason, oc.r_multiple = out.exit_time, out.exit_reason, out.r_multiple
            oc.mfe_r, oc.mae_r, oc.tp_hits, oc.resolved, oc.updated_at = (
                out.mfe_r,
                out.mae_r,
                out.tp_hits,
                out.resolved,
                utcnow(),
            )
        notif = self.settings.get("notifications")
        titles = {
            "INVALIDATED": ("signal_invalidated", "Signal invalidated"),
            "EXPIRED": ("signal_invalidated", "Signal expired"),
            "STOPPED": ("stop_reached", "Stop reached"),
            "TARGET_HIT": ("target_reached", "Final target reached"),
            "TP1_HIT": ("target_reached", "TP1 reached"),
            "TP2_HIT": ("target_reached", "TP2 reached"),
            "BREAKEVEN": ("stop_reached", "Closed at breakeven"),
            "TRIGGERED": ("new_signal", "Entry triggered"),
        }
        if new_status in titles and getattr(notif, titles[new_status][0], True):
            await self.audit.notify(
                new_status,
                f"{sig.symbol} {sig.direction}: {titles[new_status][1]}",
                f"Signal {sig.id} ({sig.timeframe})"
                + (f", {out.r_multiple:+.2f}R" if out.r_multiple is not None else "")
                + (" [DEMO]" if sig.is_demo else ""),
                symbol=sig.symbol,
                signal_id=sig.id,
                is_demo=sig.is_demo,
            )
        if out.resolved:
            result = {"WIN": "WIN", "LOSS": "LOSS", "BREAKEVEN": "BREAKEVEN"}.get(out.status, out.status)
            await self.journal.update_by(
                signal_id=sig.id,
                result=result,
                r_multiple=out.r_multiple,
                mfe_r=out.mfe_r,
                mae_r=out.mae_r,
                exit_time=datetime.fromisoformat(out.exit_time) if out.exit_time else None,
            )
            if out.filled and out.r_multiple is not None:
                await self._remember(sig, out)
        await self.ws.broadcast("signals", {"event": "UPDATE", "id": sig.id, "status": new_status})
        return 1

    async def _remember(self, sig: Signal, out: Any) -> None:
        from quant.ml.memory import SetupOutcome, SetupRecord

        async with self.db.session() as s:
            feat = await s.get(SignalFeature, sig.id)
        if feat is None or not feat.vector:
            return
        spec = self.market.spec(sig.symbol)
        rec = SetupRecord(
            symbol=sig.symbol,
            timeframe=sig.timeframe,
            timestamp=sig.bar_time.isoformat(),
            direction=sig.direction,
            score=sig.score,
            regime=sig.regime,
            asset_class=spec.asset_class.value,
            vector=feat.vector,
            entry_type=sig.entry_type or "MARKET",
            entry=sig.entry_price or sig.price,
            stop=sig.stop or sig.price,
            effective_rr=sig.effective_rr or 0.0,
            outcome=SetupOutcome(
                status=out.status,
                r_multiple=out.r_multiple,
                exit_reason=out.exit_reason,
                bars_held=out.bars_held,
                mfe_r=out.mfe_r,
                mae_r=out.mae_r,
                tp1_before_sl=out.tp1_before_sl,
            ),
            is_demo=sig.is_demo,
            provider=sig.provider,
            source="LIVE_SIGNAL",
            feature_version=sig.feature_version,
            signal_engine_version=sig.signal_engine_version,
        )
        await self.memory.store([rec], signal_id=sig.id)

    async def scan_new_bars(self, symbols: list[str], timeframe: Timeframe) -> int:
        """Background job: evaluate each symbol once per newly closed bar."""
        created = 0
        for sym in symbols:
            try:
                bundle, _, _ = await self.market.bundle(sym, timeframe)
                bar_time = bundle.df.index[-1].to_pydatetime()
                if await self._existing(sym, timeframe.value, bar_time) is not None:
                    continue
                # One open setup per instrument and timeframe: while a signal is still live
                # (ACTIVE / TRIGGERED / partially closed) the scanner does not stack another
                # overlapping one, which would double-count the same move in signal statistics.
                if await self._open_signal(sym, timeframe.value) is not None:
                    continue
                await self.generate(sym, timeframe, source="scanner")
                created += 1
            except NexusError:
                continue
            except Exception:
                logger.exception("scan_failed", extra={"event": "scan_failed", "data": {"symbol": sym}})
        return created

    async def counts(self) -> dict[str, int]:
        async with self.db.session() as s:
            rows = (await s.execute(select(Signal.status, func.count()).group_by(Signal.status))).all()
        return {a: b for a, b in rows}

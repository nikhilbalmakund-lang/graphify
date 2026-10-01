"""AI-facing application service: analyst chat tools, research, chart scanner, briefings, analytics."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select

from ai.orchestration.chat import AIChatAgent, ChatTurn
from ai.orchestration.services import AIChartAnalyzer, AIExplainer, AIResearcher, BriefingWriter
from ai.providers.base import AIProviderError, ImageInput
from app.core.database import utcnow
from app.core.errors import NexusError
from app.models import AICall, Briefing, SignalAIAnalysis
from app.services.ai_budget import budgeted_providers
from market_data.models import Timeframe
from market_data.providers.base import MarketDataError
from market_data.sessions import is_open
from quant.features.feature_set import similarity_vector
from quant.signals.scenarios import build_scenarios
from risk.engine import TradeProposal

SESSION_START = {
    "ASIA_OPEN": (0, 0),
    "PRE_MARKET": (5, 0),
    "LONDON_OPEN": (7, 0),
    "NEW_YORK_OPEN": (13, 30),
    "POST_MARKET": (21, 0),
}
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


def session_for(now: datetime) -> str:
    h = now.hour + now.minute / 60
    if h >= 21:
        return "POST_MARKET"
    if h >= 13.5:
        return "NEW_YORK_OPEN"
    if h >= 7:
        return "LONDON_OPEN"
    if h >= 5:
        return "PRE_MARKET"
    return "ASIA_OPEN"


class AIService:
    def __init__(self, c: Any):
        self.c = c

    # -------------------------------------------------------------- tools
    async def execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        c = self.c
        try:
            if name in (
                "get_market_data",
                "get_indicators",
                "get_structure",
                "get_historical_setups",
                "calculate_signal",
                "calculate_position_size",
            ):
                sym = c.catalog.resolve(str(args.get("symbol", "")))
                if sym is None:
                    return {"error": f"Unknown symbol {args.get('symbol')}", "summary": "Unknown symbol"}
                args = {**args, "symbol": sym}
            tf = Timeframe.parse(str(args.get("timeframe") or c.settings.get("markets").default_timeframe))
            demo = " [DEMO data]" if c.market.is_demo else ""
            if name == "get_market_data":
                q = await c.market_service.quote(args["symbol"])
                return {
                    "summary": f"Quote {q.symbol}",
                    "data": q.model_dump(mode="json"),
                    "calculations": [],
                    "facts": [
                        f"{q.symbol} price {q.price} (bid {q.bid} / ask {q.ask}), 24h change {q.change_pct_24h:+.2f}%, "
                        f"market {'open' if q.market_open else 'closed'}{demo}"
                    ],
                }
            if name == "get_indicators":
                b, _, rep = await c.market_service.bundle(args["symbol"], tf)
                f = b.features()
                return {
                    "summary": f"Indicators {args['symbol']} {tf.value}",
                    "data": f.model_dump(),
                    "facts": [
                        f"{args['symbol']} {tf.value}: close {f.close}, EMA20 {f.ema20:.6g}, EMA50 {f.ema50:.6g}, RSI {f.rsi14:.1f}, "
                        f"ADX {f.adx:.1f}, ATR {f.atr14:.6g} ({f.atr_pct:.2f}%), VWAP relation {f.vwap_relation}{demo}"
                    ],
                    "calculations": [
                        f"Trend score {f.trend_score:.0f}, momentum score {f.momentum_score:.0f}, volatility percentile "
                        f"{f.vol_percentile if f.vol_percentile is not None else 'n/a'}, data quality {rep.quality_score}"
                    ],
                }
            if name == "get_structure":
                b, _, _ = await c.market_service.bundle(args["symbol"], tf)
                st, reg = b.structure(), b.regime()
                mtf = await c.market_service.mtf(args["symbol"], tf)
                ev = st.last_event
                return {
                    "summary": f"Structure {args['symbol']} {tf.value}",
                    "data": {
                        "structure": st.model_dump(mode="json"),
                        "regime": reg.model_dump(mode="json"),
                        "mtf": mtf.model_dump(mode="json"),
                    },
                    "facts": [
                        f"{args['symbol']} {tf.value} structure {st.trend}; regime {reg.regime.value}; "
                        + (f"last {ev.type} {ev.direction} {ev.bars_ago} bars ago; " if ev else "")
                        + f"supports {[round(lv.price, 6) for lv in st.supports[:2]]}, resistances {[round(lv.price, 6) for lv in st.resistances[:2]]}{demo}",
                        f"Multi-timeframe: {mtf.summary}",
                    ],
                    "calculations": [
                        f"MTF alignment {mtf.alignment:+.2f} (-1 bearish .. +1 bullish); regime clarity {reg.clarity}"
                    ],
                }
            if name == "get_news":
                rows = await c.content.list_news(
                    c.catalog.resolve(str(args.get("symbol") or "")) if args.get("symbol") else None,
                    int(min(max(args.get("limit") or 5, 1), 20)),
                )
                return {
                    "summary": f"{len(rows)} news items",
                    "data": [
                        {
                            "headline": r.headline,
                            "source": r.source,
                            "url": r.url,
                            "sentiment": r.sentiment,
                            "published_at": r.published_at.isoformat(),
                            "is_demo": r.is_demo,
                        }
                        for r in rows
                    ],
                    "facts": [
                        f"{r.published_at:%Y-%m-%d %H:%M} {r.source}: {r.headline} (sentiment {r.sentiment or 'n/a'})"
                        for r in rows[:6]
                    ],
                    "calculations": [],
                }
            if name == "get_calendar":
                rows = await c.content.list_events(
                    hours_back=1,
                    hours_ahead=int(min(max(args.get("hours_ahead") or 24, 1), 168)),
                    currency=args.get("currency"),
                )
                ev = c.content.events_payload(rows)
                return {
                    "summary": f"{len(ev)} calendar events",
                    "data": ev,
                    "facts": [
                        f"{e['time'][:16]} {e['currency']} {e['event']} impact {e['impact']} (forecast {e['forecast']}, previous {e['previous']})"
                        for e in ev
                        if e["impact"] in ("HIGH", "MEDIUM")
                    ][:8],
                    "calculations": [],
                }
            if name == "get_historical_setups":
                b, series, _ = await c.market_service.bundle(args["symbol"], tf)
                f = b.features()
                vec = similarity_vector(f)
                if vec is None:
                    return {"error": "Insufficient history for similarity features", "summary": "Unavailable"}
                summary, _ = await c.memory.conditions(
                    args["symbol"],
                    tf.value,
                    vec,
                    b.regime().regime.value,
                    series.is_demo,
                    int(min(max(args.get("k") or 50, 10), 100)),
                )
                return {
                    "summary": f"{summary.sample_size} similar setups",
                    "data": summary.model_dump(),
                    "facts": [
                        f"{summary.sample_size} resolved similar setups ({summary.sample_label}); outcomes {summary.outcomes}"
                    ],
                    "calculations": [
                        f"Average R {summary.average_r}, median R {summary.median_r}, quantiles {summary.r_quantiles}",
                        *summary.caveats[:2],
                    ],
                }
            if name == "get_portfolio":
                acct = await c.paper.broker.get_account()
                pos = await c.paper.broker.get_positions()
                return {
                    "summary": "Paper portfolio (SIMULATED)",
                    "data": {"account": acct.model_dump(mode="json")},
                    "facts": [
                        f"SIMULATED paper account: equity {acct.equity:,.2f}, balance {acct.balance:,.2f}, open positions "
                        f"{len([p for p in pos if p.status.value == 'OPEN'])}",
                        *[
                            f"{p.symbol} {'LONG' if p.direction > 0 else 'SHORT'} {p.lots} @ {p.entry_price}, unrealised {p.unrealized_pnl:+.2f}"
                            for p in pos
                            if p.status.value == "OPEN"
                        ][:6],
                    ],
                    "calculations": [],
                }
            if name == "get_risk_status":
                st = await c.risk_status()
                return {
                    "summary": f"Risk state {st['state']}",
                    "data": st,
                    "facts": [
                        f"Risk engine state {st['state']}; kill switch {'ON' if st['kill_switch'] else 'off'}; open positions {st['open_positions']}"
                    ],
                    "calculations": [
                        f"Drawdown {st['drawdown']:.2%}, daily loss limit used {st['daily_loss_used']:.0%}, leverage {st['leverage']}x"
                    ],
                }
            if name == "calculate_signal":
                sig = await c.signals.generate(args["symbol"], tf, use_ai=False, source="ai_tool")
                lv = (
                    f"entry {sig['entry_price']}, stop {sig['stop']}, R:R {sig['effective_rr']}"
                    if sig["entry_price"]
                    else "no plan"
                )
                return {
                    "summary": f"Signal {sig['direction']}",
                    "data": {k: sig[k] for k in ("id", "direction", "status", "score", "regime")},
                    "facts": [
                        f"Deterministic engine: {sig['direction']} ({sig['status']}) on {args['symbol']} {tf.value}; {lv}"
                    ],
                    "calculations": [
                        f"Signal score {sig['score']}/100 (not a probability)",
                        *[f"NO_TRADE reason: {r}" for r in sig["no_trade_reasons"][:3]],
                    ],
                }
            if name == "calculate_position_size":
                spec = c.catalog.get(args["symbol"])
                d = 1 if str(args.get("direction")).upper() == "LONG" else -1
                entry, stop = float(args["entry"]), float(args["stop"])
                engine = c.risk_engine()
                q = await c.market_service.quote(spec.symbol)
                decision = engine.evaluate(
                    TradeProposal(
                        symbol=spec.symbol,
                        direction=d,
                        entry=entry,
                        stop=stop,
                        market_open=q.market_open,
                        spread=q.ask - q.bid,
                    ),
                    await c.paper.account_state(),
                    spec,
                    c.specs,
                )
                return {
                    "summary": "Position size (no order placed)",
                    "data": decision.model_dump(mode="json"),
                    "facts": [
                        f"Risk engine {'approves' if decision.approved else 'rejects'} the hypothetical trade"
                    ],
                    "calculations": [
                        f"Size {decision.lots} lots, risk {decision.risk_amount:,.2f} USD ({decision.risk_pct:.2%})",
                        *decision.reasons[:3],
                    ],
                }
            return {"error": f"Unknown tool {name}", "summary": "Unknown tool"}
        except (NexusError, MarketDataError) as exc:
            return {"error": exc.message, "summary": "Tool failed"}
        except (KeyError, ValueError, TypeError) as exc:
            return {"error": f"Invalid arguments: {type(exc).__name__}", "summary": "Tool failed"}

    async def chat(self, question: str, history: list[ChatTurn]) -> dict[str, Any]:
        c = self.c
        providers, budget_notes = await budgeted_providers(c)
        agent = AIChatAgent(
            providers,
            self.execute_tool,
            c.catalog.resolve,
            c.settings.get("markets").default_timeframe,
        )
        resp = await agent.ask(question, history)
        if resp.usage:
            async with c.db.session() as s:
                u = resp.usage
                s.add(
                    AICall(
                        created_at=utcnow(),
                        provider=u.provider,
                        model=u.model,
                        task="chat",
                        prompt_name=u.prompt_name,
                        prompt_version=u.prompt_version,
                        input_tokens=u.input_tokens,
                        output_tokens=u.output_tokens,
                        cost_usd=u.cost_usd,
                        latency_ms=u.latency_ms,
                        success=True,
                    )
                )
        out = {**resp.model_dump(mode="json"), "is_demo_data": c.market.is_demo}
        out["warnings"] = [*budget_notes, *out.get("warnings", [])]
        return out

    # ----------------------------------------------------------- research
    async def research(self, symbol: str, tf: Timeframe) -> dict[str, Any]:
        c = self.c
        spec = c.market_service.spec(symbol)
        b, series, rep = await c.market_service.bundle(spec.symbol, tf)
        f, st, reg = b.features(), b.structure(), b.regime()
        scen = build_scenarios(spec.symbol, tf.value, f, st, spec.price_precision)
        vec = similarity_vector(f)
        evidence = await c.memory.lookup(
            spec.symbol,
            tf.value,
            "LONG" if (f.trend_score or 0) >= 0 else "SHORT",
            vec,
            reg.regime.value,
            series.is_demo,
        )
        macro = await c.market_service.macro_context(spec.symbol)
        ev = await c.content.event_risk(spec.symbol)
        news = await c.content.list_news(spec.symbol, 5)
        payload = {
            "symbol": spec.symbol,
            "timeframe": tf.value,
            "price": f.close,
            "is_demo": series.is_demo,
            "features": {
                k: getattr(f, k)
                for k in (
                    "trend_score",
                    "momentum_score",
                    "rsi14",
                    "adx",
                    "atr14",
                    "atr_pct",
                    "vol_percentile",
                    "vwap",
                    "ema20",
                    "ema50",
                    "ema200",
                )
            },
            "structure": {
                "trend": st.trend,
                "supports": [lv.price for lv in st.supports[:3]],
                "resistances": [lv.price for lv in st.resistances[:3]],
                "last_event": st.last_event.model_dump() if st.last_event else None,
            },
            "regime": reg.model_dump(mode="json"),
            "macro": macro.model_dump(),
            "events": ev.model_dump(),
            "news": [
                {"headline": n.headline, "source": n.source, "sentiment": n.sentiment, "is_demo": n.is_demo}
                for n in news
            ],
            "historical_evidence": evidence.model_dump() if evidence else None,
            "scenarios": scen.model_dump(),
            "risks": [ev.detail] if ev.available else [],
            "data_quality": rep.quality_score,
        }
        try:
            providers, budget_notes = await budgeted_providers(c)
            res, errors = await AIResearcher(providers).research(payload)
            errors = [*budget_notes, *errors]
        except AIProviderError as exc:
            raise NexusError("AI_PROVIDER_UNAVAILABLE", exc.message) from exc
        await self._log(res)
        return {
            "symbol": spec.symbol,
            "timeframe": tf.value,
            "report": res.data,
            "provider": res.provider,
            "model": res.model,
            "is_ai": not res.is_demo,
            "is_demo_data": series.is_demo,
            "scenarios": scen.model_dump(),
            "inputs": {
                "evidence": payload["historical_evidence"],
                "macro": payload["macro"],
                "events": payload["events"],
            },
            "prompt": res.prompt,
            "warnings": errors,
            "generated_at": utcnow().isoformat(),
        }

    async def _log(self, res: Any) -> None:
        if res.is_demo:
            return
        async with self.c.db.session() as s:
            u = res.usage
            s.add(
                AICall(
                    created_at=utcnow(),
                    provider=u.provider,
                    model=u.model,
                    task=u.task,
                    prompt_name=u.prompt_name,
                    prompt_version=u.prompt_version,
                    input_tokens=u.input_tokens,
                    output_tokens=u.output_tokens,
                    cost_usd=u.cost_usd,
                    latency_ms=u.latency_ms,
                    success=True,
                )
            )

    # -------------------------------------------------------- chart scan
    async def chart_scan(self, content: bytes, mime: str, symbol: str | None) -> dict[str, Any]:
        c = self.c
        if mime not in ALLOWED_IMAGE_TYPES:
            raise NexusError("VALIDATION_ERROR", "Upload a PNG, JPEG or WEBP image")
        if len(content) > c.env.max_upload_mb * 1024 * 1024:
            raise NexusError("VALIDATION_ERROR", f"Image larger than {c.env.max_upload_mb} MB")
        try:
            with Image.open(io.BytesIO(content)) as img:
                img.verify()
            with Image.open(io.BytesIO(content)) as img:
                width, height = img.size
                if width * height > 40_000_000:
                    raise NexusError("VALIDATION_ERROR", "Image dimensions too large")
                clean = io.BytesIO()
                img.convert("RGB").save(
                    clean, format="PNG"
                )  # re-encode: strips metadata and malformed payloads
        except (UnidentifiedImageError, OSError) as exc:
            raise NexusError("VALIDATION_ERROR", "File is not a valid image") from exc
        context: dict[str, Any] = {
            "note": "Analyse the attached chart image only.",
            "requested_symbol": symbol,
        }
        market_snapshot = None
        sym = c.catalog.resolve(symbol) if symbol else None
        if sym:
            market_snapshot = await self._snapshot(sym)
        providers, budget_notes = await budgeted_providers(c)
        result, raw = await AIChartAnalyzer(providers).analyze(
            ImageInput(data=clean.getvalue(), mime_type="image/png"), context
        )
        if budget_notes:
            result.errors = [*budget_notes, *result.errors]
        if raw is not None:
            await self._log(raw)
            detected = (result.analysis or {}).get("asset_visible")
            dsym = c.catalog.resolve(detected) if detected else None
            if dsym and not market_snapshot:
                market_snapshot = await self._snapshot(dsym)
        return {
            **result.model_dump(mode="json"),
            "image": {"width": width, "height": height, "bytes": len(content)},
            "market_data": market_snapshot,
            "data_precedence": (
                "Actual market data shown below takes precedence over values read from the image."
                if market_snapshot
                else "No matching market data for comparison."
            ),
        }

    async def _snapshot(self, sym: str) -> dict[str, Any] | None:
        try:
            q = await self.c.market_service.quote(sym)
            b, _, _ = await self.c.market_service.bundle(sym, Timeframe.H1, 320)
            f, st = b.features(), b.structure()
            return {
                "symbol": sym,
                "price": q.price,
                "is_demo": q.is_demo,
                "provider": q.provider,
                "trend_1h": f.trend,
                "regime_1h": b.regime().regime.value,
                "supports": [lv.price for lv in st.supports[:3]],
                "resistances": [lv.price for lv in st.resistances[:3]],
            }
        except (NexusError, MarketDataError):
            return None

    # ----------------------------------------------------------- briefing
    def _session_data_ok(self, session: str, now: datetime) -> tuple[bool, str]:
        if session == "INTRADAY":
            return True, ""
        hh, mm = SESSION_START[session]
        start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if now < start:
            return (
                False,
                f"{session.replace('_', ' ').title()} has not started yet today ({hh:02d}:{mm:02d} UTC)",
            )
        fx_spec = self.c.catalog.get("EURUSD")
        if (
            not is_open(fx_spec.session, start + timedelta(minutes=1))[0]
            and not is_open(fx_spec.session, now)[0]
        ):
            return False, "Forex markets are closed: no session data exists for this briefing"
        return True, ""

    async def briefing(self, session: str | None = None, force: bool = False) -> dict[str, Any]:
        c = self.c
        now = c.market_service.now()
        session = session or session_for(now)
        if session not in SESSION_START and session != "INTRADAY":
            raise NexusError("VALIDATION_ERROR", f"Unknown session {session}")
        ok, why = self._session_data_ok(session, now)
        if not ok:
            raise NexusError("INSUFFICIENT_DATA", why)
        if not force:
            async with c.db.session() as s:
                recent = await s.scalar(
                    select(Briefing)
                    .where(
                        Briefing.session == session, Briefing.created_at >= utcnow() - timedelta(minutes=30)
                    )
                    .order_by(Briefing.created_at.desc())
                    .limit(1)
                )
            if recent is not None:
                return self._briefing_out(recent)
        symbols = c.settings.get("markets").default_assets
        cards = await c.market_service.overview(symbols, Timeframe.H1)
        latest = {s["symbol"]: s for s in await c.signals.query(limit=200)}
        assets = []
        for card in cards:
            if card.get("status") != "OK":
                continue
            sig = latest.get(card["symbol"])
            assets.append(
                {
                    "symbol": card["symbol"],
                    "price": card["price"],
                    "change_pct": card["change_pct_24h"],
                    "trend": card["trend"],
                    "trend_score": card["trend_score"],
                    "regime": card["regime"],
                    "vol_percentile": card["vol_percentile"],
                    "signal": sig["direction"] if sig else None,
                    "score": sig["score"] if sig else None,
                }
            )
        events = c.content.events_payload(await c.content.list_events(hours_back=0, hours_ahead=24))
        events = [
            {
                "event": e["event"],
                "currency": e["currency"],
                "impact": e["impact"],
                "time": e["time"][11:16] + " UTC",
            }
            for e in events
            if e["impact"] in ("HIGH", "MEDIUM")
        ][:8]
        news = [
            {"headline": n.headline, "source": n.source, "sentiment": n.sentiment}
            for n in await c.content.list_news(None, 8)
        ]
        payload = {
            "session": session,
            "as_of": now.isoformat(),
            "is_demo": c.market.is_demo,
            "assets": assets,
            "events": events,
            "news": news,
        }
        try:
            providers, budget_notes = await budgeted_providers(c)
            res, errors = await BriefingWriter(providers).write(payload)
            errors = [*budget_notes, *errors]
        except AIProviderError as exc:
            raise NexusError("AI_PROVIDER_UNAVAILABLE", exc.message) from exc
        await self._log(res)
        row = Briefing(
            id=f"brf_{uuid.uuid4().hex[:16]}",
            session=session,
            created_at=utcnow(),
            provider=res.provider,
            model=res.model,
            is_ai=not res.is_demo,
            is_demo_data=c.market.is_demo,
            content={**res.data, "warnings": errors},
            inputs=payload,
            prompt_version=res.prompt.get("prompt_version"),
        )
        async with c.db.session() as s:
            s.add(row)
        return self._briefing_out(row)

    @staticmethod
    def _briefing_out(r: Briefing) -> dict[str, Any]:
        return {
            "id": r.id,
            "session": r.session,
            "created_at": r.created_at.isoformat(),
            "provider": r.provider,
            "model": r.model,
            "is_ai": r.is_ai,
            "is_demo_data": r.is_demo_data,
            "content": r.content,
            "inputs": r.inputs,
            "prompt_version": r.prompt_version,
        }

    async def latest_briefing(self) -> dict[str, Any] | None:
        async with self.c.db.session() as s:
            r = await s.scalar(select(Briefing).order_by(Briefing.created_at.desc()).limit(1))
        return self._briefing_out(r) if r else None

    # ------------------------------------------------------------ queries
    async def history_query(self, symbol: str, tf: Timeframe, k: int) -> dict[str, Any]:
        c = self.c
        b, series, _ = await c.market_service.bundle(symbol, tf)
        f = b.features()
        vec = similarity_vector(f)
        if vec is None:
            raise NexusError("INSUFFICIENT_DATA", "Not enough history to compute similarity features")
        summary, rows = await c.memory.conditions(
            c.catalog.get(symbol).symbol, tf.value, vec, b.regime().regime.value, series.is_demo, k
        )
        return {
            "symbol": symbol,
            "timeframe": tf.value,
            "k": k,
            "current": {
                "regime": b.regime().regime.value,
                "trend_score": f.trend_score,
                "momentum_score": f.momentum_score,
                "rsi14": f.rsi14,
                "vol_percentile": f.vol_percentile,
            },
            "summary": summary.model_dump(),
            "matches": rows,
            "is_demo": series.is_demo,
        }

    async def explain(self, signal: dict[str, Any]) -> dict[str, Any]:
        slim = {
            k: signal.get(k)
            for k in (
                "symbol",
                "timeframe",
                "price",
                "direction",
                "status",
                "score",
                "regime",
                "levels",
                "supporting",
                "opposing",
                "no_trade_reasons",
                "components",
                "effective_rr",
            )
        }
        slim["levels"] = {
            "entry_price": signal.get("entry_price"),
            "stop": signal.get("stop"),
            "effective_rr": signal.get("effective_rr"),
        }
        slim["supporting_factors"], slim["opposing_factors"] = (
            signal.get("supporting"),
            signal.get("opposing"),
        )
        try:
            providers, budget_notes = await budgeted_providers(self.c)
            res, errors = await AIExplainer(providers).explain(slim)
            errors = [*budget_notes, *errors]
        except AIProviderError as exc:
            raise NexusError("AI_PROVIDER_UNAVAILABLE", exc.message) from exc
        await self._log(res)
        return {
            "explanation": res.data,
            "provider": res.provider,
            "model": res.model,
            "is_ai": not res.is_demo,
            "warnings": errors,
        }

    async def model_analytics(self) -> dict[str, Any]:
        async with self.c.db.session() as s:
            calls = (
                await s.execute(
                    select(
                        AICall.provider,
                        func.count(),
                        func.avg(AICall.latency_ms),
                        func.sum(AICall.cost_usd),
                        func.sum(AICall.input_tokens),
                        func.sum(AICall.output_tokens),
                    ).group_by(AICall.provider)
                )
            ).all()
            errors = dict(
                (
                    await s.execute(
                        select(AICall.provider, func.count())
                        .where(AICall.success.is_(False))
                        .group_by(AICall.provider)
                    )
                ).all()
            )
            cached = dict(
                (
                    await s.execute(
                        select(AICall.provider, func.count())
                        .where(AICall.cached.is_(True))
                        .group_by(AICall.provider)
                    )
                ).all()
            )
            consensus = list(
                (
                    await s.execute(select(SignalAIAnalysis).where(SignalAIAnalysis.role == "consensus"))
                ).scalars()
            )
            critics = list(
                (await s.execute(select(SignalAIAnalysis).where(SignalAIAnalysis.role == "critic"))).scalars()
            )
        providers = [
            {
                "provider": p,
                "calls": n,
                "errors": errors.get(p, 0),
                "cached": cached.get(p, 0),
                "avg_latency_ms": round(lat, 1) if lat else None,
                "cost_usd": round(cost, 4) if cost else None,
                "input_tokens": tin,
                "output_tokens": tout,
            }
            for p, n, lat, cost, tin, tout in calls
        ]
        levels: dict[str, int] = {}
        for row in consensus:
            lvl = (row.output or {}).get("agreement", "UNKNOWN")
            levels[lvl] = levels.get(lvl, 0) + 1
        compared = sum(v for k, v in levels.items() if k in ("HIGH", "MEDIUM", "LOW", "CONFLICT"))
        verdicts: dict[str, int] = {}
        for row in critics:
            v = (row.output or {}).get("verdict") or "skipped"
            verdicts[v] = verdicts.get(v, 0) + 1
        reviewed = sum(v for k, v in verdicts.items() if k != "skipped")
        return {
            "providers": providers,
            "agreement_levels": levels,
            "agreement_rate": round((levels.get("HIGH", 0) + levels.get("MEDIUM", 0)) / compared, 4)
            if compared
            else None,
            "disagreement_rate": round((levels.get("LOW", 0) + levels.get("CONFLICT", 0)) / compared, 4)
            if compared
            else None,
            "critic_verdicts": verdicts,
            "critic_rejection_rate": round(verdicts.get("rejected", 0) / reviewed, 4) if reviewed else None,
            "disclaimer": "Agreement between AI models does not demonstrate that their conclusions are correct.",
            "pricing_note": "Cost estimates use published Claude list prices; Gemini costs appear only if AI_PRICING_JSON is configured.",
        }

    @staticmethod
    def now() -> datetime:
        return datetime.now(UTC)

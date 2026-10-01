"""Alerts, global search, exports and performance analytics."""

from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, select

from app.core.database import utcnow
from app.core.errors import NexusError
from app.models import Alert, BacktestTrade, NewsItem, Signal, SignalOutcome, Strategy, TradeJournal
from market_data.models import Timeframe
from paper_trading.broker.base import PositionStatus
from paper_trading.portfolio.analytics import ClosedTrade, performance_report

logger = logging.getLogger("nexus.alerts")
AlertType = Literal[
    "PRICE_LEVEL",
    "SIGNAL_SCORE",
    "REGIME_CHANGE",
    "VOLATILITY_SPIKE",
    "BREAKOUT",
    "ECONOMIC_EVENT",
    "NEWS_SENTIMENT_SHIFT",
]


class AlertIn(BaseModel):
    type: AlertType
    symbol: str | None = None
    condition: dict[str, Any] = Field(default_factory=dict)
    note: str | None = Field(None, max_length=300)
    cooldown_minutes: int = Field(60, ge=1, le=10_080)

    @model_validator(mode="after")
    def _check(self) -> AlertIn:
        c = self.condition
        needs_symbol = self.type != "ECONOMIC_EVENT"
        if needs_symbol and not self.symbol:
            raise ValueError("symbol is required for this alert type")
        if self.type == "PRICE_LEVEL" and (
            c.get("direction") not in ("above", "below") or not isinstance(c.get("price"), (int, float))
        ):
            raise ValueError("PRICE_LEVEL needs condition {direction: above|below, price: number}")
        if self.type == "SIGNAL_SCORE" and not isinstance(c.get("min_score"), (int, float)):
            raise ValueError("SIGNAL_SCORE needs condition {min_score: number}")
        if self.type == "VOLATILITY_SPIKE" and not isinstance(c.get("min_percentile"), (int, float)):
            raise ValueError("VOLATILITY_SPIKE needs condition {min_percentile: number}")
        if self.type == "ECONOMIC_EVENT" and not isinstance(c.get("minutes_before"), int):
            raise ValueError("ECONOMIC_EVENT needs condition {minutes_before: int, currency?: str}")
        if self.type == "NEWS_SENTIMENT_SHIFT" and not isinstance(c.get("threshold"), (int, float)):
            raise ValueError("NEWS_SENTIMENT_SHIFT needs condition {threshold: number between 0 and 1}")
        return self


class AlertService:
    def __init__(self, c: Any):
        self.c = c

    async def create(self, data: AlertIn) -> Alert:
        sym = self.c.catalog.resolve(data.symbol) if data.symbol else None
        if data.symbol and sym is None:
            raise NexusError("INVALID_SYMBOL", f"Unknown symbol {data.symbol}")
        row = Alert(
            id=f"alr_{uuid.uuid4().hex[:12]}",
            type=data.type,
            symbol=sym,
            condition=data.condition,
            enabled=True,
            note=data.note,
            cooldown_minutes=data.cooldown_minutes,
            last_state={},
            created_at=utcnow(),
        )
        async with self.c.db.session() as s:
            s.add(row)
        return row

    async def all_alerts(self) -> list[Alert]:
        async with self.c.db.session() as s:
            return list((await s.execute(select(Alert).order_by(Alert.created_at.desc()))).scalars())

    async def delete(self, alert_id: str) -> None:
        async with self.c.db.session() as s:
            row = await s.get(Alert, alert_id)
            if row is None:
                raise NexusError("NOT_FOUND", "Alert not found")
            await s.delete(row)

    async def toggle(self, alert_id: str, enabled: bool) -> Alert:
        async with self.c.db.session() as s:
            row = await s.get(Alert, alert_id)
            if row is None:
                raise NexusError("NOT_FOUND", "Alert not found")
            row.enabled = enabled
            return row

    async def evaluate(self) -> int:
        """Check all enabled alerts; fire notifications for newly met conditions (with cooldown)."""
        c = self.c
        fired = 0
        now = utcnow()
        for a in await self.all_alerts():
            if not a.enabled:
                continue
            if a.last_triggered_at and now - a.last_triggered_at < timedelta(minutes=a.cooldown_minutes):
                continue
            try:
                hit, msg, state = await self._check(a)
            except Exception:  # one broken alert (e.g. data outage) must not stop the others
                logger.warning(
                    "alert_check_failed", extra={"event": "alert_check_failed", "data": {"alert": a.id}}
                )
                continue
            async with c.db.session() as s:
                row = await s.get(Alert, a.id)
                if row is None:
                    continue
                row.last_state = state
                if hit:
                    row.last_triggered_at = now
            if hit:
                fired += 1
                await c.audit.notify(
                    "ALERT",
                    f"Alert: {a.type.replace('_', ' ').title()}" + (f" {a.symbol}" if a.symbol else ""),
                    msg + (f" - {a.note}" if a.note else ""),
                    severity="WARNING",
                    symbol=a.symbol,
                    is_demo=c.market.is_demo,
                )
        return fired

    async def _check(self, a: Alert) -> tuple[bool, str, dict[str, Any]]:
        c, cond, prev = self.c, a.condition, a.last_state or {}
        if a.type == "PRICE_LEVEL":
            q = await c.market_service.quote(a.symbol)
            above = q.price >= cond["price"]
            was = prev.get("above")
            hit = (cond["direction"] == "above" and above and was is False) or (
                cond["direction"] == "below" and not above and was is True
            )
            return hit, f"{a.symbol} {q.price} crossed {cond['direction']} {cond['price']}", {"above": above}
        if a.type == "SIGNAL_SCORE":
            sigs = await c.signals.query(symbol=a.symbol, limit=1)
            if not sigs:
                return False, "", prev
            s = sigs[0]
            hit = s["score"] >= cond["min_score"] and prev.get("signal_id") != s["id"]
            return hit, f"{a.symbol} signal score {s['score']:.0f} ({s['direction']})", {"signal_id": s["id"]}
        if a.type in ("REGIME_CHANGE", "VOLATILITY_SPIKE", "BREAKOUT"):
            tf = Timeframe.parse(cond.get("timeframe", "1H"))
            b, _, _ = await c.market_service.bundle(a.symbol, tf)
            if a.type == "REGIME_CHANGE":
                reg = b.regime().regime.value
                hit = bool(prev.get("regime")) and prev.get("regime") != reg
                return (
                    hit,
                    f"{a.symbol} {tf.value} regime changed {prev.get('regime')} -> {reg}",
                    {"regime": reg},
                )
            if a.type == "VOLATILITY_SPIKE":
                vp = b.features().vol_percentile or 0
                above = vp >= cond["min_percentile"]
                return (
                    above and not prev.get("above"),
                    f"{a.symbol} {tf.value} volatility at {vp:.0f}th percentile",
                    {"above": above},
                )
            br = b.structure().breakout
            key = br.timestamp if br and br.bars_ago <= 1 else None
            return (
                bool(key and key != prev.get("ts")),
                f"{a.symbol} {tf.value} {br.direction.lower() if br else ''} breakout",
                {"ts": key or prev.get("ts")},
            )
        if a.type == "ECONOMIC_EVENT":
            rows = await c.content.list_events(
                hours_back=0,
                hours_ahead=int(cond["minutes_before"] / 60) + 1,
                impact="HIGH",
                currency=cond.get("currency"),
            )
            ev = [
                e for e in c.content.events_payload(rows) if 0 <= e["minutes_until"] <= cond["minutes_before"]
            ]
            if not ev or prev.get("event_id") == ev[0]["id"]:
                return False, "", prev
            return (
                True,
                f"HIGH impact {ev[0]['event']} ({ev[0]['currency']}) in {int(ev[0]['minutes_until'])} min",
                {"event_id": ev[0]["id"]},
            )
        if a.type == "NEWS_SENTIMENT_SHIFT":
            sent = await c.content.sentiment(a.symbol)
            side = 1 if sent.score >= cond["threshold"] else -1 if sent.score <= -cond["threshold"] else 0
            hit = sent.available and side != 0 and side != prev.get("side", 0)
            return (
                hit,
                f"{a.symbol} news sentiment {sent.score:+.2f} across {sent.articles} items",
                {"side": side},
            )
        return False, "", prev


class SearchService:
    def __init__(self, c: Any):
        self.c = c

    async def search(self, q: str, limit: int = 8) -> dict[str, list[dict[str, Any]]]:
        q = q.strip()[:80]
        if not q:
            return {"assets": [], "signals": [], "strategies": [], "journal": [], "news": []}
        like = f"%{q}%"
        ql = q.lower()
        assets = [
            {"symbol": a.symbol, "name": a.name, "asset_class": a.asset_class.value}
            for a in self.c.catalog.all()
            if ql in a.symbol.lower() or ql in a.name.lower() or self.c.catalog.resolve(q) == a.symbol
        ][:limit]
        sym = self.c.catalog.resolve(q)
        async with self.c.db.session() as s:
            sig_q = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
            sig_q = (
                sig_q.where(Signal.symbol == sym)
                if sym
                else sig_q.where(or_(Signal.id.like(like), Signal.regime.like(like)))
            )
            signals = [
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "direction": r.direction,
                    "status": r.status,
                    "score": r.score,
                    "created_at": r.created_at.isoformat(),
                }
                for r in (await s.execute(sig_q)).scalars()
            ]
            strategies = [
                {"name": r.name, "description": r.description}
                for r in (
                    await s.execute(
                        select(Strategy)
                        .where(or_(Strategy.name.like(like), Strategy.description.like(like)))
                        .limit(limit)
                    )
                ).scalars()
            ]
            jq = select(TradeJournal).order_by(TradeJournal.entry_time.desc()).limit(limit)
            jq = (
                jq.where(TradeJournal.symbol == sym)
                if sym
                else jq.where(or_(TradeJournal.notes.like(like), TradeJournal.strategy.like(like)))
            )
            journal = [
                {
                    "id": r.id,
                    "symbol": r.symbol,
                    "direction": r.direction,
                    "entry_type": r.entry_type,
                    "result": r.result,
                    "entry_time": r.entry_time.isoformat(),
                }
                for r in (await s.execute(jq)).scalars()
            ]
            news = [
                {
                    "id": r.id,
                    "headline": r.headline,
                    "source": r.source,
                    "url": r.url,
                    "is_demo": r.is_demo,
                    "published_at": r.published_at.isoformat(),
                }
                for r in (
                    await s.execute(
                        select(NewsItem)
                        .where(NewsItem.headline.like(like))
                        .order_by(NewsItem.published_at.desc())
                        .limit(limit)
                    )
                ).scalars()
            ]
        return {
            "assets": assets,
            "signals": signals,
            "strategies": strategies,
            "journal": journal,
            "news": news,
        }


def to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: _safe_cell(r.get(k)) for k in columns})
    return buf.getvalue()


def _safe_cell(v: Any) -> Any:
    """Neutralise spreadsheet formula injection in exported text cells."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") and not _is_number(v):
        return "'" + v
    if isinstance(v, (list, dict)):
        return str(v)
    return v


def _is_number(v: str) -> bool:
    try:
        float(v)
        return True
    except ValueError:
        return False


class ExportService:
    def __init__(self, c: Any):
        self.c = c

    async def signals_csv(self) -> str:
        rows = await self.c.signals.query(limit=5000)
        flat = [
            {
                **r,
                "targets": ";".join(f"{t['label']}={t['price']}" for t in r["targets"]),
                "outcome_status": (r.get("outcome") or {}).get("status"),
                "outcome_r": (r.get("outcome") or {}).get("r_multiple"),
                "no_trade_reasons": " | ".join(r["no_trade_reasons"]),
            }
            for r in rows
        ]
        return to_csv(
            flat,
            [
                "id",
                "created_at",
                "symbol",
                "timeframe",
                "direction",
                "status",
                "score",
                "regime",
                "price",
                "entry_type",
                "entry_price",
                "stop",
                "targets",
                "effective_rr",
                "outcome_status",
                "outcome_r",
                "data_mode",
                "calibrated_probability",
                "no_trade_reasons",
            ],
        )

    async def journal_csv(self) -> str:
        rows = await self.c.journal.query(limit=5000)
        return to_csv(
            [journal_dict(r) for r in rows],
            [
                "id",
                "entry_type",
                "entry_time",
                "exit_time",
                "symbol",
                "timeframe",
                "direction",
                "strategy",
                "regime",
                "signal_score",
                "entry_price",
                "exit_price",
                "lots",
                "fees",
                "pnl",
                "r_multiple",
                "duration_seconds",
                "result",
                "is_demo",
                "notes",
            ],
        )

    async def backtest_csv(self, bt_id: str) -> str:
        await self.c.research.get(bt_id)
        async with self.c.db.session() as s:
            rows = list(
                (
                    await s.execute(
                        select(BacktestTrade)
                        .where(BacktestTrade.backtest_id == bt_id)
                        .order_by(BacktestTrade.trade_no)
                    )
                ).scalars()
            )
        data = [{c.name: getattr(r, c.name) for c in BacktestTrade.__table__.columns} for r in rows]
        return to_csv(
            data,
            [
                "trade_no",
                "direction",
                "entry_time",
                "exit_time",
                "entry_price",
                "exit_price",
                "lots",
                "pnl",
                "pnl_r",
                "fees",
                "exit_reason",
                "regime",
                "bars_held",
                "mfe_r",
                "mae_r",
            ],
        )

    async def paper_csv(self) -> str:
        positions = await self.c.paper.broker.get_positions(None)
        data = [
            {
                "id": p.id,
                "symbol": p.symbol,
                "direction": "LONG" if p.direction > 0 else "SHORT",
                "lots": p.initial_lots,
                "entry_price": p.entry_price,
                "exit_price": p.exit_price,
                "opened_at": p.opened_at.isoformat(),
                "closed_at": p.closed_at.isoformat() if p.closed_at else None,
                "status": p.status.value,
                "realized_pnl": p.realized_pnl,
                "fees": p.fees,
                "exit_reason": p.exit_reason,
                "signal_id": p.signal_id,
                "simulated": True,
            }
            for p in positions
        ]
        return to_csv(
            data,
            [
                "id",
                "symbol",
                "direction",
                "lots",
                "entry_price",
                "exit_price",
                "opened_at",
                "closed_at",
                "status",
                "realized_pnl",
                "fees",
                "exit_reason",
                "signal_id",
                "simulated",
            ],
        )


def journal_dict(r: TradeJournal) -> dict[str, Any]:
    return {
        "id": r.id,
        "entry_type": r.entry_type,
        "symbol": r.symbol,
        "timeframe": r.timeframe,
        "direction": r.direction,
        "strategy": r.strategy,
        "regime": r.regime,
        "signal_score": r.signal_score,
        "entry_time": r.entry_time.isoformat(),
        "exit_time": r.exit_time.isoformat() if r.exit_time else None,
        "entry_price": r.entry_price,
        "exit_price": r.exit_price,
        "stop": r.stop,
        "lots": r.lots,
        "fees": r.fees,
        "slippage": r.slippage,
        "pnl": r.pnl,
        "r_multiple": r.r_multiple,
        "duration_seconds": r.duration_seconds,
        "mfe_r": r.mfe_r,
        "mae_r": r.mae_r,
        "result": r.result,
        "ai_reasoning": r.ai_reasoning,
        "notes": r.notes,
        "tags": r.tags,
        "signal_id": r.signal_id,
        "position_id": r.position_id,
        "is_demo": r.is_demo,
    }


class AnalyticsService:
    def __init__(self, c: Any):
        self.c = c

    async def performance(self) -> dict[str, Any]:
        rows = await self.c.journal.query(entry_type="PAPER_TRADE", limit=5000)
        closed = [
            ClosedTrade(
                closed_at=r.exit_time,
                symbol=r.symbol,
                strategy=r.strategy,
                regime=r.regime,
                pnl=r.pnl,
                r_multiple=r.r_multiple,
            )
            for r in rows
            if r.exit_time and r.pnl is not None
        ]
        report = performance_report(closed)
        async with self.c.db.session() as s:
            outcomes = list(
                (
                    await s.execute(
                        select(SignalOutcome, Signal)
                        .join(Signal, Signal.id == SignalOutcome.signal_id)
                        .where(SignalOutcome.resolved.is_(True))
                    )
                ).all()
            )
        sig_closed = [
            ClosedTrade(
                closed_at=sig.updated_at,
                symbol=sig.symbol,
                strategy="SignalEngine",
                regime=sig.regime,
                pnl=oc.r_multiple or 0.0,
                r_multiple=oc.r_multiple,
            )
            for oc, sig in outcomes
            if oc.r_multiple is not None
        ]
        sig_report = performance_report(sig_closed)
        return {
            "paper": report.model_dump(),
            "signals": sig_report.model_dump(),
            "notes": [
                "Paper trading results are SIMULATED fills.",
                "Signal performance assumes each signal was followed exactly per its plan (expressed in R); it is hypothetical.",
                "DEMO data results describe synthetic prices only."
                if self.c.market.is_demo
                else "LIVE data.",
            ],
        }

    async def open_positions(self) -> int:
        return len(await self.c.paper.broker.get_positions(PositionStatus.OPEN))

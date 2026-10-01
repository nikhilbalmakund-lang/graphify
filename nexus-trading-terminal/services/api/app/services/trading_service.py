"""Paper trading orchestration and the trade journal.

Every paper order - manual or from a signal - is evaluated by the
deterministic risk engine first. Orders are always SIMULATED; there is no code
path from here to a live broker.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.database import Database, utcnow
from app.core.errors import NexusError
from app.models import PaperAccount, PortfolioSnapshot, Signal, StrategyRegimeStat, TradeJournal
from app.repositories.paper_store import SqlPaperStore
from app.services.audit_service import KILL_SWITCH, PAPER_ORDER, RISK_REJECTION, AuditService
from app.services.market_service import MarketService
from app.websocket.manager import ConnectionManager
from market_data.assets import AssetCatalog
from market_data.models import Quote
from paper_trading.broker.base import (
    Order,
    OrderRequest,
    OrderSide,
    OrderType,
    Position,
    PositionStatus,
    TakeProfit,
)
from paper_trading.broker.paper import BrokerEvent, PaperBroker
from paper_trading.execution.fills import FillModel
from paper_trading.portfolio.outcome import TradeOutcome
from quant.signals.models import EventRisk
from risk.engine import AccountState, OpenExposure, RiskDecision, RiskEngine, TradeProposal

ACCOUNT_ID = "paper-main"


class JournalService:
    def __init__(self, db: Database):
        self.db = db

    async def add(self, **fields: Any) -> TradeJournal:
        now = utcnow()
        row = TradeJournal(id=f"jrn_{uuid.uuid4().hex[:16]}", created_at=now, updated_at=now, **fields)
        async with self.db.session() as s:
            s.add(row)
        return row

    async def update_by(
        self, *, signal_id: str | None = None, position_id: str | None = None, **fields: Any
    ) -> int:
        async with self.db.session() as s:
            q = select(TradeJournal)
            if signal_id:
                q = q.where(TradeJournal.signal_id == signal_id, TradeJournal.entry_type == "SIGNAL")
            elif position_id:
                q = q.where(TradeJournal.position_id == position_id)
            else:
                return 0
            rows = list((await s.execute(q)).scalars())
            for r in rows:
                for k, v in fields.items():
                    setattr(r, k, v)
                r.updated_at = utcnow()
            return len(rows)

    async def query(
        self,
        *,
        symbol: str | None = None,
        strategy: str | None = None,
        result: str | None = None,
        regime: str | None = None,
        entry_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[TradeJournal]:
        async with self.db.session() as s:
            q = select(TradeJournal).order_by(TradeJournal.entry_time.desc()).limit(min(limit, 5000))
            if symbol:
                q = q.where(TradeJournal.symbol == symbol)
            if strategy:
                q = q.where(TradeJournal.strategy == strategy)
            if result:
                q = q.where(TradeJournal.result == result)
            if regime:
                q = q.where(TradeJournal.regime == regime)
            if entry_type:
                q = q.where(TradeJournal.entry_type == entry_type)
            if start:
                q = q.where(TradeJournal.entry_time >= start)
            if end:
                q = q.where(TradeJournal.entry_time <= end)
            return list((await s.execute(q)).scalars())

    async def get(self, entry_id: str) -> TradeJournal | None:
        async with self.db.session() as s:
            return await s.get(TradeJournal, entry_id)

    async def patch(self, entry_id: str, notes: str | None, tags: list[str] | None) -> TradeJournal:
        async with self.db.session() as s:
            row = await s.get(TradeJournal, entry_id)
            if row is None:
                raise NexusError("NOT_FOUND", "Journal entry not found")
            if notes is not None:
                row.notes = notes
            if tags is not None:
                row.tags = tags
            row.updated_at = utcnow()
            return row


class PaperService:
    def __init__(
        self,
        db: Database,
        market: MarketService,
        catalog: AssetCatalog,
        risk_provider: Callable[[], RiskEngine],
        audit: AuditService,
        ws: ConnectionManager,
        journal: JournalService,
        settings: Any,
        event_risk: Callable[[str], Awaitable[EventRisk]] | None = None,
    ):
        self.db = db
        self.market = market
        self.catalog = catalog
        self.risk_provider = risk_provider  # callable -> RiskEngine (settings may change at runtime)
        self.audit = audit
        self.ws = ws
        self.journal = journal
        self.settings = settings
        self.event_risk = event_risk
        self._corr: tuple[datetime, dict[tuple[str, str], float]] | None = None
        self.store = SqlPaperStore(db)
        self.specs = {a.symbol: a for a in catalog.all()}
        self.broker = self._broker()

    def _broker(self) -> PaperBroker:
        paper = self.settings.get("paper")
        return PaperBroker(
            self.store,
            ACCOUNT_ID,
            self.specs,
            self.market.quote,
            FillModel(slippage_bps=paper.slippage_bps),
            clock=self.market.now,
            move_stop_to_breakeven=paper.move_stop_to_breakeven,
            on_close=self._on_close,
        )

    def refresh_settings(self) -> None:
        self.broker = self._broker()

    async def ensure_account(self) -> None:
        if await self.store.get_account(ACCOUNT_ID) is None:
            paper = self.settings.get("paper")
            await PaperBroker.create_account(
                self.store,
                ACCOUNT_ID,
                "Paper Account (SIMULATED)",
                paper.starting_balance,
                self.market.now(),
                max_leverage=self.settings.get("risk").max_leverage,
            )

    async def reset(self) -> None:
        async with self.db.session() as s:
            row = await s.get(PaperAccount, ACCOUNT_ID)
            if row is not None:
                await s.delete(row)
        await self.ensure_account()
        await self.audit.record(PAPER_ORDER, "Paper account reset", details={"account": ACCOUNT_ID})

    # ----------------------------------------------------------- risk view
    async def account_state(self) -> AccountState:
        acct = await self.broker.get_account()
        positions = await self.broker.get_positions(PositionStatus.OPEN)
        return AccountState(
            equity=acct.equity,
            balance=acct.balance,
            peak_equity=acct.peak_equity,
            day_start_equity=acct.day_start_equity,
            week_start_equity=acct.week_start_equity,
            kill_switch=acct.kill_switch,
            open_positions=[
                OpenExposure(
                    symbol=p.symbol,
                    direction=p.direction,
                    lots=p.lots,
                    entry_price=p.entry_price,
                    current_price=p.current_price or p.entry_price,
                    stop=p.stop_loss,
                    risk_usd=p.risk_usd or 0.0,
                )
                for p in positions
            ],
        )

    async def risk_check(
        self,
        symbol: str,
        direction: int,
        entry: float,
        stop: float,
        *,
        effective_rr: float | None,
        requested_lots: float | None,
        source: str,
        signal_id: str | None = None,
    ) -> RiskDecision:
        spec = self.market.spec(symbol)
        quote = await self.market.quote(spec.symbol)
        atr = atr_pct = None
        in_blackout = False
        try:
            from market_data.models import Timeframe

            bundle, _, _ = await self.market.bundle(spec.symbol, Timeframe.H1, 320)
            f = bundle.features()
            atr, atr_pct = f.atr14, f.atr_pct
            ref = bundle.frame["atr_pct"].iloc[-250:].median()
        except NexusError:
            ref = None
        if self.event_risk is not None:
            ev = await self.event_risk(spec.symbol)
            sig_cfg = self.settings.get("signals")
            in_blackout = bool(
                ev.available
                and ev.next_high_impact_minutes is not None
                and 0 <= ev.next_high_impact_minutes <= sig_cfg.news_blackout_before_min
            )
        prop = TradeProposal(
            symbol=spec.symbol,
            direction=direction,
            entry=entry,
            stop=stop,
            effective_rr=effective_rr,
            spread=quote.ask - quote.bid,
            atr=atr,
            atr_pct=atr_pct,
            atr_pct_reference=float(ref) if ref is not None else None,
            market_open=quote.market_open,
            in_news_blackout=in_blackout,
            expected_slippage_bps=self.settings.get("paper").slippage_bps,
            requested_lots=requested_lots,
            source=source,
        )
        engine: RiskEngine = self.risk_provider()
        decision = engine.evaluate(
            prop, await self.account_state(), spec, self.specs, await self.correlation_map()
        )
        if not decision.approved:
            await self.audit.record(
                RISK_REJECTION,
                f"Risk engine rejected {spec.symbol} {('LONG' if direction > 0 else 'SHORT')}",
                severity="WARNING",
                details={"reasons": decision.reasons, "source": source},
                signal_id=signal_id,
            )
        return decision

    async def correlation_map(self) -> dict[tuple[str, str], float]:
        if self._corr and (utcnow() - self._corr[0]) < timedelta(hours=6):
            return self._corr[1]
        out: dict[tuple[str, str], float] = {}
        try:
            corr = await self.market.correlations(self.catalog.symbols(), 60)
            syms = corr["symbols"]
            for i, a in enumerate(syms):
                for j, b in enumerate(syms):
                    if i < j:
                        out[(a, b)] = float(corr["matrix"][i][j])
        except Exception:
            out = {}
        self._corr = (utcnow(), out)
        return out

    # -------------------------------------------------------------- orders
    async def place(self, req: OrderRequest) -> tuple[Order, RiskDecision]:
        spec = self.market.spec(req.symbol)
        quote = await self.market.quote(spec.symbol)
        if self.settings.get("paper").require_stop_loss and req.stop_loss is None:
            raise NexusError(
                "RISK_LIMIT_REACHED", "A stop loss is required for every paper order (risk policy)"
            )
        entry = (
            req.price
            if req.type != OrderType.MARKET and req.price
            else (quote.ask if req.side == OrderSide.BUY else quote.bid)
        )
        rr = None
        if req.take_profits and req.stop_loss:
            risk = abs(entry - req.stop_loss)
            rr = (
                sum(abs(tp.price - entry) / risk * tp.fraction for tp in req.take_profits)
                / max(sum(tp.fraction for tp in req.take_profits), 1e-9)
                if risk > 0
                else None
            )
        decision = await self.risk_check(
            spec.symbol,
            req.side.sign,
            entry,
            req.stop_loss or entry,
            effective_rr=rr,
            requested_lots=req.lots,
            source=req.source,
            signal_id=req.signal_id,
        )
        if not decision.approved:
            raise NexusError(
                "RISK_LIMIT_REACHED",
                "Order rejected by the risk engine",
                {"reasons": decision.reasons, "checks": [c.model_dump() for c in decision.checks]},
            )
        order = await self.broker.place_order(req)
        await self.audit.record(
            PAPER_ORDER,
            f"Paper {req.type.value} {req.side.value} {req.lots} {spec.symbol}: {order.status.value}",
            details={
                "order_id": order.id,
                "status": order.status.value,
                "reject_reason": order.reject_reason,
                "simulated": True,
            },
            signal_id=req.signal_id,
        )
        if order.status.value == "FILLED" and order.position_id:
            await self._journal_open(order)
        await self.ws.broadcast("paper", {"event": "ORDER", "order": order.model_dump(mode="json")})
        return order, decision

    async def execute_signal(self, sig: Signal) -> tuple[Order, RiskDecision]:
        if sig.direction not in ("LONG", "SHORT") or sig.stop is None or sig.entry_price is None:
            raise NexusError(
                "RISK_LIMIT_REACHED", "Only active LONG/SHORT signals with a stop can be executed on paper"
            )
        d = 1 if sig.direction == "LONG" else -1
        decision = await self.risk_check(
            sig.symbol,
            d,
            sig.entry_price,
            sig.stop,
            effective_rr=sig.effective_rr,
            requested_lots=None,
            source="signal",
            signal_id=sig.id,
        )
        if not decision.approved:
            raise NexusError(
                "RISK_LIMIT_REACHED", "Signal rejected by the risk engine", {"reasons": decision.reasons}
            )
        tps = [TakeProfit(price=t["price"], fraction=t["allocation"], label=t["label"]) for t in sig.targets]
        otype = OrderType.MARKET if sig.entry_type == "MARKET" else OrderType.LIMIT
        expires = sig.expires_at
        req = OrderRequest(
            symbol=sig.symbol,
            side=OrderSide.BUY if d > 0 else OrderSide.SELL,
            type=otype,
            lots=decision.lots,
            price=None if otype == OrderType.MARKET else sig.entry_price,
            stop_loss=sig.stop,
            take_profits=tps,
            expires_at=expires,
            signal_id=sig.id,
            strategy="SignalEngine",
            regime=sig.regime,
            source="signal",
        )
        order = await self.broker.place_order(req)
        await self.audit.record(
            PAPER_ORDER,
            f"Paper order from signal {sig.id}: {order.status.value}",
            details={"order_id": order.id, "lots": decision.lots, "simulated": True},
            signal_id=sig.id,
        )
        if order.status.value == "FILLED" and order.position_id:
            await self._journal_open(order)
        await self.ws.broadcast("paper", {"event": "ORDER", "order": order.model_dump(mode="json")})
        return order, decision

    async def _journal_open(self, order: Order) -> None:
        pos = await self.store.get_position(order.position_id or "")
        if pos is None:
            return
        score = None
        if pos.signal_id:
            async with self.db.session() as s:
                sig = await s.get(Signal, pos.signal_id)
                score = sig.score if sig else None
        await self.journal.add(
            entry_type="PAPER_TRADE",
            symbol=pos.symbol,
            timeframe=None,
            direction="LONG" if pos.direction > 0 else "SHORT",
            strategy=pos.strategy or "Manual",
            regime=pos.regime,
            signal_score=score,
            entry_time=pos.opened_at,
            entry_price=pos.entry_price,
            stop=pos.stop_loss,
            lots=pos.initial_lots,
            fees=pos.fees,
            result="OPEN",
            signal_id=pos.signal_id,
            position_id=pos.id,
            is_demo=self.market.market.is_demo,
            tags=["PAPER"],
        )

    async def _on_close(self, pos: Position, outcome: TradeOutcome) -> None:
        await self.journal.update_by(
            position_id=pos.id,
            exit_time=pos.closed_at,
            exit_price=pos.exit_price,
            pnl=outcome.pnl,
            fees=outcome.fees,
            r_multiple=outcome.r_multiple,
            duration_seconds=outcome.duration_seconds,
            mfe_r=outcome.mfe_r,
            mae_r=outcome.mae_r,
            result=outcome.result,
        )
        async with self.db.session() as s:
            key = (pos.strategy or "Manual", pos.regime or "UNSPECIFIED", "PAPER", self.market.market.is_demo)
            row = await s.scalar(
                select(StrategyRegimeStat).where(
                    StrategyRegimeStat.strategy == key[0],
                    StrategyRegimeStat.regime == key[1],
                    StrategyRegimeStat.source == key[2],
                    StrategyRegimeStat.is_demo == key[3],
                )
            )
            if row is None:
                row = StrategyRegimeStat(
                    strategy=key[0],
                    regime=key[1],
                    source=key[2],
                    is_demo=key[3],
                    trades=0,
                    wins=0,
                    sum_r=0.0,
                    sum_pnl=0.0,
                )
                s.add(row)
            row.trades = (row.trades or 0) + 1
            row.wins = (row.wins or 0) + (1 if outcome.result == "WIN" else 0)
            row.sum_r = (row.sum_r or 0.0) + (outcome.r_multiple or 0.0)
            row.sum_pnl = (row.sum_pnl or 0.0) + outcome.pnl
            row.updated_at = utcnow()
        await self.audit.notify(
            "POSITION_CLOSED",
            f"Paper position closed: {pos.symbol} {outcome.result}",
            f"{pos.exit_reason} at {pos.exit_price}; P&L {outcome.pnl:+.2f} USD (SIMULATED)",
            severity="INFO",
            symbol=pos.symbol,
            signal_id=pos.signal_id,
            is_demo=self.market.market.is_demo,
        )
        await self.ws.broadcast(
            "paper",
            {"event": "POSITION_CLOSED", "position_id": pos.id, "outcome": outcome.model_dump(mode="json")},
        )

    async def process(self, quotes: dict[str, Quote]) -> list[BrokerEvent]:
        events = await self.broker.process_quotes(quotes)
        for e in events:
            if e.type in ("STOP_HIT", "TP_HIT", "ORDER_FILLED"):
                kind = {"STOP_HIT": "stop_reached", "TP_HIT": "target_reached", "ORDER_FILLED": "new_signal"}[
                    e.type
                ]
                if self.settings.get("notifications").model_dump().get(kind, True):
                    await self.audit.notify(
                        e.type,
                        f"{e.symbol}: {e.type.replace('_', ' ').title()} (paper)",
                        e.detail,
                        severity="WARNING" if e.type == "STOP_HIT" else "INFO",
                        symbol=e.symbol,
                        is_demo=self.market.market.is_demo,
                    )
            if e.type == "ORDER_FILLED" and e.order_id:
                order = await self.store.get_order(e.order_id)
                if order:
                    await self._journal_open(order)
        if events:
            await self.ws.broadcast(
                "paper", {"event": "UPDATE", "events": [e.model_dump(mode="json") for e in events]}
            )
        return events

    async def kill_switch(self, active: bool) -> list[Order]:
        cancelled = await self.broker.set_kill_switch(active)
        await self.audit.record(
            KILL_SWITCH,
            f"Emergency kill switch {'ACTIVATED' if active else 'released'}",
            severity="WARNING" if active else "INFO",
            details={"cancelled_orders": [o.id for o in cancelled]},
        )
        await self.audit.notify(
            "RISK_LIMIT",
            "Kill switch " + ("ACTIVATED: trading halted" if active else "released"),
            f"{len(cancelled)} pending orders cancelled",
            severity="ERROR" if active else "INFO",
            is_demo=self.market.market.is_demo,
        )
        await self.ws.broadcast("system", {"event": "KILL_SWITCH", "active": active})
        return cancelled

    async def snapshot(self) -> None:
        acct = await self.broker.get_account()
        positions = await self.store.list_positions(ACCOUNT_ID, PositionStatus.OPEN)
        dd = (acct.peak_equity - acct.equity) / acct.peak_equity if acct.peak_equity else 0.0
        async with self.db.session() as s:
            s.add(
                PortfolioSnapshot(
                    account_id=ACCOUNT_ID,
                    ts=utcnow(),
                    balance=acct.balance,
                    equity=acct.equity,
                    margin_used=acct.margin_used,
                    unrealized_pnl=acct.unrealized_pnl,
                    open_positions=len(positions),
                    drawdown=round(dd, 6),
                    is_demo_prices=self.market.market.is_demo,
                )
            )

    async def snapshots(self, limit: int = 2000) -> list[PortfolioSnapshot]:
        async with self.db.session() as s:
            q = (
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.account_id == ACCOUNT_ID)
                .order_by(PortfolioSnapshot.ts.desc())
                .limit(limit)
            )
            return list(reversed(list((await s.execute(q)).scalars())))

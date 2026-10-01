"""PaperBroker: a virtual broker for SIMULATED trading.

It never sends orders anywhere. Prices come from the configured market data
provider (DEMO or LIVE quotes); every object it creates is flagged is_paper.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from pydantic import BaseModel

from market_data.models import AssetSpec, Quote
from paper_trading.broker.base import (
    Account,
    BrokerError,
    BrokerProvider,
    Fill,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionStatus,
)
from paper_trading.broker.store import PaperStore
from paper_trading.execution.fills import FillModel
from paper_trading.portfolio.outcome import TradeOutcome, compute_outcome
from risk.sizing import margin_required, notional_usd, pnl_usd

QuoteSource = Callable[[str], Awaitable[Quote]]
CloseCallback = Callable[[Position, TradeOutcome], Awaitable[None]]


class BrokerEvent(BaseModel):
    type: str  # ORDER_FILLED | ORDER_EXPIRED | TP_HIT | STOP_HIT | POSITION_CLOSED | KILL_SWITCH
    symbol: str
    detail: str
    order_id: str | None = None
    position_id: str | None = None
    timestamp: datetime


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class PaperBroker(BrokerProvider):
    name = "paper"
    is_paper = True

    def __init__(
        self,
        store: PaperStore,
        account_id: str,
        specs: dict[str, AssetSpec],
        quotes: QuoteSource,
        fill_model: FillModel | None = None,
        clock: Callable[[], datetime] | None = None,
        move_stop_to_breakeven: bool = True,
        on_close: CloseCallback | None = None,
    ):
        self.store = store
        self.account_id = account_id
        self.specs = specs
        self.quotes = quotes
        self.fills = fill_model or FillModel()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.move_stop_to_breakeven = move_stop_to_breakeven
        self.on_close = on_close
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------ account
    @staticmethod
    async def create_account(
        store: PaperStore,
        account_id: str,
        name: str,
        balance: float,
        now: datetime,
        max_leverage: float = 10.0,
    ) -> Account:
        acct = Account(
            id=account_id,
            name=name,
            starting_balance=balance,
            balance=balance,
            equity=balance,
            free_margin=balance,
            peak_equity=balance,
            day_start_equity=balance,
            week_start_equity=balance,
            day_key=now.strftime("%Y-%m-%d"),
            week_key=now.strftime("%G-W%V"),
            created_at=now,
            updated_at=now,
            max_leverage=max_leverage,
        )
        await store.save_account(acct)
        return acct

    async def _account(self) -> Account:
        acct = await self.store.get_account(self.account_id)
        if acct is None:
            raise BrokerError("BROKER_ERROR", f"Paper account '{self.account_id}' not found")
        return acct

    def _spec(self, symbol: str) -> AssetSpec:
        spec = self.specs.get(symbol)
        if spec is None:
            raise BrokerError("BROKER_ERROR", f"Unknown symbol '{symbol}'")
        return spec

    async def _mark(
        self, acct: Account, positions: list[Position], quotes: dict[str, Quote] | None = None
    ) -> Account:
        unreal = 0.0
        margin = 0.0
        for p in positions:
            q = (quotes or {}).get(p.symbol) or await self.quotes(p.symbol)
            spec = self._spec(p.symbol)
            px = q.bid if p.direction > 0 else q.ask
            p.current_price = px
            p.unrealized_pnl = round(pnl_usd(spec, p.direction, p.entry_price, px, p.lots), 2)
            unreal += p.unrealized_pnl
            margin += margin_required(spec, p.lots, px, acct.max_leverage)
        now = self.clock()
        acct.unrealized_pnl = round(unreal, 2)
        acct.equity = round(acct.balance + unreal, 2)
        acct.margin_used = round(margin, 2)
        acct.free_margin = round(acct.equity - margin, 2)
        acct.peak_equity = max(acct.peak_equity, acct.equity)
        day, week = now.strftime("%Y-%m-%d"), now.strftime("%G-W%V")
        if acct.day_key != day:
            acct.day_key, acct.day_start_equity = day, acct.equity
        if acct.week_key != week:
            acct.week_key, acct.week_start_equity = week, acct.equity
        acct.updated_at = now
        return acct

    async def get_account(self) -> Account:
        acct = await self._account()
        positions = await self.store.list_positions(self.account_id, PositionStatus.OPEN)
        acct = await self._mark(acct, positions)
        await self.store.save_account(acct)
        return acct

    async def get_positions(self, status: PositionStatus | None = PositionStatus.OPEN) -> list[Position]:
        positions = await self.store.list_positions(self.account_id, status)
        open_pos = [p for p in positions if p.status == PositionStatus.OPEN]
        if open_pos:
            await self._mark(await self._account(), open_pos)
        return sorted(positions, key=lambda p: p.opened_at, reverse=True)

    async def get_orders(self, status: OrderStatus | None = None) -> list[Order]:
        orders = await self.store.list_orders(self.account_id, status)
        return sorted(orders, key=lambda o: o.created_at, reverse=True)

    # ------------------------------------------------------------- orders
    def _validate(self, req: OrderRequest, spec: AssetSpec, ref_price: float) -> None:
        steps = req.lots / spec.lot_step
        if req.lots < spec.min_lot or abs(steps - round(steps)) > 1e-6:
            raise BrokerError(
                "BROKER_ERROR", f"Lot size must be >= {spec.min_lot} in steps of {spec.lot_step}"
            )
        if req.lots > spec.max_lot:
            raise BrokerError("BROKER_ERROR", f"Lot size exceeds instrument maximum {spec.max_lot}")
        if req.type != OrderType.MARKET and req.price is None:
            raise BrokerError("BROKER_ERROR", f"{req.type.value} orders require a price")
        d = req.side.sign
        entry = req.price if req.type != OrderType.MARKET and req.price else ref_price
        if req.stop_loss is not None and (
            (d > 0 and req.stop_loss >= entry) or (d < 0 and req.stop_loss <= entry)
        ):
            raise BrokerError("BROKER_ERROR", "Stop loss must be on the losing side of the entry price")
        for tp in req.take_profits:
            if (d > 0 and tp.price <= entry) or (d < 0 and tp.price >= entry):
                raise BrokerError(
                    "BROKER_ERROR", "Take profit must be on the winning side of the entry price"
                )

    async def place_order(self, request: OrderRequest) -> Order:
        async with self._lock:
            acct = await self._account()
            now = self.clock()
            spec = self._spec(request.symbol)
            quote = await self.quotes(spec.symbol)
            order = Order(
                id=_new_id("ord"),
                account_id=acct.id,
                symbol=spec.symbol,
                side=request.side,
                type=request.type,
                lots=request.lots,
                price=request.price,
                stop_loss=request.stop_loss,
                take_profits=request.take_profits,
                status=OrderStatus.PENDING,
                created_at=now,
                updated_at=now,
                expires_at=request.expires_at,
                signal_id=request.signal_id,
                strategy=request.strategy,
                regime=request.regime,
                source=request.source,
                comment=request.comment,
            )
            if acct.kill_switch:
                order.status, order.reject_reason = OrderStatus.REJECTED, "Kill switch active: trading halted"
                await self.store.save_order(order)
                return order
            try:
                self._validate(request, spec, quote.price)
            except BrokerError as exc:
                order.status, order.reject_reason = OrderStatus.REJECTED, exc.message
                await self.store.save_order(order)
                return order
            positions = await self.store.list_positions(acct.id, PositionStatus.OPEN)
            acct = await self._mark(acct, positions)
            ref = request.price if request.type != OrderType.MARKET and request.price else quote.price
            need = margin_required(spec, request.lots, ref, acct.max_leverage)
            if need > acct.free_margin:
                order.status, order.reject_reason = (
                    OrderStatus.REJECTED,
                    f"Insufficient free margin (need {need:,.2f})",
                )
                await self.store.save_order(order)
                return order
            if request.type == OrderType.MARKET:
                price, slip = self.fills.market_fill(request.side, quote)
                await self._fill(order, acct, spec, price, slip, now)
            else:
                await self.store.save_order(order)
            return order

    async def _fill(
        self, order: Order, acct: Account, spec: AssetSpec, price: float, slip: float, now: datetime
    ) -> Position:
        fee = self.fills.fee(spec, order.lots, price)
        d = order.side.sign
        risk = (
            abs(pnl_usd(spec, d, price, order.stop_loss, order.lots)) if order.stop_loss is not None else None
        )
        pos = Position(
            id=_new_id("pos"),
            account_id=acct.id,
            symbol=spec.symbol,
            direction=d,
            lots=order.lots,
            initial_lots=order.lots,
            entry_price=round(price, spec.price_precision + 3),
            stop_loss=order.stop_loss,
            initial_stop=order.stop_loss,
            take_profits=list(order.take_profits),
            opened_at=now,
            fees=round(fee, 4),
            risk_usd=round(risk, 2) if risk is not None else None,
            best_price=price,
            worst_price=price,
            signal_id=order.signal_id,
            strategy=order.strategy,
            regime=order.regime,
            source=order.source,
        )
        acct.balance = round(acct.balance - fee, 2)
        order.status, order.filled_at, order.fill_price, order.updated_at, order.position_id = (
            OrderStatus.FILLED,
            now,
            pos.entry_price,
            now,
            pos.id,
        )
        await self.store.save_position(pos)
        await self.store.save_order(order)
        await self.store.add_fill(
            Fill(
                id=_new_id("fill"),
                account_id=acct.id,
                order_id=order.id,
                position_id=pos.id,
                symbol=spec.symbol,
                side=order.side,
                lots=order.lots,
                price=pos.entry_price,
                fee=round(fee, 4),
                slippage=round(slip, 8),
                reason="ENTRY",
                timestamp=now,
            )
        )
        await self.store.save_account(acct)
        return pos

    async def cancel_order(self, order_id: str) -> Order:
        async with self._lock:
            order = await self.store.get_order(order_id)
            if order is None or order.account_id != self.account_id:
                raise BrokerError("BROKER_ERROR", "Order not found")
            if order.status != OrderStatus.PENDING:
                raise BrokerError("BROKER_ERROR", f"Order is {order.status.value}, not cancellable")
            order.status, order.updated_at = OrderStatus.CANCELLED, self.clock()
            await self.store.save_order(order)
            return order

    async def close_position(
        self, position_id: str, lots: float | None = None, reason: str = "MANUAL_CLOSE"
    ) -> Position:
        async with self._lock:
            pos = await self.store.get_position(position_id)
            if pos is None or pos.account_id != self.account_id:
                raise BrokerError("BROKER_ERROR", "Position not found")
            if pos.status != PositionStatus.OPEN:
                raise BrokerError("BROKER_ERROR", "Position is already closed")
            spec = self._spec(pos.symbol)
            if lots is not None:
                steps = lots / spec.lot_step
                if lots <= 0 or lots > pos.lots + 1e-9 or abs(steps - round(steps)) > 1e-6:
                    raise BrokerError("BROKER_ERROR", "Invalid lots to close")
            quote = await self.quotes(pos.symbol)
            price, slip = self.fills.exit_fill(pos.direction, quote, None, reason)
            acct = await self._account()
            await self._exit(pos, acct, spec, lots or pos.lots, price, slip, reason)
            return pos

    async def _exit(
        self,
        pos: Position,
        acct: Account,
        spec: AssetSpec,
        lots: float,
        price: float,
        slip: float,
        reason: str,
    ) -> None:
        now = self.clock()
        lots = min(lots, pos.lots)
        gross = pnl_usd(spec, pos.direction, pos.entry_price, price, lots)
        fee = self.fills.fee(spec, lots, price)
        pos.realized_pnl = round(pos.realized_pnl + gross - fee, 2)
        pos.fees = round(pos.fees + fee, 4)
        pos.lots = round(pos.lots - lots, 8)
        acct.balance = round(acct.balance + gross - fee, 2)
        side = OrderSide.SELL if pos.direction > 0 else OrderSide.BUY
        await self.store.add_fill(
            Fill(
                id=_new_id("fill"),
                account_id=acct.id,
                order_id=None,
                position_id=pos.id,
                symbol=pos.symbol,
                side=side,
                lots=lots,
                price=round(price, spec.price_precision + 3),
                fee=round(fee, 4),
                slippage=round(slip, 8),
                reason=reason,
                timestamp=now,
                realized_pnl=round(gross - fee, 2),
            )
        )
        outcome = None
        if pos.lots <= 1e-9:
            pos.lots = 0.0
            pos.status = PositionStatus.CLOSED
            pos.closed_at = now
            pos.exit_reason = reason
            fills = [
                f
                for f in await self.store.list_fills(acct.id, 5000)
                if f.position_id == pos.id and f.reason != "ENTRY"
            ]
            total = sum(f.lots for f in fills)
            pos.exit_price = (
                round(sum(f.price * f.lots for f in fills) / total, spec.price_precision + 3)
                if total
                else price
            )
            outcome = compute_outcome(pos)
        await self.store.save_position(pos)
        await self.store.save_account(acct)
        if outcome is not None and self.on_close is not None:
            await self.on_close(pos, outcome)

    # ---------------------------------------------------- price processing
    async def process_quotes(self, quotes: dict[str, Quote]) -> list[BrokerEvent]:
        """Trigger pending orders and manage stops/targets for the given quotes."""
        events: list[BrokerEvent] = []
        async with self._lock:
            acct = await self._account()
            now = self.clock()
            for order in await self.store.list_orders(acct.id, OrderStatus.PENDING):
                q = quotes.get(order.symbol)
                if q is None:
                    continue
                if order.expires_at and now >= order.expires_at:
                    order.status, order.updated_at = OrderStatus.EXPIRED, now
                    await self.store.save_order(order)
                    events.append(
                        BrokerEvent(
                            type="ORDER_EXPIRED",
                            symbol=order.symbol,
                            detail=f"{order.type.value} order expired",
                            order_id=order.id,
                            timestamp=now,
                        )
                    )
                    continue
                if acct.kill_switch:
                    continue
                trig = self.fills.pending_trigger(order.type, order.side, order.price or 0.0, q)
                if trig is not None:
                    pos = await self._fill(order, acct, self._spec(order.symbol), trig[0], trig[1], now)
                    events.append(
                        BrokerEvent(
                            type="ORDER_FILLED",
                            symbol=order.symbol,
                            detail=f"{order.type.value} {order.side.value} {order.lots} @ {pos.entry_price}",
                            order_id=order.id,
                            position_id=pos.id,
                            timestamp=now,
                        )
                    )
            for pos in await self.store.list_positions(acct.id, PositionStatus.OPEN):
                q = quotes.get(pos.symbol)
                if q is None:
                    continue
                spec = self._spec(pos.symbol)
                exit_px = q.bid if pos.direction > 0 else q.ask
                if pos.direction > 0:
                    pos.best_price = max(pos.best_price or exit_px, exit_px)
                    pos.worst_price = min(pos.worst_price or exit_px, exit_px)
                else:
                    pos.best_price = min(pos.best_price or exit_px, exit_px)
                    pos.worst_price = max(pos.worst_price or exit_px, exit_px)
                stop_hit = pos.stop_loss is not None and (
                    (pos.direction > 0 and exit_px <= pos.stop_loss)
                    or (pos.direction < 0 and exit_px >= pos.stop_loss)
                )
                if stop_hit:
                    reason = "STOP_LOSS" if pos.stop_loss == pos.initial_stop else "BREAKEVEN_STOP"
                    price, slip = self.fills.exit_fill(pos.direction, q, pos.stop_loss, reason)
                    await self._exit(pos, acct, spec, pos.lots, price, slip, reason)
                    events.append(
                        BrokerEvent(
                            type="STOP_HIT",
                            symbol=pos.symbol,
                            detail=f"{reason} @ {price:.{spec.price_precision}f}",
                            position_id=pos.id,
                            timestamp=now,
                        )
                    )
                    continue
                while pos.status == PositionStatus.OPEN and pos.take_profits:
                    tp = pos.take_profits[0]
                    hit = (pos.direction > 0 and exit_px >= tp.price) or (
                        pos.direction < 0 and exit_px <= tp.price
                    )
                    if not hit:
                        break
                    pos.take_profits = pos.take_profits[1:]
                    lots = (
                        pos.lots
                        if not pos.take_profits
                        else max(
                            spec.min_lot,
                            round(int(pos.initial_lots * tp.fraction / spec.lot_step) * spec.lot_step, 8),
                        )
                    )
                    lots = min(lots, pos.lots)
                    price, slip = self.fills.exit_fill(pos.direction, q, tp.price, "TAKE_PROFIT")
                    reason = "TAKE_PROFIT" if lots >= pos.lots - 1e-9 else "PARTIAL_TP"
                    if reason == "PARTIAL_TP" and self.move_stop_to_breakeven:
                        pos.stop_loss = pos.entry_price
                    await self._exit(pos, acct, spec, lots, price, slip, reason)
                    events.append(
                        BrokerEvent(
                            type="TP_HIT",
                            symbol=pos.symbol,
                            detail=f"{tp.label} {reason} @ {price:.{spec.price_precision}f}",
                            position_id=pos.id,
                            timestamp=now,
                        )
                    )
                if pos.status == PositionStatus.OPEN:
                    await self.store.save_position(pos)
            positions = await self.store.list_positions(acct.id, PositionStatus.OPEN)
            acct = await self._mark(await self._account(), positions, quotes)
            await self.store.save_account(acct)
        return events

    # -------------------------------------------------------- kill switch
    async def set_kill_switch(self, active: bool, cancel_pending: bool = True) -> list[Order]:
        async with self._lock:
            acct = await self._account()
            acct.kill_switch = active
            acct.updated_at = self.clock()
            await self.store.save_account(acct)
            cancelled: list[Order] = []
            if active and cancel_pending:
                for order in await self.store.list_orders(acct.id, OrderStatus.PENDING):
                    order.status, order.updated_at, order.reject_reason = (
                        OrderStatus.CANCELLED,
                        self.clock(),
                        "Kill switch",
                    )
                    await self.store.save_order(order)
                    cancelled.append(order)
            return cancelled

    async def exposure(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for p in await self.store.list_positions(self.account_id, PositionStatus.OPEN):
            q = await self.quotes(p.symbol)
            out[p.symbol] = out.get(p.symbol, 0.0) + p.direction * notional_usd(
                self._spec(p.symbol), p.lots, q.price
            )
        return out

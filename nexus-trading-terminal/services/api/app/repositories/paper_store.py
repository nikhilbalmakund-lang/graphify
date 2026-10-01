"""SQL implementation of the paper broker's storage protocol."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import Database, utcnow
from app.models import PaperAccount, PaperFill, PaperOrder, PaperPosition
from paper_trading.broker.base import Account, Fill, Order, OrderStatus, Position, PositionStatus


class SqlPaperStore:
    def __init__(self, db: Database):
        self.db = db

    async def get_account(self, account_id: str) -> Account | None:
        async with self.db.session() as s:
            row = await s.get(PaperAccount, account_id)
            return Account.model_validate(row.data) if row else None

    async def save_account(self, account: Account) -> None:
        async with self.db.session() as s:
            row = await s.get(PaperAccount, account.id)
            data = account.model_dump(mode="json")
            if row is None:
                s.add(
                    PaperAccount(
                        id=account.id,
                        data=data,
                        kill_switch=account.kill_switch,
                        created_at=account.created_at,
                        updated_at=utcnow(),
                    )
                )
            else:
                row.data, row.kill_switch, row.updated_at = data, account.kill_switch, utcnow()

    async def list_positions(self, account_id: str, status: PositionStatus | None = None) -> list[Position]:
        async with self.db.session() as s:
            q = select(PaperPosition).where(PaperPosition.account_id == account_id)
            if status is not None:
                q = q.where(PaperPosition.status == status.value)
            return [Position.model_validate(r.data) for r in (await s.execute(q)).scalars()]

    async def get_position(self, position_id: str) -> Position | None:
        async with self.db.session() as s:
            row = await s.get(PaperPosition, position_id)
            return Position.model_validate(row.data) if row else None

    async def save_position(self, position: Position) -> None:
        async with self.db.session() as s:
            row = await s.get(PaperPosition, position.id)
            data = position.model_dump(mode="json")
            if row is None:
                s.add(
                    PaperPosition(
                        id=position.id,
                        account_id=position.account_id,
                        symbol=position.symbol,
                        status=position.status.value,
                        opened_at=position.opened_at,
                        closed_at=position.closed_at,
                        strategy=position.strategy,
                        signal_id=position.signal_id,
                        data=data,
                    )
                )
            else:
                row.status, row.closed_at, row.data = position.status.value, position.closed_at, data

    async def list_orders(self, account_id: str, status: OrderStatus | None = None) -> list[Order]:
        async with self.db.session() as s:
            q = select(PaperOrder).where(PaperOrder.account_id == account_id)
            if status is not None:
                q = q.where(PaperOrder.status == status.value)
            return [Order.model_validate(r.data) for r in (await s.execute(q)).scalars()]

    async def get_order(self, order_id: str) -> Order | None:
        async with self.db.session() as s:
            row = await s.get(PaperOrder, order_id)
            return Order.model_validate(row.data) if row else None

    async def save_order(self, order: Order) -> None:
        async with self.db.session() as s:
            row = await s.get(PaperOrder, order.id)
            data = order.model_dump(mode="json")
            if row is None:
                s.add(
                    PaperOrder(
                        id=order.id,
                        account_id=order.account_id,
                        symbol=order.symbol,
                        status=order.status.value,
                        created_at=order.created_at,
                        data=data,
                    )
                )
            else:
                row.status, row.data = order.status.value, data

    async def add_fill(self, fill: Fill) -> None:
        async with self.db.session() as s:
            s.add(
                PaperFill(
                    id=fill.id,
                    account_id=fill.account_id,
                    position_id=fill.position_id,
                    timestamp=fill.timestamp,
                    data=fill.model_dump(mode="json"),
                )
            )

    async def list_fills(self, account_id: str, limit: int = 500) -> list[Fill]:
        async with self.db.session() as s:
            q = (
                select(PaperFill)
                .where(PaperFill.account_id == account_id)
                .order_by(PaperFill.timestamp.desc())
                .limit(limit)
            )
            rows = list((await s.execute(q)).scalars())
        return [Fill.model_validate(r.data) for r in reversed(rows)]

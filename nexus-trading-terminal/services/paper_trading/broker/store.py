"""Persistence protocol for the paper broker plus an in-memory implementation.

The application provides a SQL implementation; tests use `InMemoryPaperStore`.
Keeping storage behind this protocol keeps EXECUTION separate from DATA.
"""

from __future__ import annotations

from typing import Protocol

from paper_trading.broker.base import Account, Fill, Order, OrderStatus, Position, PositionStatus


class PaperStore(Protocol):
    async def get_account(self, account_id: str) -> Account | None: ...

    async def save_account(self, account: Account) -> None: ...

    async def list_positions(
        self, account_id: str, status: PositionStatus | None = None
    ) -> list[Position]: ...

    async def get_position(self, position_id: str) -> Position | None: ...

    async def save_position(self, position: Position) -> None: ...

    async def list_orders(self, account_id: str, status: OrderStatus | None = None) -> list[Order]: ...

    async def get_order(self, order_id: str) -> Order | None: ...

    async def save_order(self, order: Order) -> None: ...

    async def add_fill(self, fill: Fill) -> None: ...

    async def list_fills(self, account_id: str, limit: int = 500) -> list[Fill]: ...


class InMemoryPaperStore:
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}
        self.positions: dict[str, Position] = {}
        self.orders: dict[str, Order] = {}
        self.fills: list[Fill] = []

    async def get_account(self, account_id: str) -> Account | None:
        a = self.accounts.get(account_id)
        return a.model_copy(deep=True) if a else None

    async def save_account(self, account: Account) -> None:
        self.accounts[account.id] = account.model_copy(deep=True)

    async def list_positions(self, account_id: str, status: PositionStatus | None = None) -> list[Position]:
        return [
            p.model_copy(deep=True)
            for p in self.positions.values()
            if p.account_id == account_id and (status is None or p.status == status)
        ]

    async def get_position(self, position_id: str) -> Position | None:
        p = self.positions.get(position_id)
        return p.model_copy(deep=True) if p else None

    async def save_position(self, position: Position) -> None:
        self.positions[position.id] = position.model_copy(deep=True)

    async def list_orders(self, account_id: str, status: OrderStatus | None = None) -> list[Order]:
        return [
            o.model_copy(deep=True)
            for o in self.orders.values()
            if o.account_id == account_id and (status is None or o.status == status)
        ]

    async def get_order(self, order_id: str) -> Order | None:
        o = self.orders.get(order_id)
        return o.model_copy(deep=True) if o else None

    async def save_order(self, order: Order) -> None:
        self.orders[order.id] = order.model_copy(deep=True)

    async def add_fill(self, fill: Fill) -> None:
        self.fills.append(fill.model_copy(deep=True))

    async def list_fills(self, account_id: str, limit: int = 500) -> list[Fill]:
        return [f for f in self.fills if f.account_id == account_id][-limit:]

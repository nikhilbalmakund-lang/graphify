"""Broker abstraction shared by the paper broker and future live brokers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class BrokerError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"

    @property
    def sign(self) -> int:
        return 1 if self == OrderSide.BUY else -1


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class PositionStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class TakeProfit(BaseModel):
    price: float
    fraction: float = Field(1.0, gt=0, le=1)
    label: str = "TP"


class OrderRequest(BaseModel):
    symbol: str
    side: OrderSide
    type: OrderType = OrderType.MARKET
    lots: float = Field(gt=0)
    price: float | None = Field(None, gt=0, description="Required for LIMIT and STOP orders")
    stop_loss: float | None = Field(None, gt=0)
    take_profits: list[TakeProfit] = Field(default_factory=list)
    expires_at: datetime | None = None
    signal_id: str | None = None
    strategy: str | None = None
    regime: str | None = None
    source: str = "manual"
    comment: str | None = Field(None, max_length=500)

    @field_validator("take_profits")
    @classmethod
    def _fractions(cls, v: list[TakeProfit]) -> list[TakeProfit]:
        if v and sum(tp.fraction for tp in v) > 1.0 + 1e-6:
            raise ValueError("Take-profit fractions must sum to at most 1.0")
        return v


class Order(BaseModel):
    id: str
    account_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    lots: float
    price: float | None = None
    stop_loss: float | None = None
    take_profits: list[TakeProfit] = Field(default_factory=list)
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    filled_at: datetime | None = None
    fill_price: float | None = None
    expires_at: datetime | None = None
    reject_reason: str | None = None
    signal_id: str | None = None
    strategy: str | None = None
    regime: str | None = None
    source: str = "manual"
    comment: str | None = None
    position_id: str | None = None
    is_paper: bool = True


class Fill(BaseModel):
    id: str
    account_id: str
    order_id: str | None
    position_id: str
    symbol: str
    side: OrderSide
    lots: float
    price: float
    fee: float
    slippage: float
    reason: str  # ENTRY | PARTIAL_TP | TAKE_PROFIT | STOP_LOSS | BREAKEVEN_STOP | MANUAL_CLOSE | KILL_SWITCH
    timestamp: datetime
    realized_pnl: float = 0.0
    is_paper: bool = True


class Position(BaseModel):
    id: str
    account_id: str
    symbol: str
    direction: int
    lots: float
    initial_lots: float
    entry_price: float
    stop_loss: float | None = None
    initial_stop: float | None = None
    take_profits: list[TakeProfit] = Field(default_factory=list)
    status: PositionStatus = PositionStatus.OPEN
    opened_at: datetime
    closed_at: datetime | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    realized_pnl: float = 0.0
    fees: float = 0.0
    risk_usd: float | None = None
    best_price: float | None = None
    worst_price: float | None = None
    signal_id: str | None = None
    strategy: str | None = None
    regime: str | None = None
    source: str = "manual"
    current_price: float | None = None
    unrealized_pnl: float = 0.0
    is_paper: bool = True


class Account(BaseModel):
    id: str
    name: str
    currency: str = "USD"
    starting_balance: float
    balance: float
    equity: float
    margin_used: float = 0.0
    free_margin: float = 0.0
    unrealized_pnl: float = 0.0
    peak_equity: float
    day_start_equity: float
    week_start_equity: float
    day_key: str = ""
    week_key: str = ""
    kill_switch: bool = False
    max_leverage: float = 10.0
    created_at: datetime
    updated_at: datetime
    is_paper: bool = True


class BrokerProvider(ABC):
    name: str = "abstract"
    is_paper: bool = True

    @abstractmethod
    async def get_account(self) -> Account: ...

    @abstractmethod
    async def get_positions(self, status: PositionStatus | None = PositionStatus.OPEN) -> list[Position]: ...

    @abstractmethod
    async def get_orders(self, status: OrderStatus | None = None) -> list[Order]: ...

    @abstractmethod
    async def place_order(self, request: OrderRequest) -> Order: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> Order: ...

    @abstractmethod
    async def close_position(self, position_id: str, lots: float | None = None) -> Position: ...

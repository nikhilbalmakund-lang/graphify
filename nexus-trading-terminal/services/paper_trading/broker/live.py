"""Live broker integrations - FUTURE EXTERNAL INTEGRATIONS (not implemented).

These classes define where MetaTrader 5, Interactive Brokers and Alpaca
adapters will plug in. Every method raises BROKER_NOT_IMPLEMENTED, so no live
order can ever be sent by this version of the application.

Live execution additionally requires, in this order:
1. LIVE_TRADING_ENABLED=true in the server environment,
2. a configured, implemented live broker adapter, and
3. the visible UI safety switch turned on for the session.
See `live_trading_gate` - it is checked before any live broker is constructed.
"""

from __future__ import annotations

from paper_trading.broker.base import (
    Account,
    BrokerError,
    BrokerProvider,
    Order,
    OrderRequest,
    OrderStatus,
    Position,
    PositionStatus,
)

NOT_IMPLEMENTED = "is a future external integration and is not implemented; live orders cannot be sent"


class _FutureLiveBroker(BrokerProvider):
    is_paper = False
    label = "Live broker"

    def _fail(self) -> BrokerError:
        return BrokerError("BROKER_NOT_IMPLEMENTED", f"{self.label} {NOT_IMPLEMENTED}")

    async def get_account(self) -> Account:
        raise self._fail()

    async def get_positions(self, status: PositionStatus | None = PositionStatus.OPEN) -> list[Position]:
        raise self._fail()

    async def get_orders(self, status: OrderStatus | None = None) -> list[Order]:
        raise self._fail()

    async def place_order(self, request: OrderRequest) -> Order:
        raise self._fail()

    async def cancel_order(self, order_id: str) -> Order:
        raise self._fail()

    async def close_position(self, position_id: str, lots: float | None = None) -> Position:
        raise self._fail()


class MT5Broker(_FutureLiveBroker):
    name = "mt5"
    label = "MetaTrader 5"


class InteractiveBrokersBroker(_FutureLiveBroker):
    name = "ibkr"
    label = "Interactive Brokers"


class AlpacaBroker(_FutureLiveBroker):
    name = "alpaca"
    label = "Alpaca"


LIVE_BROKERS: dict[str, type[_FutureLiveBroker]] = {"mt5": MT5Broker, "ibkr": InteractiveBrokersBroker, "alpaca": AlpacaBroker}


def live_trading_gate(env_enabled: bool, ui_switch_on: bool, broker_name: str | None) -> tuple[bool, list[str]]:
    """Return (allowed, reasons). All conditions must hold; default is DISABLED."""
    reasons: list[str] = []
    if not env_enabled:
        reasons.append("LIVE_TRADING_ENABLED is false in the server environment")
    if not ui_switch_on:
        reasons.append("UI live-trading safety switch is off")
    if not broker_name or broker_name not in LIVE_BROKERS:
        reasons.append("No live broker configured")
    else:
        reasons.append(f"{LIVE_BROKERS[broker_name].label} {NOT_IMPLEMENTED}")
    return False, reasons

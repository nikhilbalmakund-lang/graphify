"""Simulated execution model for PAPER TRADING.

* Market buys fill at the ASK, market sells at the BID, plus slippage.
* Limit orders fill when the executable side reaches the limit (no slippage,
  never better than the limit unless the market is already through it).
* Stop orders fill at the executable price once triggered, plus slippage.
* Commission follows the instrument specification (per lot and/or % notional).
"""

from __future__ import annotations

from pydantic import BaseModel

from market_data.models import AssetSpec, Quote
from paper_trading.broker.base import OrderSide, OrderType
from risk.sizing import commission_usd


class FillModel(BaseModel):
    slippage_bps: float = 1.0

    def slippage(self, price: float) -> float:
        return price * self.slippage_bps / 10_000.0

    def executable(self, side: OrderSide, quote: Quote) -> float:
        return quote.ask if side == OrderSide.BUY else quote.bid

    def market_fill(self, side: OrderSide, quote: Quote) -> tuple[float, float]:
        px = self.executable(side, quote)
        slip = self.slippage(px)
        return px + side.sign * slip, slip

    def pending_trigger(
        self, order_type: OrderType, side: OrderSide, level: float, quote: Quote
    ) -> tuple[float, float] | None:
        px = self.executable(side, quote)
        if order_type == OrderType.LIMIT:
            if (side == OrderSide.BUY and px <= level) or (side == OrderSide.SELL and px >= level):
                return (min(px, level) if side == OrderSide.BUY else max(px, level)), 0.0
            return None
        if order_type == OrderType.STOP:
            if (side == OrderSide.BUY and px >= level) or (side == OrderSide.SELL and px <= level):
                slip = self.slippage(px)
                return px + side.sign * slip, slip
            return None
        return None

    def exit_fill(self, direction: int, quote: Quote, level: float | None, kind: str) -> tuple[float, float]:
        """Exit price for a position: stops/market use the executable side with slippage, TPs fill at the level."""
        exit_side = OrderSide.SELL if direction > 0 else OrderSide.BUY
        px = self.executable(exit_side, quote)
        if kind == "TAKE_PROFIT" and level is not None:
            return (max(px, level) if direction > 0 else min(px, level)), 0.0
        slip = self.slippage(px)
        return px + exit_side.sign * slip, slip

    @staticmethod
    def fee(spec: AssetSpec, lots: float, price: float) -> float:
        return commission_usd(spec, lots, price)

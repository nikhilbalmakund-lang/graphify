"""Trade outcome engine: P&L, R multiple, duration, MFE and MAE for a closed position."""

from __future__ import annotations

from pydantic import BaseModel

from paper_trading.broker.base import Position


class TradeOutcome(BaseModel):
    position_id: str
    symbol: str
    direction: int
    pnl: float
    fees: float
    r_multiple: float | None
    duration_seconds: float
    mfe_r: float | None
    mae_r: float | None
    exit_reason: str | None
    result: str  # WIN | LOSS | BREAKEVEN


def compute_outcome(pos: Position) -> TradeOutcome:
    duration = (pos.closed_at - pos.opened_at).total_seconds() if pos.closed_at else 0.0
    r = None
    if pos.risk_usd and pos.risk_usd > 0:
        r = round(pos.realized_pnl / pos.risk_usd, 4)
    mfe = mae = None
    if pos.initial_stop is not None and pos.initial_stop != pos.entry_price:
        unit = abs(pos.entry_price - pos.initial_stop)
        if pos.best_price is not None:
            mfe = round(max(0.0, pos.direction * (pos.best_price - pos.entry_price)) / unit, 3)
        if pos.worst_price is not None:
            mae = round(max(0.0, -pos.direction * (pos.worst_price - pos.entry_price)) / unit, 3)
    eps = max(0.01, abs(pos.realized_pnl) * 1e-6)
    result = "WIN" if pos.realized_pnl > eps else "LOSS" if pos.realized_pnl < -eps else "BREAKEVEN"
    return TradeOutcome(
        position_id=pos.id,
        symbol=pos.symbol,
        direction=pos.direction,
        pnl=pos.realized_pnl,
        fees=pos.fees,
        r_multiple=r,
        duration_seconds=duration,
        mfe_r=mfe,
        mae_r=mae,
        exit_reason=pos.exit_reason,
        result=result,
    )

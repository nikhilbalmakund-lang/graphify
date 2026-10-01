"""Paper trading, portfolio, journal and risk endpoints. Everything here is SIMULATED."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from app.api.deps import get_container, symbol_of
from app.core.container import Container
from app.core.errors import NexusError
from app.schemas.api import JournalOut, JournalPatchIn, KillSwitchIn, ManualTradeIn, PaperOverviewOut
from app.services.ops_service import journal_dict
from paper_trading.broker.base import OrderRequest, PositionStatus
from paper_trading.broker.live import live_trading_gate
from risk.sizing import pnl_usd

router = APIRouter(prefix="/api", tags=["trading"])


@router.get("/paper-trading", response_model=PaperOverviewOut)
async def paper_overview(c: Container = Depends(get_container)) -> dict[str, Any]:
    acct = await c.paper.broker.get_account()
    positions = await c.paper.broker.get_positions(None)
    return {
        "account": acct,
        "positions": [p for p in positions if p.status == PositionStatus.OPEN],
        "closed_positions": [p for p in positions if p.status == PositionStatus.CLOSED][:200],
        "orders": (await c.paper.broker.get_orders())[:200],
        "fills": (await c.paper.store.list_fills(acct.id, 300))[::-1],
        "risk": await c.risk_status(),
        "is_demo_prices": c.market.is_demo,
    }


@router.post("/paper-trading/orders")
async def place_order(req: OrderRequest, c: Container = Depends(get_container)) -> dict[str, Any]:
    req = req.model_copy(update={"symbol": symbol_of(c, req.symbol)})
    order, decision = await c.paper.place(req)
    return {
        "order": order.model_dump(mode="json"),
        "risk": decision.model_dump(mode="json"),
        "simulated": True,
    }


@router.delete("/paper-trading/orders/{order_id}")
async def cancel_order(order_id: str, c: Container = Depends(get_container)) -> dict[str, Any]:
    order = await c.paper.broker.cancel_order(order_id)
    return {"order": order.model_dump(mode="json"), "simulated": True}


@router.post("/paper-trading/positions/{position_id}/close")
async def close_position(
    position_id: str, lots: float | None = Query(None, gt=0), c: Container = Depends(get_container)
) -> dict[str, Any]:
    pos = await c.paper.broker.close_position(position_id, lots)
    return {"position": pos.model_dump(mode="json"), "simulated": True}


@router.post("/paper-trading/kill-switch")
async def kill_switch(body: KillSwitchIn, c: Container = Depends(get_container)) -> dict[str, Any]:
    cancelled = await c.paper.kill_switch(body.active)
    return {"kill_switch": body.active, "cancelled_orders": [o.id for o in cancelled]}


@router.post("/paper-trading/reset")
async def reset(c: Container = Depends(get_container)) -> dict[str, Any]:
    await c.paper.reset()
    return {"reset": True, "account": (await c.paper.broker.get_account()).model_dump(mode="json")}


@router.get("/paper-trading/export.csv", response_class=PlainTextResponse)
async def export_paper(c: Container = Depends(get_container)) -> PlainTextResponse:
    return PlainTextResponse(
        await c.exports.paper_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=nexus-paper-trades.csv"},
    )


@router.get("/portfolio")
async def portfolio(c: Container = Depends(get_container)) -> dict[str, Any]:
    acct = await c.paper.broker.get_account()
    positions = await c.paper.broker.get_positions(PositionStatus.OPEN)
    exposure = await c.paper.broker.exposure()
    snaps = await c.paper.snapshots(2000)
    perf = await c.analytics.performance()
    closed = [p for p in await c.paper.broker.get_positions(PositionStatus.CLOSED)]
    dd = (acct.peak_equity - acct.equity) / acct.peak_equity if acct.peak_equity else 0.0
    return {
        "label": "PAPER PORTFOLIO - SIMULATED",
        "is_demo_prices": c.market.is_demo,
        "account": acct.model_dump(mode="json"),
        "summary": {
            "balance": acct.balance,
            "equity": acct.equity,
            "cash": acct.balance,
            "margin_used": acct.margin_used,
            "free_margin": acct.free_margin,
            "open_pnl": acct.unrealized_pnl,
            "closed_pnl": round(sum(p.realized_pnl for p in closed), 2),
            "daily_pnl": round(acct.equity - acct.day_start_equity, 2),
            "weekly_pnl": round(acct.equity - acct.week_start_equity, 2),
            "drawdown": round(dd, 5),
            "peak_equity": acct.peak_equity,
        },
        "positions": [p.model_dump(mode="json") for p in positions],
        "exposure": [{"symbol": k, "notional": round(v, 2)} for k, v in exposure.items()],
        "equity_curve": [
            {"ts": s.ts.isoformat(), "equity": s.equity, "balance": s.balance, "drawdown": s.drawdown}
            for s in snaps
        ],
        "performance": perf["paper"],
        "risk": await c.risk_status(),
    }


@router.get("/risk/status")
async def risk_status(c: Container = Depends(get_container)) -> dict[str, Any]:
    st = await c.risk_status()
    allowed, reasons = live_trading_gate(
        c.env.live_trading_enabled,
        c.settings.get("live_trading").ui_switch_on,
        c.env.broker if c.env.broker != "paper" else None,
    )
    return {**st, "live_trading": {"allowed": allowed, "reasons": reasons}}


# ------------------------------------------------------------------ journal
@router.get("/journal", response_model=list[JournalOut])
async def journal(
    symbol: str | None = None,
    strategy: str | None = None,
    result: str | None = None,
    regime: str | None = None,
    entry_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(500, ge=1, le=5000),
    c: Container = Depends(get_container),
) -> list[dict[str, Any]]:
    rows = await c.journal.query(
        symbol=symbol_of(c, symbol) if symbol else None,
        strategy=strategy,
        result=result,
        regime=regime,
        entry_type=entry_type,
        start=start,
        end=end,
        limit=limit,
    )
    return [journal_dict(r) for r in rows]


@router.post("/journal", response_model=JournalOut)
async def add_manual(body: ManualTradeIn, c: Container = Depends(get_container)) -> dict[str, Any]:
    """Record a MANUAL trade (taken outside the app). P&L is computed from prices when both are given."""
    sym = symbol_of(c, body.symbol)
    spec = c.catalog.get(sym)
    if body.exit_time and body.exit_time < body.entry_time:
        raise NexusError("VALIDATION_ERROR", "exit_time must be after entry_time")
    d = 1 if body.direction == "LONG" else -1
    pnl = r_mult = None
    result = "OPEN"
    if body.exit_price is not None and body.lots:
        pnl = round(pnl_usd(spec, d, body.entry_price, body.exit_price, body.lots) - body.fees, 2)
        result = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "BREAKEVEN"
        if body.stop:
            risk = abs(pnl_usd(spec, d, body.entry_price, body.stop, body.lots))
            r_mult = round(pnl / risk, 4) if risk > 0 else None
    row = await c.journal.add(
        entry_type="MANUAL_TRADE",
        symbol=sym,
        timeframe=None,
        direction=body.direction,
        strategy=body.strategy or "Manual",
        regime=body.regime,
        signal_score=None,
        entry_time=body.entry_time,
        exit_time=body.exit_time,
        entry_price=body.entry_price,
        exit_price=body.exit_price,
        stop=body.stop,
        lots=body.lots,
        fees=body.fees,
        pnl=pnl,
        r_multiple=r_mult,
        duration_seconds=(body.exit_time - body.entry_time).total_seconds() if body.exit_time else None,
        result=result,
        notes=body.notes,
        tags=body.tags,
        is_demo=False,
    )
    return journal_dict(row)


@router.patch("/journal/{entry_id}", response_model=JournalOut)
async def patch_journal(
    entry_id: str, body: JournalPatchIn, c: Container = Depends(get_container)
) -> dict[str, Any]:
    return journal_dict(await c.journal.patch(entry_id, body.notes, body.tags))


@router.get("/journal/export.csv", response_class=PlainTextResponse)
async def export_journal(c: Container = Depends(get_container)) -> PlainTextResponse:
    return PlainTextResponse(
        await c.exports.journal_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=nexus-journal.csv"},
    )


@router.get("/analytics/performance")
async def performance(c: Container = Depends(get_container)) -> dict[str, Any]:
    return await c.analytics.performance()

"""Strategy lab, backtests, walk-forward, ML calibration endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from app.api.deps import get_container, symbol_of
from app.core.container import Container
from app.schemas.api import BacktestIn, WalkForwardIn
from backtesting.engine.engine import BacktestConfig
from backtesting.validation.walk_forward import WalkForwardConfig

router = APIRouter(prefix="/api", tags=["research"])


@router.get("/strategies")
async def strategies(c: Container = Depends(get_container)) -> list[dict[str, Any]]:
    return c.research.strategies()


@router.get("/strategies/performance")
async def strategy_performance(c: Container = Depends(get_container)) -> dict[str, Any]:
    return {
        "rows": await c.research.regime_performance(),
        "note": "Historical performance by regime describes past (often simulated) results only; it is not a guarantee.",
    }


@router.post("/backtests")
async def run_backtest(body: BacktestIn, c: Container = Depends(get_container)) -> dict[str, Any]:
    cfg = BacktestConfig.model_validate(body.model_dump(exclude={"data_source"}))
    cfg = cfg.model_copy(update={"symbol": symbol_of(c, cfg.symbol)})
    return await c.research.run_backtest(cfg, body.data_source)


@router.post("/backtests/walk-forward")
async def run_walk_forward(body: WalkForwardIn, c: Container = Depends(get_container)) -> dict[str, Any]:
    wf = WalkForwardConfig.model_validate(body.model_dump(exclude={"data_source"}))
    wf.backtest.symbol = symbol_of(c, wf.backtest.symbol)
    return await c.research.run_walk_forward(wf, body.data_source)


@router.get("/backtests")
async def list_backtests(
    limit: int = Query(50, ge=1, le=500), c: Container = Depends(get_container)
) -> list[dict[str, Any]]:
    return await c.research.list_backtests(limit)


@router.get("/backtests/{bt_id}")
async def get_backtest(bt_id: str, c: Container = Depends(get_container)) -> dict[str, Any]:
    return await c.research.get(bt_id)


@router.get("/backtests/{bt_id}/trades.csv", response_class=PlainTextResponse)
async def backtest_csv(bt_id: str, c: Container = Depends(get_container)) -> PlainTextResponse:
    return PlainTextResponse(
        await c.exports.backtest_csv(bt_id),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=nexus-{bt_id}.csv"},
    )


@router.post("/strategies/ml/train")
async def train_ml(c: Container = Depends(get_container)) -> dict[str, Any]:
    """Train and validate the TP1-before-SL model. Its output is shown as a probability only if calibration passes."""
    return (await c.memory.train_model()).model_dump(mode="json")


@router.get("/strategies/ml")
async def ml_status(c: Container = Depends(get_container)) -> dict[str, Any]:
    return {"report": await c.memory.latest_report(), "loaded": c.memory.model.report is not None}

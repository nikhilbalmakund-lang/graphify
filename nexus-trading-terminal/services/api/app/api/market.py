"""Market data endpoints: assets, quotes, candles, features, regime, structure, MTF, overview, import."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.api.deps import get_container, symbol_of, timeframe_of
from app.core.container import Container
from app.core.errors import NexusError
from app.schemas.api import AssetOut, CandlesOut
from market_data.models import Quote
from market_data.sessions import is_open
from quant.features.feature_set import FeatureSnapshot
from quant.mtf.alignment import MTFAnalysis
from quant.regime.detector import RegimeResult
from quant.structure.engine import StructureSnapshot

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/assets", response_model=list[AssetOut])
async def assets(c: Container = Depends(get_container)) -> list[dict[str, Any]]:
    now = c.market.now()
    out = []
    for a in c.catalog.all():
        open_, reason = is_open(a.session, now)
        out.append(
            {
                "symbol": a.symbol,
                "name": a.name,
                "asset_class": a.asset_class.value,
                "session": a.session.value,
                "price_precision": a.price_precision,
                "pip_size": a.pip_size,
                "contract_size": a.contract_size,
                "min_lot": a.min_lot,
                "lot_step": a.lot_step,
                "max_leverage": a.max_leverage,
                "typical_spread": a.typical_spread,
                "currencies": a.currencies,
                "market_open": open_,
                "market_status": reason,
            }
        )
    return out


@router.get("/quotes", response_model=list[Quote])
async def quotes(
    symbols: str | None = Query(None, description="Comma-separated symbols"),
    c: Container = Depends(get_container),
) -> list[Quote]:
    syms = (
        [symbol_of(c, s) for s in symbols.split(",")] if symbols else c.settings.get("markets").default_assets
    )
    return await c.market_service.quotes(syms)


@router.get("/candles", response_model=CandlesOut)
async def candles(
    symbol: str,
    timeframe: str = "15m",
    limit: int = Query(500, ge=10, le=5000),
    c: Container = Depends(get_container),
) -> dict[str, Any]:
    return await c.market_service.candles_payload(symbol_of(c, symbol), timeframe_of(timeframe), limit)


@router.get("/features", response_model=FeatureSnapshot)
async def features(
    symbol: str, timeframe: str = "15m", c: Container = Depends(get_container)
) -> FeatureSnapshot:
    bundle, _, _ = await c.market_service.bundle(symbol_of(c, symbol), timeframe_of(timeframe))
    return bundle.features()


@router.get("/regime", response_model=RegimeResult)
async def regime(symbol: str, timeframe: str = "1H", c: Container = Depends(get_container)) -> RegimeResult:
    bundle, _, _ = await c.market_service.bundle(symbol_of(c, symbol), timeframe_of(timeframe))
    return bundle.regime()


@router.get("/structure", response_model=StructureSnapshot)
async def structure(
    symbol: str, timeframe: str = "15m", c: Container = Depends(get_container)
) -> StructureSnapshot:
    bundle, _, _ = await c.market_service.bundle(symbol_of(c, symbol), timeframe_of(timeframe))
    return bundle.structure()


@router.get("/mtf", response_model=MTFAnalysis)
async def mtf(symbol: str, timeframe: str = "15m", c: Container = Depends(get_container)) -> MTFAnalysis:
    return await c.market_service.mtf(symbol_of(c, symbol), timeframe_of(timeframe))


@router.get("/overlays")
async def overlays(
    symbol: str, timeframe: str = "15m", c: Container = Depends(get_container)
) -> dict[str, Any]:
    """Indicator series, structure, swing and BOS/CHoCH markers for the chart."""
    return await c.market_service.overlays(symbol_of(c, symbol), timeframe_of(timeframe))


@router.get("/overview")
async def overview(timeframe: str = "1H", c: Container = Depends(get_container)) -> dict[str, Any]:
    cards = await c.market_service.overview(c.settings.get("markets").default_assets, timeframe_of(timeframe))
    return {**c.market_service.meta(), "cards": cards}


@router.get("/status")
async def market_status(c: Container = Depends(get_container)) -> dict[str, Any]:
    return c.market.status()


@router.post("/import")
async def import_csv(
    file: UploadFile = File(...),
    symbol: str = Form(...),
    timeframe: str = Form(...),
    c: Container = Depends(get_container),
) -> dict[str, Any]:
    """Import historical OHLCV CSV (columns: timestamp, open, high, low, close, volume). Invalid data is rejected."""
    content = await file.read(20 * 1024 * 1024 + 1)
    if len(content) > 20 * 1024 * 1024:
        raise NexusError("VALIDATION_ERROR", "CSV larger than 20 MB")
    return await c.research.import_csv(
        content, symbol_of(c, symbol), timeframe_of(timeframe), file.filename or "upload.csv"
    )


@router.get("/imports")
async def imports(c: Container = Depends(get_container)) -> list[dict[str, Any]]:
    return await c.research.imports()

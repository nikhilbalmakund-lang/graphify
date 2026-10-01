"""Signals, scanner and historical-evidence endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from app.api.deps import get_container, symbol_of, timeframe_of
from app.core.container import Container
from app.schemas.api import GenerateSignalIn, SignalDetailOut, SignalOut

router = APIRouter(prefix="/api", tags=["signals"])


@router.get("/signals", response_model=list[SignalOut])
async def list_signals(
    status: str | None = None,
    symbol: str | None = None,
    direction: str | None = None,
    active: bool = False,
    limit: int = Query(100, ge=1, le=1000),
    c: Container = Depends(get_container),
) -> list[dict[str, Any]]:
    return await c.signals.query(
        status=status,
        symbol=symbol_of(c, symbol) if symbol else None,
        direction=direction,
        active_only=active,
        limit=limit,
    )


@router.post("/signals/generate", response_model=SignalDetailOut)
async def generate(body: GenerateSignalIn, c: Container = Depends(get_container)) -> dict[str, Any]:
    """Run the full pipeline for one instrument (quant -> optional Claude+Gemini -> critic -> evidence -> risk)."""
    return await c.signals.generate(
        symbol_of(c, body.symbol),
        timeframe_of(body.timeframe),
        use_ai=body.use_ai,
        source="manual",
        force=body.force,
    )


@router.get("/signals/export.csv", response_class=PlainTextResponse)
async def export_signals(c: Container = Depends(get_container)) -> PlainTextResponse:
    return PlainTextResponse(
        await c.exports.signals_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=nexus-signals.csv"},
    )


@router.get("/signals/stats")
async def signal_stats(c: Container = Depends(get_container)) -> dict[str, int]:
    return await c.signals.counts()


@router.get("/signals/{signal_id}", response_model=SignalDetailOut)
async def get_signal(signal_id: str, c: Container = Depends(get_container)) -> dict[str, Any]:
    return await c.signals.detail(signal_id)


@router.post("/signals/{signal_id}/explain")
async def explain(signal_id: str, c: Container = Depends(get_container)) -> dict[str, Any]:
    return await c.ai.explain(await c.signals.detail(signal_id))


@router.get("/signals/{signal_id}/similar")
async def similar(
    signal_id: str, k: int = Query(50, ge=10, le=100), c: Container = Depends(get_container)
) -> dict[str, Any]:
    sig = await c.signals.detail(signal_id)
    vec = None
    from quant.features.feature_set import FeatureSnapshot, similarity_vector

    if sig.get("analysis"):
        vec = similarity_vector(FeatureSnapshot.model_validate(sig["analysis"]["features"]))
    if vec is None:
        return {"summary": None, "matches": [], "note": "Similarity features unavailable for this signal"}
    summary, rows = await c.memory.conditions(
        sig["symbol"], sig["timeframe"], vec, sig["regime"], sig["is_demo"], k
    )
    return {"summary": summary.model_dump(), "matches": rows}


@router.post("/signals/{signal_id}/paper")
async def execute_on_paper(signal_id: str, c: Container = Depends(get_container)) -> dict[str, Any]:
    """Send an active signal to the PAPER broker (SIMULATED) after a risk-engine check."""
    order, decision = await c.paper.execute_signal(await c.signals.get_row(signal_id))
    return {
        "order": order.model_dump(mode="json"),
        "risk": decision.model_dump(mode="json"),
        "simulated": True,
    }


@router.get("/scanner")
async def scanner(
    timeframe: str = "15m",
    min_score: float = Query(0, ge=0, le=100),
    min_rr: float = Query(0, ge=0),
    max_vol_percentile: float = Query(100, ge=0, le=100),
    exclude_news_risk: bool = False,
    regime: str | None = None,
    only_signals: bool = False,
    sort: str = "score",
    c: Container = Depends(get_container),
) -> dict[str, Any]:
    rows = await c.scanner.scan(timeframe_of(timeframe), c.settings.get("markets").default_assets)
    ok = [r for r in rows if r.get("status") == "OK"]
    filtered = [
        r
        for r in ok
        if r["score"] >= min_score
        and (r["rr"] or 0) >= min_rr
        and (r["vol_percentile"] is None or r["vol_percentile"] <= max_vol_percentile)
        and not (exclude_news_risk and r["news_risk"])
        and (regime is None or r["regime"] == regime)
        and (not only_signals or r["direction"] in ("LONG", "SHORT"))
    ]
    key = sort if sort in ("score", "rr", "change_pct_24h", "vol_percentile", "symbol") else "score"
    filtered.sort(key=lambda r: (r.get(key) is None, r.get(key) if key == "symbol" else -(r.get(key) or 0)))
    return {
        "timeframe": timeframe,
        **c.market_service.meta(),
        "rows": filtered,
        "errors": [r for r in rows if r.get("status") != "OK"],
        "note": "Ranked by rules-based signal score. Top setups are not predictions and are not guaranteed to work.",
    }


@router.get("/history/conditions")
async def conditions(
    symbol: str,
    timeframe: str = "1H",
    k: int = Query(50, ge=10, le=100),
    c: Container = Depends(get_container),
) -> dict[str, Any]:
    """What happened the last k times conditions looked like this?"""
    return await c.ai.history_query(symbol_of(c, symbol), timeframe_of(timeframe), k)


@router.get("/history/memory")
async def memory_stats(c: Container = Depends(get_container)) -> dict[str, Any]:
    return await c.memory.stats()

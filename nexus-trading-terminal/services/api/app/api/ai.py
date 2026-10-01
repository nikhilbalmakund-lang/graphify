"""AI endpoints: analyst chat, on-demand analysis, research workspace, chart scanner, briefings, model analytics."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile

from ai.orchestration.chat import ChatTurn
from ai.prompts.registry import PROMPTS
from app.api.deps import get_container, symbol_of, timeframe_of
from app.core.container import Container
from app.core.errors import NexusError
from app.schemas.api import ChatIn, HistoryQueryIn, SignalDetailOut, SymbolTimeframeIn

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/chat")
async def chat(body: ChatIn, c: Container = Depends(get_container)) -> dict[str, Any]:
    """AI analyst. Uses read-only internal tools; the answer separates facts, calculations, interpretation, uncertainty."""
    return await c.ai.chat(body.question, [ChatTurn(role=t.role, content=t.content) for t in body.history])


@router.post("/analyze", response_model=SignalDetailOut)
async def analyze(body: SymbolTimeframeIn, c: Container = Depends(get_container)) -> dict[str, Any]:
    """Run the full signal pipeline with the AI stage forced on (Claude + Gemini + critic when configured)."""
    return await c.signals.generate(
        symbol_of(c, body.symbol), timeframe_of(body.timeframe), use_ai=True, source="ai_analyze", force=True
    )


@router.post("/research")
async def research(body: SymbolTimeframeIn, c: Container = Depends(get_container)) -> dict[str, Any]:
    return await c.ai.research(symbol_of(c, body.symbol), timeframe_of(body.timeframe))


@router.post("/chart-scan")
async def chart_scan(
    file: UploadFile = File(...), symbol: str | None = Form(None), c: Container = Depends(get_container)
) -> dict[str, Any]:
    """IMAGE ANALYSIS of an uploaded chart screenshot. Never equivalent to exchange/broker data."""
    limit = c.env.max_upload_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise NexusError("VALIDATION_ERROR", f"Image larger than {c.env.max_upload_mb} MB")
    return await c.ai.chart_scan(content, (file.content_type or "").lower(), symbol)


@router.get("/briefing")
async def latest_briefing(c: Container = Depends(get_container)) -> dict[str, Any]:
    return {"briefing": await c.ai.latest_briefing()}


@router.post("/briefing")
async def generate_briefing(
    session: str | None = None, force: bool = False, c: Container = Depends(get_container)
) -> dict[str, Any]:
    return {"briefing": await c.ai.briefing(session, force)}


@router.post("/history-query")
async def history_query(body: HistoryQueryIn, c: Container = Depends(get_container)) -> dict[str, Any]:
    return await c.ai.history_query(symbol_of(c, body.symbol), timeframe_of(body.timeframe), body.k)


@router.get("/analytics")
async def analytics(c: Container = Depends(get_container)) -> dict[str, Any]:
    return await c.ai.model_analytics()


@router.get("/prompts")
async def prompts() -> list[dict[str, Any]]:
    return [
        {
            "name": p.name,
            "version": p.version,
            "date": p.date,
            "task": p.task,
            "tier": p.tier,
            "output_schema": p.output_schema,
            "temperature": p.temperature,
            "claude_effort": p.claude_effort,
        }
        for p in PROMPTS.values()
    ]


@router.get("/status")
async def ai_status(c: Container = Depends(get_container)) -> dict[str, Any]:
    return {
        "providers": {k: v.model_dump(mode="json") for k, v in c.ai_status.items()},
        "routing": c.router.table(),
        "fallback": "Rule-based demo summaries are used where possible when no AI provider is configured; they are labelled as non-AI.",
    }

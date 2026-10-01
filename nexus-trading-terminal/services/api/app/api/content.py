"""News, economic calendar, heatmap and market psychology endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_container, symbol_of
from app.core.container import Container
from app.schemas.api import EventOut, NewsOut
from app.services.ai_budget import budgeted_providers

router = APIRouter(prefix="/api", tags=["content"])


def _news(r: Any) -> dict[str, Any]:
    return {
        "id": r.id,
        "headline": r.headline,
        "summary": r.summary,
        "source": r.source,
        "url": r.url,
        "published_at": r.published_at.isoformat(),
        "symbols": r.symbols,
        "countries": r.countries,
        "sentiment": r.sentiment,
        "sentiment_source": r.sentiment_source,
        "sentiment_rationale": r.sentiment_rationale,
        "importance": r.importance,
        "provider": r.provider,
        "is_demo": r.is_demo,
    }


@router.get("/news", response_model=list[NewsOut])
async def news(
    symbol: str | None = None, limit: int = Query(50, ge=1, le=200), c: Container = Depends(get_container)
) -> list[dict[str, Any]]:
    rows = await c.content.list_news(symbol_of(c, symbol) if symbol else None, limit)
    return [_news(r) for r in rows]


@router.post("/news/refresh")
async def refresh_news(c: Container = Depends(get_container)) -> dict[str, Any]:
    providers, _ = await budgeted_providers(c)
    n = await c.content.refresh_news(providers, c.settings.get("ai").ai_news_sentiment)
    return {
        "new_items": n,
        "provider": c.content.news_provider.name,
        "is_demo": c.content.news_provider.is_demo,
    }


@router.get("/calendar", response_model=list[EventOut])
async def calendar(
    hours_back: int = Query(24, ge=0, le=720),
    hours_ahead: int = Query(168, ge=1, le=720),
    impact: str | None = Query(None, pattern="^(LOW|MEDIUM|HIGH)$"),
    currency: str | None = Query(None, max_length=8),
    c: Container = Depends(get_container),
) -> list[dict[str, Any]]:
    rows = await c.content.list_events(hours_back, hours_ahead, impact, currency)
    return c.content.events_payload(rows)


@router.get("/calendar/risk/{symbol}")
async def calendar_risk(symbol: str, c: Container = Depends(get_container)) -> dict[str, Any]:
    return (await c.content.event_risk(symbol_of(c, symbol))).model_dump()


@router.get("/heatmap")
async def heatmap(
    asset_class: str | None = Query(None, pattern="^(FOREX|CRYPTO|INDICES|COMMODITIES)$"),
    c: Container = Depends(get_container),
) -> dict[str, Any]:
    syms = [a.symbol for a in c.catalog.all() if asset_class is None or a.asset_class.value == asset_class]
    rows = await c.market_service.heatmap(syms, await c.signals.latest_scores())
    return {**c.market_service.meta(), "asset_class": asset_class, "rows": rows}


@router.get("/psychology")
async def psychology(c: Container = Depends(get_container)) -> dict[str, Any]:
    return await c.market_service.psychology(c.catalog.symbols())


@router.get("/correlations")
async def correlations(
    days: int = Query(60, ge=20, le=250), c: Container = Depends(get_container)
) -> dict[str, Any]:
    return {**c.market_service.meta(), **(await c.market_service.correlations(c.catalog.symbols(), days))}

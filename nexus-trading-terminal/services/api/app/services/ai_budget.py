"""Daily AI call cap shared by every AI entry point (signals, chat, research,
briefings, explanations, chart scans, news sentiment)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from app.models import AICall


async def ai_calls_today(db: Any) -> int:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    async with db.session() as s:
        used = await s.scalar(
            select(func.count())
            .select_from(AICall)
            .where(AICall.created_at >= start, AICall.cached.is_(False))
        )
    return int(used or 0)


async def ai_budget_left(db: Any, settings: Any) -> bool:
    return await ai_calls_today(db) < settings.get("ai").max_calls_per_day


async def budgeted_providers(c: Any) -> tuple[list[Any], list[str]]:
    """Configured providers, or none (plus a warning) once today's cap is used up."""
    providers = c.ai_providers()
    if providers and not await ai_budget_left(c.db, c.settings):
        limit = c.settings.get("ai").max_calls_per_day
        return [], [
            f"Daily AI call cap reached ({limit} calls). AI providers are paused until 00:00 UTC; "
            "rule-based fallbacks are used where available."
        ]
    return providers, []

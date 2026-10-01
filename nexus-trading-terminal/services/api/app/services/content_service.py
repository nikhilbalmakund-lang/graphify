"""News and economic calendar: fetch, normalise, persist, classify sentiment, assess event risk."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, select

from ai.orchestration.services import NewsClassifier
from ai.providers.base import AIProvider, AIProviderError
from app.core.database import Database, utcnow
from app.models import EconomicEvent, NewsItem
from app.providers.calendar import EconomicCalendarProvider
from app.providers.news import NewsProvider
from market_data.assets import AssetCatalog
from market_data.models import ProviderHealth
from market_data.providers.base import MarketDataError
from quant.signals.models import EventRisk, SentimentContext

logger = logging.getLogger("nexus.content")
SENTIMENT_VALUE = {"BULLISH": 1.0, "BEARISH": -1.0, "NEUTRAL": 0.0, "UNCERTAIN": 0.0}
IMPORTANCE_WEIGHT = {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.3}


class ContentService:
    def __init__(
        self,
        db: Database,
        catalog: AssetCatalog,
        news: NewsProvider,
        calendar: EconomicCalendarProvider,
        clock: Any,
    ):
        self.db = db
        self.catalog = catalog
        self.news_provider = news
        self.calendar_provider = calendar
        self.clock = clock
        self.news_health = ProviderHealth(
            provider=news.name,
            status="DEMO" if news.is_demo else "CONFIGURED_UNVERIFIED",
            is_demo=news.is_demo,
        )
        self.calendar_health = ProviderHealth(
            provider=calendar.name,
            status="DEMO" if calendar.is_demo else "CONFIGURED_UNVERIFIED",
            is_demo=calendar.is_demo,
        )
        self.last_news_refresh: datetime | None = None
        self.last_calendar_refresh: datetime | None = None

    async def validate(self) -> None:
        self.news_health = await self.news_provider.validate()
        self.calendar_health = await self.calendar_provider.validate()

    # --------------------------------------------------------------- news
    async def refresh_news(self, providers: list[AIProvider], use_ai: bool) -> int:
        try:
            articles = await self.news_provider.fetch(60)
        except MarketDataError as exc:
            self.news_health = ProviderHealth(
                provider=self.news_provider.name, status="DISCONNECTED", is_demo=False, detail=exc.message
            )
            raise
        new_rows: list[NewsItem] = []
        async with self.db.session() as s:
            for a in articles:
                exists = await s.scalar(
                    select(NewsItem.id).where(
                        NewsItem.provider == a.provider, NewsItem.external_id == a.external_id
                    )
                )
                if exists:
                    continue
                row = NewsItem(
                    id=f"news_{uuid.uuid4().hex[:16]}",
                    external_id=a.external_id,
                    headline=a.headline,
                    summary=a.summary,
                    source=a.source,
                    url=a.url,
                    published_at=a.published_at,
                    symbols=a.symbols,
                    countries=a.countries,
                    importance=a.importance,
                    provider=a.provider,
                    is_demo=a.is_demo,
                    data_change_pct=a.data_change_pct,
                    fetched_at=utcnow(),
                )
                s.add(row)
                new_rows.append(row)
        if new_rows:
            await self.classify(new_rows, providers if use_ai else [])
        self.last_news_refresh = utcnow()
        return len(new_rows)

    async def classify(self, rows: list[NewsItem], providers: list[AIProvider]) -> None:
        payload = {
            "items": [
                {
                    "id": r.id,
                    "headline": r.headline,
                    "symbols": r.symbols,
                    "data_change_pct": r.data_change_pct,
                }
                for r in rows
            ]
        }
        # Demo items carry a measured price change: classify them with the transparent rule, never with AI.
        use_ai = providers and not all(r.is_demo for r in rows)
        try:
            res, _ = await NewsClassifier(providers if use_ai else []).classify(payload)
        except AIProviderError as exc:
            logger.warning(
                "news_sentiment_failed",
                extra={"event": "news_sentiment_failed", "data": {"error": exc.message}},
            )
            return
        by_id = {i["id"]: i for i in res.data.get("items", [])}
        source = "rule-based" if res.is_demo else f"ai:{res.provider}:{res.model}"
        async with self.db.session() as s:
            for r in rows:
                item = by_id.get(r.id)
                if not item:
                    continue
                row = await s.get(NewsItem, r.id)
                if row:
                    row.sentiment, row.sentiment_rationale, row.sentiment_source = (
                        item["sentiment"],
                        item["rationale"],
                        source,
                    )

    async def list_news(self, symbol: str | None = None, limit: int = 50) -> list[NewsItem]:
        cap = min(limit, 200)
        async with self.db.session() as s:
            q = select(NewsItem).order_by(NewsItem.published_at.desc()).limit(cap * 5 if symbol else cap)
            rows = list((await s.execute(q)).scalars())
        if symbol:  # JSON-array membership filtered in Python for portability across SQLite/PostgreSQL
            rows = [r for r in rows if symbol in (r.symbols or [])][:cap]
        return rows

    async def sentiment(self, symbol: str, hours: int = 24) -> SentimentContext:
        since = self.clock() - timedelta(hours=hours)
        rows = [r for r in await self.list_news(symbol, 100) if r.published_at >= since and r.sentiment]
        if not rows:
            return SentimentContext(
                available=False, is_demo=self.news_provider.is_demo, source=self.news_provider.name
            )
        wsum = sum(IMPORTANCE_WEIGHT.get(r.importance, 0.5) for r in rows)
        score = (
            sum(
                SENTIMENT_VALUE.get(r.sentiment or "", 0.0) * IMPORTANCE_WEIGHT.get(r.importance, 0.5)
                for r in rows
            )
            / wsum
        )
        return SentimentContext(
            available=True,
            score=round(score, 3),
            articles=len(rows),
            is_demo=all(r.is_demo for r in rows),
            source=self.news_provider.name,
        )

    # ----------------------------------------------------------- calendar
    async def refresh_calendar(self, days_back: int = 2, days_ahead: int = 8) -> int:
        now = self.clock()
        try:
            events = await self.calendar_provider.fetch(
                now - timedelta(days=days_back), now + timedelta(days=days_ahead)
            )
        except MarketDataError as exc:
            self.calendar_health = ProviderHealth(
                provider=self.calendar_provider.name, status="DISCONNECTED", is_demo=False, detail=exc.message
            )
            raise
        n = 0
        async with self.db.session() as s:
            for e in events:
                row = await s.scalar(
                    select(EconomicEvent).where(
                        EconomicEvent.provider == e.provider, EconomicEvent.external_id == e.external_id
                    )
                )
                if row is None:
                    s.add(
                        EconomicEvent(
                            id=f"evt_{uuid.uuid4().hex[:16]}",
                            external_id=e.external_id,
                            event=e.event,
                            currency=e.currency,
                            country=e.country,
                            scheduled_at=e.scheduled_at,
                            impact=e.impact,
                            previous=e.previous,
                            forecast=e.forecast,
                            actual=e.actual,
                            source=e.source,
                            provider=e.provider,
                            is_demo=e.is_demo,
                            fetched_at=utcnow(),
                        )
                    )
                    n += 1
                else:
                    row.actual, row.forecast, row.previous, row.fetched_at = (
                        e.actual,
                        e.forecast,
                        e.previous,
                        utcnow(),
                    )
        self.last_calendar_refresh = utcnow()
        return n

    async def list_events(
        self,
        hours_back: int = 24,
        hours_ahead: int = 168,
        impact: str | None = None,
        currency: str | None = None,
    ) -> list[EconomicEvent]:
        now = self.clock()
        async with self.db.session() as s:
            q = select(EconomicEvent).where(
                and_(
                    EconomicEvent.scheduled_at >= now - timedelta(hours=hours_back),
                    EconomicEvent.scheduled_at <= now + timedelta(hours=hours_ahead),
                ),
                EconomicEvent.provider == self.calendar_provider.name,
            )
            if impact:
                q = q.where(EconomicEvent.impact == impact.upper())
            if currency:
                q = q.where(EconomicEvent.currency == currency.upper())
            return list((await s.execute(q.order_by(EconomicEvent.scheduled_at))).scalars())

    async def event_risk(self, symbol: str) -> EventRisk:
        spec = self.catalog.get(symbol)
        ccys = set(spec.currencies) | ({"USD"} if spec.symbol == "USOIL" else set())
        now = self.clock()
        async with self.db.session() as s:
            q = select(EconomicEvent).where(
                EconomicEvent.provider == self.calendar_provider.name,
                EconomicEvent.impact == "HIGH",
                EconomicEvent.currency.in_(ccys),
                EconomicEvent.scheduled_at >= now - timedelta(hours=6),
                EconomicEvent.scheduled_at <= now + timedelta(hours=48),
            )
            rows = list((await s.execute(q)).scalars())
        if self.last_calendar_refresh is None and not rows:
            return EventRisk(
                available=False, is_demo=self.calendar_provider.is_demo, detail="Calendar not loaded"
            )
        upcoming = sorted((r for r in rows if r.scheduled_at >= now), key=lambda r: r.scheduled_at)
        past = sorted((r for r in rows if r.scheduled_at < now), key=lambda r: r.scheduled_at, reverse=True)
        nxt = upcoming[0] if upcoming else None
        rec = past[0] if past else None
        return EventRisk(
            available=True,
            is_demo=self.calendar_provider.is_demo,
            next_high_impact_minutes=round((nxt.scheduled_at - now).total_seconds() / 60, 1) if nxt else None,
            next_high_impact_event=f"{nxt.event} ({nxt.currency})" if nxt else None,
            recent_high_impact_minutes=round((now - rec.scheduled_at).total_seconds() / 60, 1)
            if rec
            else None,
            detail=f"{len(upcoming)} high-impact events in the next 48h for {', '.join(sorted(ccys))}",
        )

    def events_payload(self, rows: list[EconomicEvent]) -> list[dict[str, Any]]:
        now = self.clock()
        return [
            {
                "id": r.id,
                "event": r.event,
                "currency": r.currency,
                "country": r.country,
                "time": r.scheduled_at.isoformat(),
                "impact": r.impact,
                "previous": r.previous,
                "forecast": r.forecast,
                "actual": r.actual,
                "source": r.source,
                "provider": r.provider,
                "is_demo": r.is_demo,
                "minutes_until": round((r.scheduled_at - now).total_seconds() / 60, 1),
            }
            for r in rows
        ]

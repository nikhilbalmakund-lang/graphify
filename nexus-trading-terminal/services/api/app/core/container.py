"""Service container: builds and wires every component once per process."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from ai.orchestration.analysts import AIReviewOrchestrator
from ai.orchestration.router import ModelRouter
from ai.providers.base import AIProvider, AIStatus, ProviderHealthInfo
from ai.providers.claude.provider import ClaudeProvider
from ai.providers.gemini.provider import GeminiProvider
from app.core.cache import CacheBackend, InMemoryCache, create_cache
from app.core.config import PROJECT_ROOT, Settings, get_settings
from app.core.database import Database
from app.providers.calendar import DemoEconomicProvider, EconomicCalendarProvider, FMPCalendarProvider
from app.providers.market import MarketDataManager
from app.providers.news import DemoNewsProvider, FinnhubNewsProvider, NewsProvider
from app.services.ai_service import AIService
from app.services.audit_service import SYSTEM, AuditService
from app.services.background import TaskManager, start_background
from app.services.content_service import ContentService
from app.services.market_service import MarketService
from app.services.memory_service import MemoryService
from app.services.ops_service import AlertService, AnalyticsService, ExportService, SearchService
from app.services.research_service import ResearchService, ScannerService
from app.services.settings_service import SecretsService, SettingsService
from app.services.signal_service import SignalService
from app.services.trading_service import JournalService, PaperService
from app.websocket.manager import ConnectionManager
from market_data.assets import AssetCatalog
from market_data.providers.demo import DemoMarketDataProvider
from risk.engine import RiskEngine

logger = logging.getLogger("nexus.container")
ALEMBIC_INI = PROJECT_ROOT / "database" / "alembic.ini"


def run_migrations(sync_url: str, ini: Path = ALEMBIC_INI) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ini))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")


class Container:
    def __init__(
        self,
        env: Settings | None = None,
        db: Database | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.env = env or get_settings()
        env = self.env
        self.catalog = AssetCatalog(symbol_overrides=env.symbol_overrides())
        self.specs = {a.symbol: a for a in self.catalog.all()}
        self.db = db or Database(env.resolved_database_url)
        self.ws = ConnectionManager()
        self.cache: CacheBackend = InMemoryCache()
        self.audit = AuditService(self.db, self.ws)
        self.settings = SettingsService(self.db, env)
        self.secrets = SecretsService()
        demo = DemoMarketDataProvider(self.catalog, clock=clock)
        self.market = MarketDataManager(
            self.catalog,
            env.market_data_provider,
            env.secret("market_data_api_key"),
            env.market_data_ttl_multiplier,
            demo=demo,
        )
        self.market_service = MarketService(self.market, self.catalog)
        self.content = ContentService(
            self.db, self.catalog, self._news_provider(demo), self._calendar_provider(), self.market.now
        )
        self.journal = JournalService(self.db)
        self.paper = PaperService(
            self.db,
            self.market_service,
            self.catalog,
            self.risk_engine,
            self.audit,
            self.ws,
            self.journal,
            self.settings,
            event_risk=self.content.event_risk,
        )
        self.memory = MemoryService(self.db, self.market)
        self.ai_status: dict[str, ProviderHealthInfo] = {}
        self._build_ai()
        self.signals = SignalService(
            self.db,
            self.market_service,
            self.content,
            self.memory,
            self.paper,
            self.journal,
            self.audit,
            self.ws,
            self.settings,
            self.cache,
            self.orchestrator,
            self.ai_configured,
        )
        self.research = ResearchService(self.db, self.market_service, self.ws)
        self.scanner = ScannerService(self.signals, self.market_service, self.content, self.settings)
        self.ai = AIService(self)
        self.alerts = AlertService(self)
        self.search = SearchService(self)
        self.exports = ExportService(self)
        self.analytics = AnalyticsService(self)
        self.tasks: TaskManager | None = None
        self.started_at: datetime | None = None

    # ------------------------------------------------------------ builders
    def _news_provider(self, demo: DemoMarketDataProvider) -> NewsProvider:
        key = self.env.secret("news_api_key")
        if self.env.news_provider == "finnhub" and key:
            return FinnhubNewsProvider(key)
        return DemoNewsProvider(demo, self.catalog)

    def _calendar_provider(self) -> EconomicCalendarProvider:
        key = self.env.secret("economic_calendar_api_key")
        if self.env.economic_calendar_provider == "fmp" and key:
            return FMPCalendarProvider(key)
        return DemoEconomicProvider(clock=self.market.now)

    def _build_ai(self) -> None:
        env = self.env
        self.router = ModelRouter(
            models={
                "claude": {"fast": env.claude_model_fast, "strong": env.claude_model_strong},
                "gemini": {"fast": env.gemini_model_fast, "strong": env.gemini_model_strong},
            }
        )
        self.claude = ClaudeProvider(
            self.router, env.secret("anthropic_api_key"), refusal_fallback=env.claude_refusal_fallback
        )
        self.gemini = GeminiProvider(self.router, env.secret("gemini_api_key"))

    def ai_providers(self) -> list[AIProvider]:
        """Configured providers, excluding any whose credentials failed validation."""
        out: list[AIProvider] = []
        for p in (self.claude, self.gemini):
            st = self.ai_status.get(p.name)
            if p.configured and (st is None or st.status != AIStatus.ERROR):
                out.append(p)
        return out

    def ai_configured(self) -> bool:
        return bool(self.ai_providers())

    def orchestrator(self) -> AIReviewOrchestrator:
        ai = self.settings.get("ai")
        usable = {p.name for p in self.ai_providers()}
        claude = self.claude if "claude" in usable else ClaudeProvider(self.router, None)
        gemini = self.gemini if "gemini" in usable else GeminiProvider(self.router, None)
        return AIReviewOrchestrator(claude, gemini, ai.block_on_low_agreement, ai.require_ai_review)

    def risk_engine(self) -> RiskEngine:
        return RiskEngine(self.settings.get("risk"))

    async def risk_status(self) -> dict[str, Any]:
        st = self.risk_engine().status(await self.paper.account_state(), self.specs)
        return st.model_dump(mode="json")

    async def refresh_ai_status(self) -> dict[str, ProviderHealthInfo]:
        results = await asyncio.gather(self.claude.validate(), self.gemini.validate())
        self.ai_status = {r.provider: r for r in results}
        return self.ai_status

    async def reload_env(self) -> None:
        """Re-read environment/secrets and rebuild AI providers (no code changes needed for new keys)."""
        get_settings.cache_clear()
        self.env = get_settings()
        self.settings.env = self.env
        self._build_ai()
        await self.refresh_ai_status()

    # ----------------------------------------------------------- lifecycle
    async def startup(self, run_background: bool | None = None, migrate: bool = True) -> None:
        from app.core.database import utcnow

        if migrate:
            await asyncio.to_thread(run_migrations, self.env.sync_database_url)
        self.cache = await create_cache(self.env.redis_url or None)
        self.signals.cache = self.cache
        await self.settings.load()
        self.paper.refresh_settings()
        await self.market.init()
        await self.content.validate()
        await self.paper.ensure_account()
        await self.research.sync_strategies()
        await self.refresh_ai_status()
        for job in (self.content.refresh_calendar,):
            try:
                await job()
            except Exception:
                logger.warning(
                    "initial_calendar_refresh_failed", extra={"event": "initial_calendar_refresh_failed"}
                )
        try:
            await self.content.refresh_news(self.ai_providers(), self.settings.get("ai").ai_news_sentiment)
        except Exception:
            logger.warning("initial_news_refresh_failed", extra={"event": "initial_news_refresh_failed"})
        self.started_at = utcnow()
        await self.audit.record(
            SYSTEM,
            f"{self.env.app_name} started in {self.market.mode} mode",
            details={
                "market_data": self.market.status()["health"],
                "ai": {k: v.status.value for k, v in self.ai_status.items()},
            },
        )
        if run_background if run_background is not None else self.env.background_tasks:
            self.tasks = start_background(self)

    async def shutdown(self) -> None:
        if self.tasks:
            await self.tasks.stop()
        await self.db.dispose()

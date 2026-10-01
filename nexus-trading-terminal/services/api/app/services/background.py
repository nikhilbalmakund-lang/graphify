"""Background loops: quotes, signal scanning, signal tracking, paper broker, snapshots, content, health, alerts, retention."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import delete

from app.core.database import utcnow
from app.models import Signal, SystemEvent
from app.services.ai_budget import budgeted_providers
from market_data.models import Timeframe

logger = logging.getLogger("nexus.background")


class TaskManager:
    def __init__(self) -> None:
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.state: dict[str, dict[str, Any]] = {}

    def start(
        self, name: str, interval: float, fn: Callable[[], Awaitable[Any]], initial_delay: float = 0.0
    ) -> None:
        self.state[name] = {
            "interval_s": interval,
            "runs": 0,
            "errors": 0,
            "last_run": None,
            "last_error": None,
        }

        async def loop() -> None:
            await asyncio.sleep(initial_delay)
            while True:
                try:
                    await fn()
                    self.state[name]["runs"] += 1
                    self.state[name]["last_run"] = utcnow().isoformat()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # isolate failures: one job must not stop the others
                    self.state[name]["errors"] += 1
                    self.state[name]["last_error"] = f"{type(exc).__name__}: {getattr(exc, 'message', '')}"[
                        :300
                    ]
                    logger.warning(
                        "background_job_failed",
                        extra={"event": "background_job_failed", "data": {"job": name}},
                    )
                await asyncio.sleep(interval)

        self.tasks[name] = asyncio.create_task(loop(), name=f"nexus:{name}")

    def run_once(self, name: str, fn: Callable[[], Awaitable[Any]]) -> None:
        self.state[name] = {"interval_s": None, "runs": 0, "errors": 0, "last_run": None, "last_error": None}

        async def once() -> None:
            try:
                await fn()
                self.state[name]["runs"] = 1
                self.state[name]["last_run"] = utcnow().isoformat()
            except Exception as exc:
                self.state[name]["errors"] = 1
                self.state[name]["last_error"] = f"{type(exc).__name__}"
                logger.warning(
                    "background_job_failed", extra={"event": "background_job_failed", "data": {"job": name}}
                )

        self.tasks[name] = asyncio.create_task(once(), name=f"nexus:{name}")

    async def stop(self) -> None:
        for t in self.tasks.values():
            t.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        self.tasks.clear()


def start_background(c: Any) -> TaskManager:
    tm = TaskManager()
    env = c.env

    async def quotes() -> None:
        qs = await c.market_service.quotes(c.settings.get("markets").default_assets)
        await c.ws.broadcast("quotes", [q.model_dump(mode="json") for q in qs])
        await c.paper.process({q.symbol: q for q in qs})

    async def scan() -> None:
        markets = c.settings.get("markets")
        if markets.auto_scan:
            await c.signals.scan_new_bars(markets.default_assets, Timeframe.parse(markets.default_timeframe))

    async def content() -> None:
        await c.content.refresh_calendar()
        providers, _ = await budgeted_providers(c)
        await c.content.refresh_news(providers, c.settings.get("ai").ai_news_sentiment)

    async def health() -> None:
        before = c.market.health.status
        await c.market.revalidate()
        if (
            before == "CONNECTED"
            and c.market.health.status != "CONNECTED"
            and c.settings.get("notifications").data_disconnection
        ):
            await c.audit.notify(
                "DATA_DISCONNECTION",
                "Market data disconnected",
                c.market.health.detail,
                severity="ERROR",
                is_demo=c.market.is_demo,
                dedupe_minutes=30,
            )
        await c.refresh_ai_status()

    async def events_warning() -> None:
        if not c.settings.get("notifications").economic_event:
            return
        rows = await c.content.list_events(hours_back=0, hours_ahead=1, impact="HIGH")
        for e in c.content.events_payload(rows):
            if 0 <= e["minutes_until"] <= 30:
                await c.audit.notify(
                    "ECONOMIC_EVENT",
                    f"HIGH impact event in {int(e['minutes_until'])} min: {e['event']}",
                    f"{e['currency']} at {e['time'][11:16]} UTC"
                    + (" [DEMO calendar]" if e["is_demo"] else ""),
                    severity="WARNING",
                    dedupe_minutes=120,
                    is_demo=e["is_demo"],
                )

    async def risk_watch() -> None:
        st = await c.risk_status()
        if st["state"] != "NORMAL" and c.settings.get("notifications").risk_limit:
            await c.audit.notify(
                "RISK_LIMIT",
                f"Risk engine state: {st['state']}",
                "; ".join(st["messages"]) or st["state"],
                severity="ERROR" if st["state"] == "HALTED" else "WARNING",
                dedupe_minutes=240,
                is_demo=c.market.is_demo,
            )

    async def retention() -> None:
        days = c.settings.get("data").retention_days or env.data_retention_days
        nt_days = c.settings.get("data").retain_no_trade_days
        async with c.db.session() as s:
            if days:  # only with explicit configuration
                await s.execute(delete(SystemEvent).where(SystemEvent.ts < utcnow() - timedelta(days=days)))
            if nt_days:
                await s.execute(
                    delete(Signal).where(
                        Signal.status == "NO_TRADE", Signal.created_at < utcnow() - timedelta(days=nt_days)
                    )
                )

    async def build_memory() -> None:
        markets = c.settings.get("markets")
        await c.memory.ensure_built(
            markets.default_assets, [Timeframe.parse(markets.default_timeframe)], c.signals.engine()
        )
        await c.memory.restore_model()

    tm.start("quotes", env.quote_broadcast_interval_seconds, quotes, 1.0)
    tm.start("content", 600, content, 2.0)
    if env.build_memory_on_startup:
        tm.run_once("memory_build", build_memory)
    tm.start("scanner", env.signal_scan_interval_seconds, scan, 20.0)
    tm.start("signal_tracker", 60, c.signals.track, 30.0)
    tm.start("alerts", 30, c.alerts.evaluate, 15.0)
    tm.start("event_warnings", 300, events_warning, 10.0)
    tm.start("risk_watch", 120, risk_watch, 25.0)
    tm.start("snapshots", 300, c.paper.snapshot, 5.0)
    tm.start("provider_health", 300, health, 300.0)
    tm.start("retention", 86_400, retention, 3600.0)
    return tm

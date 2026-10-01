"""Health, system status, settings, secrets, alerts, notifications, search, audit log."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ai.prompts.registry import PROMPTS
from app.api.deps import get_container
from app.core.container import Container
from app.core.database import utcnow
from app.core.errors import NexusError
from app.schemas.api import (
    AlertOut,
    AlertToggleIn,
    ComponentStatus,
    LiveSwitchIn,
    NotificationOut,
    NotificationsReadIn,
    SystemStatusOut,
)
from app.schemas.settings import CATEGORIES, SecretStatus, SecretsUpdate
from app.services.audit_service import SETTINGS_CHANGED
from app.services.ops_service import AlertIn
from backtesting.engine.engine import ENGINE_VERSION
from paper_trading.broker.live import live_trading_gate
from quant.features.feature_set import FEATURE_VERSION
from quant.regime.detector import REGIME_VERSION
from quant.signals.models import SIGNAL_ENGINE_VERSION
from risk.engine import RISK_ENGINE_VERSION

APP_VERSION = "1.0.0"
router = APIRouter(tags=["system"])


@router.get("/health")
async def health(c: Container = Depends(get_container)) -> dict[str, Any]:
    db_ok = await c.db.ping()
    cache_ok = await c.cache.ping()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "cache": "ok" if cache_ok else "error",
        "market_data": c.market.health.status,
        "mode": c.market.mode,
        "ai": {k: v.status.value for k, v in c.ai_status.items()},
        "broker": "paper (SIMULATED)",
        "time": utcnow().isoformat(),
    }


def _live(c: Container) -> dict[str, Any]:
    allowed, reasons = live_trading_gate(
        c.env.live_trading_enabled,
        c.settings.get("live_trading").ui_switch_on,
        c.env.broker if c.env.broker != "paper" else None,
    )
    return {
        "env_enabled": c.env.live_trading_enabled,
        "ui_switch_on": c.settings.get("live_trading").ui_switch_on,
        "broker": c.env.broker,
        "allowed": allowed,
        "reasons": reasons,
    }


@router.get("/api/system/status", response_model=SystemStatusOut)
async def system_status(c: Container = Depends(get_container)) -> dict[str, Any]:
    db_ok = await c.db.ping()
    mh = c.market.health
    comps = [
        ComponentStatus(name="Backend", status="CONNECTED", detail=f"API v{APP_VERSION}"),
        ComponentStatus(
            name="Database", status="CONNECTED" if db_ok else "ERROR", detail=c.db.url.split(":")[0]
        ),
        ComponentStatus(
            name="Cache", status="CONNECTED" if await c.cache.ping() else "ERROR", detail=c.cache.name
        ),
        ComponentStatus(
            name="Market Data",
            status=mh.status,
            detail=mh.detail,
            provider=mh.provider,
            latency_ms=mh.latency_ms,
        ),
    ]
    labels = {"claude": "Claude", "gemini": "Gemini"}
    for key, label in labels.items():
        st = c.ai_status.get(key)
        comps.append(
            ComponentStatus(
                name=label,
                status=st.status.value if st else "NOT_CONFIGURED",
                detail=st.detail if st else "",
                provider=", ".join(f"{k}: {v}" for k, v in (st.models if st else {}).items()) or None,
                latency_ms=st.latency_ms if st else None,
            )
        )
    nh, ch = c.content.news_health, c.content.calendar_health
    comps.append(
        ComponentStatus(
            name="News", status=nh.status, detail=nh.detail, provider=nh.provider, latency_ms=nh.latency_ms
        )
    )
    comps.append(
        ComponentStatus(
            name="Economic Calendar",
            status=ch.status,
            detail=ch.detail,
            provider=ch.provider,
            latency_ms=ch.latency_ms,
        )
    )
    comps.append(
        ComponentStatus(
            name="Paper Broker",
            status="CONNECTED",
            detail="Virtual broker - SIMULATED fills only",
            provider="paper",
        )
    )
    demo_fallback = not c.ai_configured()
    if demo_fallback:
        comps.append(
            ComponentStatus(
                name="AI Demo Fallback", status="DEMO", detail="Rule-based summaries active (labelled non-AI)"
            )
        )
    return {
        "app_name": c.env.app_name,
        "version": APP_VERSION,
        "mode": c.market.mode,
        "trading_mode": "PAPER",
        "live_trading": _live(c),
        "components": comps,
        "versions": {
            "signal_engine": SIGNAL_ENGINE_VERSION,
            "features": FEATURE_VERSION,
            "regime": REGIME_VERSION,
            "risk_engine": RISK_ENGINE_VERSION,
            "backtest_engine": ENGINE_VERSION,
            "prompts": ", ".join(f"{p.name}@{p.version}" for p in PROMPTS.values()),
        },
        "background": c.tasks.state if c.tasks else {},
        "memory": c.memory.status,
        "server_time": utcnow().isoformat(),
    }


@router.get("/api/system/events")
async def system_events(
    limit: int = Query(200, ge=1, le=1000),
    event_type: str | None = None,
    severity: str | None = None,
    c: Container = Depends(get_container),
) -> list[dict[str, Any]]:
    rows = await c.audit.events(limit, event_type, severity)
    return [
        {
            "id": r.id,
            "ts": r.ts.isoformat(),
            "event_type": r.event_type,
            "severity": r.severity,
            "source": r.source,
            "message": r.message,
            "details": r.details,
            "request_id": r.request_id,
            "signal_id": r.signal_id,
        }
        for r in rows
    ]


# ---------------------------------------------------------------- settings
@router.get("/api/settings")
async def get_settings_all(c: Container = Depends(get_container)) -> dict[str, Any]:
    return {
        "settings": c.settings.all(),
        "secrets": [s.model_dump() for s in c.secrets.status(c.env)],
        "providers": c.secrets.providers(c.env),
        "live_trading": _live(c),
        "app": {
            "name": c.env.app_name,
            "short_name": c.env.app_short_name,
            "default_market": c.catalog.resolve(c.env.default_market) or "XAUUSD",
        },
    }


@router.put("/api/settings/{category}")
async def update_settings(
    category: str, values: dict[str, Any], c: Container = Depends(get_container)
) -> dict[str, Any]:
    if category not in CATEGORIES or category == "live_trading":
        raise NexusError("NOT_FOUND", f"Unknown settings category '{category}'")
    try:
        new, diff = await c.settings.update(category, values)
    except ValueError as exc:
        raise NexusError("VALIDATION_ERROR", str(exc)[:500]) from exc
    if category in ("paper",):
        c.paper.refresh_settings()
    await c.audit.record(SETTINGS_CHANGED, f"Settings '{category}' updated", details={"changes": diff})
    return {"category": category, "values": new.model_dump(mode="json")}


@router.put("/api/settings-secrets", response_model=list[SecretStatus])
async def update_secrets(body: SecretsUpdate, c: Container = Depends(get_container)) -> list[SecretStatus]:
    """Store API keys server-side (git-ignored .secrets.env). Keys are never returned; only configured/last-4 hints."""
    changed = c.secrets.write(body.values)
    await c.reload_env()
    await c.audit.record(SETTINGS_CHANGED, "Provider credentials updated", details={"keys": changed})
    return c.secrets.status(c.env)


@router.post("/api/settings/live-trading-switch")
async def live_switch(body: LiveSwitchIn, c: Container = Depends(get_container)) -> dict[str, Any]:
    await c.settings.update("live_trading", {"ui_switch_on": body.on})
    await c.audit.record(
        SETTINGS_CHANGED,
        f"Live-trading UI safety switch turned {'ON' if body.on else 'OFF'}",
        severity="WARNING" if body.on else "INFO",
    )
    return _live(c)


@router.get("/api/settings/export")
async def export_settings(c: Container = Depends(get_container)) -> dict[str, Any]:
    """JSON configuration export (no secrets)."""
    data = c.settings.all()
    data.pop("live_trading", None)
    return {"app": c.env.app_name, "exported_at": utcnow().isoformat(), "settings": data}


@router.post("/api/settings/import")
async def import_settings(payload: dict[str, Any], c: Container = Depends(get_container)) -> dict[str, Any]:
    data = payload.get("settings", payload)
    if not isinstance(data, dict):
        raise NexusError("VALIDATION_ERROR", "Expected {settings: {...}}")
    try:
        changed = await c.settings.import_all(data)
    except ValueError as exc:
        raise NexusError("VALIDATION_ERROR", str(exc)[:500]) from exc
    c.paper.refresh_settings()
    await c.audit.record(SETTINGS_CHANGED, "Settings imported", details={"categories": changed})
    return {"imported": changed}


# ---------------------------------------------------------- alerts/notifs
def _alert(a: Any) -> dict[str, Any]:
    return {
        "id": a.id,
        "type": a.type,
        "symbol": a.symbol,
        "condition": a.condition,
        "enabled": a.enabled,
        "note": a.note,
        "cooldown_minutes": a.cooldown_minutes,
        "last_triggered_at": a.last_triggered_at.isoformat() if a.last_triggered_at else None,
        "created_at": a.created_at.isoformat(),
    }


@router.get("/api/alerts", response_model=list[AlertOut])
async def list_alerts(c: Container = Depends(get_container)) -> list[dict[str, Any]]:
    return [_alert(a) for a in await c.alerts.all_alerts()]


@router.post("/api/alerts", response_model=AlertOut)
async def create_alert(body: AlertIn, c: Container = Depends(get_container)) -> dict[str, Any]:
    return _alert(await c.alerts.create(body))


@router.patch("/api/alerts/{alert_id}", response_model=AlertOut)
async def toggle_alert(
    alert_id: str, body: AlertToggleIn, c: Container = Depends(get_container)
) -> dict[str, Any]:
    return _alert(await c.alerts.toggle(alert_id, body.enabled))


@router.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id: str, c: Container = Depends(get_container)) -> dict[str, bool]:
    await c.alerts.delete(alert_id)
    return {"deleted": True}


@router.get("/api/notifications", response_model=list[NotificationOut])
async def notifications(
    limit: int = Query(50, ge=1, le=500), unread: bool = False, c: Container = Depends(get_container)
) -> list[dict[str, Any]]:
    return [
        {
            "id": n.id,
            "ts": n.ts.isoformat(),
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "severity": n.severity,
            "symbol": n.symbol,
            "signal_id": n.signal_id,
            "is_demo": n.is_demo,
            "read": n.read,
        }
        for n in await c.audit.notifications(limit, unread)
    ]


@router.post("/api/notifications/read")
async def read_notifications(
    body: NotificationsReadIn, c: Container = Depends(get_container)
) -> dict[str, int]:
    return {"updated": await c.audit.mark_read(body.ids)}


@router.get("/api/search")
async def search(
    q: str = Query(..., min_length=1, max_length=80), c: Container = Depends(get_container)
) -> dict[str, Any]:
    return await c.search.search(q)

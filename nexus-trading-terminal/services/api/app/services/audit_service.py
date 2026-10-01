"""Audit log (system_events) and user notifications."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, update

from app.core.database import Database, utcnow
from app.core.logging import request_id_var
from app.models import Notification, SystemEvent
from app.websocket.manager import ConnectionManager

logger = logging.getLogger("nexus.audit")

# Audited event types
SIGNAL_GENERATED = "SIGNAL_GENERATED"
SIGNAL_REJECTED = "SIGNAL_REJECTED"
RISK_REJECTION = "RISK_REJECTION"
PAPER_ORDER = "PAPER_ORDER"
LIVE_ORDER = "LIVE_ORDER"
SETTINGS_CHANGED = "SETTINGS_CHANGED"
AI_ERROR = "AI_ERROR"
DATA_ERROR = "DATA_ERROR"
KILL_SWITCH = "KILL_SWITCH"
SYSTEM = "SYSTEM"


class AuditService:
    def __init__(self, db: Database, ws: ConnectionManager):
        self.db = db
        self.ws = ws

    async def record(
        self,
        event_type: str,
        message: str,
        severity: str = "INFO",
        source: str = "api",
        details: dict[str, Any] | None = None,
        signal_id: str | None = None,
    ) -> None:
        level = {"INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}.get(
            severity, logging.INFO
        )
        logger.log(level, message, extra={"event": event_type, "data": details or {}, "signal_id": signal_id})
        try:
            async with self.db.session() as s:
                s.add(
                    SystemEvent(
                        ts=utcnow(),
                        event_type=event_type,
                        severity=severity,
                        source=source,
                        message=message[:2000],
                        details=details or {},
                        request_id=request_id_var.get(),
                        signal_id=signal_id,
                    )
                )
        except Exception:
            logger.exception("audit_write_failed", extra={"event": "audit_write_failed"})

    async def events(
        self, limit: int = 200, event_type: str | None = None, severity: str | None = None
    ) -> list[SystemEvent]:
        async with self.db.session() as s:
            q = select(SystemEvent).order_by(SystemEvent.ts.desc()).limit(min(limit, 1000))
            if event_type:
                q = q.where(SystemEvent.event_type == event_type)
            if severity:
                q = q.where(SystemEvent.severity == severity)
            return list((await s.execute(q)).scalars())

    async def notify(
        self,
        type_: str,
        title: str,
        body: str,
        severity: str = "INFO",
        symbol: str | None = None,
        signal_id: str | None = None,
        is_demo: bool = True,
        dedupe_minutes: int = 0,
    ) -> None:
        async with self.db.session() as s:
            if dedupe_minutes:
                since = utcnow() - timedelta(minutes=dedupe_minutes)
                exists = await s.scalar(
                    select(func.count())
                    .select_from(Notification)
                    .where(Notification.type == type_, Notification.title == title, Notification.ts >= since)
                )
                if exists:
                    return
            n = Notification(
                ts=utcnow(),
                type=type_,
                title=title[:200],
                body=body[:2000],
                severity=severity,
                symbol=symbol,
                signal_id=signal_id,
                is_demo=is_demo,
                read=False,
            )
            s.add(n)
            await s.flush()
            payload = {
                "id": n.id,
                "ts": n.ts.isoformat(),
                "type": type_,
                "title": n.title,
                "body": n.body,
                "severity": severity,
                "symbol": symbol,
                "signal_id": signal_id,
                "is_demo": is_demo,
            }
        await self.ws.broadcast("notifications", payload)

    async def notifications(self, limit: int = 50, unread_only: bool = False) -> list[Notification]:
        async with self.db.session() as s:
            q = select(Notification).order_by(Notification.ts.desc()).limit(min(limit, 500))
            if unread_only:
                q = q.where(Notification.read.is_(False))
            return list((await s.execute(q)).scalars())

    async def mark_read(self, ids: list[int] | None) -> int:
        async with self.db.session() as s:
            q = update(Notification).values(read=True)
            if ids:
                q = q.where(Notification.id.in_(ids))
            res = await s.execute(q)
            return int(getattr(res, "rowcount", 0) or 0)

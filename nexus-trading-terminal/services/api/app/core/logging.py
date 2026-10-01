"""Structured JSON logging with request and signal correlation IDs.

Each record carries: timestamp, service, event, severity, request_id and
signal_id (when relevant). Values that look like credentials are redacted.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
signal_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("signal_id", default=None)

_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|apikey|secret|token|password)(\"?\s*[:=]\s*\"?)([^\s\"&,]+)"),
]


def redact(text: str) -> str:
    out = text
    for pat in _SECRET_PATTERNS[:2]:
        out = pat.sub("[REDACTED]", out)
    return _SECRET_PATTERNS[2].sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", out)


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "service": self.service,
            "severity": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", None) or record.getMessage(),
            "message": redact(record.getMessage()),
            "request_id": request_id_var.get(),
            "signal_id": getattr(record, "signal_id", None) or signal_id_var.get(),
        }
        extra = getattr(record, "data", None)
        if isinstance(extra, dict):
            payload["data"] = json.loads(redact(json.dumps(extra, default=str)))
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


class PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rid = request_id_var.get()
        base = f"{datetime.fromtimestamp(record.created, UTC).strftime('%H:%M:%S')} {record.levelname:<7} {record.name}: {redact(record.getMessage())}"
        return f"{base} [req {rid}]" if rid else base


def configure_logging(level: str = "INFO", json_logs: bool = True, service: str = "nexus-api") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service) if json_logs else PlainFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "anthropic", "google_genai", "aiosqlite", "watchfiles"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **data: Any) -> None:
    logger.log(level, event, extra={"event": event, "data": data, "signal_id": data.get("signal_id")})

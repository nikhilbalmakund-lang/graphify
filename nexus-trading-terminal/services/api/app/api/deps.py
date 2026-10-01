"""FastAPI dependencies and small helpers shared by routers."""

from __future__ import annotations

from fastapi import Request

from app.core.container import Container
from app.core.errors import NexusError
from market_data.models import Timeframe


def get_container(request: Request) -> Container:
    return request.app.state.container  # type: ignore[no-any-return]


def symbol_of(c: Container, raw: str) -> str:
    sym = c.catalog.resolve(raw)
    if sym is None:
        raise NexusError("INVALID_SYMBOL", f"Unknown symbol '{raw}'")
    return sym


def timeframe_of(raw: str) -> Timeframe:
    try:
        return Timeframe.parse(raw)
    except ValueError as exc:
        raise NexusError("VALIDATION_ERROR", str(exc)) from exc

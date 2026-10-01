"""Error codes and safe error responses.

All errors leave the API as {"error": {"code", "message", "request_id"}}.
Stack traces are logged server-side and never returned to the client.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ai.providers.base import AIProviderError
from app.core.logging import request_id_var
from market_data.providers.base import MarketDataError
from paper_trading.broker.base import BrokerError

logger = logging.getLogger("nexus.errors")


class ErrorCode(StrEnum):
    DATA_PROVIDER_UNAVAILABLE = "DATA_PROVIDER_UNAVAILABLE"
    AI_PROVIDER_UNAVAILABLE = "AI_PROVIDER_UNAVAILABLE"
    INVALID_MARKET_DATA = "INVALID_MARKET_DATA"
    STALE_MARKET_DATA = "STALE_MARKET_DATA"
    RISK_LIMIT_REACHED = "RISK_LIMIT_REACHED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    BACKTEST_ERROR = "BACKTEST_ERROR"
    BROKER_ERROR = "BROKER_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    LIVE_TRADING_DISABLED = "LIVE_TRADING_DISABLED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


STATUS: dict[str, int] = {
    "DATA_PROVIDER_UNAVAILABLE": 503,
    "AI_PROVIDER_UNAVAILABLE": 503,
    "INVALID_MARKET_DATA": 422,
    "STALE_MARKET_DATA": 409,
    "RISK_LIMIT_REACHED": 409,
    "INSUFFICIENT_DATA": 422,
    "BACKTEST_ERROR": 422,
    "BROKER_ERROR": 400,
    "BROKER_NOT_IMPLEMENTED": 501,
    "VALIDATION_ERROR": 422,
    "NOT_FOUND": 404,
    "RATE_LIMITED": 429,
    "INVALID_SYMBOL": 404,
    "LIVE_TRADING_DISABLED": 403,
    "INTERNAL_ERROR": 500,
    "AI_REFUSAL": 502,
    "AI_INVALID_OUTPUT": 502,
    "AI_RATE_LIMITED": 429,
    "AI_BAD_REQUEST": 502,
    "AI_TOOL_LOOP_LIMIT": 502,
    "AI_TOOL_FORBIDDEN": 403,
}


class NexusError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = str(code)
        self.message = message
        self.details = details or {}


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message, "request_id": request_id_var.get()}
    if details:
        body["details"] = details
    return {"error": body}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NexusError)
    async def _nexus(_: Request, exc: NexusError) -> JSONResponse:
        return JSONResponse(
            status_code=STATUS.get(exc.code, 400), content=error_body(exc.code, exc.message, exc.details)
        )

    @app.exception_handler(MarketDataError)
    async def _md(_: Request, exc: MarketDataError) -> JSONResponse:
        return JSONResponse(status_code=STATUS.get(exc.code, 503), content=error_body(exc.code, exc.message))

    @app.exception_handler(AIProviderError)
    async def _ai(_: Request, exc: AIProviderError) -> JSONResponse:
        return JSONResponse(status_code=STATUS.get(exc.code, 503), content=error_body(exc.code, exc.message))

    @app.exception_handler(BrokerError)
    async def _broker(_: Request, exc: BrokerError) -> JSONResponse:
        return JSONResponse(status_code=STATUS.get(exc.code, 400), content=error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": [str(x) for x in e.get("loc", [])], "msg": e.get("msg", "")} for e in exc.errors()][
            :20
        ]
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "Request validation failed", {"errors": errors}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "NOT_FOUND", 405: "VALIDATION_ERROR", 429: "RATE_LIMITED"}.get(
            exc.status_code, "INTERNAL_ERROR"
        )
        return JSONResponse(status_code=exc.status_code, content=error_body(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", extra={"event": "unhandled_error"})
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "An internal error occurred. See server logs."),
        )

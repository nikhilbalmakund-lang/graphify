"""NEXUS Trading Intelligence API (FastAPI application factory).

Single-user, local-first: there is no authentication, so the server binds to
127.0.0.1 by default. Do not expose it to a network without adding an
authenticating reverse proxy.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api import ai, content, market, research, signals, system, trading
from app.core.config import Settings, get_settings
from app.core.container import Container
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, request_id_var
from app.core.rate_limit import RateLimiter, RateLimitMiddleware
from app.websocket import routes as ws_routes

API_DESCRIPTION = """
NEXUS Trading Intelligence - local AI trading research terminal.

* Every market object is tagged with its data mode (LIVE / DEMO). DEMO data is synthetic.
* SIGNAL SCORE is a rules-based 0-100 quality score, never a probability.
* All trading endpoints operate on a PAPER (simulated) broker. Live execution is disabled.
* Errors are returned as `{"error": {"code", "message", "request_id"}}`.
"""


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid[:40])
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid[:40]
        response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response


def create_app(
    settings: Settings | None = None, container: Container | None = None, run_background: bool | None = None
) -> FastAPI:
    env = settings or get_settings()
    configure_logging(env.log_level, env.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        c = container or Container(env)
        app.state.container = c
        await c.startup(run_background=run_background)
        try:
            yield
        finally:
            await c.shutdown()

    app = FastAPI(
        title=env.app_name,
        version="1.0.0",
        description=API_DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    limiter = RateLimiter(
        {
            "ai": env.rate_limit_ai_per_minute,
            "backtest": env.rate_limit_backtest_per_minute,
            "news": 120,
            "market": env.rate_limit_market_per_minute,
            "default": env.rate_limit_default_per_minute,
        }
    )
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=env.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    for r in (
        system.router,
        market.router,
        signals.router,
        trading.router,
        research.router,
        content.router,
        ai.router,
        ws_routes.router,
    ):
        app.include_router(r)
    return app


app = create_app()

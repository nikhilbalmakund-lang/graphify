"""Per-client token-bucket rate limiting by route group (AI, backtests, news, market data)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.errors import error_body


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    def __init__(self, limits_per_minute: dict[str, int]):
        self.limits = limits_per_minute
        self._buckets: dict[tuple[str, str], _Bucket] = {}

    @staticmethod
    def group_for(path: str) -> str:
        if path.startswith("/api/ai"):
            return "ai"
        if path.startswith(("/api/backtests", "/api/strategies/ml")):
            return "backtest"
        if path.startswith("/api/news") or path.startswith("/api/calendar"):
            return "news"
        if path.startswith(("/api/market", "/api/scanner", "/api/heatmap")):
            return "market"
        return "default"

    def allow(self, client: str, group: str, now: float | None = None) -> tuple[bool, float]:
        limit = self.limits.get(group, self.limits.get("default", 300))
        now = time.monotonic() if now is None else now
        key = (client, group)
        b = self._buckets.get(key)
        if b is None:
            b = _Bucket(tokens=float(limit), updated=now)
            self._buckets[key] = b
        b.tokens = min(float(limit), b.tokens + (now - b.updated) * limit / 60.0)
        b.updated = now
        if b.tokens >= 1.0:
            b.tokens -= 1.0
            return True, 0.0
        return False, (1.0 - b.tokens) * 60.0 / limit


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if not path.startswith("/api") or request.method == "OPTIONS":
            return await call_next(request)
        client = request.client.host if request.client else "local"
        group = RateLimiter.group_for(path)
        if request.method == "GET" and group in ("ai", "backtest"):
            group = "default"  # reading results is cheap; only generation is limited tightly
        ok, retry = self.limiter.allow(client, group)
        if not ok:
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(max(1, int(retry)))},
                content=error_body(
                    "RATE_LIMITED", f"Rate limit exceeded for {group} endpoints; retry in {retry:.0f}s"
                ),
            )
        return await call_next(request)

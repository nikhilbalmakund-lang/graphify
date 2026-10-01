"""Redis-compatible cache abstraction with an in-memory fallback.

Set REDIS_URL to use Redis; otherwise a process-local TTL cache is used.
Values are JSON-serialisable objects.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger("nexus.cache")


class CacheBackend(ABC):
    name = "abstract"

    @abstractmethod
    async def get(self, key: str) -> Any | None: ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: float) -> None: ...

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> int: ...

    @abstractmethod
    async def ping(self) -> bool: ...

    async def get_or_set(self, key: str, ttl: float, factory: Callable[[], Awaitable[Any]]) -> Any:
        hit = await self.get(key)
        if hit is not None:
            return hit
        value = await factory()
        if value is not None:
            await self.set(key, value, ttl)
        return value

    def stats(self) -> dict[str, Any]:
        return {"backend": self.name}


class InMemoryCache(CacheBackend):
    name = "memory"

    def __init__(self, max_items: int = 5000):
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max = max_items
        self._lock = asyncio.Lock()
        self.hits = 0
        self.misses = 0

    async def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if item is None:
            self.misses += 1
            return None
        expires, value = item
        if expires < time.monotonic():
            self._data.pop(key, None)
            self.misses += 1
            return None
        self._data.move_to_end(key)
        self.hits += 1
        return value

    async def set(self, key: str, value: Any, ttl: float) -> None:
        async with self._lock:
            self._data[key] = (time.monotonic() + ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    async def delete_prefix(self, prefix: str) -> int:
        keys = [k for k in self._data if k.startswith(prefix)]
        for k in keys:
            self._data.pop(k, None)
        return len(keys)

    async def ping(self) -> bool:
        return True

    def stats(self) -> dict[str, Any]:
        return {"backend": self.name, "items": len(self._data), "hits": self.hits, "misses": self.misses}


class RedisCache(CacheBackend):
    name = "redis"

    def __init__(self, url: str, prefix: str = "nexus:"):
        import redis.asyncio as aioredis

        self._r = aioredis.from_url(url, decode_responses=True)
        self._prefix = prefix

    async def get(self, key: str) -> Any | None:
        raw = await self._r.get(self._prefix + key)
        return None if raw is None else json.loads(raw)

    async def set(self, key: str, value: Any, ttl: float) -> None:
        await self._r.set(self._prefix + key, json.dumps(value, default=str), ex=max(1, int(ttl)))

    async def delete_prefix(self, prefix: str) -> int:
        n = 0
        async for k in self._r.scan_iter(match=f"{self._prefix}{prefix}*"):
            await self._r.delete(k)
            n += 1
        return n

    async def ping(self) -> bool:
        try:
            return bool(await self._r.ping())
        except Exception:
            return False


async def create_cache(redis_url: str | None) -> CacheBackend:
    if redis_url:
        try:
            cache = RedisCache(redis_url)
            if await cache.ping():
                logger.info("cache_backend", extra={"event": "cache_backend", "data": {"backend": "redis"}})
                return cache
            logger.warning("Redis unreachable; using in-memory cache", extra={"event": "cache_fallback"})
        except Exception:
            logger.warning(
                "Redis client unavailable; using in-memory cache", extra={"event": "cache_fallback"}
            )
    return InMemoryCache()

"""Rate limit helpers with Redis fallback to in-memory map."""
from __future__ import annotations

import asyncio
import time
from typing import Callable, Awaitable

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover - safety net
    redis = None


class MemoryLimiter:
    def __init__(self):
        self.storage: dict[str, float] = {}
        self.lock = asyncio.Lock()

    async def hit(self, key: str, cooldown: int) -> bool:
        async with self.lock:
            now = time.time()
            expires = self.storage.get(key, 0)
            if expires > now:
                return False
            self.storage[key] = now + cooldown
            return True

    async def remaining(self, key: str) -> float:
        async with self.lock:
            now = time.time()
            expires = self.storage.get(key, 0)
            return max(0.0, expires - now)


class RedisLimiter:
    def __init__(self, client):
        self.client = client

    async def hit(self, key: str, cooldown: int) -> bool:
        return await self.client.set(name=key, value=1, ex=cooldown, nx=True)

    async def remaining(self, key: str) -> float:
        ttl = await self.client.ttl(key)
        return max(0.0, float(ttl if ttl else 0))


class RateLimiter:
    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url
        self.memory = MemoryLimiter()
        self._redis_client = None

    async def get_client(self):
        if redis and self.redis_url and not self._redis_client:
            self._redis_client = redis.from_url(self.redis_url)
        return self._redis_client

    async def hit(self, key: str, cooldown: int) -> bool:
        client = await self.get_client()
        if client:
            try:
                return bool(await RedisLimiter(client).hit(key, cooldown))
            except Exception:
                pass
        return await self.memory.hit(key, cooldown)

    async def remaining(self, key: str) -> float:
        client = await self.get_client()
        if client:
            try:
                return await RedisLimiter(client).remaining(key)
            except Exception:
                pass
        return await self.memory.remaining(key)

"""Antiflood tracking leveraging Redis when available."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover
    redis = None


@dataclass
class FloodSettings:
    limit: int
    window: int


class AntifloodService:
    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url
        self._client = None
        self._fallback: dict[tuple[int, int], list[float]] = {}
        self._lock = asyncio.Lock()

    async def get_client(self):
        if redis and self.redis_url and not self._client:
            self._client = redis.from_url(self.redis_url)
        return self._client

    async def hit(self, chat_id: int, user_id: int, settings: FloodSettings) -> int:
        key = f"flood:{chat_id}:{user_id}"
        client = await self.get_client()
        now = time.time()
        if client:
            try:
                pipe = client.pipeline()
                pipe.zadd(key, {now: now})
                pipe.zremrangebyscore(key, min=0, max=now - settings.window)
                pipe.zcard(key)
                pipe.expire(key, settings.window)
                _, _, count, _ = await pipe.execute()
                return int(count)
            except Exception:
                pass
        async with self._lock:
            window_list = self._fallback.setdefault((chat_id, user_id), [])
            window_list.append(now)
            cutoff = now - settings.window
            self._fallback[(chat_id, user_id)] = [ts for ts in window_list if ts >= cutoff]
            return len(self._fallback[(chat_id, user_id)])

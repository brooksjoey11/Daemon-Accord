from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Optional

import structlog
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)

LoaderFn = Callable[[str], Awaitable[Optional[dict]]]


class MemoryCache:
    """
    Read-through cache with single-flight lock to prevent stampedes.
    """

    def __init__(
        self,
        redis: Redis,
        ttl_seconds: int = 600,
        prefix: str = "memory:job:",
        lock_ttl_seconds: int = 5,
    ) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds
        self.prefix = prefix
        self.lock_ttl_seconds = lock_ttl_seconds

    def _key(self, job_id: str) -> str:
        return f"{self.prefix}{job_id}"

    def _lock_key(self, job_id: str) -> str:
        return f"{self.prefix}lock:{job_id}"

    async def get_or_load(self, job_id: str, loader: LoaderFn) -> Optional[dict]:
        key = self._key(job_id)
        cached = await self.redis.get(key)
        if cached:
            logger.debug("cache_hit", job_id=job_id)
            return json.loads(cached)

        lock_key = self._lock_key(job_id)
        acquired = await self.redis.set(lock_key, "1", nx=True, ex=self.lock_ttl_seconds)
        if acquired:
            try:
                logger.debug("cache_miss_loading", job_id=job_id)
                data = await loader(job_id)
                if data is None:
                    return None
                await self.redis.set(key, json.dumps(data), ex=self.ttl_seconds)
                return data
            finally:
                await self.redis.delete(lock_key)
        else:
            # Another coroutine is loading; wait briefly and retry.
            for _ in range(10):
                await asyncio.sleep(0.05)
                cached_retry = await self.redis.get(key)
                if cached_retry:
                    logger.debug("cache_race_winner", job_id=job_id)
                    return json.loads(cached_retry)
            # Fallback: load directly without caching to avoid unbounded wait.
            logger.debug("cache_fallback_direct_load", job_id=job_id)
            return await loader(job_id)

    async def set(self, job_id: str, payload: dict) -> None:
        key = self._key(job_id)
        await self.redis.set(key, json.dumps(payload), ex=self.ttl_seconds)
        logger.debug("cache_write", job_id=job_id)

    async def invalidate(self, job_id: str) -> None:
        await self.redis.delete(self._key(job_id))
        logger.debug("cache_invalidate", job_id=job_id)

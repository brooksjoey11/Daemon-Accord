import asyncio
from datetime import datetime

import pytest
from fakeredis.aioredis import FakeRedis

from services.memory.cache import MemoryCache


@pytest.mark.asyncio
async def test_cache_cold_then_warm():
    redis = FakeRedis()
    cache = MemoryCache(redis, ttl_seconds=60)
    loaded = {"job_id": "a", "content": {"value": 1}}

    calls = 0

    async def loader(job_id: str):
        nonlocal calls
        calls += 1
        return loaded

    result1 = await cache.get_or_load("a", loader)
    assert result1 == loaded
    assert calls == 1

    result2 = await cache.get_or_load("a", loader)
    assert result2 == loaded
    assert calls == 1  # warm cache used


@pytest.mark.asyncio
async def test_single_flight_race():
    redis = FakeRedis()
    cache = MemoryCache(redis, ttl_seconds=60, lock_ttl_seconds=2)
    calls = 0

    async def loader(job_id: str):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return {"job_id": job_id, "content": {"value": 1}}

    async def reader():
        return await cache.get_or_load("race", loader)

    results = await asyncio.gather(*[reader() for _ in range(10)])
    assert calls == 1  # single-flight ensured
    assert all(r["content"]["value"] == 1 for r in results)

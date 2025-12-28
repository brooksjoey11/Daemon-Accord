import asyncio
from typing import Dict

import pytest
from fakeredis.aioredis import FakeRedis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.pool import StaticPool

from services.memory.cache import MemoryCache
from services.memory.models import JobMemory
from services.memory.repo import Database, MemoryRepository, MemorySettings


def build_db() -> Database:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        future=True,
    )
    Session = sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    db = Database(MemorySettings(postgres_dsn="sqlite+aiosqlite:///:memory:"))
    db._engine = engine  # type: ignore
    db._session_factory = Session  # type: ignore
    return db


@pytest.mark.asyncio
async def test_concurrent_read_write():
    db = build_db()
    async with db.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    repo = MemoryRepository(db)
    redis = FakeRedis()
    cache = MemoryCache(redis, ttl_seconds=30)

    async def writer(job_id: str):
        await repo.upsert_memory(
            job_id=job_id,
            content={"value": job_id},
            artifact_paths=[],
            signed_artifacts=[],
            adapter_version=None,
        )
        await cache.invalidate(job_id)

    async def reader(job_id: str):
        async def load(_jid: str):
            record = await repo.get_memory(_jid)
            if record:
                return record.model_dump()
            return None

        return await cache.get_or_load(job_id, load)

    writers = [writer(f"job-{i}") for i in range(10)]
    await asyncio.gather(*writers)

    readers = [reader(f"job-{i%10}") for i in range(50)]
    results = await asyncio.gather(*readers)

    assert all(res is not None for res in results)
    assert len({res["job_id"] for res in results if res}) == 10

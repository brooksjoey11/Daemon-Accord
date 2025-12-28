import pytest
from fakeredis.aioredis import FakeRedis
from sqlmodel import SQLModel
from sqlmodel.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from services.memory.reflection import Reflector
from services.memory.repo import Database, MemoryRepository, MemorySettings
from services.memory.models import IncidentLog, SiteAdapter


def in_memory_db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
        poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    return engine, Session


@pytest.mark.asyncio
async def test_reflection_selector_miss():
    engine, Session = in_memory_db()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    db = Database(MemorySettings(postgres_dsn="sqlite+aiosqlite:///:memory:"))
    db._engine = engine  # type: ignore
    db._session_factory = Session  # type: ignore
    repo = MemoryRepository(db)
    reflector = Reflector(repo)

    adapter = SiteAdapter(domain="example.com", selectors={"primary": "//div"}, wait_strategies={})
    await repo.save_adapter(adapter)
    incident = IncidentLog(domain="example.com", error_type="selector_miss", message="no match")
    await repo.append_incidents([incident])

    updated = await reflector.reflect_domain("example.com")

    assert updated is not None
    assert updated.version == adapter.version + 1
    assert "fallback" in updated.selectors
    assert updated.wait_strategies == {}

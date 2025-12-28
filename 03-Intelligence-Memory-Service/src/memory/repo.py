from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from typing import Iterable, List, Optional

import structlog
from pydantic import BaseSettings, Field
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select

from .models import IncidentLog, JobMemory, MemorySummary, SiteAdapter

logger = structlog.get_logger(__name__)


class MemorySettings(BaseSettings):
    postgres_dsn: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
        validation_alias="POSTGRES_DSN",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL",
    )
    supabase_url: str = Field(default="", validation_alias="SUPABASE_URL")
    supabase_service_key: str = Field(
        default="", validation_alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase_bucket: str = Field(default="artifacts", validation_alias="ARTIFACT_BUCKET")
    enable_vector: bool = Field(default=False, validation_alias="ENABLE_PGVECTOR")

    class Config:
        env_file = ".env"
        case_sensitive = False


class Database:
    """
    Thin async DB wrapper around SQLModel + asyncpg.
    """

    def __init__(self, settings: MemorySettings) -> None:
        self._settings = settings
        self._engine: AsyncEngine = create_async_engine(
            settings.postgres_dsn,
            pool_pre_ping=True,
            future=True,
        )
        self._session_factory = sessionmaker(
            bind=self._engine, expire_on_commit=False, class_=AsyncSession
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    def session(self) -> AsyncSession:
        return self._session_factory()

    async def init_models(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        logger.info("memory_tables_initialized")

    async def dispose(self) -> None:
        await self._engine.dispose()


class MemoryRepository:
    """
    Data access layer for memory, adapters, incidents, and summaries.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    async def get_memory(self, job_id: str) -> Optional[JobMemory]:
        async with self.db.session() as session:
            result = await session.exec(
                select(JobMemory).where(JobMemory.job_id == job_id).order_by(JobMemory.id.desc())
            )
            return result.first()

    async def upsert_memory(
        self,
        job_id: str,
        content: dict,
        artifact_paths: List[str],
        signed_artifacts: List[str],
        adapter_version: Optional[int],
    ) -> JobMemory:
        payload = JobMemory(
            job_id=job_id,
            content=content,
            artifact_paths=artifact_paths,
            signed_artifacts=signed_artifacts,
            adapter_version=adapter_version,
            created_at=datetime.utcnow(),
        )
        async with self.db.session() as session:
            session.add(payload)
            await session.commit()
            await session.refresh(payload)
        logger.info(
            "memory_upserted",
            job_id=job_id,
            adapter_version=adapter_version,
            artifact_count=len(artifact_paths),
        )
        return payload

    async def get_adapter(self, domain: str) -> Optional[SiteAdapter]:
        async with self.db.session() as session:
            result = await session.exec(select(SiteAdapter).where(SiteAdapter.domain == domain))
            return result.first()

    async def save_adapter(self, adapter: SiteAdapter) -> SiteAdapter:
        async with self.db.session() as session:
            session.add(adapter)
            await session.commit()
            await session.refresh(adapter)
        logger.info(
            "site_adapter_saved",
            domain=adapter.domain,
            version=adapter.version,
        )
        return adapter

    async def append_incidents(self, incidents: Iterable[IncidentLog]) -> None:
        async with self.db.session() as session:
            session.add_all(list(incidents))
            await session.commit()
        logger.info("incident_log_appended", count=len(list(incidents)))

    async def fetch_incidents(self, domain: str) -> List[IncidentLog]:
        async with self.db.session() as session:
            result = await session.exec(
                select(IncidentLog).where(IncidentLog.domain == domain).order_by(IncidentLog.created_at.desc())
            )
            return list(result)

    async def add_summary(
        self,
        job_id: str,
        summary: str,
        embedding: dict,
    ) -> MemorySummary:
        record = MemorySummary(
            job_id=job_id,
            summary=summary,
            embedding=embedding,
            created_at=datetime.utcnow(),
        )
        async with self.db.session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return record

    async def latest_summary(self, job_id: str) -> Optional[MemorySummary]:
        async with self.db.session() as session:
            result = await session.exec(
                select(MemorySummary)
                .where(MemorySummary.job_id == job_id)
                .order_by(MemorySummary.created_at.desc())
            )
            return result.first()


async def with_lifespan(db: Database):
    """
    Async context manager to initialize and dispose resources for FastAPI lifespan.
    """

    @contextlib.asynccontextmanager
    async def lifespan(app):
        await db.init_models()
        try:
            yield
        finally:
            await db.dispose()

    return lifespan

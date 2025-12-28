from __future__ import annotations

import asyncio
import logging
from typing import Optional
from urllib.parse import urlsplit

import structlog
from fastapi import Depends, FastAPI, HTTPException, status
from redis.asyncio import Redis
from supabase import Client, create_client

from .cache import MemoryCache
from .models import IncidentLog, MemoryReadResponse, MemoryWriteRequest, serialize_sqlmodel
from .reflection import Reflector
from .repo import Database, MemoryRepository, MemorySettings, with_lifespan


def setup_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )
    logging.basicConfig(level=logging.INFO)


settings = MemorySettings()
setup_logging()

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
db = Database(settings)
repo = MemoryRepository(db)
cache = MemoryCache(redis_client)
reflector = Reflector(repo)

supabase_client: Optional[Client] = None
if settings.supabase_url and settings.supabase_service_key:
    supabase_client = create_client(settings.supabase_url, settings.supabase_service_key)


async def lifespan(app: FastAPI):
    await db.init_models()
    yield
    await db.dispose()
    await redis_client.aclose()


app = FastAPI(
    title="memory-service",
    description="Level-5 reflective memory service for browser jobs",
    lifespan=lifespan,
)


def get_repo() -> MemoryRepository:
    return repo


def get_cache() -> MemoryCache:
    return cache


def get_reflector() -> Reflector:
    return reflector


async def _sign_artifacts(paths: list[str]) -> list[str]:
    if not paths:
        return []
    if supabase_client is None:
        return paths
    signed: list[str] = []
    for path in paths:
        try:
            res = supabase_client.storage.from_(settings.supabase_bucket).create_signed_url(
                path, expires_in=3600
            )
            if res and "signedURL" in res:
                signed.append(res["signedURL"])
            else:
                signed.append(path)
        except Exception as exc:
            structlog.get_logger(__name__).warning(
                "artifact_sign_failed", path=path, error=str(exc)
            )
            signed.append(path)
    return signed


def _domain_from_url(url: str) -> str:
    return urlsplit(url).hostname or "unknown"


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "memory-service"
    }


@app.get("/memory/{job_id}", response_model=MemoryReadResponse)
async def get_memory(
    job_id: str,
    repo: MemoryRepository = Depends(get_repo),
    cache: MemoryCache = Depends(get_cache),
):
    async def loader(jid: str):
        record = await repo.get_memory(jid)
        if record is None:
            return None
        adapter = None
        summary = None
        domain = None
        if record.content.get("url"):
            domain = _domain_from_url(record.content["url"])
        if domain:
            adapter = await repo.get_adapter(domain)
        summary_obj = await repo.latest_summary(jid)
        if summary_obj:
            summary = summary_obj.summary
        payload = {
            "job_id": record.job_id,
            "content": record.content,
            "signed_artifacts": record.signed_artifacts,
            "adapter_version": record.adapter_version,
            "adapter": serialize_sqlmodel(adapter) if adapter else None,
            "summary": summary,
        }
        return payload

    data = await cache.get_or_load(job_id, loader)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="memory not found")
    return MemoryReadResponse(**data)


@app.post("/memory", response_model=MemoryReadResponse, status_code=status.HTTP_201_CREATED)
async def write_memory(
    request: MemoryWriteRequest,
    repo: MemoryRepository = Depends(get_repo),
    cache: MemoryCache = Depends(get_cache),
    reflector: Reflector = Depends(get_reflector),
):
    domain = _domain_from_url(str(request.url))
    adapter = await repo.get_adapter(domain)
    adapter_version = adapter.version if adapter else None

    signed_artifacts = await _sign_artifacts(request.artifact_paths)

    record = await repo.upsert_memory(
        job_id=request.job_id,
        content=request.content | {"url": str(request.url), "selector": request.selector},
        artifact_paths=request.artifact_paths,
        signed_artifacts=signed_artifacts,
        adapter_version=adapter_version,
    )

    await cache.set(request.job_id, request.model_dump())

    # Trigger reflection in background
    asyncio.create_task(reflector.reflect_domain(domain))

    return MemoryReadResponse(
        job_id=request.job_id,
        content=record.content,
        signed_artifacts=record.signed_artifacts,
        adapter_version=adapter_version,
        adapter=serialize_sqlmodel(adapter) if adapter else None,
        summary=None,
    )


@app.post(
    "/memory/incident/{domain}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Record incidents for reflection",
)
async def log_incident(
    domain: str,
    incident: dict,
    repo: MemoryRepository = Depends(get_repo),
    reflector: Reflector = Depends(get_reflector),
):
    record = structlog.get_logger(__name__)
    error_type = incident.get("error_type") or "unknown"
    message = incident.get("message") or ""
    job_id = incident.get("job_id")
    metadata = incident.get("metadata") or {}

    log = IncidentLog(job_id=job_id, domain=domain, error_type=error_type, message=message, metadata=metadata)
    await repo.append_incidents([log])
    asyncio.create_task(reflector.reflect_domain(domain))
    record.info("incident_logged", domain=domain, error_type=error_type)
    return {"status": "accepted"}

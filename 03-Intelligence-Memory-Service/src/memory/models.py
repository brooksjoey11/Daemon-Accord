from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlmodel import Column, JSON, SQLModel


# ---------------------------------------------------------------------------
# Persistence models (SQLModel)
# ---------------------------------------------------------------------------


class JobMemory(SQLModel, table=True):
    __tablename__ = "job_memory"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True, description="Logical job id / correlation id")
    content: Dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False),
        description="Opaque memory payload for the job",
    )
    artifact_paths: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
        description="Artifact object paths in Supabase storage",
    )
    signed_artifacts: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
        description="Signed URLs cached alongside memory for quick retrieval",
    )
    adapter_version: Optional[int] = Field(
        default=None,
        description="Site adapter version applied when memory was captured",
    )
    execution_context: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Execution context: strategy used, timing, errors",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp",
    )
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
    
    # Vector search fields (optional, enabled via feature flag)
    embedding: Optional[List[float]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Vector embedding for semantic search",
    )
    embedding_model: Optional[str] = Field(
        default=None,
        description="Model used for generating embedding",
    )


class SiteAdapter(SQLModel, table=True):
    __tablename__ = "site_adapter"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str = Field(index=True, unique=True)
    selectors: Dict[str, str] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Selector strategies keyed by logical name",
    )
    wait_strategies: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Wait strategies such as timeouts, network idle, DOM ready",
    )
    version: int = Field(default=1, description="Monotonic adapter version")
    audit_trail: List[Dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
        description="Append-only audit trail of changes",
    )
    success_rate: float = Field(default=0.0, description="Recent success rate (0.0-1.0)")
    avg_execution_time: float = Field(default=0.0, description="Average execution time in ms")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Performance metrics
    total_executions: int = Field(default=0, description="Total number of executions")
    successful_executions: int = Field(default=0, description="Number of successful executions")
    common_errors: Dict[str, int] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Frequency of common error types",
    )


class IncidentLog(SQLModel, table=True):
    __tablename__ = "incident_log"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: Optional[str] = Field(default=None, index=True)
    domain: Optional[str] = Field(default=None, index=True)
    error_type: str = Field(description="Error taxonomy value, e.g., selector_miss")
    message: str = Field(description="Human readable description")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Execution context at time of incident",
    )
    severity: str = Field(default="medium", description="Incident severity: low, medium, high")
    resolved: bool = Field(default=False, description="Whether incident has been addressed")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Reflection tracking
    reflection_applied: bool = Field(default=False, description="Whether reflection was applied")
    reflection_version: Optional[int] = Field(default=None, description="Adapter version after reflection")


class MemorySummary(SQLModel, table=True):
    __tablename__ = "memory_summary"
    __table_args__ = {"extend_existing": True}

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True)
    summary: str = Field(description="Rolling summary for the job")
    embedding: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
        description="Vector embedding stored as JSON (pgvector-ready)",
    )
    embedding_model: Optional[str] = Field(default=None, description="Model used for embedding")
    similarity_score: Optional[float] = Field(default=None, description="Similarity to query if searched")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# API models (Pydantic v2)
# ---------------------------------------------------------------------------


class MemoryWriteRequest(BaseModel):
    job_id: str = Field(min_length=1, description="Correlation id for the job")
    url: HttpUrl = Field(description="Source URL for the memory payload")
    cron: str = Field(description="Cron expression for scheduling")
    selector: str = Field(description="CSS/XPath selector regex")
    content: Dict[str, Any] = Field(
        default_factory=dict, description="Opaque memory payload to persist"
    )
    artifact_paths: List[str] = Field(
        default_factory=list,
        description="Supabase storage object paths to sign and persist",
    )

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        # Lightweight cron validation to avoid runtime surprises.
        parts = v.split()
        if len(parts) != 5 and len(parts) != 6:
            raise ValueError("cron expressions must have 5 or 6 fields")
        return v

    @field_validator("selector")
    @classmethod
    def validate_selector(cls, v: str) -> str:
        import re

        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"invalid selector regex: {exc}") from exc
        return v


class MemoryReadResponse(BaseModel):
    job_id: str
    content: Dict[str, Any]
    signed_artifacts: List[str]
    adapter_version: Optional[int]
    adapter: Optional[Dict[str, Any]]
    summary: Optional[str] = None


class SiteAdapterUpdate(BaseModel):
    domain: str
    selectors: Dict[str, str]
    wait_strategies: Dict[str, Any]
    version: int
    audit_trail: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def serialize_sqlmodel(obj: SQLModel) -> Dict[str, Any]:
    """
    Serialize a SQLModel instance to a JSON-serializable dict.
    """
    data = obj.model_dump()
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, bytes):
            data[key] = value.decode("utf-8")
    return json.loads(json.dumps(data))

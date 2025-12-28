from sqlmodel import SQLModel, Field, Column, JSON
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum as PyEnum
import json

class JobStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_BROKEN = "circuit_broken"

class Job(SQLModel, table=True):
    id: Optional[str] = Field(default=None, primary_key=True)
    type: str = Field(index=True)
    status: JobStatus = Field(default=JobStatus.PENDING)
    target: Dict[str, Any] = Field(sa_column=Column(JSON))
    parameters: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    result_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    artifacts: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: Optional[float] = None
    priority: int = Field(default=0, index=True)
    retry_count: int = Field(default=0)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

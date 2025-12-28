from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass
from enum import Enum

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_BROKEN = "circuit_broken"

@dataclass
class JobResult:
    job_id: str
    status: JobStatus
    data: Dict[str, Any]
    artifacts: Dict[str, Any]
    error: Optional[str] = None
    execution_time: float = 0.0

class BaseExecutor(ABC):
    @abstractmethod
    async def execute(self, job_data: Dict[str, Any]) -> JobResult:
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        pass
    
    @abstractmethod
    async def cleanup(self):
        pass

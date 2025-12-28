from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import hashlib
import json

class ActionResult:
    def __init__(self, 
                 action_type: str,
                 success: bool,
                 data: Optional[Dict[str, Any]] = None,
                 error: Optional[str] = None,
                 artifacts: Optional[Dict[str, str]] = None,
                 metrics: Optional[Dict[str, float]] = None):
        self.action_type = action_type
        self.success = success
        self.data = data or {}
        self.error = error
        self.artifacts = artifacts or {}
        self.metrics = metrics or {}
        self.timestamp = datetime.utcnow().isoformat()
        self.action_id = hashlib.md5(f"{action_type}{self.timestamp}".encode()).hexdigest()[:8]
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "artifacts": self.artifacts,
            "metrics": self.metrics,
            "timestamp": self.timestamp,
            "action_id": self.action_id
        }

class ActionContext:
    def __init__(self, 
                 page: Any,  # Playwright Page
                 job: Any,   # Job model
                 domain: str,
                 browser_pool: Optional[Any] = None,
                 config: Optional[Dict[str, Any]] = None):
        self.page = page
        self.job = job
        self.domain = domain
        self.browser_pool = browser_pool
        self.config = config or {}
        self.state = {}
        self._start_time = datetime.utcnow()
        
    def elapsed_ms(self) -> float:
        return (datetime.utcnow() - self._start_time).total_seconds() * 1000

class BaseAction(ABC):
    action_type = "base"
    
    @abstractmethod
    async def execute(self, context: ActionContext) -> ActionResult:
        pass
    
    def _create_result(self, 
                       success: bool, 
                       context: ActionContext,
                       data: Optional[Dict[str, Any]] = None,
                       error: Optional[str] = None,
                       artifacts: Optional[Dict[str, str]] = None) -> ActionResult:
        return ActionResult(
            action_type=self.action_type,
            success=success,
            data=data or {},
            error=error,
            artifacts=artifacts or {},
            metrics={"elapsed_ms": context.elapsed_ms()}
        )

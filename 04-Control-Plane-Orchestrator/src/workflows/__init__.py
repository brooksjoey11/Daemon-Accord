"""
Workflow Templates Module

First-class workflow templates for common use cases:
- Page change detection
- Job posting monitoring
- Uptime/UX smoke checks
"""
from .workflow_registry import WorkflowRegistry, get_workflow_registry
from .workflow_executor import WorkflowExecutor
from .models import WorkflowDefinition, WorkflowResult

__all__ = [
    "WorkflowRegistry",
    "get_workflow_registry",
    "WorkflowExecutor",
    "WorkflowDefinition",
    "WorkflowResult",
]


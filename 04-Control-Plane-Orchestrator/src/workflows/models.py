"""
Workflow Models

Defines workflow schemas and result structures.
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowDefinition(BaseModel):
    """Workflow template definition."""
    name: str = Field(description="Workflow name (unique identifier)")
    display_name: str = Field(description="Human-readable display name")
    description: str = Field(description="Workflow description")
    input_schema: Dict[str, Any] = Field(description="JSON Schema for input validation")
    output_schema: Dict[str, Any] = Field(description="JSON Schema for output validation")
    execution_steps: List[str] = Field(description="List of execution steps")
    job_type: str = Field(description="Underlying job type to use")
    default_strategy: str = Field(default="vanilla", description="Default execution strategy")


class WorkflowInput(BaseModel):
    """Workflow input validation."""
    url: str = Field(description="Target URL")
    domain: str = Field(description="Target domain")
    webhook_url: Optional[str] = Field(default=None, description="Optional webhook URL for notifications")
    strategy: Optional[str] = Field(default=None, description="Execution strategy override")
    additional_params: Optional[Dict[str, Any]] = Field(default=None, description="Workflow-specific parameters")


class WorkflowResult(BaseModel):
    """Workflow execution result."""
    workflow_name: str = Field(description="Workflow that was executed")
    job_id: str = Field(description="Underlying job ID")
    status: WorkflowStatus = Field(description="Workflow status")
    input: Dict[str, Any] = Field(description="Workflow input")
    output: Optional[Dict[str, Any]] = Field(default=None, description="Workflow output")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    webhook_sent: bool = Field(default=False, description="Whether webhook was sent")


class PageChangeDetectionInput(WorkflowInput):
    """Input for page change detection workflow."""
    selectors: List[str] = Field(description="CSS selectors to monitor for changes")
    baseline_content: Optional[str] = Field(default=None, description="Baseline content hash (for first run)")
    alert_on_change: bool = Field(default=True, description="Send alert when changes detected")


class JobPostingMonitorInput(WorkflowInput):
    """Input for job posting monitor workflow."""
    extract_fields: Dict[str, str] = Field(
        description="Field mappings: {'field_name': 'css_selector'}"
    )
    alert_on_new: bool = Field(default=True, description="Send alert when new postings found")
    filter_keywords: Optional[List[str]] = Field(default=None, description="Keywords to filter postings")


class UptimeSmokeCheckInput(WorkflowInput):
    """Input for uptime/UX smoke check workflow."""
    required_selectors: List[str] = Field(description="CSS selectors that must be present")
    screenshot: bool = Field(default=True, description="Capture screenshot")
    verify_load_time: bool = Field(default=True, description="Verify page load time")
    max_load_time_ms: Optional[int] = Field(default=5000, description="Maximum acceptable load time (ms)")


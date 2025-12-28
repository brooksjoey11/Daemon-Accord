"""
Workflow Registry

Registers and manages available workflow templates.
"""
from typing import Dict, Optional, Any
from .models import WorkflowDefinition


class WorkflowRegistry:
    """Registry of available workflow templates."""
    
    def __init__(self):
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._register_default_workflows()
    
    def _register_default_workflows(self):
        """Register the three default workflow templates."""
        
        # 1. Page Change Detection
        self.register(WorkflowDefinition(
            name="page_change_detection",
            display_name="Page Change Detection",
            description="Monitor public pages for changes and alert when content differs from baseline",
            input_schema={
                "type": "object",
                "required": ["url", "domain", "selectors"],
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "domain": {"type": "string"},
                    "selectors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "CSS selectors to monitor"
                    },
                    "baseline_content": {"type": "string", "description": "Baseline content hash"},
                    "alert_on_change": {"type": "boolean", "default": True},
                    "webhook_url": {"type": "string", "format": "uri"},
                    "strategy": {"type": "string", "enum": ["vanilla", "stealth", "assault"], "default": "vanilla"}
                }
            },
            output_schema={
                "type": "object",
                "properties": {
                    "changed": {"type": "boolean", "description": "Whether content changed"},
                    "baseline_hash": {"type": "string", "description": "Previous content hash"},
                    "current_hash": {"type": "string", "description": "Current content hash"},
                    "diff_summary": {"type": "string", "description": "Summary of changes"},
                    "extracted_content": {"type": "object", "description": "Extracted content from selectors"},
                    "alert_sent": {"type": "boolean", "description": "Whether alert was sent"}
                }
            },
            execution_steps=[
                "1. Navigate to target URL",
                "2. Extract content from specified selectors",
                "3. Calculate content hash",
                "4. Compare with baseline (if provided)",
                "5. Generate diff summary if changed",
                "6. Send webhook alert if changes detected"
            ],
            job_type="navigate_extract",
            default_strategy="vanilla"
        ))
        
        # 2. Job Posting Monitor
        self.register(WorkflowDefinition(
            name="job_posting_monitor",
            display_name="Job Posting Monitor",
            description="Monitor job board pages and extract structured job posting data",
            input_schema={
                "type": "object",
                "required": ["url", "domain", "extract_fields"],
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "domain": {"type": "string"},
                    "extract_fields": {
                        "type": "object",
                        "description": "Field mappings: {'title': 'h2.job-title', 'company': '.company-name'}",
                        "additionalProperties": {"type": "string"}
                    },
                    "alert_on_new": {"type": "boolean", "default": True},
                    "filter_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keywords to filter postings"
                    },
                    "webhook_url": {"type": "string", "format": "uri"},
                    "strategy": {"type": "string", "enum": ["vanilla", "stealth", "assault"], "default": "stealth"}
                }
            },
            output_schema={
                "type": "object",
                "properties": {
                    "postings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "description": "Extracted job posting data"
                        }
                    },
                    "posting_count": {"type": "integer", "description": "Number of postings found"},
                    "new_postings": {"type": "integer", "description": "Number of new postings"},
                    "alert_sent": {"type": "boolean", "description": "Whether alert was sent"}
                }
            },
            execution_steps=[
                "1. Navigate to job board URL",
                "2. Extract structured data using field mappings",
                "3. Filter postings by keywords (if provided)",
                "4. Compare with previous run (if baseline exists)",
                "5. Identify new postings",
                "6. Send webhook alert if new postings found"
            ],
            job_type="navigate_extract",
            default_strategy="stealth"
        ))
        
        # 3. Uptime/UX Smoke Check
        self.register(WorkflowDefinition(
            name="uptime_smoke_check",
            display_name="Uptime/UX Smoke Check",
            description="Verify page loads correctly, required elements present, and capture screenshot",
            input_schema={
                "type": "object",
                "required": ["url", "domain", "required_selectors"],
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "domain": {"type": "string"},
                    "required_selectors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "CSS selectors that must be present"
                    },
                    "screenshot": {"type": "boolean", "default": True},
                    "verify_load_time": {"type": "boolean", "default": True},
                    "max_load_time_ms": {"type": "integer", "default": 5000},
                    "webhook_url": {"type": "string", "format": "uri"},
                    "strategy": {"type": "string", "enum": ["vanilla", "stealth", "assault"], "default": "vanilla"}
                }
            },
            output_schema={
                "type": "object",
                "properties": {
                    "page_loaded": {"type": "boolean", "description": "Whether page loaded successfully"},
                    "load_time_ms": {"type": "number", "description": "Page load time in milliseconds"},
                    "selectors_found": {
                        "type": "object",
                        "description": "Map of selector to found status"
                    },
                    "all_selectors_present": {"type": "boolean", "description": "Whether all required selectors found"},
                    "screenshot_path": {"type": "string", "description": "Path to screenshot if captured"},
                    "status": {"type": "string", "enum": ["pass", "fail"], "description": "Overall check status"},
                    "alert_sent": {"type": "boolean", "description": "Whether alert was sent"}
                }
            },
            execution_steps=[
                "1. Navigate to target URL and measure load time",
                "2. Verify all required selectors are present",
                "3. Capture screenshot (if enabled)",
                "4. Determine overall status (pass/fail)",
                "5. Send webhook alert if check fails"
            ],
            job_type="navigate_extract",
            default_strategy="vanilla"
        ))
    
    def register(self, workflow: WorkflowDefinition):
        """Register a workflow template."""
        self._workflows[workflow.name] = workflow
    
    def get(self, name: str) -> Optional[WorkflowDefinition]:
        """Get a workflow by name."""
        return self._workflows.get(name)
    
    def list_all(self) -> Dict[str, WorkflowDefinition]:
        """List all registered workflows."""
        return self._workflows.copy()
    
    def get_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get summary of all workflows (for API listing)."""
        return {
            name: {
                "name": wf.name,
                "display_name": wf.display_name,
                "description": wf.description,
                "input_schema": wf.input_schema,
                "output_schema": wf.output_schema,
            }
            for name, wf in self._workflows.items()
        }


# Global registry instance
_workflow_registry: Optional[WorkflowRegistry] = None


def get_workflow_registry() -> WorkflowRegistry:
    """Get the global workflow registry."""
    global _workflow_registry
    if _workflow_registry is None:
        _workflow_registry = WorkflowRegistry()
    return _workflow_registry


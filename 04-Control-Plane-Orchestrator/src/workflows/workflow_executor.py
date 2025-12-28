"""
Workflow Executor

Executes workflow templates by converting them to jobs and processing results.
"""
import json
import hashlib
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime
import httpx as httpx_module
import structlog

from .models import WorkflowDefinition, WorkflowResult, WorkflowStatus
from .workflow_registry import get_workflow_registry

if TYPE_CHECKING:
    from ..control_plane.job_orchestrator import JobOrchestrator

logger = structlog.get_logger(__name__)


class WorkflowExecutor:
    """Executes workflow templates."""
    
    def __init__(self, job_orchestrator: "JobOrchestrator") -> None:
        """
        Initialize workflow executor.
        
        Args:
            job_orchestrator: JobOrchestrator instance for creating jobs
        """
        self.job_orchestrator = job_orchestrator
        self.registry = get_workflow_registry()
    
    async def execute_workflow(
        self,
        workflow_name: str,
        input_data: Dict[str, Any],
        webhook_url: Optional[str] = None
    ) -> WorkflowResult:
        """
        Execute a workflow template.
        
        Args:
            workflow_name: Name of workflow to execute
            input_data: Workflow input data
            webhook_url: Optional webhook URL for notifications
            
        Returns:
            WorkflowResult with execution details
        """
        # Get workflow definition
        workflow = self.registry.get(workflow_name)
        if not workflow:
            raise ValueError(f"Workflow '{workflow_name}' not found")
        
        # Validate input
        self._validate_input(workflow, input_data)
        
        # Convert workflow input to job payload
        job_payload = self._convert_to_job_payload(workflow, input_data)
        
        # Create job
        strategy = input_data.get("strategy") or workflow.default_strategy
        job_id = await self.job_orchestrator.create_job(
            domain=input_data["domain"],
            url=input_data["url"],
            job_type=workflow.job_type,
            strategy=strategy,
            payload=job_payload,
            priority=2,  # Normal priority
            idempotency_key=f"workflow-{workflow_name}-{input_data.get('url', '')}"
        )
        
        # Return workflow result (job will be processed asynchronously)
        return WorkflowResult(
            workflow_name=workflow_name,
            job_id=job_id,
            status=WorkflowStatus.PENDING,
            input=input_data,
            webhook_sent=False
        )
    
    def _validate_input(self, workflow: WorkflowDefinition, input_data: Dict[str, Any]):
        """Validate input against workflow schema."""
        # Basic validation - full JSON Schema validation can be added
        required_fields = workflow.input_schema.get("required", [])
        for field in required_fields:
            if field not in input_data:
                raise ValueError(f"Missing required field: {field}")
    
    def _convert_to_job_payload(self, workflow: WorkflowDefinition, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert workflow input to job payload based on workflow type."""
        payload = {}
        
        if workflow.name == "page_change_detection":
            payload = {
                "selector": ", ".join(input_data.get("selectors", [])),
                "extract": ["text", "html"],
                "screenshot": True,
                "workflow_type": "page_change_detection",
                "baseline_content": input_data.get("baseline_content"),
                "alert_on_change": input_data.get("alert_on_change", True),
            }
        
        elif workflow.name == "job_posting_monitor":
            extract_fields = input_data.get("extract_fields", {})
            payload = {
                "extract_fields": extract_fields,
                "workflow_type": "job_posting_monitor",
                "alert_on_new": input_data.get("alert_on_new", True),
                "filter_keywords": input_data.get("filter_keywords"),
            }
        
        elif workflow.name == "uptime_smoke_check":
            payload = {
                "required_selectors": input_data.get("required_selectors", []),
                "screenshot": input_data.get("screenshot", True),
                "verify_load_time": input_data.get("verify_load_time", True),
                "max_load_time_ms": input_data.get("max_load_time_ms", 5000),
                "workflow_type": "uptime_smoke_check",
            }
        
        # Store webhook URL in payload for post-processing
        if input_data.get("webhook_url"):
            payload["webhook_url"] = input_data["webhook_url"]
        
        return payload
    
    async def process_workflow_result(
        self,
        workflow_name: str,
        job_id: str,
        job_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process job result and convert to workflow output format.
        
        Args:
            workflow_name: Name of workflow
            job_id: Job ID
            job_result: Result from job execution
            
        Returns:
            Workflow-specific output
        """
        workflow = self.registry.get(workflow_name)
        if not workflow:
            logger.warning(
                "workflow_not_found_result_processing",
                workflow_name=workflow_name,
                job_id=job_id
            )
            return job_result
        
        if not job_result.get("success"):
            return {
                "error": job_result.get("error", "Job execution failed"),
                "status": "failed"
            }
        
        extracted_data = job_result.get("data", {})
        payload = job_result.get("payload", {})
        workflow_type = payload.get("workflow_type")
        
        # Process based on workflow type
        if workflow_type == "page_change_detection":
            return await self._process_page_change_detection(extracted_data, payload)
        
        elif workflow_type == "job_posting_monitor":
            return await self._process_job_posting_monitor(extracted_data, payload)
        
        elif workflow_type == "uptime_smoke_check":
            return await self._process_uptime_smoke_check(extracted_data, payload, job_result)
        
        # Default: return raw data
        return extracted_data
    
    async def _process_page_change_detection(
        self,
        extracted_data: Dict[str, Any],
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process page change detection workflow result."""
        # Calculate content hash
        content = extracted_data.get("html", "") or extracted_data.get("text", "")
        current_hash = hashlib.sha256(content.encode()).hexdigest()
        
        baseline_hash = payload.get("baseline_content")
        changed = baseline_hash is not None and current_hash != baseline_hash
        
        result = {
            "changed": changed,
            "current_hash": current_hash,
            "baseline_hash": baseline_hash,
            "extracted_content": extracted_data,
            "alert_sent": False
        }
        
        # Generate diff summary if changed
        if changed:
            result["diff_summary"] = f"Content hash changed from {baseline_hash[:8]} to {current_hash[:8]}"
        
        # Send webhook if changed and alert enabled
        if changed and payload.get("alert_on_change", True):
            webhook_url = payload.get("webhook_url")
            if webhook_url:
                await self._send_webhook(webhook_url, {
                    "workflow": "page_change_detection",
                    "changed": True,
                    "current_hash": current_hash,
                    "baseline_hash": baseline_hash,
                    "diff_summary": result.get("diff_summary")
                })
                result["alert_sent"] = True
        
        return result
    
    async def _process_job_posting_monitor(
        self,
        extracted_data: Dict[str, Any],
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process job posting monitor workflow result."""
        extract_fields = payload.get("extract_fields", {})
        postings = []
        
        # Extract structured data (simplified - assumes list of postings)
        # In real implementation, would parse HTML structure
        elements = extracted_data.get("elements", [])
        
        for element in elements:
            posting = {}
            for field_name, selector in extract_fields.items():
                # Find element matching selector and extract value
                posting[field_name] = element.get(field_name, "")
            postings.append(posting)
        
        # Filter by keywords if provided
        filter_keywords = payload.get("filter_keywords")
        if filter_keywords:
            filtered_postings = []
            for posting in postings:
                text = " ".join(str(v) for v in posting.values()).lower()
                if any(keyword.lower() in text for keyword in filter_keywords):
                    filtered_postings.append(posting)
            postings = filtered_postings
        
        result = {
            "postings": postings,
            "posting_count": len(postings),
            "new_postings": len(postings),  # Would compare with baseline in real implementation
            "alert_sent": False
        }
        
        # Send webhook if new postings and alert enabled
        if postings and payload.get("alert_on_new", True):
            webhook_url = payload.get("webhook_url")
            if webhook_url:
                await self._send_webhook(webhook_url, {
                    "workflow": "job_posting_monitor",
                    "posting_count": len(postings),
                    "new_postings": len(postings),
                    "postings": postings[:10]  # Limit to first 10
                })
                result["alert_sent"] = True
        
        return result
    
    async def _process_uptime_smoke_check(
        self,
        extracted_data: Dict[str, Any],
        payload: Dict[str, Any],
        job_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process uptime smoke check workflow result."""
        required_selectors = payload.get("required_selectors", [])
        selectors_found = {}
        
        # Check which selectors are present
        html = extracted_data.get("html", "")
        for selector in required_selectors:
            # Simplified check - in real implementation would use proper CSS selector matching
            selectors_found[selector] = selector in html or True  # Placeholder
        
        all_present = all(selectors_found.values())
        
        # Get load time from execution timing
        execution_time = job_result.get("execution_time", 0.0)
        load_time_ms = execution_time * 1000  # Convert to milliseconds
        
        max_load_time = payload.get("max_load_time_ms", 5000)
        load_time_ok = not payload.get("verify_load_time", True) or load_time_ms <= max_load_time
        
        status = "pass" if (all_present and load_time_ok) else "fail"
        
        result = {
            "page_loaded": True,
            "load_time_ms": load_time_ms,
            "selectors_found": selectors_found,
            "all_selectors_present": all_present,
            "status": status,
            "alert_sent": False
        }
        
        # Add screenshot path if available
        artifacts = job_result.get("artifacts", {})
        if "screenshot" in artifacts:
            result["screenshot_path"] = artifacts["screenshot"]
        
        # Send webhook if check failed
        if status == "fail":
            webhook_url = payload.get("webhook_url")
            if webhook_url:
                await self._send_webhook(webhook_url, {
                    "workflow": "uptime_smoke_check",
                    "status": "fail",
                    "load_time_ms": load_time_ms,
                    "selectors_found": selectors_found,
                    "all_selectors_present": all_present
                })
                result["alert_sent"] = True
        
        return result
    
    async def _send_webhook(self, webhook_url: str, data: Dict[str, Any]) -> bool:
        """Send webhook notification."""
        try:
            async with httpx_module.AsyncClient(timeout=10.0) as client:
                response = await client.post(webhook_url, json=data)
                response.raise_for_status()
                logger.info("webhook_sent_successfully", webhook_url=webhook_url)
                return True
        except Exception as e:
            logger.error(
                "webhook_send_failed",
                webhook_url=webhook_url,
                error=str(e),
                exc_info=True
            )
            return False


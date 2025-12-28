import aiohttp
import json
import asyncio
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
import logging

class MemoryHook:
    def __init__(self, 
                 memory_service_url: str = "http://memory:8100",
                 api_key: Optional[str] = None,
                 session: Optional[aiohttp.ClientSession] = None):
        self.base_url = memory_service_url.rstrip('/')
        self.api_key = api_key or "default_key"
        self.session = session
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "User-Agent": "ExecutionWorker/1.0"
        }
        self.timeout = aiohttp.ClientTimeout(total=30)
    
    async def store_execution(self, job: Any, result: Any, 
                            artifact_references: Dict[str, str] = None) -> Dict[str, Any]:
        """Store execution result in memory service."""
        if artifact_references is None:
            artifact_references = {}
        
        payload = {
            "execution_id": job.id if hasattr(job, 'id') else str(hash(job)),
            "job_id": job.id if hasattr(job, 'id') else "unknown",
            "timestamp": datetime.utcnow().isoformat(),
            "domain": job.domain if hasattr(job, 'domain') else self._extract_domain(job.url),
            "url": job.url if hasattr(job, 'url') else "",
            "strategy_used": job.payload.get('evasion_level', 0) if hasattr(job, 'payload') else 0,
            "success": result.success if hasattr(result, 'success') else False,
            "duration_ms": result.timing.get('total_ms', 0) if hasattr(result, 'timing') else 0,
            "error": result.error if hasattr(result, 'error') else None,
            "data_snippets": self._extract_data_snippets(result),
            "artifact_references": artifact_references,
            "metadata": {
                "user_agent": job.user_agent if hasattr(job, 'user_agent') else None,
                "viewport": job.viewport if hasattr(job, 'viewport') else None,
                "evasion_techniques": job.payload.get('evasion_techniques', []) if hasattr(job, 'payload') else []
            }
        }
        
        try:
            response = await self._post("/memory", payload)
            return response
        except Exception as e:
            logging.error(f"Failed to store execution: {e}")
            return {"error": str(e), "stored": False}
    
    async def publish_incident(self, domain: str, error_type: str, 
                              context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Publish incident to memory service."""
        if context is None:
            context = {}
        
        payload = {
            "domain": domain,
            "error_type": error_type,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context,
            "severity": context.get("severity", "medium"),
            "automated_response": context.get("automated_response", False)
        }
        
        try:
            response = await self._post(f"/memory/incident/{domain}", payload)
            return response
        except Exception as e:
            logging.error(f"Failed to publish incident: {e}")
            return {"error": str(e), "published": False}
    
    async def store_reflection(self, reflection_event: Dict[str, Any]) -> Dict[str, Any]:
        """Store reflection/learning event."""
        payload = {
            "type": "strategy_reflection",
            "timestamp": datetime.utcnow().isoformat(),
            "event": reflection_event,
            "processed": False
        }
        
        try:
            response = await self._post("/memory/reflection", payload)
            return response
        except Exception as e:
            logging.error(f"Failed to store reflection: {e}")
            return {"error": str(e), "stored": False}
    
    async def get_domain_insights(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get insights for a domain."""
        try:
            response = await self._get(f"/memory/insights/{domain}")
            return response
        except Exception as e:
            logging.warning(f"Failed to get domain insights: {e}")
            return None
    
    async def update_domain_health(self, domain: str, health_score: float, 
                                  details: Dict[str, Any] = None) -> Dict[str, Any]:
        """Update domain health score."""
        if details is None:
            details = {}
        
        payload = {
            "domain": domain,
            "health_score": health_score,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details
        }
        
        try:
            response = await self._post("/memory/health", payload)
            return response
        except Exception as e:
            logging.error(f"Failed to update domain health: {e}")
            return {"error": str(e), "updated": False}
    
    async def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to memory service."""
        session = self.session or aiohttp.ClientSession()
        
        try:
            async with session.post(
                f"{self.base_url}{endpoint}",
                json=data,
                headers=self.headers,
                timeout=self.timeout
            ) as response:
                if response.status in (200, 201):
                    return await response.json()
                else:
                    text = await response.text()
                    raise Exception(f"HTTP {response.status}: {text}")
        finally:
            if not self.session:
                await session.close()
    
    async def _get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Make GET request to memory service."""
        session = self.session or aiohttp.ClientSession()
        
        try:
            async with session.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                timeout=self.timeout
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
        finally:
            if not self.session:
                await session.close()
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        
        if ':' in domain:
            domain = domain.split(':')[0]
        
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return domain
    
    def _extract_data_snippets(self, result: Any) -> Dict[str, Any]:
        """Extract data snippets from execution result."""
        snippets = {}
        
        if hasattr(result, 'data') and result.data:
            # Extract first few items/characters
            for key, value in result.data.items():
                if isinstance(value, str):
                    snippets[key] = value[:200] + ("..." if len(value) > 200 else "")
                elif isinstance(value, (list, dict)):
                    snippets[key] = str(value)[:200] + ("..." if len(str(value)) > 200 else "")
        
        return snippets

class MemoryHookManager:
    def __init__(self, memory_service_url: str, api_key: Optional[str] = None):
        self.memory_hook = MemoryHook(memory_service_url, api_key)
        self.batch_queue = []
        self.batch_size = 50
        self.batch_interval = 5  # seconds
    
    async def batch_store_execution(self, job: Any, result: Any, 
                                  artifact_references: Dict[str, str] = None):
        """Batch execution storage for efficiency."""
        self.batch_queue.append(("execution", job, result, artifact_references))
        
        if len(self.batch_queue) >= self.batch_size:
            await self._process_batch()
    
    async def _process_batch(self):
        """Process batched requests."""
        if not self.batch_queue:
            return
        
        batch = self.batch_queue.copy()
        self.batch_queue.clear()
        
        tasks = []
        for item in batch:
            req_type, job, result, artifacts = item
            
            if req_type == "execution":
                task = self.memory_hook.store_execution(job, result, artifacts)
                tasks.append(task)
            elif req_type == "incident":
                domain, error_type, context = job, result, artifacts
                task = self.memory_hook.publish_incident(domain, error_type, context)
                tasks.append(task)
        
        # Execute all tasks concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def start_batch_processor(self):
        """Start background batch processor."""
        async def processor():
            while True:
                await asyncio.sleep(self.batch_interval)
                await self._process_batch()
        
        asyncio.create_task(processor())
    
    async def flush(self):
        """Flush remaining items in batch."""
        await self._process_batch()

import asyncio
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta
from .standard_executor import StandardExecutor
from .executor import JobResult, JobStatus
import hashlib
import logging
from dataclasses import dataclass
from playwright.async_api import Page, Request, Response
import json
import os

logger = logging.getLogger(__name__)

@dataclass
class ArtifactConfig:
    capture_screenshots: bool = True
    capture_har: bool = True
    capture_console: bool = True
    capture_dom: bool = True
    full_page: bool = True

class EnhancedExecutor(StandardExecutor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.artifact_queue = asyncio.Queue()
        self.active_sessions = {}
        
    async def _execute_job(self, job_data: Dict[str, Any]) -> JobResult:
        job_id = job_data.get('id', 'unknown')
        job_type = job_data.get('type', 'unknown')
        
        artifacts = {}
        session_key = await self._get_session_key(job_data)
        
        if session_key in self.active_sessions:
            page = self.active_sessions[session_key]
            logger.info(f"Reusing session for {session_key}")
        else:
            page = await self.pool.acquire_page()
            self.active_sessions[session_key] = page
            logger.info(f"Created new session for {session_key}")
        
        try:
            await self._setup_artifact_capture(page, job_id)
            
            if job_type in ['price_extraction']:
                result = await self._execute_price_extraction(page, job_data)
            elif job_type in ['login']:
                result = await self._execute_login(page, job_data)
            else:
                result = await super()._execute_job(job_data)
            
            artifacts = await self._collect_artifacts(page, job_data)
            result.artifacts.update(artifacts)
            
            return result
            
        finally:
            if session_key not in self.active_sessions:
                await self.pool.release_page(page)
    
    async def _execute_price_extraction(self, page: Page, job_data: Dict[str, Any]) -> JobResult:
        start_time = time.time()
        target = job_data.get('target', {})
        url = target.get('url', '')
        selectors = job_data.get('selectors', [])
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=10000)
            
            extracted_data = {}
            for selector in selectors:
                elements = await page.query_selector_all(selector)
                values = []
                for element in elements:
                    text = await element.text_content()
                    if text:
                        values.append(text.strip())
                extracted_data[selector] = values
            
            execution_time = time.time() - start_time
            logger.info(f"Price extraction completed in {execution_time:.2f}s")
            
            return JobResult(
                job_id=job_data.get('id', ''),
                status=JobStatus.SUCCESS,
                data={'extracted': extracted_data},
                artifacts={},
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            raise Exception(f"Price extraction failed: {str(e)}")
    
    async def _execute_login(self, page: Page, job_data: Dict[str, Any]) -> JobResult:
        start_time = time.time()
        target = job_data.get('target', {})
        url = target.get('url', '')
        credentials = await self._get_credentials(job_data)
        
        try:
            await page.goto(url, wait_until='networkidle')
            
            login_success = await self._perform_login_sequence(page, credentials)
            
            if login_success:
                cookies = await page.context.cookies()
                await self._persist_session(cookies, job_data)
                
                execution_time = time.time() - start_time
                logger.info(f"Login completed in {execution_time:.2f}s")
                
                return JobResult(
                    job_id=job_data.get('id', ''),
                    status=JobStatus.SUCCESS,
                    data={'authenticated': True, 'cookies': len(cookies)},
                    artifacts={},
                    execution_time=execution_time
                )
            else:
                raise Exception("Login sequence failed")
                
        except Exception as e:
            execution_time = time.time() - start_time
            raise Exception(f"Login failed: {str(e)}")
    
    async def _get_session_key(self, job_data: Dict[str, Any]) -> str:
        target = job_data.get('target', {})
        domain = target.get('domain', '')
        credentials = await self._get_credentials(job_data)
        
        if credentials:
            cred_hash = hashlib.md5(json.dumps(credentials).encode()).hexdigest()
            return f"{domain}:{cred_hash}"
        
        return domain
    
    async def _get_credentials(self, job_data: Dict[str, Any]) -> Dict[str, str]:
        credentials = job_data.get('credentials', {})
        
        if not credentials:
            target = job_data.get('target', {})
            domain = target.get('domain', '')
            
            env_key = f"CRED_{domain.upper().replace('.', '_')}"
            username = credentials.get('username') or os.getenv(f"{env_key}_USERNAME")
            password = credentials.get('password') or os.getenv(f"{env_key}_PASSWORD")
            
            if username and password:
                return {'username': username, 'password': password}
        
        return credentials
    
    async def _setup_artifact_capture(self, page: Page, job_id: str):
        console_messages = []
        network_requests = []
        
        def console_handler(msg):
            console_messages.append({
                'type': msg.type,
                'text': msg.text,
                'timestamp': datetime.utcnow().isoformat()
            })
        
        def request_handler(request: Request):
            network_requests.append({
                'url': request.url,
                'method': request.method,
                'headers': dict(request.headers),
                'timestamp': datetime.utcnow().isoformat()
            })
        
        page.on('console', console_handler)
        page.on('request', request_handler)
        
        self.artifact_queue.put_nowait({
            'job_id': job_id,
            'console': console_messages,
            'network': network_requests
        })
    
    async def _collect_artifacts(self, page: Page, job_data: Dict[str, Any]) -> Dict[str, Any]:
        artifacts = {}
        config = job_data.get('artifact_config', {})
        
        if config.get('capture_screenshots', True):
            if config.get('full_page', True):
                screenshot = await page.screenshot(full_page=True)
                artifacts['screenshot_full'] = screenshot
            
            screenshot = await page.screenshot()
            artifacts['screenshot'] = screenshot
        
        if config.get('capture_dom', True):
            dom_content = await page.content()
            artifacts['dom'] = dom_content
        
        if config.get('capture_console', True):
            console_logs = await page.evaluate("""() => {
                return window.console.messages || [];
            }""")
            artifacts['console_logs'] = console_logs
        
        return artifacts
    
    async def _persist_session(self, cookies: List[Dict], job_data: Dict[str, Any]):
        session_key = await self._get_session_key(job_data)
        
        await self.redis.setex(
            f"session:{session_key}",
            timedelta(hours=24),
            json.dumps(cookies)
        )
    
    async def cleanup(self):
        for page in self.active_sessions.values():
            await self.pool.release_page(page)
        self.active_sessions.clear()
        await super().cleanup()

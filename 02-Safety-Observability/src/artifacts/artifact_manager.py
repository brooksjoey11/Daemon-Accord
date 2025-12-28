import asyncio
import json
import os
import base64
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import aiofiles
from playwright.async_api import Page, Request, Response
import gzip

class ArtifactManager:
    def __init__(self, base_path: str = "/app/artifacts"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    async def capture(self, page: Page, job_id: str, 
                     capture_types: Optional[list] = None) -> Dict[str, Any]:
        """
        Capture comprehensive evidence from Playwright page.
        Returns dict with evidence types as keys and paths as values.
        """
        if capture_types is None:
            capture_types = ['fullpage', 'viewport', 'network', 'console', 
                           'dom', 'cookies', 'storage']
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        job_path = self.base_path / job_id
        job_path.mkdir(exist_ok=True)
        
        evidence = {}
        tasks = []
        
        # Capture full-page screenshot
        if 'fullpage' in capture_types:
            tasks.append(self._capture_fullpage(page, job_path, timestamp, evidence))
        
        # Capture viewport screenshot
        if 'viewport' in capture_types:
            tasks.append(self._capture_viewport(page, job_path, timestamp, evidence))
        
        # Capture network traffic
        if 'network' in capture_types:
            tasks.append(self._capture_network(page, job_path, timestamp, evidence))
        
        # Capture console logs
        if 'console' in capture_types:
            tasks.append(self._capture_console(page, job_path, timestamp, evidence))
        
        # Capture DOM
        if 'dom' in capture_types:
            tasks.append(self._capture_dom(page, job_path, timestamp, evidence))
        
        # Capture cookies
        if 'cookies' in capture_types:
            tasks.append(self._capture_cookies(page.context, job_path, timestamp, evidence))
        
        # Capture localStorage/sessionStorage
        if 'storage' in capture_types:
            tasks.append(self._capture_storage(page, job_path, timestamp, evidence))
        
        # Execute all captures concurrently
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Create symlink to latest
        await self._create_latest_symlink(job_path, timestamp)
        
        return evidence
    
    async def _capture_fullpage(self, page: Page, job_path: Path, 
                              timestamp: str, evidence: Dict[str, Any]):
        """Capture full page screenshot."""
        try:
            filename = f"{timestamp}_fullpage.png"
            filepath = job_path / filename
            
            await page.screenshot(
                path=str(filepath),
                full_page=True,
                type='png'
            )
            
            evidence['fullpage'] = {
                'path': str(filepath),
                'type': 'image/png',
                'checksum': await self._calculate_checksum(filepath)
            }
        except Exception as e:
            evidence['fullpage'] = {'error': str(e)}
    
    async def _capture_viewport(self, page: Page, job_path: Path, 
                              timestamp: str, evidence: Dict[str, Any]):
        """Capture viewport screenshot."""
        try:
            filename = f"{timestamp}_viewport.png"
            filepath = job_path / filename
            
            await page.screenshot(
                path=str(filepath),
                full_page=False,
                type='png'
            )
            
            evidence['viewport'] = {
                'path': str(filepath),
                'type': 'image/png',
                'checksum': await self._calculate_checksum(filepath)
            }
        except Exception as e:
            evidence['viewport'] = {'error': str(e)}
    
    async def _capture_network(self, page: Page, job_path: Path, 
                             timestamp: str, evidence: Dict[str, Any]):
        """Capture network traffic as HAR."""
        try:
            filename = f"{timestamp}_network.har"
            filepath = job_path / filename
            
            # Extract network data via CDP
            cdp_session = await page.context.new_cdp_session(page)
            await cdp_session.send('Network.enable')
            
            # Collect requests and responses
            requests = {}
            
            def on_request(request):
                requests[request['requestId']] = {
                    'request': request,
                    'response': None
                }
            
            def on_response(response):
                if response['requestId'] in requests:
                    requests[response['requestId']]['response'] = response
            
            cdp_session.on('Network.requestWillBeSent', on_request)
            cdp_session.on('Network.responseReceived', on_response)
            
            # Wait a moment for data
            await asyncio.sleep(0.5)
            
            # Build HAR structure
            har_data = {
                "log": {
                    "version": "1.2",
                    "creator": {"name": "ArtifactManager", "version": "1.0"},
                    "pages": [],
                    "entries": []
                }
            }
            
            for req_id, data in requests.items():
                request = data.get('request')
                response = data.get('response')
                
                if request:
                    entry = {
                        "startedDateTime": datetime.utcnow().isoformat(),
                        "time": 0,
                        "request": {
                            "method": request.get('method', 'GET'),
                            "url": request.get('url', ''),
                            "httpVersion": "HTTP/1.1",
                            "headers": [
                                {"name": k, "value": v} 
                                for k, v in request.get('headers', {}).items()
                            ],
                            "queryString": [],
                            "postData": {"mimeType": "", "text": ""} if request.get('hasPostData') else None
                        },
                        "response": {
                            "status": response.get('status', 0) if response else 0,
                            "statusText": response.get('statusText', '') if response else '',
                            "headers": [
                                {"name": k, "value": v} 
                                for k, v in (response.get('headers', {}) if response else {})
                            ]
                        } if response else {"status": 0, "statusText": "", "headers": []},
                        "cache": {},
                        "timings": {}
                    }
                    har_data["log"]["entries"].append(entry)
            
            await cdp_session.detach()
            
            # Save HAR file
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(har_data, indent=2))
            
            evidence['network'] = {
                'path': str(filepath),
                'type': 'application/json',
                'checksum': await self._calculate_checksum(filepath)
            }
            
        except Exception as e:
            evidence['network'] = {'error': str(e)}
    
    async def _capture_console(self, page: Page, job_path: Path, 
                             timestamp: str, evidence: Dict[str, Any]):
        """Capture console logs."""
        try:
            filename = f"{timestamp}_console.json"
            filepath = job_path / filename
            
            # Evaluate JavaScript to get console logs
            console_logs = await page.evaluate('''() => {
                if (!window.__capturedLogs) {
                    window.__capturedLogs = [];
                    const originalLog = console.log;
                    const originalError = console.error;
                    const originalWarn = console.warn;
                    const originalInfo = console.info;
                    
                    function capture(type, args) {
                        window.__capturedLogs.push({
                            type: type,
                            timestamp: new Date().toISOString(),
                            message: Array.from(args).map(arg => 
                                typeof arg === 'object' ? JSON.stringify(arg) : String(arg)
                            ).join(' '),
                            stack: new Error().stack
                        });
                    }
                    
                    console.log = (...args) => { capture('log', args); originalLog.apply(console, args); };
                    console.error = (...args) => { capture('error', args); originalError.apply(console, args); };
                    console.warn = (...args) => { capture('warn', args); originalWarn.apply(console, args); };
                    console.info = (...args) => { capture('info', args); originalInfo.apply(console, args); };
                }
                return window.__capturedLogs;
            }''')
            
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(console_logs, indent=2))
            
            evidence['console'] = {
                'path': str(filepath),
                'type': 'application/json',
                'checksum': await self._calculate_checksum(filepath),
                'entries': len(console_logs)
            }
            
        except Exception as e:
            evidence['console'] = {'error': str(e)}
    
    async def _capture_dom(self, page: Page, job_path: Path, 
                         timestamp: str, evidence: Dict[str, Any]):
        """Capture DOM HTML."""
        try:
            filename = f"{timestamp}_dom.html"
            filepath = job_path / filename
            
            # Get full HTML
            html = await page.content()
            
            # Add metadata comment
            metadata = f"<!-- Captured: {timestamp} -->\n"
            html = metadata + html
            
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(html)
            
            evidence['dom'] = {
                'path': str(filepath),
                'type': 'text/html',
                'checksum': await self._calculate_checksum(filepath),
                'size': len(html)
            }
            
        except Exception as e:
            evidence['dom'] = {'error': str(e)}
    
    async def _capture_cookies(self, context, job_path: Path, 
                             timestamp: str, evidence: Dict[str, Any]):
        """Capture cookies."""
        try:
            filename = f"{timestamp}_cookies.json"
            filepath = job_path / filename
            
            cookies = await context.cookies()
            
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(cookies, indent=2))
            
            evidence['cookies'] = {
                'path': str(filepath),
                'type': 'application/json',
                'checksum': await self._calculate_checksum(filepath),
                'count': len(cookies)
            }
            
        except Exception as e:
            evidence['cookies'] = {'error': str(e)}
    
    async def _capture_storage(self, page: Page, job_path: Path, 
                             timestamp: str, evidence: Dict[str, Any]):
        """Capture localStorage and sessionStorage."""
        try:
            filename = f"{timestamp}_storage.json"
            filepath = job_path / filename
            
            storage_data = await page.evaluate('''() => {
                const data = {
                    localStorage: {},
                    sessionStorage: {}
                };
                
                try {
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        data.localStorage[key] = localStorage.getItem(key);
                    }
                } catch (e) {}
                
                try {
                    for (let i = 0; i < sessionStorage.length; i++) {
                        const key = sessionStorage.key(i);
                        data.sessionStorage[key] = sessionStorage.getItem(key);
                    }
                } catch (e) {}
                
                return data;
            }''')
            
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(storage_data, indent=2))
            
            evidence['storage'] = {
                'path': str(filepath),
                'type': 'application/json',
                'checksum': await self._calculate_checksum(filepath),
                'localStorage_count': len(storage_data.get('localStorage', {})),
                'sessionStorage_count': len(storage_data.get('sessionStorage', {}))
            }
            
        except Exception as e:
            evidence['storage'] = {'error': str(e)}
    
    async def _calculate_checksum(self, filepath: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256_hash = hashlib.sha256()
        
        try:
            async with aiofiles.open(filepath, 'rb') as f:
                while chunk := await f.read(8192):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except:
            return "0" * 64
    
    async def _create_latest_symlink(self, job_path: Path, timestamp: str):
        """Create symlink to latest capture."""
        try:
            latest_path = job_path / "latest"
            if latest_path.exists():
                latest_path.unlink()
            
            # Create relative symlink
            latest_path.symlink_to(timestamp, target_is_directory=False)
        except:
            pass
    
    async def capture_metadata(self, page: Page, job: Any) -> Dict[str, Any]:
        """Capture execution metadata."""
        metadata = {
            "job_id": job.id if hasattr(job, 'id') else "unknown",
            "url": job.url if hasattr(job, 'url') else await page.url(),
            "timestamp": datetime.utcnow().isoformat(),
            "user_agent": await page.evaluate('() => navigator.userAgent'),
            "viewport": await page.evaluate('''() => ({
                width: window.innerWidth,
                height: window.innerHeight,
                deviceScaleFactor: window.devicePixelRatio
            })'''),
            "platform": await page.evaluate('() => navigator.platform'),
            "language": await page.evaluate('() => navigator.language'),
            "cookies_enabled": await page.evaluate('() => navigator.cookieEnabled'),
            "online": await page.evaluate('() => navigator.onLine'),
            "execution_data": {
                "strategy": job.payload.get('evasion_level', 0) if hasattr(job, 'payload') else 0,
                "domain": self._extract_domain(job.url if hasattr(job, 'url') else await page.url()),
                "duration": getattr(job, 'duration_ms', 0) if hasattr(job, 'duration_ms') else 0
            }
        }
        
        # Add page metrics
        try:
            metrics = await page.evaluate('''() => {
                const entries = performance.getEntriesByType('navigation');
                return entries.length > 0 ? {
                    dom_content_loaded: entries[0].domContentLoadedEventEnd,
                    load_event: entries[0].loadEventEnd,
                    dom_complete: entries[0].domComplete,
                    redirect_count: entries[0].redirectCount,
                    type: entries[0].type
                } : {};
            }''')
            metadata["performance"] = metrics
        except:
            pass
        
        return metadata
    
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

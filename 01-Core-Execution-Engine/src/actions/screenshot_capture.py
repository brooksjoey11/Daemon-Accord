from typing import Dict, Any, Optional, Tuple
from playwright.async_api import Page
import asyncio
import time
import logging
import base64
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ScreenshotResult:
    screenshots: Dict[str, str]
    metadata: Dict[str, Any]
    duration: float
    error: Optional[str] = None

async def execute_screenshot_capture(job_data: Dict[str, Any], browser_pool) -> ScreenshotResult:
    page = await browser_pool.acquire_page()
    start_time = time.time()
    
    try:
        target = job_data.get('target', {})
        url = target.get('url', '')
        capture_config = job_data.get('capture_config', {})
        
        if not url:
            raise ValueError("No URL provided for screenshot capture")
        
        logger.info(f"Capturing screenshots from {url}")
        
        await page.goto(url, wait_until='networkidle')
        
        screenshots = {}
        metadata = {
            'url': url,
            'timestamp': datetime.utcnow().isoformat(),
            'user_agent': await page.evaluate('navigator.userAgent')
        }
        
        if capture_config.get('full_page', True):
            full_screenshot = await page.screenshot(full_page=True)
            screenshots['full_page'] = base64.b64encode(full_screenshot).decode('utf-8')
        
        if capture_config.get('viewport', True):
            viewport_screenshot = await page.screenshot()
            screenshots['viewport'] = base64.b64encode(viewport_screenshot).decode('utf-8')
        
        trigger_selectors = capture_config.get('trigger_selectors', [])
        for selector in trigger_selectors:
            try:
                await page.wait_for_selector(selector, timeout=5000)
                trigger_screenshot = await page.screenshot()
                screenshots[f'trigger_{selector}'] = base64.b64encode(trigger_screenshot).decode('utf-8')
            except:
                pass
        
        before_after = capture_config.get('before_after', False)
        if before_after:
            action = capture_config.get('action')
            if action == 'click' and capture_config.get('action_selector'):
                before = await page.screenshot()
                
                await page.click(capture_config['action_selector'])
                await page.wait_for_timeout(1000)
                
                after = await page.screenshot()
                
                screenshots['before_action'] = base64.b64encode(before).decode('utf-8')
                screenshots['after_action'] = base64.b64encode(after).decode('utf-8')
        
        duration = time.time() - start_time
        metadata['capture_duration'] = duration
        
        logger.info(f"Screenshot capture completed in {duration:.2f}s")
        
        return ScreenshotResult(
            screenshots=screenshots,
            metadata=metadata,
            duration=duration
        )
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Screenshot capture failed: {str(e)}"
        logger.error(error_msg)
        
        return ScreenshotResult(
            screenshots={},
            metadata={'error': error_msg},
            duration=duration,
            error=error_msg
        )
        
    finally:
        await browser_pool.release_page(page)

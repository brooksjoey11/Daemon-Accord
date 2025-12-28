from typing import Dict, Any, Optional
from playwright.async_api import Page, Cookie
import asyncio
import time
import logging
import os
import json
from dataclasses import dataclass
import hashlib

logger = logging.getLogger(__name__)

@dataclass
class AuthResult:
    authenticated: bool
    cookies: list
    session_id: Optional[str] = None
    duration: float = 0.0
    error: Optional[str] = None

async def execute_authentication(job_data: Dict[str, Any], browser_pool) -> AuthResult:
    page = await browser_pool.acquire_page()
    start_time = time.time()
    
    try:
        target = job_data.get('target', {})
        url = target.get('url', '')
        auth_config = job_data.get('auth_config', {})
        
        credentials = await _get_credentials(job_data)
        if not credentials:
            raise ValueError("No credentials available for authentication")
        
        logger.info(f"Attempting authentication to {url}")
        
        await page.goto(url, wait_until='networkidle')
        
        success = await _perform_login_flow(page, credentials, auth_config)
        
        if success:
            cookies = await page.context.cookies()
            session_id = await _persist_session(cookies, job_data, browser_pool)
            
            duration = time.time() - start_time
            logger.info(f"Authentication successful in {duration:.2f}s")
            
            return AuthResult(
                authenticated=True,
                cookies=cookies,
                session_id=session_id,
                duration=duration
            )
        else:
            raise Exception("Authentication flow did not complete successfully")
            
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Authentication failed: {str(e)}"
        logger.error(error_msg)
        
        return AuthResult(
            authenticated=False,
            cookies=[],
            duration=duration,
            error=error_msg
        )
        
    finally:
        await browser_pool.release_page(page)

async def _get_credentials(job_data: Dict[str, Any]) -> Dict[str, str]:
    credentials = job_data.get('credentials', {})
    
    if not credentials:
        target = job_data.get('target', {})
        domain = target.get('domain', '')
        
        if domain:
            env_prefix = f"CRED_{domain.upper().replace('.', '_')}"
            username = os.getenv(f"{env_prefix}_USERNAME")
            password = os.getenv(f"{env_prefix}_PASSWORD")
            
            if username and password:
                return {'username': username, 'password': password}
    
    return credentials

async def _perform_login_flow(page: Page, credentials: Dict[str, str], config: Dict[str, Any]) -> bool:
    selectors = config.get('selectors', {})
    
    username_selector = selectors.get('username', 'input[name=\"username\"], input[name=\"email\"], input[type=\"email\"]')
    password_selector = selectors.get('password', 'input[type=\"password\"]')
    submit_selector = selectors.get('submit', 'button[type=\"submit\"], input[type=\"submit\"]')
    
    try:
        if username_selector:
            await page.fill(username_selector, credentials.get('username', ''))
        
        if password_selector:
            await page.fill(password_selector, credentials.get('password', ''))
        
        if submit_selector:
            await page.click(submit_selector)
            await page.wait_for_timeout(2000)
            await page.wait_for_load_state('networkidle')
        
        success_indicator = config.get('success_indicator')
        if success_indicator:
            try:
                await page.wait_for_selector(success_indicator, timeout=5000)
                return True
            except:
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Login flow error: {e}")
        return False

async def _persist_session(cookies: list, job_data: Dict[str, Any], browser_pool) -> str:
    target = job_data.get('target', {})
    domain = target.get('domain', '')
    
    if not cookies or not domain:
        return ""
    
    credentials = await _get_credentials(job_data)
    if credentials:
        cred_hash = hashlib.md5(json.dumps(credentials).encode()).hexdigest()
        session_key = f"{domain}:{cred_hash}"
    else:
        session_key = domain
    
    redis_client = getattr(browser_pool, 'redis', None)
    if redis_client:
        await redis_client.setex(
            f"session:{session_key}",
            86400,
            json.dumps([dict(cookie) for cookie in cookies])
        )
    
    return session_key

from typing import Dict, Any, List
from playwright.async_api import Page
import asyncio
import time
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class FormResult:
    submitted: bool
    response_data: Dict[str, Any]
    duration: float
    error: Optional[str] = None

async def execute_form_submit(job_data: Dict[str, Any], browser_pool) -> FormResult:
    page = await browser_pool.acquire_page()
    start_time = time.time()
    
    try:
        target = job_data.get('target', {})
        url = target.get('url', '')
        form_config = job_data.get('form_config', {})
        fields = form_config.get('fields', {})
        validation = form_config.get('validation', {})
        
        if not url:
            raise ValueError("No URL provided for form submission")
        
        logger.info(f"Submitting form to {url}")
        
        await page.goto(url, wait_until='networkidle')
        
        success = await _fill_and_submit_form(page, fields, form_config)
        
        if success and validation:
            valid = await _validate_response(page, validation)
            if not valid:
                raise Exception("Form submission validation failed")
        
        response_data = await _capture_response_data(page)
        
        duration = time.time() - start_time
        logger.info(f"Form submission completed in {duration:.2f}s")
        
        return FormResult(
            submitted=True,
            response_data=response_data,
            duration=duration
        )
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Form submission failed: {str(e)}"
        logger.error(error_msg)
        
        return FormResult(
            submitted=False,
            response_data={},
            duration=duration,
            error=error_msg
        )
        
    finally:
        await browser_pool.release_page(page)

async def _fill_and_submit_form(page: Page, fields: Dict[str, Any], config: Dict[str, Any]) -> bool:
    form_selector = config.get('form_selector', 'form')
    submit_selector = config.get('submit_selector', 'button[type=\"submit\"], input[type=\"submit\"]')
    
    try:
        for field_name, field_config in fields.items():
            selector = field_config.get('selector', f'[name=\"{field_name}\"]')
            value = field_config.get('value', '')
            field_type = field_config.get('type', 'text')
            
            element = await page.query_selector(selector)
            if element:
                if field_type == 'select':
                    await element.select_option(value)
                elif field_type == 'checkbox':
                    if value:
                        await element.check()
                    else:
                        await element.uncheck()
                else:
                    await element.fill(str(value))
        
        if submit_selector:
            await page.click(submit_selector)
            await page.wait_for_timeout(1000)
            await page.wait_for_load_state('networkidle')
        
        return True
        
    except Exception as e:
        logger.error(f"Form filling error: {e}")
        return False

async def _validate_response(page: Page, validation: Dict[str, Any]) -> bool:
    success_selectors = validation.get('success_selectors', [])
    error_selectors = validation.get('error_selectors', [])
    expected_text = validation.get('expected_text', '')
    max_wait = validation.get('max_wait', 5000)
    
    try:
        if success_selectors:
            for selector in success_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=max_wait)
                    return True
                except:
                    continue
        
        if error_selectors:
            for selector in error_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=1000)
                    if element:
                        return False
                except:
                    continue
        
        if expected_text:
            content = await page.content()
            if expected_text in content:
                return True
        
        return True
        
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return False

async def _capture_response_data(page: Page) -> Dict[str, Any]:
    try:
        url = page.url
        title = await page.title()
        
        status_elements = await page.query_selector_all('.status, .message, .alert')
        status_texts = []
        for element in status_elements:
            text = await element.text_content()
            if text:
                status_texts.append(text.strip())
        
        return {
            'url': url,
            'title': title,
            'status_messages': status_texts,
            'timestamp': time.time()
        }
    except:
        return {}

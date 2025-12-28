import asyncio
from typing import List, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import logging
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)

@dataclass
class BrowserInstance:
    browser: Browser
    context: BrowserContext
    pages: List[Page]
    last_used: float
    in_use: bool = False

class BrowserPool:
    def __init__(self, max_instances: int = 20, max_pages_per_instance: int = 5):
        self.max_instances = max_instances
        self.max_pages_per_instance = max_pages_per_instance
        self.instances: List[BrowserInstance] = []
        self.playwright = None
        self.lock = asyncio.Lock()
        
    async def initialize(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
        
        for _ in range(min(5, self.max_instances)):
            await self._create_instance()
    
    async def acquire_page(self) -> Page:
        async with self.lock:
            for instance in self.instances:
                if not instance.in_use and len(instance.pages) < self.max_pages_per_instance:
                    instance.in_use = True
                    instance.last_used = time.time()
                    
                    if instance.pages:
                        page = instance.pages.pop()
                        await page.bring_to_front()
                    else:
                        page = await instance.context.new_page()
                    
                    return page
            
            if len(self.instances) < self.max_instances:
                new_instance = await self._create_instance()
                new_instance.in_use = True
                new_instance.last_used = time.time()
                page = await new_instance.context.new_page()
                return page
            
            raise Exception("Browser pool exhausted")
    
    async def release_page(self, page: Page):
        async with self.lock:
            for instance in self.instances:
                if page.context == instance.context:
                    instance.in_use = False
                    instance.last_used = time.time()
                    
                    if len(instance.pages) < self.max_pages_per_instance:
                        await page.bring_to_front()
                        instance.pages.append(page)
                    else:
                        await page.close()
                    
                    break
            
            await self._cleanup_idle_instances()
    
    async def _create_instance(self) -> BrowserInstance:
        browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        instance = BrowserInstance(
            browser=browser,
            context=context,
            pages=[],
            last_used=time.time()
        )
        
        self.instances.append(instance)
        logger.info(f"Created browser instance. Total: {len(self.instances)}")
        return instance
    
    async def _cleanup_idle_instances(self):
        current_time = time.time()
        to_remove = []
        
        for instance in self.instances:
            if (not instance.in_use and 
                current_time - instance.last_used > 300 and 
                len(self.instances) > 5):
                
                await instance.context.close()
                await instance.browser.close()
                to_remove.append(instance)
        
        for instance in to_remove:
            self.instances.remove(instance)
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} idle browser instances")
    
    async def health_check(self) -> bool:
        try:
            if self.instances:
                instance = self.instances[0]
                page = await instance.context.new_page()
                await page.goto('about:blank', timeout=5000)
                await page.close()
                return True
        except:
            pass
        return False
    
    async def cleanup(self):
        async with self.lock:
            for instance in self.instances:
                try:
                    await instance.context.close()
                    await instance.browser.close()
                except:
                    pass
            self.instances.clear()
        
        if self.playwright:
            await self.playwright.stop()

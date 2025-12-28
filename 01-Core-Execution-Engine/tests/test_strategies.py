import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from ...models.job import Job
from ..strategies import (
    BaseExecutor,
    VanillaExecutor,
    StealthExecutor,
    AssaultExecutor,
    ExecutionResult,
    StrategyExecutor
)

class MockPage:
    async def goto(self, *args, **kwargs):
        return Mock(status=200)
    async def close(self):
        pass
    async def set_viewport_size(self, *args, **kwargs):
        pass
    async def evaluate(self, *args, **kwargs):
        pass
    async def mouse(self, *args, **kwargs):
        return Mock(move=AsyncMock(), wheel=AsyncMock())
    async def content(self):
        return "<html>test</html>"
    async def query_selector(self, *args, **kwargs):
        return Mock(text_content=AsyncMock(return_value="test"))
    async def set_extra_http_headers(self, *args, **kwargs):
        pass

class MockBrowser:
    async def new_page(self):
        return MockPage()
    async def close(self):
        pass

class MockBrowserPool:
    async def acquire(self):
        return MockBrowser()
    async def release(self, browser):
        pass

@pytest.mark.asyncio
async def test_strategy_hierarchy():
    # Test inheritance chain
    assert issubclass(VanillaExecutor, BaseExecutor)
    assert issubclass(StealthExecutor, VanillaExecutor)
    assert issubclass(AssaultExecutor, StealthExecutor)
    
    # Test base executor cannot be instantiated directly
    with pytest.raises(NotImplementedError):
        executor = BaseExecutor()
        await executor.execute(None)
        
    # Test vanilla executor
    job = Job(id="test1", url="http://example.com", payload={})
    executor = VanillaExecutor(browser_pool=MockBrowserPool())
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_browser = MockBrowser()
        mock_playwright.return_value.start.return_value = Mock(
            chromium=Mock(launch=AsyncMock(return_value=mock_browser))
        )
        
        result = await executor.execute(job)
        assert isinstance(result, ExecutionResult)
        assert result.job_id == "test1"
        assert result.success == True
        
    # Test stealth executor with randomized delays
    job = Job(id="test2", url="http://example.com", payload={'random_delay': True})
    executor = StealthExecutor(browser_pool=MockBrowserPool())
    
    start = datetime.utcnow()
    with patch('playwright.async_api.async_playwright'):
        result = await executor.execute(job)
    duration = (datetime.utcnow() - start).total_seconds()
    
    assert result.success == True
    assert hasattr(executor, 'viewports')
    
    # Test assault executor applies additional techniques
    job = Job(id="test3", url="http://example.com", payload={'evasion_level': 2})
    executor = AssaultExecutor(browser_pool=MockBrowserPool())
    
    with patch('playwright.async_api.async_playwright'):
        result = await executor.execute(job)
        
    assert result.success == True
    
    # Test strategy selection
    strategy_executor = StrategyExecutor()
    
    job_low = Job(id="low", url="http://example.com", payload={'evasion_level': 0})
    assert isinstance(strategy_executor.get_executor(job_low), VanillaExecutor)
    
    job_medium = Job(id="medium", url="http://example.com", payload={'evasion_level': 1})
    assert isinstance(strategy_executor.get_executor(job_medium), StealthExecutor)
    
    job_high = Job(id="high", url="http://example.com", payload={'evasion_level': 2})
    assert isinstance(strategy_executor.get_executor(job_high), AssaultExecutor)
    
    # Test domain heuristics
    job_cloudflare = Job(id="cf", url="https://cloudflare-protected.com", payload={})
    executor = strategy_executor.get_executor(job_cloudflare)
    assert isinstance(executor, AssaultExecutor)
    
    # Test evasion techniques only apply when configured
    job_no_evasion = Job(id="no_evasion", url="http://example.com", 
                        payload={'evasion_level': 0, 'random_delay': False})
    executor = VanillaExecutor(browser_pool=MockBrowserPool())
    result = await executor.execute(job_no_evasion)
    assert result.success == True
    
    # Test resource cleanup
    job = Job(id="cleanup", url="http://example.com", payload={})
    executor = VanillaExecutor()
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_browser = MockBrowser()
        mock_page = MockPage()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_playwright.return_value.start.return_value = Mock(
            chromium=Mock(launch=AsyncMock(return_value=mock_browser))
        )
        
        # Mock close methods to verify they're called
        mock_page.close = AsyncMock()
        mock_browser.close = AsyncMock()
        
        result = await executor.execute(job)
        
        # Verify cleanup happened
        mock_page.close.assert_called_once()
        mock_browser.close.assert_called_once()
        
    # Test error handling
    job = Job(id="error", url="http://example.com", payload={})
    executor = VanillaExecutor(browser_pool=MockBrowserPool())
    
    with patch('playwright.async_api.async_playwright') as mock_playwright:
        mock_playwright.return_value.start.side_effect = Exception("Browser failed")
        
        result = await executor.execute(job)
        assert result.success == False
        assert "Browser failed" in result.error
        
    print("All hierarchy tests passed")



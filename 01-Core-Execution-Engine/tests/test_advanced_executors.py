"""
Tests for Enterprise Advanced Executors

Tests for UltimateStealthExecutor and CustomExecutor (enterprise features).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.strategies.ultimate_stealth_executor import UltimateStealthExecutor
from src.strategies.custom_executor import CustomExecutor
from src.strategies.vanilla_executor import Job, ExecutionResult


@pytest.fixture
def mock_browser_pool():
    """Mock browser pool."""
    pool = AsyncMock()
    browser = AsyncMock()
    page = AsyncMock()
    
    browser.new_page = AsyncMock(return_value=page)
    pool.acquire = AsyncMock(return_value=browser)
    pool.release = AsyncMock()
    
    return pool


@pytest.fixture
def mock_page():
    """Mock Playwright page."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.content = AsyncMock(return_value="<html>Test</html>")
    page.set_viewport_size = AsyncMock()
    page.set_extra_http_headers = AsyncMock()
    page.evaluate = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.close = AsyncMock()
    return page


@pytest.fixture
def sample_job():
    """Sample job for testing."""
    return Job(
        id="test-job-1",
        url="https://example.com",
        type="navigate_extract",
        payload={},
        strategy="ultimate_stealth"
    )


@pytest.mark.asyncio
async def test_ultimate_stealth_executor_instantiation(mock_browser_pool):
    """Test that UltimateStealthExecutor can be instantiated."""
    executor = UltimateStealthExecutor(
        browser_pool=mock_browser_pool,
        redis_client=None
    )
    
    assert executor is not None
    assert executor.behavior_simulator is not None
    assert executor.timing_obfuscator is not None
    assert executor.network_obfuscator is not None
    assert executor.advanced_evasion is not None


@pytest.mark.asyncio
async def test_ultimate_stealth_executor_execute(mock_browser_pool, mock_page, sample_job):
    """Test UltimateStealthExecutor execution (smoke test)."""
    executor = UltimateStealthExecutor(
        browser_pool=mock_browser_pool,
        redis_client=None
    )
    
    # Mock the execute_with_ultimate_stealth method
    executor.execute_with_ultimate_stealth = AsyncMock()
    
    # Mock browser pool
    browser = AsyncMock()
    browser.new_page = AsyncMock(return_value=mock_page)
    mock_browser_pool.acquire = AsyncMock(return_value=browser)
    
    # Execute
    result = await executor.execute(sample_job)
    
    # Verify
    assert result is not None
    assert isinstance(result, ExecutionResult)
    assert result.job_id == sample_job.id
    mock_browser_pool.acquire.assert_called_once()
    mock_browser_pool.release.assert_called_once()


@pytest.mark.asyncio
async def test_ultimate_stealth_cleanup_method_exists(mock_browser_pool):
    """Test that _cleanup_stealth_artifacts method exists and is callable."""
    executor = UltimateStealthExecutor(
        browser_pool=mock_browser_pool,
        redis_client=None
    )
    
    # Verify method exists
    assert hasattr(executor, '_cleanup_stealth_artifacts')
    assert callable(executor._cleanup_stealth_artifacts)
    
    # Test it can be called (smoke test)
    mock_page = AsyncMock()
    await executor._cleanup_stealth_artifacts(mock_page)
    
    # Should not raise exception
    assert True


@pytest.mark.asyncio
async def test_custom_executor_instantiation(mock_browser_pool):
    """Test that CustomExecutor can be instantiated."""
    executor = CustomExecutor(
        browser_pool=mock_browser_pool,
        redis_client=None
    )
    
    assert executor is not None
    assert executor.custom_techniques_enabled is True


@pytest.mark.asyncio
async def test_custom_executor_execute(mock_browser_pool, mock_page, sample_job):
    """Test CustomExecutor execution (smoke test)."""
    executor = CustomExecutor(
        browser_pool=mock_browser_pool,
        redis_client=None
    )
    
    # Mock browser pool
    browser = AsyncMock()
    browser.new_page = AsyncMock(return_value=mock_page)
    mock_browser_pool.acquire = AsyncMock(return_value=browser)
    
    # Mock parent class methods
    executor._apply_stealth_techniques = AsyncMock()
    executor._navigate_with_timeout = AsyncMock(return_value=None)
    executor._extract_data = AsyncMock(return_value={'content': 'test'})
    
    # Execute
    result = await executor.execute(sample_job)
    
    # Verify
    assert result is not None
    assert isinstance(result, ExecutionResult)
    assert result.job_id == sample_job.id
    mock_browser_pool.acquire.assert_called_once()
    mock_browser_pool.release.assert_called_once()


@pytest.mark.asyncio
async def test_custom_executor_custom_techniques(mock_browser_pool):
    """Test CustomExecutor custom techniques methods."""
    executor = CustomExecutor(
        browser_pool=mock_browser_pool,
        redis_client=None
    )
    
    mock_page = AsyncMock()
    
    # Test custom techniques application
    job = Job(
        id="test-job-2",
        url="https://example.com",
        type="navigate_extract",
        payload={
            'custom_techniques': {
                'header_rotation': True,
                'user_agent_rotation': True,
                'custom_headers': {'X-Custom': 'value'}
            }
        },
        strategy="custom"
    )
    
    await executor._apply_custom_techniques(mock_page, job)
    
    # Verify methods were called
    mock_page.set_extra_http_headers.assert_called()


@pytest.mark.asyncio
async def test_custom_executor_custom_js(mock_browser_pool, mock_page, sample_job):
    """Test CustomExecutor custom JavaScript execution."""
    executor = CustomExecutor(
        browser_pool=mock_browser_pool,
        redis_client=None
    )
    
    # Mock parent methods
    executor._apply_stealth_techniques = AsyncMock()
    executor._navigate_with_timeout = AsyncMock(return_value=None)
    executor._extract_data = AsyncMock(return_value={'content': 'test'})
    
    # Mock browser pool
    browser = AsyncMock()
    browser.new_page = AsyncMock(return_value=mock_page)
    mock_browser_pool.acquire = AsyncMock(return_value=browser)
    
    # Job with custom JS
    sample_job.payload = {
        'custom_js': 'console.log("test");'
    }
    
    # Execute
    result = await executor.execute(sample_job)
    
    # Verify custom JS was executed
    mock_page.evaluate.assert_called()
    assert result.success is True


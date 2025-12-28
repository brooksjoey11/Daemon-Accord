# Testing Guide

Comprehensive guide for running and writing tests for the Control Plane Orchestrator.

## Quick Start

### Run All Tests
```bash
pytest
```

### Run with Coverage
```bash
pytest --cov=src --cov-report=html
```

### Run Specific Test Types
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# E2E tests only
pytest tests/e2e/
```

## Test Structure

### Unit Tests (`tests/unit/`)
Fast, isolated tests that don't require external dependencies.

**Coverage:**
- `test_queue_manager.py` - Queue operations
- `test_idempotency_engine.py` - Idempotency logic
- `test_state_manager.py` - State management

**Run:**
```bash
pytest tests/unit/ -v
```

### Integration Tests (`tests/integration/`)
Tests that verify component integration with mocked dependencies.

**Coverage:**
- `test_job_orchestrator.py` - Full orchestrator flow

**Run:**
```bash
pytest tests/integration/ -v
```

### End-to-End Tests (`tests/e2e/`)
Tests that exercise the full API with a test client.

**Coverage:**
- `test_api_endpoints.py` - All API endpoints

**Run:**
```bash
pytest tests/e2e/ -v
```

## Coverage Requirements

- **Minimum**: 60% overall coverage
- **Target**: 70%+ for core modules
- **Current**: See coverage report after running tests

### View Coverage Report
```bash
# HTML report (opens in browser)
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Terminal report
pytest --cov=src --cov-report=term-missing
```

## Writing Tests

### Test Naming
- Files: `test_<module>.py`
- Functions: `test_<feature>_<scenario>()`

### Using Fixtures
All shared fixtures are in `tests/conftest.py`:

```python
@pytest.mark.asyncio
async def test_my_feature(mock_redis, mock_db_session, sample_job):
    # Use fixtures
    pass
```

### Async Tests
Use `@pytest.mark.asyncio` for async tests:

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await my_async_function()
    assert result is not None
```

### Mocking
Use `AsyncMock` for async mocks:

```python
from unittest.mock import AsyncMock

mock_redis = AsyncMock()
mock_redis.get = AsyncMock(return_value="value")
```

## Test Data

### Using Faker
Generate realistic test data:

```python
from faker import Faker

fake = Faker()
domain = fake.domain_name()
url = fake.url()
```

### Sample Data Fixtures
Common test data is available as fixtures:
- `sample_job` - Sample Job instance
- `sample_job_data` - Job data dictionary
- `sample_job_result` - Execution result

## CI/CD Integration

Tests run automatically on:
- Push to `main` or `develop` branches
- Pull requests
- Manual workflow dispatch

CI will fail if:
- Coverage drops below 60%
- Any test fails
- Linting fails (warnings allowed)

## Local Development

### Pre-commit Testing
Run tests before committing:

```bash
# Quick test run
pytest tests/unit/ -v

# Full test suite
pytest -v

# With coverage
pytest --cov=src --cov-report=term-missing
```

### Debugging Tests
Run specific test with output:

```bash
pytest tests/unit/test_queue_manager.py::test_enqueue_job -v -s
```

### Test Markers
Use markers to run specific test groups:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only E2E tests
pytest -m e2e
```

## Performance Testing

For load/performance tests (future):

```bash
# Install locust
pip install locust

# Run load tests
locust -f tests/performance/locustfile.py
```

## Troubleshooting

### Import Errors
Ensure you're in the project root:
```bash
cd 04-Control-Plane-Orchestrator
pytest
```

### Database Connection
Integration tests require database connection. Use test database:
```bash
export DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_accord_engine"
export REDIS_URL="redis://localhost:6379/1"
pytest tests/integration/
```

### Async Test Issues
Ensure `pytest-asyncio` is installed and `asyncio_mode = auto` in `pytest.ini`.

## Best Practices

1. **Write tests first** (TDD) when possible
2. **Keep tests isolated** - each test should be independent
3. **Use descriptive names** - test names should describe what they test
4. **Mock external dependencies** - don't require real services for unit tests
5. **Test edge cases** - test error conditions, boundaries, null cases
6. **Keep tests fast** - unit tests should run in milliseconds
7. **Maintain coverage** - aim for >70% on critical paths


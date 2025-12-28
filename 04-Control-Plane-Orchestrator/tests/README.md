# Test Suite Documentation

## Overview

This directory contains comprehensive test coverage for the Control Plane Orchestrator.

## Test Structure

```
tests/
├── unit/              # Unit tests (mocked dependencies)
│   ├── test_job_orchestrator.py
│   ├── test_queue_manager.py
│   ├── test_state_manager.py
│   ├── test_idempotency_engine.py
│   └── test_executor_adapter.py
├── integration/       # Integration tests (real dependencies)
│   └── test_job_orchestrator.py
└── e2e/              # End-to-end tests
    └── test_api_endpoints.py
```

## Running Tests

### All Tests
```bash
pytest tests/ -v
```

### Unit Tests Only
```bash
pytest tests/unit/ -v
```

### Integration Tests Only
```bash
pytest tests/integration/ -v
```

### E2E Tests Only
```bash
pytest tests/e2e/ -v
```

### With Coverage
```bash
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
```

### Coverage Threshold
```bash
pytest tests/ --cov=src --cov-fail-under=60
```

## Test Coverage Goals

- **Target:** >60% coverage
- **Critical Modules:** >80% coverage
  - `job_orchestrator.py`
  - `queue_manager.py`
  - `state_manager.py`

## Test Categories

### Unit Tests
- Fast execution (< 1 second each)
- Mocked dependencies (Redis, Database)
- Test individual functions/methods
- No external services required

### Integration Tests
- Test component interactions
- Use test containers or mocks for external services
- Validate data flow between components

### E2E Tests
- Test complete workflows
- Require running services (Docker Compose)
- Validate end-to-end functionality

## Writing New Tests

### Unit Test Template
```python
@pytest.mark.asyncio
async def test_function_name(mock_redis, mock_db_session, mock_database):
    """Test description."""
    # Arrange
    component = Component(mock_redis, mock_database)
    
    # Act
    result = await component.method()
    
    # Assert
    assert result == expected_value
```

### Integration Test Template
```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_component_integration():
    """Test component integration."""
    # Setup real dependencies
    # Test interaction
    # Verify results
```

## Fixtures

### Available Fixtures (from conftest.py)
- `mock_redis`: Mocked Redis client
- `mock_db_session`: Mocked database session
- `mock_database`: Mocked Database instance
- `sample_job`: Sample Job object for testing
- `sample_job_data`: Sample job data dictionary

## Continuous Integration

Tests run automatically on:
- Pull requests
- Pushes to main/develop branches
- Manual workflow triggers

See `.github/workflows/ci.yml` for CI configuration.

## Coverage Reports

Coverage reports are generated in:
- Terminal output (term-missing)
- HTML report: `htmlcov/index.html`
- XML report: `coverage.xml` (for CI/CD)

## Best Practices

1. **Test Isolation:** Each test should be independent
2. **Clear Names:** Test names should describe what they test
3. **Arrange-Act-Assert:** Follow AAA pattern
4. **Mock External Dependencies:** Use mocks for Redis, Database, etc.
5. **Test Edge Cases:** Include error conditions and boundary cases
6. **Keep Tests Fast:** Unit tests should run in < 1 second

## Troubleshooting

### Tests Failing
1. Check test output for error messages
2. Verify fixtures are properly configured
3. Ensure dependencies are installed
4. Check for environment variable requirements

### Coverage Not Meeting Threshold
1. Review coverage report: `htmlcov/index.html`
2. Identify untested code paths
3. Add tests for missing coverage
4. Focus on critical modules first

### Integration Tests Failing
1. Verify test containers are running
2. Check database/Redis connectivity
3. Ensure test data is properly set up
4. Review test isolation (cleanup between tests)

---

**Last Updated:** 2024-12-24

# Execution Engine Integration

## Overview

The Control Plane is now fully integrated with the Execution Engine, enabling end-to-end job processing from API request to browser automation.

## Architecture

```
┌─────────────────────────────────────────┐
│  Control Plane API (FastAPI)            │
│  POST /api/v1/jobs                      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  JobOrchestrator                       │
│  - Creates job in DB                    │
│  - Enqueues in Redis                    │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Worker Loop                            │
│  - Reads from queue                     │
│  - Calls ExecutorAdapter                │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  ExecutorAdapter                        │
│  - Converts job format                  │
│  - Selects executor by strategy         │
│  - Executes via Execution Engine        │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Execution Engine                       │
│  - VanillaExecutor                      │
│  - StealthExecutor                      │
│  - AssaultExecutor                      │
│  - Browser automation (Playwright)      │
└─────────────────────────────────────────┘
```

## Components

### 1. ExecutorAdapter (`executor_adapter.py`)

**Purpose**: Bridge between Control Plane and Execution Engine.

**Responsibilities**:
- Creates appropriate executor based on strategy
- Converts Control Plane job format to Execution Engine format
- Executes jobs and handles results
- Maps Execution Engine results back to Control Plane format

**Key Methods**:
- `_get_executor(strategy)`: Gets or creates executor for strategy
- `_convert_job_to_execution_format(...)`: Converts job format
- `execute_job(...)`: Main execution method
- `_convert_result_to_control_plane_format(...)`: Converts results

### 2. Job Format Conversion

**Control Plane Format**:
```python
{
    "id": "job-uuid",
    "domain": "example.com",
    "url": "https://example.com",
    "job_type": "navigate_extract",
    "strategy": "vanilla",
    "payload": "{...}"  # JSON string
}
```

**Execution Engine Format**:
```python
{
    "id": "job-uuid",
    "type": "navigate_extract",
    "target": {
        "domain": "example.com",
        "url": "https://example.com",
        "ip": ""
    },
    "parameters": {...}  # Parsed payload
}
```

### 3. Strategy Selection

The adapter supports three execution strategies:

- **vanilla**: Basic execution (VanillaExecutor)
- **stealth**: Stealth execution with evasion (StealthExecutor)
- **assault**: Maximum evasion (AssaultExecutor)

The executor is selected based on the `strategy` field in the job.

### 4. Browser Pool Management

The browser pool is initialized in `main.py` during FastAPI startup:

```python
# Initialize browser pool
browser_pool = BrowserPool(max_instances=20, max_pages_per_instance=5)
await browser_pool.initialize()
```

The pool is:
- Shared across all workers
- Automatically cleaned up on shutdown
- Handles browser instance lifecycle

## Integration Points

### JobOrchestrator

Updated to accept:
- `browser_pool`: BrowserPool instance
- `db_session`: AsyncSession for Execution Engine

The `_execute_job()` method now:
1. Gets the executor adapter
2. Calls `adapter.execute_job()`
3. Returns results in Control Plane format

### Main Application

The FastAPI app:
1. Initializes browser pool on startup
2. Passes browser pool to orchestrator
3. Cleans up browser pool on shutdown

## Error Handling

The integration is designed to fail gracefully:

- If Execution Engine is not available, jobs will fail with clear error messages
- Browser pool initialization is optional
- Executor creation errors are logged and handled

## Result Mapping

Execution Engine returns different result types:

**JobResult** (from StandardExecutor):
```python
JobResult(
    job_id="...",
    status=JobStatus.SUCCESS,
    data={...},
    artifacts={...},
    error=None,
    execution_time=1.5
)
```

**ExecutionResult** (from strategies):
```python
ExecutionResult(
    job_id="...",
    success=True,
    data={...},
    error=None,
    timing={"total_ms": 1500}
)
```

The adapter converts both to Control Plane format:
```python
{
    "success": bool,
    "data": dict,
    "artifacts": dict,
    "error": str | None,
    "execution_time": float
}
```

## Usage Example

```python
# Job is created via API
POST /api/v1/jobs
{
    "domain": "example.com",
    "url": "https://example.com",
    "job_type": "navigate_extract",
    "strategy": "stealth",
    "payload": {"selector": "h1"}
}

# Flow:
# 1. Job created in DB
# 2. Job enqueued in Redis
# 3. Worker picks up job
# 4. ExecutorAdapter converts format
# 5. StealthExecutor executes
# 6. Browser automation runs
# 7. Results stored in DB
# 8. Job status updated
```

## Configuration

Browser pool settings can be configured via environment variables:

- `BROWSER_POOL_MAX_INSTANCES`: Max browser instances (default: 20)
- `BROWSER_POOL_MAX_PAGES`: Max pages per instance (default: 5)

## Testing

To test the integration:

1. Ensure Execution Engine is available in path
2. Start Control Plane API
3. Create a job via API
4. Monitor logs for execution
5. Check job status endpoint

## Future Enhancements

- Add metrics for execution times
- Support for custom executors
- Better error recovery
- Execution Engine health checks
- Dynamic strategy selection based on domain history


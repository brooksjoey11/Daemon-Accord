# Containerized Architecture

## Execution Flow in Containers

In containerized deployments (docker-compose), the execution flow is:

```
1. Client → Control Plane API → Creates Job in DB → Enqueues to Redis Stream
2. Execution Engine Worker → Consumes from Redis Stream → Executes Job
3. Execution Engine Worker → Updates Job Status (via Control Plane API or directly to DB)
```

## Key Points

### Control Plane Container
- **Does NOT contain Execution Engine code** (separate service)
- **Enqueues jobs** to Redis Streams with full `job_data` JSON
- **Monitors job status** via database
- **Direct execution disabled** in containerized mode (Execution Engine code not available)

### Execution Engine Container
- **Runs as worker service** (`src/worker.py`)
- **Consumes jobs** from Redis Streams (all priority levels)
- **Executes jobs** using Execution Engine strategies
- **Updates job status** (needs to integrate with Control Plane or DB directly)

## Current Limitation

The Execution Engine worker currently:
- ✅ Consumes jobs from Redis Streams
- ✅ Executes jobs using Execution Engine
- ❌ Does NOT update Control Plane job status after execution

**Workaround**: Control Plane's `process_job()` method will attempt direct execution, fail gracefully in containers, and jobs will be marked as "awaiting worker processing". The Execution Engine worker needs to update job status after execution.

## Recommended Integration

For full containerized operation, the Execution Engine worker should:

1. After executing a job, call Control Plane API to update status:
   ```python
   # In worker.py after execution
   await httpx.post(
       f"{CONTROL_PLANE_URL}/api/v1/jobs/{job_id}/status",
       json={"status": "completed", "result": result}
   )
   ```

2. Or update database directly (if shared DB access):
   ```python
   # Update job status in DB
   async with db.session() as session:
       job = await session.get(Job, job_id)
       job.status = "completed"
       job.result = json.dumps(result)
       await session.commit()
   ```

## Development vs Production

- **Development (local)**: Control Plane can execute directly via `executor_adapter` (Execution Engine code in repo)
- **Production (containers)**: Execution Engine worker handles all execution via Redis Streams


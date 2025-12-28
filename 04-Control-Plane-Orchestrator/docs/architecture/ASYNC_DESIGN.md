# Async Architecture in Control Plane

## Overview

The Control Plane uses a **fully async architecture** for all I/O operations. This ensures maximum concurrency, throughput, and prevents event loop blocking.

## Architecture

### Fully Async Components

#### 1. **FastAPI Layer (Fully Async)**
```python
# main.py
@app.post("/api/v1/jobs")
async def create_job(...):  # Async endpoint
    job_id = await orchestrator.create_job(...)  # Async call
```

**Why Async?**
- HTTP requests are I/O-bound
- FastAPI handles many concurrent requests efficiently
- Non-blocking request handling

#### 2. **Database Layer (Fully Async: AsyncEngine + AsyncSession)**

```python
# database.py - Creates async engine
self._engine: AsyncEngine = create_async_engine(
    settings.postgres_dsn,  # Uses asyncpg
    ...
)

# job_orchestrator.py - Uses AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession

async with self.db.session() as session:  # AsyncSession
    job = await session.get(Job, job_id)  # Async operation
    job.status = JobStatus.RUNNING
    await session.commit()  # Async commit
```

**Why Fully Async?**
- **Non-blocking I/O**: All database operations are async
- **Event Loop**: Never blocked by DB operations
- **Concurrency**: Can handle many concurrent DB operations
- **Consistency**: Matches the async-first architecture

#### 3. **Redis Operations (Fully Async)**

```python
# queue_manager.py
import redis.asyncio as redis

async def enqueue(self, ...):
    message_id = await self.redis.xadd(...)  # Async Redis operation
```

**Why Async?**
- Network I/O (Redis is remote)
- Non-blocking operations
- Can handle many concurrent queue operations

#### 4. **Execution Engine (Fully Async)**

```python
# Execution Engine
async def execute(self, job_data: Dict) -> JobResult:
    page = await browser_pool.acquire_page()  # Async browser operation
    result = await page.goto(url)  # Async navigation
```

**Why Async?**
- Browser automation is I/O-bound (network, rendering)
- Playwright is fully async
- Can run multiple jobs concurrently

## Flow Diagram

```
┌─────────────────────────────────────────┐
│  FastAPI Endpoint (ASYNC)                │
│  - HTTP request handling                 │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  JobOrchestrator (FULLY ASYNC)          │
│  - Redis: ASYNC (network I/O)           │
│  - DB: AsyncSession (non-blocking)      │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  QueueManager (ASYNC)                    │
│  - Redis Streams: ASYNC                  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Worker Loop (ASYNC)                     │
│  - Reads queue: ASYNC                    │
│  - Calls executor: ASYNC                 │
│  - Updates DB: AsyncSession              │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Execution Engine (ASYNC)                │
│  - Browser automation: ASYNC             │
│  - Playwright: ASYNC                     │
└─────────────────────────────────────────┘
```

## Why Fully Async?

### Performance Benefits
1. **Non-blocking I/O**: All network and database operations are async
2. **Maximum Concurrency**: Can handle many jobs simultaneously
3. **Efficient Resource Use**: Event loop never blocked
4. **Scalability**: Can scale to high throughput

### Code Consistency
1. **Uniform Pattern**: All I/O operations use async/await
2. **No Blocking**: Event loop always available for other operations
3. **Predictable Behavior**: Consistent async pattern throughout

## Implementation Pattern

### Database Operations

```python
# ✅ CORRECT: Fully async
async with self.db.session() as session:
    job = await session.get(Job, job_id)
    job.status = JobStatus.RUNNING
    await session.commit()

# ❌ WRONG: Sync Session blocks event loop
with Session(self.db_engine) as session:
    job = session.get(Job, job_id)  # BLOCKS!
    session.commit()  # BLOCKS!
```

### Key Points
- Always use `async with self.db.session()` (AsyncSession)
- Always use `await` for DB operations (`get`, `commit`, `exec`)
- Never use sync `Session()` in async functions
- Database instance provides `session()` method that returns AsyncSession

## Best Practices

### ✅ Do:
- Use `AsyncSession` for all DB operations
- Use `await` for all async operations
- Keep async context managers (`async with`)
- Use `async def` for all functions that perform I/O

### ❌ Don't:
- Use sync `Session()` in async functions
- Forget `await` on async operations
- Mix sync and async patterns unnecessarily
- Block the event loop with sync I/O

## Migration History

**Previous (Incorrect) Pattern:**
- Mixed async engine with sync Session
- Blocked event loop on DB operations
- Inconsistent async pattern

**Current (Correct) Pattern:**
- Fully async: AsyncEngine + AsyncSession
- Non-blocking DB operations
- Consistent async architecture

## Summary

The Control Plane uses a fully async architecture:
- **All I/O is async**: HTTP, Redis, Database, Browser
- **No blocking**: Event loop always available
- **Maximum concurrency**: Can handle many operations simultaneously
- **Consistent pattern**: Uniform async/await usage throughout

This ensures optimal performance, scalability, and maintainability.

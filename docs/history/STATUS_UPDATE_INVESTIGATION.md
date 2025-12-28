# Status Update Timing Issue - Investigation

## Problem
Execution Engine worker processes jobs and logs "Updated job X status to COMPLETED", but:
1. E2E test times out waiting for status change
2. Database shows status as PENDING (until manually updated)
3. API returns status as "pending" initially, then "completed" after manual SQL update

## Root Cause Analysis

### Architecture Conflict
There are **TWO workers** consuming from the same Redis streams:

1. **Control Plane Worker** (`JobOrchestrator.start_worker()`)
   - Started in `main.py` lifespan
   - Consumes from Redis streams
   - Calls `process_job()` which uses `ExecutorAdapter`
   - `ExecutorAdapter` tries to import Execution Engine code
   - If Execution Engine not available, returns mock failure result
   - Updates job status to FAILED with error message

2. **Execution Engine Worker** (`ExecutionWorker`)
   - Separate container/service
   - Consumes from Redis streams (same streams!)
   - Executes jobs directly using Execution Engine
   - Updates job status to COMPLETED

### Race Condition
Both workers consume from the same Redis stream. Whichever processes the job first:
- Execution Engine worker: Executes successfully, updates to COMPLETED
- Control Plane worker: Tries to execute, fails (no Execution Engine code), updates to FAILED/PENDING

The Control Plane worker is overwriting the Execution Engine worker's status update!

## Solution

**Option 1: Disable Control Plane Worker (Recommended)**
- The Execution Engine worker should be the ONLY consumer
- Control Plane should only enqueue jobs, not process them
- Remove or disable `start_worker()` calls in `main.py`

**Option 2: Use Different Consumer Groups**
- Control Plane worker uses group "workers"
- Execution Engine worker uses group "execution-workers"
- But they're still competing for the same messages

**Option 3: Separate Streams**
- Control Plane enqueues to one stream
- Execution Engine consumes from that stream
- Control Plane doesn't consume at all

## Recommended Fix

Disable the Control Plane worker loop since we have a dedicated Execution Engine worker service.

## Executor Validation Plan

We need to validate ALL executors, not just vanilla:
- ✅ vanilla_executor.py
- ⏳ stealth_executor.py
- ⏳ ultimate_stealth_executor.py
- ⏳ assault_executor.py
- ⏳ custom_executor.py

Each executor should be tested with:
1. Job creation
2. Execution
3. Status update
4. Result storage


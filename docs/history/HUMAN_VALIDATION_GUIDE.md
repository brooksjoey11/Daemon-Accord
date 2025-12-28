# Human Validation Guide

## Overview
This guide walks you through validating the Accord Engine system manually, step by step. We'll verify each component works correctly before moving to fresh VM deployment.

## Prerequisites
- Docker Desktop running
- All services built and running
- Terminal/Command Prompt ready

---

## VALIDATION CHUNK 1: Service Health Check

**Objective:** Verify all services are running and healthy

### Steps:
1. Check service status
2. Verify health endpoints
3. Check logs for errors

### Commands:
```powershell
# Check all services
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml ps

# Check Control Plane health
curl http://localhost:8082/health

# Check Execution Engine health (if exposed)
curl http://localhost:8081/health

# Check for errors in logs
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml logs --tail=20 control-plane execution-engine
```

### Expected Results:
- ✅ All services show "Up" status
- ✅ Control Plane health returns `{"status": "healthy"}`
- ✅ No critical errors in logs

### What to Look For:
- Services are running (not "Created" or "Exited")
- Health endpoint responds
- No error messages in logs

---

## VALIDATION CHUNK 2: Job Creation & Enqueue

**Objective:** Verify jobs can be created and enqueued to Redis

### Steps:
1. Create a test job via API
2. Verify job appears in database
3. Verify job is in Redis stream

### Commands:
```powershell
# Create a job
$jobId = (python -c "import httpx; r = httpx.post('http://localhost:8082/api/v1/jobs', params={'domain':'example.com','url':'https://example.com','job_type':'navigate_extract','strategy':'vanilla','priority':2}, json={'selector':'h1'}, timeout=30); print(r.json()['job_id'])" 2>&1)
Write-Host "Job ID: $jobId"

# Check job in database
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml exec postgres psql -U postgres -d accord_engine -c "SELECT id, status, domain, url FROM jobs WHERE id = '$jobId';"

# Check job in Redis stream
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml exec redis redis-cli XINFO STREAM jobs:stream:normal
```

### Expected Results:
- ✅ Job ID returned from API
- ✅ Job appears in database with status "pending" or "queued"
- ✅ Job appears in Redis stream

### What to Look For:
- Job ID is a valid UUID
- Database query returns the job
- Redis stream shows at least 1 entry

---

## VALIDATION CHUNK 3: Job Execution

**Objective:** Verify Execution Engine consumes and executes jobs

### Steps:
1. Watch Execution Engine logs
2. Verify job is consumed from Redis
3. Verify job executes successfully

### Commands:
```powershell
# Watch Execution Engine logs (in separate terminal or background)
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml logs -f execution-engine

# In another terminal, create a job and watch it process
$jobId = (python -c "import httpx; r = httpx.post('http://localhost:8082/api/v1/jobs', params={'domain':'example.com','url':'https://example.com','job_type':'navigate_extract','strategy':'vanilla','priority':2}, json={'selector':'h1'}, timeout=30); print(r.json()['job_id'])" 2>&1)
Write-Host "Job ID: $jobId"

# Check Redis consumer groups (should show consumption)
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml exec redis redis-cli XINFO GROUPS jobs:stream:normal
```

### Expected Results:
- ✅ Execution Engine logs show "Processing job {job_id}"
- ✅ Execution Engine logs show "Job {job_id} completed: True"
- ✅ Redis consumer group shows entries-read > 0

### What to Look For:
- Logs show job being processed
- No errors during execution
- Consumer group shows messages have been read

---

## VALIDATION CHUNK 4: Status Update Verification

**Objective:** Verify job status updates correctly after execution

### Steps:
1. Check job status via API
2. Verify status in database
3. Confirm status changed from pending → completed

### Commands:
```powershell
# Check status via API
curl -s "http://localhost:8082/api/v1/jobs/$jobId" | python -m json.tool

# Check status in database
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml exec postgres psql -U postgres -d accord_engine -c "SELECT id, status, attempts, completed_at FROM jobs WHERE id = '$jobId';"
```

### Expected Results:
- ✅ API returns `"status": "completed"`
- ✅ Database shows `status = 'COMPLETED'` (uppercase)
- ✅ `completed_at` timestamp is set

### What to Look For:
- Status is "completed" (not "pending" or "failed")
- Result data is present
- No error message

---

## VALIDATION CHUNK 5: Result Storage Verification

**Objective:** Verify job results are stored correctly

### Steps:
1. Check result data in API response
2. Verify result in database
3. Confirm result contains expected data

### Commands:
```powershell
# Get full job details
$jobData = curl -s "http://localhost:8082/api/v1/jobs/$jobId" | python -m json.tool
$jobData | Select-String -Pattern "result|html"

# Check result in database
docker compose -f 05-Deploy-Monitoring-Infra/src/deploy/docker-compose.full.yml exec postgres psql -U postgres -d accord_engine -c "SELECT id, left(result::text, 200) as result_preview FROM jobs WHERE id = '$jobId';"
```

### Expected Results:
- ✅ Result contains HTML content
- ✅ Result is stored as JSON in database
- ✅ Result matches what was executed

### What to Look For:
- Result field is not null
- Result contains expected data (HTML for navigate_extract)
- Result is valid JSON

---

## VALIDATION CHUNK 6: End-to-End Test

**Objective:** Run the automated E2E test to verify everything works

### Steps:
1. Run E2E test script
2. Verify all steps pass
3. Check for any warnings

### Commands:
```powershell
# Run E2E test
python scripts/test_e2e_flow.py
```

### Expected Results:
- ✅ All steps pass
- ✅ Job completes successfully
- ✅ Results verified in database

### What to Look For:
- Test output shows "[PASS]"
- No errors or failures
- All verification steps succeed

---

## VALIDATION CHUNK 7: Multiple Jobs Test

**Objective:** Verify system handles multiple jobs correctly

### Steps:
1. Create 3-5 jobs
2. Verify all execute
3. Check all complete successfully

### Commands:
```powershell
# Create multiple jobs
$jobIds = @()
for ($i=1; $i -le 3; $i++) {
    $jobId = (python -c "import httpx; r = httpx.post('http://localhost:8082/api/v1/jobs', params={'domain':'example.com','url':'https://example.com','job_type':'navigate_extract','strategy':'vanilla','priority':2}, json={'selector':'h1'}, timeout=30); print(r.json()['job_id'])" 2>&1)
    $jobIds += $jobId
    Write-Host "Job $i created: $jobId"
    Start-Sleep -Seconds 2
}

# Wait a bit, then check all statuses
Start-Sleep -Seconds 30
foreach ($jobId in $jobIds) {
    $status = curl -s "http://localhost:8082/api/v1/jobs/$jobId" | python -c "import sys, json; print(json.load(sys.stdin)['status'])"
    Write-Host "Job $jobId status: $status"
}
```

### Expected Results:
- ✅ All jobs created successfully
- ✅ All jobs complete within reasonable time
- ✅ All jobs have status "completed"

### What to Look For:
- No jobs stuck in "pending"
- All jobs have results
- System handles concurrency correctly

---

## VALIDATION CHUNK 8: Executor Validation (Optional)

**Objective:** Test different executor strategies

### Steps:
1. Run executor validation script
2. Verify all executors work
3. Check for any failures

### Commands:
```powershell
# Run executor validation
python scripts/validate_all_executors.py
```

### Expected Results:
- ✅ All executors pass validation
- ✅ Each executor executes successfully
- ✅ Results are stored correctly

### What to Look For:
- All executors show "PASSED"
- No executor-specific errors
- Each executor produces valid results

---

## Validation Checklist

Use this checklist to track your progress:

- [ ] Chunk 1: Service Health Check
- [ ] Chunk 2: Job Creation & Enqueue
- [ ] Chunk 3: Job Execution
- [ ] Chunk 4: Status Update Verification
- [ ] Chunk 5: Result Storage Verification
- [ ] Chunk 6: End-to-End Test
- [ ] Chunk 7: Multiple Jobs Test
- [ ] Chunk 8: Executor Validation (Optional)

---

## Next Steps

After completing human validation:
1. Document any issues found
2. Fix any problems
3. Re-validate if needed
4. Proceed to fresh VM deployment


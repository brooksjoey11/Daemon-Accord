# Verification Guide

This guide documents the verification processes for the Accord Engine system.

## Production Verification

### Control Plane Verification

The Control Plane includes a production verification script that validates core components:

**Location**: `04-Control-Plane-Orchestrator/production_verification.py`

**Usage**:
```bash
cd 04-Control-Plane-Orchestrator
python production_verification.py
```

**What it verifies**:
- JobOrchestrator can be instantiated
- Core components are functional
- Async architecture is correctly implemented
- Production readiness

**Output**:
- `[OK]` - Component verified successfully
- `[ERROR]` - Verification failed
- `[PASS]` - Overall verification passed
- `[FAIL]` - Overall verification failed

## Dependency Verification

### Control Plane Dependencies

**Location**: `04-Control-Plane-Orchestrator/bin/verify_dependencies.py`

**Usage**:
```bash
cd 04-Control-Plane-Orchestrator
python bin/verify_dependencies.py
```

**What it verifies**:
- All module imports work correctly
- Configuration modules load
- Database modules are accessible
- Control plane components can be imported

**Output**:
- `✓` - Module verified
- `✗` - Module failed
- `[WARN]` - Warning (may be OK in runtime)
- `[ERROR]` - Import error found
- `[OK]` - All dependencies verified

## End-to-End Flow Verification

### Complete System Test

**Location**: `scripts/test_e2e_flow.py`

**Usage**:
```bash
# Start all services first
cd 05-Deploy-Monitoring-Infra/src/deploy
docker-compose -f docker-compose.full.yml up -d

# Wait for services to be healthy
sleep 30

# Run E2E test
cd ../../..
python scripts/test_e2e_flow.py
```

**What it verifies**:
1. **Health Check**: Control Plane is healthy
2. **Enqueue**: Job can be created via API
3. **Orchestrate**: Job appears in queue
4. **Execute**: Job is processed and completes
5. **Store**: Results and artifacts are stored
6. **Query**: Job status can be retrieved

**Flow**:
```
POST /api/v1/jobs → GET /api/v1/queue/stats → 
GET /api/v1/jobs/{id} (poll) → Verify results
```

**Output**:
- `[STEP N]` - Current step being executed
- `[OK]` - Step completed successfully
- `[FAIL]` - Step failed
- `[PASS]` - All steps passed
- `[FAIL]` - One or more steps failed

## Syntax Verification

### Python Compilation Check

**Usage**:
```bash
# Check all Python files
python -m compileall -q .

# Check specific service
python -m compileall -q 04-Control-Plane-Orchestrator/src
```

**What it verifies**:
- All Python files have valid syntax
- No compilation errors
- Imports are syntactically correct

**Expected**: Zero errors

## Docker Build Verification

### Service Builds

**Usage**:
```bash
cd 05-Deploy-Monitoring-Infra/src/deploy
docker-compose -f docker-compose.full.yml build
```

**What it verifies**:
- All Dockerfiles are valid
- Dependencies can be installed
- Services can be built successfully

**Services to build**:
- execution-engine
- control-plane
- memory-service

## Service Health Checks

### Control Plane

```bash
curl http://localhost:8082/health
```

**Expected response**:
```json
{
  "status": "healthy",
  "service": "control-plane",
  "workers": 5
}
```

### Memory Service

```bash
curl http://localhost:8100/health
```

**Expected response**:
```json
{
  "status": "healthy",
  "service": "memory-service"
}
```

## Queue Statistics Verification

### Check Queue Status

```bash
curl http://localhost:8082/api/v1/queue/stats
```

**Expected response**:
```json
{
  "normal": {"length": 0, "pending": 0},
  "high": {"length": 0, "pending": 0},
  "emergency": {"length": 0, "pending": 0},
  "low": {"length": 0, "pending": 0},
  "dlq": {"length": 0},
  "delayed": {"count": 0},
  "total": 0
}
```

## Best Practices

1. **Run verification before deployment**: Always run production verification before deploying to production
2. **Check dependencies**: Verify dependencies are installed before running services
3. **Test E2E flow**: Run the E2E test after any major changes
4. **Monitor health endpoints**: Regularly check service health in production
5. **Verify syntax**: Run syntax checks before committing code

## Troubleshooting

### Verification Script Fails

- Check that all dependencies are installed
- Verify environment variables are set correctly
- Ensure services are running (for E2E tests)
- Check logs for specific error messages

### E2E Test Timeout

- Increase `MAX_WAIT_TIME` in the script if jobs take longer
- Check that Execution Engine is properly configured
- Verify Redis and PostgreSQL are accessible
- Check service logs for errors

### Docker Build Fails

- Verify Dockerfile syntax
- Check that all required files are present
- Ensure base images are accessible
- Review build logs for specific errors


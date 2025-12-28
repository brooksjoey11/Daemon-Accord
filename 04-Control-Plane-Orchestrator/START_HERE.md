# START HERE - Control Plane Operational Guide

## Quick Start (Make It Run)

### Prerequisites
1. **PostgreSQL** running (port 5432)
2. **Redis** running (port 6379)
3. **Python 3.11+** installed

### Step 1: Install Dependencies

```bash
cd 04-Control-Plane-Orchestrator
pip install -r requirements.txt
```

### Step 2: Start Infrastructure

```bash
# Option A: Using docker-compose (recommended)
cd 05-Deploy-Monitoring-Infra/src/deploy
docker-compose -f docker-compose.full.yml up -d redis postgres

# Option B: Manual
# Start PostgreSQL and Redis on your system
```

### Step 3: Configure (if needed)

Create `.env` file (optional - defaults work for local dev):

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/accord_engine
REDIS_URL=redis://localhost:6379/0
```

### Step 4: Initialize Database

```bash
# Option A: Quick start (dev only)
# Set SKIP_INIT_MODELS=false (default)
# Tables auto-created on startup

# Option B: Production (use migrations)
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
export SKIP_INIT_MODELS=true
```

### Step 5: Start Service

```bash
# Option A: Direct
python -m src.main

# Option B: Uvicorn
uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

### Step 6: Verify

```bash
# Health check
curl http://localhost:8080/health

# Should return:
# {"status":"healthy","service":"control-plane","workers":5}
```

## Create Your First Job

```bash
curl -X POST "http://localhost:8080/api/v1/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "example.com",
    "url": "https://example.com",
    "job_type": "navigate_extract",
    "strategy": "vanilla",
    "priority": 2,
    "payload": {"selector": "h1"}
  }'
```

## Docker Deployment

```bash
# Build
docker build -t control-plane .

# Run (requires Redis and PostgreSQL accessible)
docker run -p 8080:8080 \
  -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@host.docker.internal:5432/accord_engine \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  control-plane
```

## Full Stack (All Services)

```bash
cd 05-Deploy-Monitoring-Infra/src/deploy
docker-compose -f docker-compose.full.yml up
```

This starts:
- Redis
- PostgreSQL  
- Control Plane (port 8082)
- Memory Service (port 8100)
- Execution Engine (port 8081)
- Prometheus & Grafana

## Troubleshooting

### Service won't start
- Check PostgreSQL is running: `pg_isready`
- Check Redis is running: `redis-cli ping`
- Check ports 5432 and 6379 are available

### Database errors
- Verify DATABASE_URL uses `asyncpg://` (not just `postgresql://`)
- Check database exists: `createdb accord_engine` (if needed)
- Check user permissions

### Import errors
- Ensure you're in the `04-Control-Plane-Orchestrator` directory
- Verify PYTHONPATH includes `src` directory
- Check all dependencies installed: `pip install -r requirements.txt`

### Worker errors
- Check Redis Streams consumer groups are initialized
- Verify queue streams exist in Redis
- Check worker logs for specific errors

## API Endpoints

- `GET /health` - Health check
- `POST /api/v1/jobs` - Create job
- `GET /api/v1/jobs/{job_id}` - Get job status  
- `GET /api/v1/queue/stats` - Queue statistics

## Next Steps

Once operational:
1. Test job creation and execution
2. Monitor queue stats
3. Check job status endpoints
4. Review logs for errors

See `OPERATIONAL_CHECKLIST.md` for full deployment checklist.


# Operational Readiness Checklist

## Pre-Deployment

### Dependencies
- [x] PostgreSQL running and accessible
- [x] Redis running and accessible
- [x] Database schema initialized (migrations or init_models)
- [x] Environment variables configured

### Code
- [x] All imports resolve
- [x] Async architecture properly implemented
- [x] Error handling in place
- [x] Logging configured

### Infrastructure
- [x] Dockerfile exists
- [x] docker-compose configuration updated
- [x] Health check endpoint functional
- [x] API endpoints operational

## Deployment Steps

1. **Database Setup**
   ```bash
   # Run migrations
   alembic upgrade head
   ```

2. **Environment Configuration**
   ```bash
   export DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
   export REDIS_URL=redis://host:6379/0
   export SKIP_INIT_MODELS=true  # Use migrations in production
   ```

3. **Start Service**
   ```bash
   uvicorn src.main:app --host 0.0.0.0 --port 8080
   ```

4. **Verify**
   ```bash
   curl http://localhost:8080/health
   ```

## Known Limitations

- Execution Engine integration requires Execution Engine module to be available
- Browser pool initialization requires Playwright installation
- Memory Service integration not yet wired (optional)

## Troubleshooting

- **Import errors**: Check PYTHONPATH includes src directory
- **Database connection**: Verify DATABASE_URL format (use asyncpg://)
- **Redis connection**: Verify Redis is running and accessible
- **Worker startup**: Check logs for initialization errors


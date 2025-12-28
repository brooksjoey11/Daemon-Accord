# Security Documentation

## Overview

This document outlines the security posture, practices, and configuration for the Accord Engine Control Plane.

## Authentication

### Current Status

**Development Mode:** Authentication is **disabled** by default.

**Production Mode:** Enable authentication by setting:
```bash
ENABLE_AUTH=true
API_KEY=your-secure-api-key-here
```

### API Key Authentication

The Control Plane supports API key authentication via the `X-API-Key` header.

**Usage:**
```bash
curl -H "X-API-Key: your-api-key" \
  http://localhost:8080/api/v1/jobs
```

### Configuration

API keys can be set via environment variables:
- `API_KEY`: Single API key
- `API_KEYS`: Comma-separated list of API keys

**Example:**
```bash
export API_KEY=secret-key-123
# OR
export API_KEYS=key1,key2,key3
```

## Rate Limiting

### Current Implementation

Rate limiting is implemented using a token bucket algorithm with Redis.

**Default Limits:**
- Job Creation: 100 requests/minute per IP/API key
- Status Checks: 1000 requests/minute per IP/API key
- Queue Stats: 200 requests/minute per IP/API key

### Rate Limit Headers

When rate limiting is active, responses include:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests in window
- `Retry-After`: Seconds to wait before retrying (on 429)

### Configuration

Rate limits can be configured in `src/auth/rate_limiter.py`:
```python
self.limits = {
    "job_creation": {"requests": 100, "window": 60},
    "status_check": {"requests": 1000, "window": 60},
    "queue_stats": {"requests": 200, "window": 60},
}
```

## Security Headers

### Recommended Headers (Production)

Add these headers in production via reverse proxy (nginx, CloudFlare, etc.):

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
```

## Dependency Security

### Vulnerability Scanning

Run regular security scans:

```bash
# Using safety
pip install safety
safety check

# Using pip-audit
pip install pip-audit
pip-audit --requirement requirements.txt
```

### CI/CD Integration

Security scanning is integrated into the CI/CD pipeline (`.github/workflows/ci.yml`).

## Database Security

### Connection Security

- Use SSL/TLS for database connections in production
- Use connection pooling with appropriate limits
- Rotate database credentials regularly

**Example:**
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?ssl=require
```

### Credential Management

**DO NOT:**
- Commit credentials to version control
- Use default passwords
- Share credentials via insecure channels

**DO:**
- Use environment variables or secret management (Vault, AWS Secrets Manager)
- Rotate credentials regularly
- Use least-privilege access

## Redis Security

### Connection Security

- Use Redis AUTH in production
- Use SSL/TLS for Redis connections
- Restrict network access

**Example:**
```bash
REDIS_URL=rediss://:password@host:6380/0  # rediss:// = SSL
```

## API Security Best Practices

### 1. Always Use HTTPS in Production

Never expose the API over HTTP in production. Use:
- Reverse proxy (nginx, Traefik)
- Load balancer with SSL termination
- Cloud provider SSL (AWS ALB, GCP LB)

### 2. Validate Input

All input is validated via Pydantic models. Additional validation:
- URL validation
- Domain whitelisting (if needed)
- Payload size limits

### 3. Logging and Monitoring

- Log all authentication attempts
- Monitor for suspicious patterns
- Set up alerts for rate limit violations
- Track failed job attempts

### 4. Idempotency

Always use idempotency keys for critical operations to prevent duplicate processing.

## Known Limitations

1. **No JWT Support (Yet):** Currently only API key authentication
2. **No OAuth2:** Not implemented
3. **No Role-Based Access Control:** All authenticated users have same permissions
4. **Rate Limiting:** Basic implementation, can be enhanced with distributed rate limiting

## Security Incident Response

### If API Key is Compromised

1. Immediately rotate the API key
2. Review access logs for unauthorized usage
3. Revoke compromised key from all systems
4. Notify affected users/clients

### If Rate Limiting is Bypassed

1. Review rate limit configuration
2. Check Redis connection and health
3. Temporarily lower limits if needed
4. Monitor for abuse patterns

## Security Checklist

Before deploying to production:

- [ ] Authentication enabled (`ENABLE_AUTH=true`)
- [ ] Strong API keys configured
- [ ] Rate limiting enabled and tested
- [ ] HTTPS configured
- [ ] Security headers added
- [ ] Database SSL enabled
- [ ] Redis AUTH enabled
- [ ] Dependency vulnerabilities scanned
- [ ] Credentials stored securely (not in code)
- [ ] Logging and monitoring configured
- [ ] Backup and recovery tested

## Reporting Security Issues

If you discover a security vulnerability, please:
1. **DO NOT** open a public issue
2. Email security concerns to: [security@accord-engine.com]
3. Include details and steps to reproduce
4. Allow time for response before disclosure

---

**Last Updated:** 2024-12-24  
**Version:** 1.0.0


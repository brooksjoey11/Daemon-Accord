# Control Plane API - Complete Usage Guide

**Version:** 1.0.0  
**Base URL:** `http://localhost:8080` (development) / `https://api.accord-engine.com` (production)

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [Core Workflows](#core-workflows)
4. [Job Types](#job-types)
5. [Execution Strategies](#execution-strategies)
6. [Error Handling](#error-handling)
7. [Best Practices](#best-practices)
8. [Code Examples](#code-examples)
9. [Integration Patterns](#integration-patterns)

---

## Quick Start

### 1. Check Service Health

```bash
curl http://localhost:8080/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "control-plane",
  "workers": 5
}
```

### 2. Create Your First Job

```bash
curl -X POST "http://localhost:8080/api/v1/jobs?domain=example.com&url=https://example.com&job_type=navigate_extract" \
  -H "Content-Type: application/json" \
  -d '{"selector": "h1"}'
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "created",
  "domain": "example.com",
  "job_type": "navigate_extract"
}
```

### 3. Check Job Status

```bash
curl http://localhost:8080/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000
```

---

## Authentication

### Current Status
Authentication is **disabled** in development. In production, API key authentication will be required.

### Production Authentication (Coming Soon)

**API Key Authentication:**
```bash
curl -H "X-API-Key: your-api-key-here" \
  http://localhost:8080/api/v1/jobs
```

**JWT Token Authentication:**
```bash
curl -H "Authorization: Bearer your-jwt-token" \
  http://localhost:8080/api/v1/jobs
```

---

## Core Workflows

### Workflow 1: Simple Content Extraction

**Use Case:** Extract text from a webpage

```python
import httpx
import asyncio

async def extract_content(url: str, selector: str):
    async with httpx.AsyncClient() as client:
        # 1. Create job
        response = await client.post(
            "http://localhost:8080/api/v1/jobs",
            params={
                "domain": "example.com",
                "url": url,
                "job_type": "navigate_extract",
                "strategy": "vanilla",
                "priority": 2
            },
            json={"selector": selector}
        )
        job = response.json()
        job_id = job["job_id"]
        
        # 2. Poll for completion
        while True:
            status_response = await client.get(
                f"http://localhost:8080/api/v1/jobs/{job_id}"
            )
            status = status_response.json()
            
            if status["status"] in ["completed", "failed", "cancelled"]:
                return status
            
            await asyncio.sleep(2)  # Poll every 2 seconds

# Usage
result = asyncio.run(extract_content("https://example.com", "h1"))
print(result["result"])
```

### Workflow 2: Authenticated Data Extraction

**Use Case:** Login to a site and extract protected content

```python
async def authenticated_extract(url: str, username: str, password: str):
    async with httpx.AsyncClient() as client:
        # 1. Authenticate
        auth_response = await client.post(
            "http://localhost:8080/api/v1/jobs",
            params={
                "domain": "example.com",
                "url": url,
                "job_type": "authenticate",
                "strategy": "stealth"
            },
            json={
                "username": username,
                "password": password,
                "form_selector": "#login-form"
            }
        )
        auth_job = auth_response.json()
        
        # Wait for authentication
        auth_status = await poll_job(client, auth_job["job_id"])
        if auth_status["status"] != "completed":
            raise Exception("Authentication failed")
        
        # 2. Extract content (using same session)
        extract_response = await client.post(
            "http://localhost:8080/api/v1/jobs",
            params={
                "domain": "example.com",
                "url": f"{url}/dashboard",
                "job_type": "navigate_extract",
                "strategy": "stealth"
            },
            json={"selector": ".dashboard-content"}
        )
        extract_job = extract_response.json()
        
        return await poll_job(client, extract_job["job_id"])
```

### Workflow 3: Batch Processing with Idempotency

**Use Case:** Process multiple URLs without duplicates

```python
async def batch_extract(urls: list[str], idempotency_prefix: str):
    async with httpx.AsyncClient() as client:
        jobs = []
        
        for url in urls:
            response = await client.post(
                "http://localhost:8080/api/v1/jobs",
                params={
                    "domain": "example.com",
                    "url": url,
                    "job_type": "navigate_extract",
                    "idempotency_key": f"{idempotency_prefix}-{url}"  # Prevent duplicates
                },
                json={"selector": "h1"}
            )
            jobs.append(response.json()["job_id"])
        
        # Wait for all jobs
        results = []
        for job_id in jobs:
            status = await poll_job(client, job_id)
            results.append(status)
        
        return results
```

---

## Job Types

### navigate_extract

Navigate to a URL and extract content using CSS selectors.

**Payload:**
```json
{
  "selector": "h1, .content, #main",
  "extract": ["text", "href", "src"],
  "screenshot": true,
  "wait_for": ".loaded"
}
```

**Response:**
```json
{
  "html": "<h1>Title</h1>",
  "text": "Title",
  "elements": [
    {"selector": "h1", "text": "Title", "attributes": {}}
  ]
}
```

### authenticate

Authenticate with a website using credentials.

**Payload:**
```json
{
  "username": "user@example.com",
  "password": "password123",
  "form_selector": "#login-form",
  "username_selector": "#username",
  "password_selector": "#password",
  "submit_selector": "button[type='submit']"
}
```

**Response:**
```json
{
  "success": true,
  "cookies": ["session_id=abc123"],
  "redirect_url": "https://example.com/dashboard"
}
```

### form_submit

Fill out and submit a form.

**Payload:**
```json
{
  "form_selector": "#contact-form",
  "fields": {
    "name": "John Doe",
    "email": "john@example.com",
    "message": "Hello world"
  },
  "submit": true
}
```

### file_download

Download files from a webpage.

**Payload:**
```json
{
  "selector": "a.download-link",
  "save_path": "/downloads",
  "filename_pattern": "{title}-{timestamp}.pdf"
}
```

### screenshot_capture

Capture screenshots of pages.

**Payload:**
```json
{
  "full_page": true,
  "wait_for": ".loaded",
  "format": "png"
}
```

---

## Execution Strategies

### vanilla (Default)
- **Speed:** Fastest
- **Evasion:** None
- **Use When:** Standard websites, no bot detection
- **Example:** Public websites, documentation sites

```python
params = {"strategy": "vanilla"}
```

### stealth
- **Speed:** Medium
- **Evasion:** Basic (fingerprint randomization, timing)
- **Use When:** Sites with basic bot detection
- **Example:** E-commerce sites, news sites

```python
params = {"strategy": "stealth"}
```

### assault
- **Speed:** Slowest
- **Evasion:** Maximum (all techniques)
- **Use When:** Advanced bot detection, CAPTCHA protection
- **Example:** LinkedIn, Gmail, financial sites

```python
params = {"strategy": "assault"}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 201 | Created | Job created successfully |
| 400 | Bad Request | Check request parameters |
| 404 | Not Found | Job ID invalid |
| 429 | Too Many Requests | Implement backoff |
| 500 | Server Error | Retry with exponential backoff |
| 503 | Service Unavailable | Service starting up |

### Job Status Errors

```python
async def handle_job_result(status: dict):
    if status["status"] == "failed":
        error = status.get("error", "Unknown error")
        
        # Categorize errors
        if "timeout" in error.lower():
            # Retry with longer timeout
            return "retry_with_longer_timeout"
        elif "captcha" in error.lower():
            # Switch to assault strategy
            return "retry_with_assault"
        elif "rate_limit" in error.lower():
            # Wait and retry
            return "wait_and_retry"
        else:
            # Log and alert
            return "log_and_alert"
    
    return "success"
```

### Retry Pattern

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def create_job_with_retry(client, params, payload):
    response = await client.post(
        "http://localhost:8080/api/v1/jobs",
        params=params,
        json=payload
    )
    response.raise_for_status()
    return response.json()
```

---

## Best Practices

### 1. Always Use Idempotency Keys

Prevent duplicate jobs for the same operation:

```python
idempotency_key = f"{domain}-{url}-{hash(payload)}"
```

### 2. Set Appropriate Priorities

- **Emergency (0):** Critical, time-sensitive operations
- **High (1):** Important but not urgent
- **Normal (2):** Standard operations (default)
- **Low (3):** Background tasks, bulk operations

### 3. Monitor Job Status Efficiently

Use polling with exponential backoff:

```python
async def poll_job(client, job_id, max_wait=300):
    start_time = time.time()
    poll_interval = 1  # Start with 1 second
    
    while time.time() - start_time < max_wait:
        response = await client.get(f"/api/v1/jobs/{job_id}")
        status = response.json()
        
        if status["status"] in ["completed", "failed", "cancelled"]:
            return status
        
        await asyncio.sleep(poll_interval)
        poll_interval = min(poll_interval * 1.5, 10)  # Max 10 seconds
    
    raise TimeoutError(f"Job {job_id} did not complete in {max_wait}s")
```

### 4. Choose the Right Strategy

- Start with `vanilla` - upgrade only if needed
- Use `stealth` for sites with basic detection
- Reserve `assault` for difficult targets

### 5. Handle Rate Limits

```python
async def create_job_with_rate_limit(client, params, payload):
    try:
        return await client.post("/api/v1/jobs", params=params, json=payload)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            retry_after = int(e.response.headers.get("Retry-After", 60))
            await asyncio.sleep(retry_after)
            return await create_job_with_rate_limit(client, params, payload)
        raise
```

---

## Code Examples

### Python Client Class

```python
import httpx
import asyncio
from typing import Optional, Dict, Any

class AccordEngineClient:
    def __init__(self, base_url: str = "http://localhost:8080", api_key: Optional[str] = None):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            headers={"X-API-Key": api_key} if api_key else {}
        )
    
    async def create_job(
        self,
        domain: str,
        url: str,
        job_type: str,
        payload: Dict[str, Any],
        strategy: str = "vanilla",
        priority: int = 2,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new job."""
        params = {
            "domain": domain,
            "url": url,
            "job_type": job_type,
            "strategy": strategy,
            "priority": priority
        }
        if idempotency_key:
            params["idempotency_key"] = idempotency_key
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/jobs",
            params=params,
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status."""
        response = await self.client.get(f"{self.base_url}/api/v1/jobs/{job_id}")
        response.raise_for_status()
        return response.json()
    
    async def wait_for_completion(
        self,
        job_id: str,
        max_wait: int = 300,
        poll_interval: int = 2
    ) -> Dict[str, Any]:
        """Wait for job to complete."""
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < max_wait:
            status = await self.get_job_status(job_id)
            
            if status["status"] in ["completed", "failed", "cancelled"]:
                return status
            
            await asyncio.sleep(poll_interval)
        
        raise TimeoutError(f"Job {job_id} did not complete in {max_wait}s")
    
    async def close(self):
        """Close the client."""
        await self.client.aclose()

# Usage
async def main():
    client = AccordEngineClient()
    try:
        job = await client.create_job(
            domain="example.com",
            url="https://example.com",
            job_type="navigate_extract",
            payload={"selector": "h1"}
        )
        result = await client.wait_for_completion(job["job_id"])
        print(result)
    finally:
        await client.close()
```

### JavaScript/TypeScript Client

```typescript
class AccordEngineClient {
  constructor(
    private baseUrl: string = "http://localhost:8080",
    private apiKey?: string
  ) {}

  async createJob(
    domain: string,
    url: string,
    jobType: string,
    payload: object,
    options: {
      strategy?: string;
      priority?: number;
      idempotencyKey?: string;
    } = {}
  ): Promise<any> {
    const params = new URLSearchParams({
      domain,
      url,
      job_type: jobType,
      strategy: options.strategy || "vanilla",
      priority: String(options.priority || 2),
    });

    if (options.idempotencyKey) {
      params.append("idempotency_key", options.idempotencyKey);
    }

    const headers: HeadersInit = { "Content-Type": "application/json" };
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }

    const response = await fetch(
      `${this.baseUrl}/api/v1/jobs?${params}`,
      {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    return response.json();
  }

  async getJobStatus(jobId: string): Promise<any> {
    const headers: HeadersInit = {};
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }

    const response = await fetch(
      `${this.baseUrl}/api/v1/jobs/${jobId}`,
      { headers }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    return response.json();
  }

  async waitForCompletion(
    jobId: string,
    maxWait: number = 300000,
    pollInterval: number = 2000
  ): Promise<any> {
    const startTime = Date.now();

    while (Date.now() - startTime < maxWait) {
      const status = await this.getJobStatus(jobId);

      if (["completed", "failed", "cancelled"].includes(status.status)) {
        return status;
      }

      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }

    throw new Error(`Job ${jobId} did not complete in ${maxWait}ms`);
  }
}

// Usage
const client = new AccordEngineClient();
const job = await client.createJob(
  "example.com",
  "https://example.com",
  "navigate_extract",
  { selector: "h1" }
);
const result = await client.waitForCompletion(job.job_id);
console.log(result);
```

---

## Integration Patterns

### Pattern 1: Webhook Notifications (Future)

```python
# When webhooks are implemented
payload = {
    "selector": "h1",
    "webhook_url": "https://your-app.com/webhooks/job-complete"
}
```

### Pattern 2: Batch Processing

```python
async def process_batch(urls: list[str], batch_size: int = 10):
    """Process URLs in batches."""
    for i in range(0, len(urls), batch_size):
        batch = urls[i:i + batch_size]
        jobs = await asyncio.gather(*[
            client.create_job(domain="example.com", url=url, ...)
            for url in batch
        ])
        # Wait for batch completion
        results = await asyncio.gather(*[
            client.wait_for_completion(job["job_id"])
            for job in jobs
        ])
        yield results
```

### Pattern 3: Circuit Breaker Pattern

```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
async def create_job_safe(client, params, payload):
    """Create job with circuit breaker."""
    return await client.create_job(params, payload)
```

---

## Additional Resources

- **Interactive API Docs:** http://localhost:8080/docs
- **OpenAPI Spec:** http://localhost:8080/openapi.json
- **API Reference:** See `API.md`
- **Architecture Docs:** See `docs/architecture/`

---

**Last Updated:** 2024-12-24  
**API Version:** 1.0.0


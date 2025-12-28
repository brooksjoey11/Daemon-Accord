# Control Plane API Documentation

Complete API reference for the Control Plane Orchestrator.

## Base URL

```
http://localhost:8080
```

## Interactive Documentation

- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc
- **OpenAPI JSON**: http://localhost:8080/openapi.json

## Authentication

Currently authentication is disabled for development. In production, API keys or JWT tokens will be required.

---

## Endpoints

### Health Check

Check if the service is operational.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "service": "control-plane",
  "workers": 5
}
```

**Example:**
```bash
curl http://localhost:8080/health
```

---

### Create Job

Create a new job for execution.

**Endpoint:** `POST /api/v1/jobs`

**Query Parameters:**
- `domain` (required, string): Target domain (e.g., 'amazon.com')
- `url` (required, string): Target URL for the job
- `job_type` (required, string): Type of job (e.g., 'navigate_extract', 'authenticate')
- `strategy` (optional, string, default: 'vanilla'): Execution strategy ('vanilla', 'stealth', 'assault')
- `priority` (optional, integer, default: 2): Priority level (0=emergency, 1=high, 2=normal, 3=low)
- `idempotency_key` (optional, string): Key to prevent duplicate job creation
- `timeout_seconds` (optional, integer, default: 300): Job timeout in seconds

**Request Body:**
```json
{
  "selector": "h1",
  "extract": ["title", "content"]
}
```

**Response:** `201 Created`
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "created",
  "domain": "example.com",
  "job_type": "navigate_extract"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8080/api/v1/jobs?domain=example.com&url=https://example.com&job_type=navigate_extract&strategy=vanilla&priority=2" \
  -H "Content-Type: application/json" \
  -d '{"selector": "h1"}'
```

**With Idempotency:**
```bash
curl -X POST "http://localhost:8080/api/v1/jobs?domain=example.com&url=https://example.com&job_type=navigate_extract&idempotency_key=unique-key-123" \
  -H "Content-Type: application/json" \
  -d '{"selector": "h1"}'
```

---

### Get Job Status

Get the current status and details of a job.

**Endpoint:** `GET /api/v1/jobs/{job_id}`

**Path Parameters:**
- `job_id` (required, string): The job ID

**Response:** `200 OK`
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100.0,
  "result": {
    "content": "Extracted content",
    "title": "Page Title"
  },
  "error": null,
  "started_at": "2024-01-01T12:00:00Z",
  "completed_at": "2024-01-01T12:00:05Z",
  "artifacts": ["screenshot.png"]
}
```

**Job Status Values:**
- `pending`: Job is queued and waiting to be processed
- `queued`: Job is in the queue
- `running`: Job is currently being executed
- `completed`: Job completed successfully
- `failed`: Job failed after all retry attempts
- `cancelled`: Job was cancelled

**Example:**
```bash
curl http://localhost:8080/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000
```

**Error Response:** `404 Not Found`
```json
{
  "detail": "Job 550e8400-e29b-41d4-a716-446655440000 not found"
}
```

---

### Get Queue Statistics

Get statistics about the job queue.

**Endpoint:** `GET /api/v1/queue/stats`

**Response:** `200 OK`
```json
{
  "normal": {
    "length": 5,
    "pending": 2
  },
  "high": {
    "length": 2,
    "pending": 0
  },
  "emergency": {
    "length": 0,
    "pending": 0
  },
  "low": {
    "length": 3,
    "pending": 1
  },
  "dlq": {
    "length": 1
  },
  "delayed": {
    "count": 2
  },
  "total": 10
}
```

**Example:**
```bash
curl http://localhost:8080/api/v1/queue/stats
```

---

### Root Endpoint

Get service information.

**Endpoint:** `GET /`

**Response:** `200 OK`
```json
{
  "service": "control-plane",
  "version": "1.0.0",
  "status": "operational"
}
```

---

## Job Types

### navigate_extract
Navigate to a URL and extract content using selectors.

**Payload Example:**
```json
{
  "selector": "h1, .content",
  "extract": ["text", "href"],
  "screenshot": true
}
```

### authenticate
Authenticate with a website.

**Payload Example:**
```json
{
  "username": "user@example.com",
  "password": "password123",
  "form_selector": "#login-form"
}
```

### fill_form
Fill out a form on a webpage.

**Payload Example:**
```json
{
  "form_fields": {
    "name": "John Doe",
    "email": "john@example.com"
  },
  "submit": true
}
```

---

## Execution Strategies

### vanilla
Standard execution without evasion techniques. Fastest, suitable for most sites.

### stealth
Uses basic evasion techniques. Good for sites with basic bot detection.

### assault
Maximum evasion with all techniques. Slower but most effective against advanced detection.

---

## Priority Levels

- `0` - Emergency: Processed immediately
- `1` - High: Processed before normal priority
- `2` - Normal: Standard processing (default)
- `3` - Low: Processed when queue is less busy

---

## Error Responses

All error responses follow this format:

```json
{
  "detail": "Error message description"
}
```

**HTTP Status Codes:**
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service not ready

---

## Rate Limiting

Rate limiting will be implemented in production. Current limits:
- Job creation: 100 requests/minute per IP
- Status checks: 1000 requests/minute per IP

---

## Idempotency

Use the `idempotency_key` parameter to ensure jobs are not created multiple times. If a job with the same idempotency key exists, the existing job ID is returned instead of creating a new job.

Idempotency keys are valid for 24 hours.

**Example:**
```bash
# First request - creates job
curl -X POST "http://localhost:8080/api/v1/jobs?...&idempotency_key=unique-123"

# Second request with same key - returns existing job ID
curl -X POST "http://localhost:8080/api/v1/jobs?...&idempotency_key=unique-123"
```

---

## Best Practices

1. **Always use idempotency keys** for critical jobs to prevent duplicates
2. **Set appropriate priorities** based on business needs
3. **Monitor job status** using the status endpoint
4. **Handle errors gracefully** - check error field in job status
5. **Use appropriate strategies** - vanilla for most cases, stealth/assault only when needed

---

## Code Examples

### Python

```python
import httpx

async def create_job(domain: str, url: str, job_type: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8080/api/v1/jobs",
            params={
                "domain": domain,
                "url": url,
                "job_type": job_type,
                "strategy": "vanilla",
                "priority": 2,
                "idempotency_key": f"{domain}-{url}"
            },
            json={"selector": "h1"}
        )
        return response.json()

async def get_job_status(job_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8080/api/v1/jobs/{job_id}"
        )
        return response.json()
```

### JavaScript/Node.js

```javascript
async function createJob(domain, url, jobType) {
  const response = await fetch(
    `http://localhost:8080/api/v1/jobs?domain=${domain}&url=${url}&job_type=${jobType}&strategy=vanilla&priority=2`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selector: 'h1' })
    }
  );
  return await response.json();
}

async function getJobStatus(jobId) {
  const response = await fetch(
    `http://localhost:8080/api/v1/jobs/${jobId}`
  );
  return await response.json();
}
```

### cURL

```bash
# Create job
JOB_ID=$(curl -X POST "http://localhost:8080/api/v1/jobs?domain=example.com&url=https://example.com&job_type=navigate_extract" \
  -H "Content-Type: application/json" \
  -d '{"selector": "h1"}' | jq -r '.job_id')

# Check status
curl "http://localhost:8080/api/v1/jobs/$JOB_ID"
```


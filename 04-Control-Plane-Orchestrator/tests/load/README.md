# Load Testing

Performance validation suite for Accord Engine Control Plane.

## Prerequisites

```bash
pip install locust
```

## Running Load Tests

### Basic Load Test
```bash
locust -f tests/load/locustfile.py --host=http://localhost:8080
```

Then open http://localhost:8089 in your browser to:
- Set number of users
- Set spawn rate
- Start the test
- View real-time statistics

### Command Line (Headless)
```bash
# 100 users, spawn rate 10/second, run for 5 minutes
locust -f tests/load/locustfile.py \
  --host=http://localhost:8080 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=5m \
  --headless \
  --html=load_test_report.html
```

### Stress Test (High Load)
```bash
# 1000 users, spawn rate 50/second, run for 10 minutes
locust -f tests/load/locustfile.py \
  --host=http://localhost:8080 \
  --users=1000 \
  --spawn-rate=50 \
  --run-time=10m \
  --headless \
  --html=stress_test_report.html
```

## Test Scenarios

### Scenario 1: Normal Load
- Users: 50
- Spawn Rate: 5/second
- Duration: 5 minutes
- Expected: All requests succeed, <200ms p95 latency

### Scenario 2: High Load
- Users: 200
- Spawn Rate: 20/second
- Duration: 10 minutes
- Expected: <500ms p95 latency, <1% error rate

### Scenario 3: Stress Test
- Users: 1000
- Spawn Rate: 50/second
- Duration: 15 minutes
- Expected: System remains stable, graceful degradation

## Metrics to Monitor

1. **Response Times:**
   - p50 (median)
   - p95 (95th percentile)
   - p99 (99th percentile)

2. **Throughput:**
   - Requests per second (RPS)
   - Successful requests
   - Failed requests

3. **Error Rates:**
   - HTTP 4xx errors
   - HTTP 5xx errors
   - Timeout errors

4. **Resource Usage:**
   - CPU usage
   - Memory usage
   - Database connections
   - Redis connections

## Baseline Targets

Based on system specifications:

- **Job Creation:** <50ms p95
- **Status Check:** <20ms p95
- **Queue Stats:** <30ms p95
- **Throughput:** 1000+ RPS per instance
- **Error Rate:** <0.1% under normal load

## Interpreting Results

### Good Performance
- p95 latency within targets
- Error rate <0.1%
- Throughput meets targets
- Resource usage stable

### Performance Issues
- p95 latency exceeds targets → Need optimization
- Error rate >1% → Need investigation
- Throughput below targets → Need scaling
- Resource usage spikes → Need capacity planning

## Reports

Load test reports are generated in HTML format:
- `load_test_report.html` - Normal load test
- `stress_test_report.html` - Stress test

---

**Note:** Ensure all services are running before load testing:
- Control Plane API
- Redis
- PostgreSQL
- Execution Engine (optional, for full E2E)


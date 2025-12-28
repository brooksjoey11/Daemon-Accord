#!/bin/bash
# One-Command Demo: Start services → Run sample job → Show results + artifacts + audit entry

set -e

echo "🚀 Daemon Accord - One-Command Demo"
echo "===================================="
echo ""

# Step 1: Start services
echo "📦 Step 1: Starting Docker services..."
docker compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 10

# Wait for health check
echo "🏥 Checking service health..."
for i in {1..30}; do
    if curl -s http://localhost:8082/health > /dev/null 2>&1; then
        echo "✅ Services are ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Services failed to start. Check logs: docker compose logs"
        exit 1
    fi
    sleep 2
done

# Step 2: Create a sample job
echo ""
echo "📝 Step 2: Creating sample job..."
JOB_RESPONSE=$(curl -s -X POST "http://localhost:8082/api/v1/jobs?domain=example.com&url=https://example.com&job_type=navigate_extract" \
  -H "Content-Type: application/json" \
  -d '{"selector": "h1"}')

JOB_ID=$(echo $JOB_RESPONSE | grep -o '"job_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$JOB_ID" ]; then
    echo "❌ Failed to create job. Response: $JOB_RESPONSE"
    exit 1
fi

echo "✅ Job created: $JOB_ID"

# Step 3: Wait for job completion
echo ""
echo "⏳ Step 3: Waiting for job to complete (max 60 seconds)..."
for i in {1..60}; do
    JOB_STATUS=$(curl -s "http://localhost:8082/api/v1/jobs/$JOB_ID" | grep -o '"status":"[^"]*' | cut -d'"' -f4)
    
    if [ "$JOB_STATUS" = "completed" ]; then
        echo "✅ Job completed!"
        break
    elif [ "$JOB_STATUS" = "failed" ] || [ "$JOB_STATUS" = "cancelled" ]; then
        echo "❌ Job $JOB_STATUS"
        exit 1
    fi
    
    sleep 1
done

# Step 4: Show results
echo ""
echo "📊 Step 4: Job Result"
echo "===================="
curl -s "http://localhost:8082/api/v1/jobs/$JOB_ID" | python3 -m json.tool || cat

# Step 5: Show artifacts
echo ""
echo "📁 Step 5: Artifacts Generated"
echo "=============================="
if [ -d "artifacts" ]; then
    echo "Artifacts directory contents:"
    ls -lh artifacts/ | head -10
else
    echo "No artifacts directory found"
fi

# Step 6: Show audit log entry
echo ""
echo "🔍 Step 6: Audit Log Entry"
echo "=========================="
docker compose exec -T postgres psql -U postgres -d daemon_accord -c "SELECT id, job_id, domain, action, allowed, reason, timestamp FROM audit_logs WHERE job_id = '$JOB_ID' ORDER BY timestamp DESC LIMIT 1;" 2>/dev/null || echo "Note: Audit logs require database access. Run manually: docker compose exec postgres psql -U postgres -d daemon_accord -c \"SELECT * FROM audit_logs WHERE job_id = '$JOB_ID';\""

echo ""
echo "✅ Demo complete!"
echo ""
echo "Next steps:"
echo "  - View full job details: curl http://localhost:8082/api/v1/jobs/$JOB_ID"
echo "  - View all audit logs: docker compose exec postgres psql -U postgres -d daemon_accord -c \"SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 10;\""
echo "  - Stop services: docker compose down"


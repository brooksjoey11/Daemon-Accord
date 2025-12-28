# One-Command Demo: Start services → Run sample job → Show results + artifacts + audit entry

Write-Host "🚀 Daemon Accord - One-Command Demo" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Start services
Write-Host "📦 Step 1: Starting Docker services..." -ForegroundColor Yellow
docker compose up -d

Write-Host "⏳ Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Wait for health check
Write-Host "🏥 Checking service health..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
$ready = $false

while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8082/health" -Method GET -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Services are ready!" -ForegroundColor Green
            $ready = $true
            break
        }
    } catch {
        # Service not ready yet
    }
    
    $attempt++
    Start-Sleep -Seconds 2
}

if (-not $ready) {
    Write-Host "❌ Services failed to start. Check logs: docker compose logs" -ForegroundColor Red
    exit 1
}

# Step 2: Create a sample job
Write-Host ""
Write-Host "📝 Step 2: Creating sample job..." -ForegroundColor Yellow

$body = @{
    selector = "h1"
} | ConvertTo-Json

$jobResponse = Invoke-RestMethod -Uri "http://localhost:8082/api/v1/jobs?domain=example.com&url=https://example.com&job_type=navigate_extract" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

$jobId = $jobResponse.job_id

if (-not $jobId) {
    Write-Host "❌ Failed to create job. Response: $($jobResponse | ConvertTo-Json)" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Job created: $jobId" -ForegroundColor Green

# Step 3: Wait for job completion
Write-Host ""
Write-Host "⏳ Step 3: Waiting for job to complete (max 60 seconds)..." -ForegroundColor Yellow

$maxWait = 60
$waited = 0
$completed = $false

while ($waited -lt $maxWait) {
    try {
        $jobStatus = Invoke-RestMethod -Uri "http://localhost:8082/api/v1/jobs/$jobId" -Method GET
        
        if ($jobStatus.status -eq "completed") {
            Write-Host "✅ Job completed!" -ForegroundColor Green
            $completed = $true
            break
        } elseif ($jobStatus.status -eq "failed" -or $jobStatus.status -eq "cancelled") {
            Write-Host "❌ Job $($jobStatus.status)" -ForegroundColor Red
            exit 1
        }
    } catch {
        # Job not found or error
    }
    
    Start-Sleep -Seconds 1
    $waited++
}

# Step 4: Show results
Write-Host ""
Write-Host "📊 Step 4: Job Result" -ForegroundColor Cyan
Write-Host "====================" -ForegroundColor Cyan
$jobResult = Invoke-RestMethod -Uri "http://localhost:8082/api/v1/jobs/$jobId" -Method GET
$jobResult | ConvertTo-Json -Depth 10

# Step 5: Show artifacts
Write-Host ""
Write-Host "📁 Step 5: Artifacts Generated" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
if (Test-Path "artifacts") {
    Write-Host "Artifacts directory contents:"
    Get-ChildItem -Path "artifacts" | Select-Object -First 10 | Format-Table Name, Length, LastWriteTime
} else {
    Write-Host "No artifacts directory found"
}

# Step 6: Show audit log entry
Write-Host ""
Write-Host "🔍 Step 6: Audit Log Entry" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan
$auditQuery = "SELECT id, job_id, domain, action, allowed, reason, timestamp FROM audit_logs WHERE job_id = '$jobId' ORDER BY timestamp DESC LIMIT 1;"
docker compose exec -T postgres psql -U postgres -d daemon_accord -c $auditQuery 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Note: Audit logs require database access. Run manually:" -ForegroundColor Yellow
    Write-Host "  docker compose exec postgres psql -U postgres -d daemon_accord -c `"SELECT * FROM audit_logs WHERE job_id = '$jobId';`"" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Demo complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  - View full job details: Invoke-RestMethod -Uri http://localhost:8082/api/v1/jobs/$jobId"
Write-Host "  - View all audit logs: docker compose exec postgres psql -U postgres -d daemon_accord -c `"SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 10;`""
Write-Host "  - Stop services: docker compose down"


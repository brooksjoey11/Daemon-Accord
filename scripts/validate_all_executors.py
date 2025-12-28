#!/usr/bin/env python3
"""
Validate All Executors

Tests each executor strategy to ensure they work correctly end-to-end.
"""
import asyncio
import httpx
import time
from typing import Dict, Any, Optional, List

CONTROL_PLANE_URL = "http://localhost:8082"
MAX_WAIT_TIME = 60  # seconds
POLL_INTERVAL = 2  # seconds

# Executors to validate
EXECUTORS = [
    {"strategy": "vanilla", "name": "Vanilla Executor"},
    {"strategy": "stealth", "name": "Stealth Executor"},
    {"strategy": "ultimate_stealth", "name": "Ultimate Stealth Executor"},
    {"strategy": "assault", "name": "Assault Executor"},
    {"strategy": "custom", "name": "Custom Executor"},
]

async def create_job(strategy: str) -> Optional[str]:
    """Create a job with the specified strategy."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{CONTROL_PLANE_URL}/api/v1/jobs",
                params={
                    "domain": "example.com",
                    "url": "https://example.com",
                    "job_type": "navigate_extract",
                    "strategy": strategy,
                    "priority": 2
                },
                json={"selector": "h1"}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("job_id")
        except Exception as e:
            print(f"[ERROR] Failed to create job with strategy '{strategy}': {e}")
            return None

async def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job status from API."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{CONTROL_PLANE_URL}/api/v1/jobs/{job_id}")
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

async def wait_for_job_completion(job_id: str, strategy: str) -> Optional[Dict[str, Any]]:
    """Wait for job to complete."""
    start_time = time.time()
    
    while time.time() - start_time < MAX_WAIT_TIME:
        status = await get_job_status(job_id)
        
        if status is None:
            await asyncio.sleep(POLL_INTERVAL)
            continue
        
        job_status = status.get("status", "").lower()
        
        if job_status in ["completed", "failed", "cancelled"]:
            return status
        
        await asyncio.sleep(POLL_INTERVAL)
    
    print(f"[ERROR] Job {job_id} ({strategy}) did not complete within {MAX_WAIT_TIME} seconds")
    return None

async def verify_job_result(status: Dict[str, Any], strategy: str) -> bool:
    """Verify job result is valid."""
    if status.get("status") != "completed":
        print(f"[FAIL] Job status is '{status.get('status')}', expected 'completed'")
        return False
    
    result = status.get("result")
    if not result:
        print(f"[FAIL] Job has no result data")
        return False
    
    if not isinstance(result, dict):
        print(f"[FAIL] Result is not a dictionary")
        return False
    
    # Check for expected data (HTML content for navigate_extract)
    if "html" not in result:
        print(f"[WARN] Result missing 'html' field (may be OK for other job types)")
    
    error = status.get("error")
    if error:
        print(f"[WARN] Job completed but has error: {error}")
    
    return True

async def validate_executor(executor: Dict[str, str]) -> Dict[str, Any]:
    """Validate a single executor."""
    strategy = executor["strategy"]
    name = executor["name"]
    
    print(f"\n{'='*60}")
    print(f"Validating: {name} (strategy: {strategy})")
    print(f"{'='*60}")
    
    # Step 1: Create job
    print(f"[STEP 1] Creating job with strategy '{strategy}'...")
    job_id = await create_job(strategy)
    if not job_id:
        return {
            "strategy": strategy,
            "name": name,
            "status": "FAILED",
            "error": "Failed to create job"
        }
    print(f"[OK] Job created: {job_id}")
    
    # Step 2: Wait for completion
    print(f"[STEP 2] Waiting for job execution...")
    final_status = await wait_for_job_completion(job_id, strategy)
    if not final_status:
        return {
            "strategy": strategy,
            "name": name,
            "status": "FAILED",
            "error": "Job did not complete in time"
        }
    
    # Step 3: Verify result
    print(f"[STEP 3] Verifying job result...")
    is_valid = await verify_job_result(final_status, strategy)
    
    if is_valid:
        print(f"[PASS] {name} validation successful")
        return {
            "strategy": strategy,
            "name": name,
            "status": "PASSED",
            "job_id": job_id,
            "result": final_status.get("result", {})
        }
    else:
        print(f"[FAIL] {name} validation failed")
        return {
            "strategy": strategy,
            "name": name,
            "status": "FAILED",
            "job_id": job_id,
            "error": "Result verification failed"
        }

async def main():
    """Main validation function."""
    print("\n" + "="*60)
    print("EXECUTOR VALIDATION SUITE")
    print("="*60)
    print(f"\nValidating {len(EXECUTORS)} executors...")
    
    results = []
    for executor in EXECUTORS:
        result = await validate_executor(executor)
        results.append(result)
        await asyncio.sleep(2)  # Brief pause between tests
    
    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results if r["status"] == "PASSED")
    failed = sum(1 for r in results if r["status"] == "FAILED")
    
    print(f"\nTotal: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    print("\nDetailed Results:")
    for result in results:
        status_icon = "✅" if result["status"] == "PASSED" else "❌"
        print(f"  {status_icon} {result['name']}: {result['status']}")
        if result["status"] == "FAILED" and "error" in result:
            print(f"      Error: {result['error']}")
    
    if failed > 0:
        print("\n" + "="*60)
        print("[FAIL] SOME EXECUTORS FAILED VALIDATION")
        print("="*60)
        return 1
    else:
        print("\n" + "="*60)
        print("[PASS] ALL EXECUTORS PASSED VALIDATION")
        print("="*60)
        return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)


"""
Locust load test for Control Plane API.

Usage:
    locust -f tests/load/locustfile.py --host=http://localhost:8080

Then open http://localhost:8089 to start the test.
"""
import random
from locust import HttpUser, task, between
import json


class ControlPlaneUser(HttpUser):
    """Simulated user for load testing."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Called when a simulated user starts."""
        # Health check
        self.client.get("/health")
    
    @task(3)
    def create_job(self):
        """Create a job (most common operation)."""
        payload = {
            "selector": "h1",
            "extract": ["text"]
        }
        
        params = {
            "domain": "example.com",
            "url": f"https://example.com/page-{random.randint(1, 100)}",
            "job_type": "navigate_extract",
            "strategy": random.choice(["vanilla", "stealth", "assault"]),
            "priority": random.choice([0, 1, 2, 3])
        }
        
        with self.client.post(
            "/api/v1/jobs",
            params=params,
            json=payload,
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
                # Store job_id for status checks
                data = response.json()
                self.job_id = data.get("job_id")
            else:
                response.failure(f"Failed to create job: {response.status_code}")
    
    @task(5)
    def get_job_status(self):
        """Get job status (very common operation)."""
        if hasattr(self, 'job_id') and self.job_id:
            self.client.get(f"/api/v1/jobs/{self.job_id}")
        else:
            # Use a known job ID or skip
            pass
    
    @task(1)
    def get_queue_stats(self):
        """Get queue statistics."""
        self.client.get("/api/v1/queue/stats")
    
    @task(1)
    def health_check(self):
        """Health check endpoint."""
        self.client.get("/health")


class HighLoadUser(HttpUser):
    """High-frequency user for stress testing."""
    
    wait_time = between(0.1, 0.5)  # Very short wait times
    
    @task(10)
    def rapid_job_creation(self):
        """Rapid job creation."""
        payload = {"selector": "h1"}
        params = {
            "domain": "test.com",
            "url": f"https://test.com/page-{random.randint(1, 1000)}",
            "job_type": "navigate_extract",
            "strategy": "vanilla",
            "priority": 2
        }
        
        self.client.post("/api/v1/jobs", params=params, json=payload)


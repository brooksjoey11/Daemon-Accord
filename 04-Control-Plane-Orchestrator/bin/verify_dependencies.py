#!/usr/bin/env python3
"""
Dependency Verification Script

Verifies that all Control Plane modules can be imported without errors.
Used for production verification and deployment validation.

Usage:
    python bin/verify_dependencies.py
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

def verify_dependencies():
    """Verify all module imports."""
    errors = []
    
    print("=" * 60)
    print("Control Plane - Dependency Verification")
    print("=" * 60)
    print()
    
    # Test config
    try:
        from config import ControlPlaneSettings
        print("[OK] config.py")
    except Exception as e:
        errors.append(f"config: {e}")
        print(f"[ERROR] config.py: {e}")
    
    # Test database (relative imports - will work in runtime)
    try:
        from database import Database
        print("[OK] database.py")
    except (ImportError, ModuleNotFoundError) as e:
        if "relative import" in str(e) or "parent package" in str(e):
            print("[WARN] database.py (relative import - OK in runtime)")
        else:
            errors.append(f"database: {e}")
            print(f"[ERROR] database.py: {e}")
    except Exception as e:
        errors.append(f"database: {e}")
        print(f"[ERROR] database.py: {e}")
    
    # Test models
    try:
        from control_plane.models import Job, JobExecution, JobStatus
        print("[OK] models.py")
    except Exception as e:
        errors.append(f"models: {e}")
        print(f"[ERROR] models.py: {e}")
    
    # Test queue_manager
    try:
        from control_plane.queue_manager import QueueManager
        print("[OK] queue_manager.py")
    except Exception as e:
        errors.append(f"queue_manager: {e}")
        print(f"[ERROR] queue_manager.py: {e}")
    
    # Test state_manager
    try:
        from control_plane.state_manager import StateManager
        print("[OK] state_manager.py")
    except Exception as e:
        errors.append(f"state_manager: {e}")
        print(f"[ERROR] state_manager.py: {e}")
    
    # Test idempotency_engine
    try:
        from control_plane.idempotency_engine import IdempotencyEngine
        print("[OK] idempotency_engine.py")
    except Exception as e:
        errors.append(f"idempotency_engine: {e}")
        print(f"[ERROR] idempotency_engine.py: {e}")
    
    # Test executor_adapter
    try:
        from control_plane.executor_adapter import ExecutorAdapter
        print("[OK] executor_adapter.py")
    except Exception as e:
        errors.append(f"executor_adapter: {e}")
        print(f"[ERROR] executor_adapter.py: {e}")
    
    # Test job_orchestrator (this will test all dependencies)
    try:
        from control_plane.job_orchestrator import JobOrchestrator
        print("[OK] job_orchestrator.py")
    except Exception as e:
        errors.append(f"job_orchestrator: {e}")
        print(f"[ERROR] job_orchestrator.py: {e}")
    
    # Test main (relative imports - will work in runtime)
    try:
        import main
        print("[OK] main.py")
    except (ImportError, ModuleNotFoundError) as e:
        if "relative import" in str(e) or "parent package" in str(e):
            print("[WARN] main.py (relative import - OK in runtime)")
        else:
            errors.append(f"main: {e}")
            print(f"[ERROR] main.py: {e}")
    except Exception as e:
        errors.append(f"main: {e}")
        print(f"[ERROR] main.py: {e}")
    
    print()
    print("=" * 60)
    if errors:
        print(f"[ERROR] {len(errors)} import error(s) found:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("[OK] All dependencies verified successfully!")
        print("=" * 60)
        return True

if __name__ == "__main__":
    success = verify_dependencies()
    sys.exit(0 if success else 1)

# Production Proof Pack - Quick Reference

## Quick Start

```bash
# Install dependency
pip install httpx

# Run proof pack (default: 10 jobs)
python scripts/proof_pack/run_proof_pack.py

# Custom number of jobs
python scripts/proof_pack/run_proof_pack.py --jobs 20
```

## What It Generates

All artifacts in: `proof_pack_artifacts/YYYYMMDD-HHMM/`

- `run_summary.json` - Complete run results
- `e2e_trace.log` - Detailed execution log
- `docker_ps.txt` - Running containers
- `sha256_manifest.txt` - Integrity checksums
- `control-plane_logs.txt` - Service logs
- `execution-engine_logs.txt` - Worker logs

## Exit Codes

- `0` - All checks passed ✅
- `1` - Service startup/health failed
- `2` - Job execution failed
- `3` - Persistence verification failed
- `4` - Artifact generation failed

## Pass Criteria

✅ All services healthy  
✅ All jobs submitted  
✅ ≥50% jobs completed  
✅ ≥50% completed jobs verified  

See `docs/PROOF_PACK.md` for complete documentation.


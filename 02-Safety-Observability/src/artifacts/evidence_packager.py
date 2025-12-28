# backend/app/execution/artifacts/evidence_packager.py
import asyncio
import json
import zipfile
import hashlib
import os
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import aiofiles
import aiohttp
import base64

class EvidencePackager:
    def __init__(self, base_path: str = "/app/artifacts"):
        self.base_path = Path(base_path)
        self.supabase_url = os.environ.get("SUPABASE_URL", "")
        self.supabase_key = os.environ.get("SUPABASE_KEY", "")
    
    async def package(self, evidence_dict: Dict[str, Any], 
                     metadata: Dict[str, Any],
                     include_diffs: bool = False,
                     diff_results: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """
        Package evidence into ZIP file.
        Returns (zip_path, sha256_checksum)
        """
        job_id = metadata.get('job_id', 'unknown')
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Create package directory
        package_dir = self.base_path / job_id / f"package_{timestamp}"
        package_dir.mkdir(parents=True, exist_ok=True)
"""
API Key Authentication middleware.

In production, this should be enabled via ENABLE_AUTH environment variable.
"""
import os
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from ..config import ControlPlaneSettings

settings = ControlPlaneSettings()

# API Key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyAuth:
    """API Key authentication handler."""
    
    def __init__(self):
        # In production, load from secure storage (vault, env, etc.)
        # For now, use environment variable or default for development
        self.valid_api_keys = set()
        
        # Load API keys from environment
        api_key = os.getenv("API_KEY")
        if api_key:
            self.valid_api_keys.add(api_key)
        
        # Allow multiple keys (comma-separated)
        api_keys = os.getenv("API_KEYS", "")
        if api_keys:
            self.valid_api_keys.update(api_keys.split(","))
        
        # Development: if no keys set and auth disabled, allow all
        self.enabled = settings.enable_auth or bool(self.valid_api_keys)
    
    def verify(self, api_key: Optional[str]) -> bool:
        """Verify API key."""
        if not self.enabled:
            return True  # Auth disabled in development
        
        if not api_key:
            return False
        
        return api_key in self.valid_api_keys


# Global instance
_api_key_auth = APIKeyAuth()


def get_api_key_auth(api_key: Optional[str] = Security(api_key_header)) -> bool:
    """
    Dependency to verify API key.
    
    Usage:
        @app.get("/protected")
        async def protected_route(auth: bool = Depends(get_api_key_auth)):
            ...
    """
    if not _api_key_auth.verify(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return True


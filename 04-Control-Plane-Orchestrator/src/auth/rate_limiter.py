"""
Rate limiting middleware.

Uses token bucket algorithm with Redis for distributed rate limiting.
"""
import time
from typing import Optional
from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from ..config import ControlPlaneSettings

settings = ControlPlaneSettings()


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, redis_client: Optional[Redis] = None):
        self.redis = redis_client
        # Default limits (can be configured)
        self.limits = {
            "job_creation": {"requests": 100, "window": 60},  # 100/min
            "status_check": {"requests": 1000, "window": 60},  # 1000/min
            "queue_stats": {"requests": 200, "window": 60},  # 200/min
        }
    
    async def check_rate_limit(
        self,
        key: str,
        limit_type: str = "job_creation",
        identifier: Optional[str] = None
    ) -> bool:
        """
        Check if request is within rate limit.
        
        Args:
            key: Redis key prefix
            limit_type: Type of limit to check
            identifier: Optional identifier (IP, API key, etc.)
        
        Returns:
            True if within limit, False otherwise
        """
        if not self.redis:
            return True  # No Redis = no rate limiting
        
        limit_config = self.limits.get(limit_type, {"requests": 100, "window": 60})
        max_requests = limit_config["requests"]
        window_seconds = limit_config["window"]
        
        # Create unique key
        if identifier:
            redis_key = f"ratelimit:{key}:{limit_type}:{identifier}"
        else:
            redis_key = f"ratelimit:{key}:{limit_type}"
        
        # Get current count
        current = await self.redis.get(redis_key)
        
        if current is None:
            # First request in window
            await self.redis.setex(redis_key, window_seconds, "1")
            return True
        
        current_count = int(current)
        
        if current_count >= max_requests:
            return False
        
        # Increment counter
        await self.redis.incr(redis_key)
        await self.redis.expire(redis_key, window_seconds)
        
        return True
    
    async def get_remaining(
        self,
        key: str,
        limit_type: str = "job_creation",
        identifier: Optional[str] = None
    ) -> int:
        """Get remaining requests in current window."""
        if not self.redis:
            return 999999  # Unlimited
        
        limit_config = self.limits.get(limit_type, {"requests": 100, "window": 60})
        max_requests = limit_config["requests"]
        
        if identifier:
            redis_key = f"ratelimit:{key}:{limit_type}:{identifier}"
        else:
            redis_key = f"ratelimit:{key}:{limit_type}"
        
        current = await self.redis.get(redis_key)
        if current is None:
            return max_requests
        
        current_count = int(current)
        return max(0, max_requests - current_count)


# Global instance (will be initialized in main.py)
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        raise RuntimeError("Rate limiter not initialized")
    return _rate_limiter


async def rate_limit_middleware(
    request: Request,
    limit_type: str = "job_creation"
) -> None:
    """
    Rate limiting middleware.
    
    Usage:
        @app.post("/api/v1/jobs")
        async def create_job(..., rate_limit: None = Depends(rate_limit_middleware)):
            ...
    """
    limiter = get_rate_limiter()
    
    # Get identifier (IP address or API key)
    identifier = request.client.host if request.client else "unknown"
    
    # Check for API key in header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        identifier = f"apikey:{api_key}"
    
    # Check rate limit
    allowed = await limiter.check_rate_limit(
        key="control-plane",
        limit_type=limit_type,
        identifier=identifier
    )
    
    if not allowed:
        remaining = await limiter.get_remaining(
            key="control-plane",
            limit_type=limit_type,
            identifier=identifier
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again later.",
            headers={
                "X-RateLimit-Limit": str(limiter.limits[limit_type]["requests"]),
                "X-RateLimit-Remaining": str(remaining),
                "Retry-After": "60"
            }
        )


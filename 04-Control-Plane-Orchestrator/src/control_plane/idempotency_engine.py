"""
Idempotency Engine

Prevents duplicate job creation by tracking idempotency keys.
Uses Redis for fast lookups with configurable TTL.
"""
from typing import Optional
import redis.asyncio as redis
import structlog

from ..exceptions import RedisError

logger = structlog.get_logger(__name__)


class IdempotencyEngine:
    """
    Manages idempotency keys to prevent duplicate job creation.
    
    Stores idempotency_key -> job_id mappings in Redis with TTL.
    This ensures that if the same job is submitted multiple times
    (e.g., due to network retries), only one job is created.
    """
    
    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 86400):
        """
        Initialize idempotency engine.
        
        Args:
            redis_client: Redis async client
            ttl_seconds: Time-to-live for idempotency keys (default: 24 hours)
        """
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
        self.key_prefix = "idempotency:"
    
    async def check(self, idempotency_key: str) -> Optional[str]:
        """
        Check if an idempotency key already exists.
        
        Args:
            idempotency_key: The idempotency key to check
            
        Returns:
            Existing job_id if key exists, None otherwise
        """
        if not idempotency_key:
            return None
        
        try:
            redis_key = f"{self.key_prefix}{idempotency_key}"
            existing_job_id = await self.redis.get(redis_key)
            
            if existing_job_id:
                # Decode bytes to string if needed
                if isinstance(existing_job_id, bytes):
                    existing_job_id = existing_job_id.decode('utf-8')
                
                logger.info(
                    "idempotency_key_found",
                    idempotency_key=idempotency_key,
                    job_id=existing_job_id
                )
                return existing_job_id
            
            return None
            
        except Exception as e:
            logger.error(
                "error_checking_idempotency_key",
                idempotency_key=idempotency_key,
                error=str(e),
                exc_info=True
            )
            # On error, allow the request to proceed (fail open)
            # But log the error for monitoring
            raise RedisError(
                f"Failed to check idempotency key {idempotency_key}",
                operation="check_idempotency",
                details={"idempotency_key": idempotency_key}
            ) from e
    
    async def store(self, idempotency_key: str, job_id: str) -> bool:
        """
        Store an idempotency key -> job_id mapping.
        
        Args:
            idempotency_key: The idempotency key
            job_id: The job ID to associate with the key
            
        Returns:
            True if stored successfully, False otherwise
        """
        if not idempotency_key or not job_id:
            return False
        
        try:
            redis_key = f"{self.key_prefix}{idempotency_key}"
            
            # Store with TTL
            await self.redis.setex(
                redis_key,
                self.ttl_seconds,
                job_id
            )
            
            logger.debug(
                "idempotency_key_stored",
                idempotency_key=idempotency_key,
                job_id=job_id,
                ttl_seconds=self.ttl_seconds
            )
            return True
            
        except Exception as e:
            logger.error(
                "error_storing_idempotency_key",
                idempotency_key=idempotency_key,
                job_id=job_id,
                error=str(e),
                exc_info=True
            )
            raise RedisError(
                f"Failed to store idempotency key {idempotency_key}",
                operation="store_idempotency",
                details={"idempotency_key": idempotency_key, "job_id": job_id}
            ) from e
    
    async def delete(self, idempotency_key: str) -> bool:
        """
        Delete an idempotency key (for testing/cleanup).
        
        Args:
            idempotency_key: The idempotency key to delete
            
        Returns:
            True if deleted, False otherwise
        """
        if not idempotency_key:
            return False
        
        try:
            redis_key = f"{self.key_prefix}{idempotency_key}"
            deleted = await self.redis.delete(redis_key)
            return deleted > 0
        except Exception as e:
            logger.error(
                "error_deleting_idempotency_key",
                idempotency_key=idempotency_key,
                error=str(e),
                exc_info=True
            )
            raise RedisError(
                f"Failed to delete idempotency key {idempotency_key}",
                operation="delete_idempotency",
                details={"idempotency_key": idempotency_key}
            ) from e
    
    async def exists(self, idempotency_key: str) -> bool:
        """
        Check if an idempotency key exists (without returning the job_id).
        
        Args:
            idempotency_key: The idempotency key to check
            
        Returns:
            True if key exists, False otherwise
        """
        if not idempotency_key:
            return False
        
        try:
            redis_key = f"{self.key_prefix}{idempotency_key}"
            exists = await self.redis.exists(redis_key)
            return exists > 0
        except Exception as e:
            logger.error(
                "error_checking_idempotency_key_existence",
                idempotency_key=idempotency_key,
                error=str(e),
                exc_info=True
            )
            raise RedisError(
                f"Failed to check idempotency key existence {idempotency_key}",
                operation="exists_idempotency",
                details={"idempotency_key": idempotency_key}
            ) from e


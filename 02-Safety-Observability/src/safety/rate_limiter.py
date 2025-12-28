import asyncio
import time
import json
from typing import Optional, Tuple, Dict, Any
import hashlib
import random

RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local tokens_per_interval = tonumber(ARGV[2])
local interval_seconds = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local max_tokens = tonumber(ARGV[5])

local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')

local current_tokens = 0
local last_refill = now

if bucket[1] then
    current_tokens = tonumber(bucket[1])
end

if bucket[2] then
    last_refill = tonumber(bucket[2])
end

-- Calculate tokens to add
local time_passed = now - last_refill
local intervals_passed = math.floor(time_passed / interval_seconds)
local tokens_to_add = intervals_passed * tokens_per_interval

if tokens_to_add > 0 then
    current_tokens = math.min(current_tokens + tokens_to_add, max_tokens)
    last_refill = last_refill + (intervals_passed * interval_seconds)
end

-- Check if enough tokens available
if current_tokens >= requested then
    current_tokens = current_tokens - requested
    redis.call('HMSET', key, 'tokens', current_tokens, 'last_refill', last_refill)
    redis.call('EXPIRE', key, math.ceil(interval_seconds * 2))
    return {1, current_tokens, last_refill}
else
    -- Calculate wait time
    local tokens_needed = requested - current_tokens
    local intervals_needed = math.ceil(tokens_needed / tokens_per_interval)
    local wait_seconds = (intervals_needed * interval_seconds) - (now - last_refill)
    wait_seconds = math.max(wait_seconds, 0)
    
    redis.call('HMSET', key, 'tokens', current_tokens, 'last_refill', last_refill)
    redis.call('EXPIRE', key, math.ceil(interval_seconds * 2))
    return {0, current_tokens, wait_seconds}
end
"""

class RateLimiter:
    def __init__(self, redis_client, identifier: str, rate_type: str = "domain"):
        self.redis = redis_client
        self.identifier = identifier
        self.rate_type = rate_type
        
        # Define rate limits based on type
        if rate_type == "domain":
            self.tokens_per_minute = 5
            self.tokens_per_hour = 30
            self.max_tokens = 50
            self.key_prefix = f"rate:domain:{identifier}"
        elif rate_type == "ip":
            self.tokens_per_minute = 20
            self.tokens_per_hour = 100
            self.max_tokens = 150
            self.key_prefix = f"rate:ip:{identifier}"
        else:
            self.tokens_per_minute = 10
            self.tokens_per_hour = 50
            self.max_tokens = 75
            self.key_prefix = f"rate:custom:{identifier}"
        
        # Load Lua script
        self.script_sha = None
    
    async def _load_script(self):
        """Load Lua script into Redis."""
        if not self.script_sha:
            self.script_sha = await self.redis.script_load(RATE_LIMIT_SCRIPT)
        return self.script_sha
    
    async def acquire(self, tokens: int = 1, interval: str = "minute") -> Tuple[bool, float, Dict[str, Any]]:
        """
        Attempt to acquire tokens.
        Returns: (success, wait_time_seconds, metadata)
        """
        script_sha = await self._load_script()
        
        # Determine rate limits for interval
        if interval == "minute":
            tokens_per_interval = self.tokens_per_minute
            interval_seconds = 60
            key = f"{self.key_prefix}:minute"
        elif interval == "hour":
            tokens_per_interval = self.tokens_per_hour
            interval_seconds = 3600
            key = f"{self.key_prefix}:hour"
        else:
            raise ValueError(f"Unsupported interval: {interval}")
        
        now = time.time()
        
        try:
            # Execute Lua script atomically
            result = await self.redis.evalsha(
                script_sha,
                1,  # number of keys
                key,
                now,
                tokens_per_interval,
                interval_seconds,
                tokens,
                self.max_tokens
            )
            
            success = bool(result[0])
            current_tokens = float(result[1])
            
            if success:
                wait_time = 0
                last_refill = float(result[2])
            else:
                wait_time = float(result[2])
                last_refill = now
            
            metadata = {
                'identifier': self.identifier,
                'rate_type': self.rate_type,
                'interval': interval,
                'tokens_requested': tokens,
                'tokens_remaining': current_tokens,
                'tokens_per_interval': tokens_per_interval,
                'last_refill': last_refill,
                'success': success
            }
            
            return success, wait_time, metadata
            
        except Exception as e:
            # Fallback: always allow if Redis fails
            return True, 0, {
                'identifier': self.identifier,
                'error': str(e),
                'fallback': True
            }
    
    async def acquire_with_backoff(self, tokens: int = 1, max_attempts: int = 3) -> Tuple[bool, Dict[str, Any]]:
        """
        Attempt to acquire tokens with exponential backoff.
        """
        attempts = []
        
        for attempt in range(max_attempts):
            # Try minute bucket first
            success_minute, wait_minute, meta_minute = await self.acquire(tokens, "minute")
            attempts.append(('minute', success_minute, wait_minute, meta_minute))
            
            if success_minute:
                # Try hour bucket
                success_hour, wait_hour, meta_hour = await self.acquire(tokens, "hour")
                attempts.append(('hour', success_hour, wait_hour, meta_hour))
                
                if success_hour:
                    return True, {
                        'attempts': attempts,
                        'final_success': True
                    }
                else:
                    # Release minute tokens if hour fails
                    await self.release(tokens, "minute")
            
            # Calculate backoff with jitter
            base_backoff = min(2 ** attempt, 60)  # Max 60 seconds
            jitter = random.uniform(0, base_backoff * 0.3)  # 0-30% jitter
            backoff_time = base_backoff + jitter
            
            if attempt < max_attempts - 1:
                await asyncio.sleep(backoff_time)
        
        return False, {
            'attempts': attempts,
            'final_success': False,
            'exhausted': True
        }
    
    async def release(self, tokens: int = 1, interval: str = "minute"):
        """Release previously acquired tokens."""
        if interval == "minute":
            key = f"{self.key_prefix}:minute"
        elif interval == "hour":
            key = f"{self.key_prefix}:hour"
        else:
            return
        
        try:
            # Get current tokens
            current = await self.redis.hget(key, 'tokens')
            if current:
                current_tokens = float(current)
                new_tokens = min(current_tokens + tokens, self.max_tokens)
                await self.redis.hset(key, 'tokens', new_tokens)
        except:
            pass
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current rate limit status for all intervals."""
        status = {
            'identifier': self.identifier,
            'rate_type': self.rate_type,
            'limits': {
                'tokens_per_minute': self.tokens_per_minute,
                'tokens_per_hour': self.tokens_per_hour,
                'max_tokens': self.max_tokens
            }
        }
        
        # Check minute bucket
        try:
            minute_data = await self.redis.hgetall(f"{self.key_prefix}:minute")
            if minute_data:
                status['minute'] = {
                    'tokens': float(minute_data.get(b'tokens', 0)),
                    'last_refill': float(minute_data.get(b'last_refill', 0)),
                    'ttl': await self.redis.ttl(f"{self.key_prefix}:minute")
                }
        except:
            pass
        
        # Check hour bucket
        try:
            hour_data = await self.redis.hgetall(f"{self.key_prefix}:hour")
            if hour_data:
                status['hour'] = {
                    'tokens': float(hour_data.get(b'tokens', 0)),
                    'last_refill': float(hour_data.get(b'last_refill', 0)),
                    'ttl': await self.redis.ttl(f"{self.key_prefix}:hour")
                }
        except:
            pass
        
        return status
    
    async def reset(self):
        """Reset rate limits for this identifier."""
        try:
            await self.redis.delete(f"{self.key_prefix}:minute")
            await self.redis.delete(f"{self.key_prefix}:hour")
        except:
            pass

class RateLimitManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.limiters = {}
    
    def get_limiter(self, identifier: str, rate_type: str = "domain") -> RateLimiter:
        """Get or create rate limiter for identifier."""
        key = f"{rate_type}:{identifier}"
        
        if key not in self.limiters:
            self.limiters[key] = RateLimiter(
                redis_client=self.redis,
                identifier=identifier,
                rate_type=rate_type
            )
        
        return self.limiters[key]
    
    async def check_all_limits(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered limiters."""
        results = {}
        for limiter in self.limiters.values():
            status = await limiter.get_status()
            results[limiter.identifier] = status
        return results

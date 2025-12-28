import redis
import time
import hashlib
from pathlib import Path
from typing import Tuple

class RateLimiter:
    def __init__(self, redis_client=None):
        if redis_client is None:
            from backend.app.queues.redis_streams import RedisStreams
            self.redis = RedisStreams().get_client()
        else:
            self.redis = redis_client
        
        # Load Lua script
        lua_path = Path(__file__).parent / "rate_limit.lua"
        with open(lua_path, 'r') as f:
            self.lua_script = f.read()
        
        self.script_sha = self.redis.script_load(self.lua_script)
        
        # Default limits
        self.default_limits = {
            'domain_per_minute': 5,
            'ip_per_hour': 100,
            'concurrent': 20
        }
    
    def acquire(self, domain: str, client_ip: str) -> Tuple[bool, int, int]:
        """Check rate limits for domain+IP combination."""
        current_time = int(time.time())
        
        # Generate keys
        domain_minute_key = f"rl:domain:{domain}:minute"
        ip_hour_key = f"rl:ip:{client_ip}:hour"
        concurrent_key = f"rl:concurrent:{domain}"
        
        # Get limits from config or use defaults
        from .target_registry import TargetRegistry
        registry = TargetRegistry()
        config = registry.get_config(domain)
        limits = config.rate_limits or self.default_limits
        
        # Execute Lua script atomically
        result = self.redis.evalsha(
            self.script_sha,
            4,  # Number of keys
            domain_minute_key,
            ip_hour_key,
            concurrent_key,
            f"rl:config:{hashlib.md5(domain.encode()).hexdigest()}",
            limits.get('domain_per_minute', 5),
            limits.get('ip_per_hour', 100),
            limits.get('concurrent', 20),
            current_time,
            60,  # minute window
            3600,  # hour window
            300  # concurrent timeout (5 minutes)
        )
        
        allowed = bool(result[0])
        remaining = int(result[1])
        reset_after = int(result[2])
        
        return allowed, remaining, reset_after
    
    def release_concurrent(self, domain: str):
        """Release concurrent slot when job completes."""
        concurrent_key = f"rl:concurrent:{domain}"
        self.redis.decr(concurrent_key)

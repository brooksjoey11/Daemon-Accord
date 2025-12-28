import redis
import time
import json
from typing import Optional, Tuple

class CircuitBreaker:
    def __init__(self, redis_client=None):
        if redis_client is None:
            from backend.app.queues.redis_streams import RedisStreams
            self.redis = RedisStreams().get_client()
        else:
            self.redis = redis_client
        
        self.failure_thresholds = [3, 5, 10]
        self.backoff_times = [3600, 21600, 86400]  # 1h, 6h, 24h
    
    def _get_key(self, domain: str) -> str:
        return f"circuit:{domain}"
    
    def check(self, domain: str) -> Tuple[bool, Optional[int]]:
        """Check if circuit is open for domain."""
        circuit_key = self._get_key(domain)
        
        # Get current state
        data = self.redis.get(circuit_key)
        if not data:
            return True, None
        
        state = json.loads(data)
        
        # Check if in backoff period
        if state.get('status') == 'open':
            opened_at = state.get('opened_at', 0)
            backoff_time = state.get('backoff_time', 0)
            
            if time.time() - opened_at < backoff_time:
                return False, backoff_time - int(time.time() - opened_at)
            else:
                # Backoff expired, reset to half-open
                self.redis.delete(circuit_key)
                return True, None
        
        return True, None
    
    def record_failure(self, domain: str, error_type: str = "generic"):
        """Record failure and update circuit state."""
        circuit_key = self._get_key(domain)
        
        with self.redis.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(circuit_key)
                    
                    # Get current state
                    data = pipe.get(circuit_key)
                    current_state = json.loads(data) if data else {
                        'failures': 0,
                        'status': 'closed',
                        'last_failure': 0
                    }
                    
                    # Update failure count
                    current_state['failures'] += 1
                    current_state['last_failure'] = time.time()
                    
                    # Check if threshold reached
                    failures = current_state['failures']
                    for i, threshold in enumerate(self.failure_thresholds):
                        if failures == threshold:
                            current_state['status'] = 'open'
                            current_state['opened_at'] = time.time()
                            current_state['backoff_time'] = self.backoff_times[i]
                            break
                    
                    # Store updated state
                    pipe.multi()
                    pipe.setex(
                        circuit_key,
                        self.backoff_times[-1] * 2,  # Double max backoff for cleanup
                        json.dumps(current_state)
                    )
                    pipe.execute()
                    break
                    
                except redis.WatchError:
                    continue
    
    def record_success(self, domain: str):
        """Reset circuit on successful execution."""
        circuit_key = self._get_key(domain)
        self.redis.delete(circuit_key)

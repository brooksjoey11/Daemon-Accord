import asyncio
import time
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import random

class CircuitState:
    CLOSED = 0
    OPEN = 1
    HALF_OPEN = 2

class CircuitBreaker:
    def __init__(self, redis_client, domain: str, failure_threshold: int = 3, 
                 cooldown_sequence: list = None, name: str = None):
        self.redis = redis_client
        self.domain = domain
        self.failure_threshold = failure_threshold
        self.cooldown_sequence = cooldown_sequence or [3600, 21600, 86400]  # 1h, 6h, 24h
        self.name = name or f"circuit:{domain}"
        self.metrics_prefix = "circuit_breaker"
        
    async def allow_execution(self) -> tuple[bool, Optional[float]]:
        """Check if circuit allows execution. Returns (allowed, remaining_cooldown)."""
        circuit_data = await self._get_circuit_state()
        
        if circuit_data['state'] == CircuitState.CLOSED:
            return True, 0
        
        elif circuit_data['state'] == CircuitState.OPEN:
            current_time = time.time()
            cooldown_until = circuit_data.get('cooldown_until', 0)
            
            if current_time >= cooldown_until:
                # Transition to HALF_OPEN for test request
                await self._set_half_open()
                return True, 0
            else:
                remaining = cooldown_until - current_time
                return False, remaining
        
        elif circuit_data['state'] == CircuitState.HALF_OPEN:
            # Allow exactly one request through
            await self._consume_half_open_token()
            return True, 0
        
        return False, 0
    
    async def record_success(self):
        """Record successful execution, reset failure count."""
        circuit_data = await self._get_circuit_state()
        
        if circuit_data['state'] == CircuitState.HALF_OPEN:
            # Success in HALF_OPEN state closes the circuit
            await self._reset_circuit()
        elif circuit_data['state'] == CircuitState.CLOSED:
            # Reset consecutive failures
            circuit_data['consecutive_failures'] = 0
            circuit_data['last_failure'] = None
            await self._set_circuit_state(circuit_data, ttl=86400)
        
        # Emit metrics
        await self._emit_metrics(CircuitState.CLOSED)
    
    async def record_failure(self, error_type: str = "generic"):
        """Record failed execution, potentially open circuit."""
        circuit_data = await self._get_circuit_state()
        
        if circuit_data['state'] == CircuitState.HALF_OPEN:
            # Failure in HALF_OPEN re-opens circuit with next cooldown
            failure_count = circuit_data.get('consecutive_failures', 0) + 1
            cooldown_index = min(failure_count - 1, len(self.cooldown_sequence) - 1)
            cooldown = self.cooldown_sequence[cooldown_index]
            
            circuit_data['state'] = CircuitState.OPEN
            circuit_data['cooldown_until'] = time.time() + cooldown
            circuit_data['last_failure'] = {
                'timestamp': time.time(),
                'error_type': error_type
            }
            
            await self._set_circuit_state(circuit_data, ttl=cooldown + 3600)
            await self._emit_metrics(CircuitState.OPEN)
            return
        
        # Increment failure count
        current_failures = circuit_data.get('consecutive_failures', 0) + 1
        circuit_data['consecutive_failures'] = current_failures
        circuit_data['last_failure'] = {
            'timestamp': time.time(),
            'error_type': error_type
        }
        
        # Check if threshold reached
        if current_failures >= self.failure_threshold:
            cooldown_index = min(current_failures - self.failure_threshold, len(self.cooldown_sequence) - 1)
            cooldown = self.cooldown_sequence[cooldown_index]
            
            circuit_data['state'] = CircuitState.OPEN
            circuit_data['cooldown_until'] = time.time() + cooldown
            ttl = cooldown + 3600
        else:
            ttl = 86400
        
        await self._set_circuit_state(circuit_data, ttl=ttl)
        
        if circuit_data['state'] == CircuitState.OPEN:
            await self._emit_metrics(CircuitState.OPEN)
    
    async def force_open(self, cooldown_seconds: int = 3600):
        """Force circuit open regardless of failure count."""
        circuit_data = {
            'state': CircuitState.OPEN,
            'consecutive_failures': self.failure_threshold,
            'cooldown_until': time.time() + cooldown_seconds,
            'last_failure': {
                'timestamp': time.time(),
                'error_type': 'forced'
            },
            'forced': True
        }
        
        await self._set_circuit_state(circuit_data, ttl=cooldown_seconds + 3600)
        await self._emit_metrics(CircuitState.OPEN)
    
    async def force_reset(self):
        """Force circuit closed, reset all counters."""
        await self._reset_circuit()
        await self._emit_metrics(CircuitState.CLOSED)
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get current circuit state and statistics."""
        circuit_data = await self._get_circuit_state()
        
        if circuit_data['state'] == CircuitState.OPEN:
            remaining = max(0, circuit_data.get('cooldown_until', 0) - time.time())
        else:
            remaining = 0
        
        return {
            'domain': self.domain,
            'state': circuit_data['state'],
            'state_name': ['CLOSED', 'OPEN', 'HALF_OPEN'][circuit_data['state']],
            'consecutive_failures': circuit_data.get('consecutive_failures', 0),
            'remaining_cooldown': remaining,
            'last_failure': circuit_data.get('last_failure'),
            'is_forced': circuit_data.get('forced', False)
        }
    
    async def _get_circuit_state(self) -> Dict[str, Any]:
        """Retrieve circuit state from Redis."""
        try:
            data = await self.redis.get(self.name)
            if data:
                return json.loads(data)
        except:
            pass
        
        # Default state
        return {
            'state': CircuitState.CLOSED,
            'consecutive_failures': 0,
            'last_failure': None,
            'cooldown_until': 0
        }
    
    async def _set_circuit_state(self, data: Dict[str, Any], ttl: int):
        """Store circuit state in Redis with TTL."""
        try:
            await self.redis.setex(
                self.name,
                ttl,
                json.dumps(data)
            )
        except:
            pass
    
    async def _set_half_open(self):
        """Transition circuit to HALF_OPEN state."""
        circuit_data = await self._get_circuit_state()
        circuit_data['state'] = CircuitState.HALF_OPEN
        circuit_data['half_open_token'] = hashlib.md5(str(time.time()).encode()).hexdigest()
        
        # Allow exactly one request through in next 60 seconds
        await self._set_circuit_state(circuit_data, ttl=60)
        await self._emit_metrics(CircuitState.HALF_OPEN)
    
    async def _consume_half_open_token(self):
        """Mark HALF_OPEN token as consumed."""
        circuit_data = await self._get_circuit_state()
        circuit_data['half_open_token_consumed'] = True
        await self._set_circuit_state(circuit_data, ttl=60)
    
    async def _reset_circuit(self):
        """Reset circuit to initial CLOSED state."""
        circuit_data = {
            'state': CircuitState.CLOSED,
            'consecutive_failures': 0,
            'last_failure': None,
            'cooldown_until': 0
        }
        await self._set_circuit_state(circuit_data, ttl=86400)
    
    async def _emit_metrics(self, state: int):
        """Emit Prometheus metrics."""
        try:
            from prometheus_client import Gauge
            gauge = Gauge(
                f'{self.metrics_prefix}_state',
                'Circuit breaker state (0=closed, 1=open, 2=half_open)',
                ['domain']
            )
            gauge.labels(domain=self.domain).set(state)
        except:
            pass

class CircuitBreakerManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.breakers = {}
        self.default_cooldown = [3600, 21600, 86400]
    
    def get_breaker(self, domain: str, failure_threshold: int = 3, 
                   cooldown_sequence: list = None) -> CircuitBreaker:
        """Get or create circuit breaker for domain."""
        key = f"{domain}:{failure_threshold}"
        
        if key not in self.breakers:
            self.breakers[key] = CircuitBreaker(
                redis_client=self.redis,
                domain=domain,
                failure_threshold=failure_threshold,
                cooldown_sequence=cooldown_sequence or self.default_cooldown
            )
        
        return self.breakers[key]
    
    async def check_all_breakers(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered breakers."""
        results = {}
        for breaker in self.breakers.values():
            metrics = await breaker.get_metrics()
            results[breaker.domain] = metrics
        return results

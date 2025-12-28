# backend/app/execution/safety/__init__.py
from .circuit_breaker import CircuitBreaker, CircuitBreakerManager, CircuitState
from .rate_limiter import RateLimiter, RateLimitManager, RATE_LIMIT_SCRIPT
from .credential_vault import CredentialVault, CredentialManager

class SafetyLayer:
    def __init__(self, redis_client, prometheus_client=None):
        self.redis = redis_client
        self.prometheus = prometheus_client
        
        self.circuit_manager = CircuitBreakerManager(redis_client)
        self.rate_manager = RateLimitManager(redis_client)
        self.cred_manager = CredentialManager(redis_client) 
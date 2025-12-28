import pytest
import redis
import time
import yaml
from pathlib import Path
from testcontainers.redis import RedisContainer

from ..src.targets.target_registry import TargetRegistry, TargetConfig
from ..src.targets.circuit_breakers import CircuitBreaker
from ..src.targets.rate_limiter import RateLimiter

@pytest.fixture
def redis_container():
    with RedisContainer() as redis_container:
        yield redis_container

@pytest.fixture
def redis_client(redis_container):
    return redis.Redis(
        host=redis_container.get_container_host_ip(),
        port=redis_container.get_exposed_port(6379),
        decode_responses=True
    )

@pytest.fixture
def target_registry(redis_client):
    registry = TargetRegistry()
    # Override Redis client for testing
    registry.circuit_breaker = CircuitBreaker(redis_client)
    registry.rate_limiter = RateLimiter(redis_client)
    return registry

def test_registry_loads_configs(tmp_path):
    # Create test YAML config
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    
    config_data = {
        'domain': 'test.com',
        'selectors': {'test': '//div'},
        'wait_strategies': {'wait': 5},
        'rate_limits': {'limit': 10},
        'circuit_breaker_settings': {'thresholds': [1,2,3]},
        'heuristics': {'risk': 'low'}
    }
    
    config_file = config_dir / "test.com.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    
    registry = TargetRegistry()
    registry.load_configs(str(config_dir))
    
    config = registry.get_config('test.com')
    assert config.domain == 'test.com'
    assert config.selectors['test'] == '//div'

def test_domain_extraction():
    registry = TargetRegistry()
    
    test_cases = [
        ("https://www.amazon.com/product", "amazon.com"),
        ("http://api.stripe.com/v1", "stripe.com"),
        ("https://sub.domain.co.uk/path", "domain.co.uk"),
        ("mail.google.com", "google.com")
    ]
    
    for url, expected in test_cases:
        assert registry.get_domain(url) == expected

def test_circuit_breaker_open_close(redis_client):
    cb = CircuitBreaker(redis_client)
    domain = "test.com"
    
    # Initially closed
    allowed, retry = cb.check(domain)
    assert allowed is True
    
    # Record failures up to threshold
    for _ in range(3):
        cb.record_failure(domain)
    
    # Should be open after 3 failures
    allowed, retry = cb.check(domain)
    assert allowed is False
    assert retry is not None

def test_rate_limiter_acquire(redis_client):
    rl = RateLimiter(redis_client)
    domain = "test.com"
    ip = "192.168.1.1"
    
    # First request should succeed
    allowed, remaining, reset = rl.acquire(domain, ip)
    assert allowed is True
    
    # Exhaust domain limit
    for _ in range(10):
        rl.acquire(domain, ip)
    
    # Should be rate limited
    allowed, remaining, reset = rl.acquire(domain, ip)
    assert allowed is False

def test_concurrent_limit(redis_client):
    rl = RateLimiter(redis_client)
    domain = "test.com"
    
    # Simulate concurrent requests
    results = []
    for i in range(25):  # More than default 20
        ip = f"192.168.1.{i}"
        allowed, _, _ = rl.acquire(domain, ip)
        results.append(allowed)
    
    # Some should be limited
    assert not all(results)

def test_lua_script_atomic(redis_client):
    """Test Lua script executes atomically."""
    import threading
    
    rl = RateLimiter(redis_client)
    domain = "atomic-test.com"
    
    results = []
    def make_request():
        ip = f"10.0.0.{threading.current_thread().ident % 256}"
        allowed, _, _ = rl.acquire(domain, ip)
        results.append(allowed)
    
    # Create concurrent requests
    threads = []
    for _ in range(50):
        t = threading.Thread(target=make_request)
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # Count successes - should not exceed limits
    success_count = sum(results)
    assert success_count <= 20  # concurrent limit

def test_heuristic_config_creation():
    registry = TargetRegistry()
    
    # Test high-risk domain detection
    high_risk = registry._create_heuristic_config("cloudflare-protected.com")
    assert high_risk.heuristics['risk_level'] == 'high'
    assert high_risk.wait_strategies['between_requests'] == 2
    
    # Test normal domain
    normal = registry._create_heuristic_config("example.com")
    assert normal.heuristics['risk_level'] == 'medium'
    assert normal.wait_strategies['between_requests'] == 1

def test_benchmark_registry_lookup(target_registry, benchmark):
    def lookup():
        return target_registry.get_config("amazon.com")
    
    result = benchmark(lookup)
    assert isinstance(result, TargetConfig)

def test_benchmark_domain_extraction(target_registry, benchmark):
    def extract():
        return target_registry.get_domain("https://www.amazon.com/product/123")
    
    result = benchmark(extract)
    assert result == "amazon.com"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

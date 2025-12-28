import yaml
import tldextract
import asyncio
import time
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import json
import hashlib
import sys

from .circuit_breakers import CircuitBreaker
from .rate_limiter import RateLimiter

@dataclass
class TargetConfig:
    domain: str
    selectors: Dict[str, str] = field(default_factory=dict)
    wait_strategies: Dict[str, Any] = field(default_factory=dict)
    rate_limits: Dict[str, int] = field(default_factory=dict)
    circuit_breaker_settings: Dict[str, Any] = field(default_factory=dict)
    heuristics: Dict[str, Any] = field(default_factory=dict)

class TargetRegistry:
    _instance = None
    _configs: Dict[str, TargetConfig] = {}
    _extractor = tldextract.TLDExtract()
    _cache: Dict[str, Tuple[TargetConfig, float]] = {}
    _cache_ttl = 60
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.circuit_breaker = CircuitBreaker()
        self.rate_limiter = RateLimiter()
    
    def load_configs(self, config_dir: str):
        config_path = Path(config_dir)
        for yaml_file in config_path.glob("*.yaml"):
            with open(yaml_file, 'r') as f:
                config_data = yaml.safe_load(f)
                domain = config_data['domain']
                config = TargetConfig(
                    domain=domain,
                    selectors=config_data.get('selectors', {}),
                    wait_strategies=config_data.get('wait_strategies', {}),
                    rate_limits=config_data.get('rate_limits', {}),
                    circuit_breaker_settings=config_data.get('circuit_breaker_settings', {}),
                    heuristics=config_data.get('heuristics', {})
                )
                self._configs[domain] = config
    
    def get_domain(self, url: str) -> str:
        extracted = self._extractor(url)
        return f"{extracted.domain}.{extracted.suffix}" if extracted.suffix else extracted.domain
    
    def get_config(self, domain: str) -> TargetConfig:
        now = time.time()
        
        # Check cache
        if domain in self._cache:
            config, timestamp = self._cache[domain]
            if now - timestamp < self._cache_ttl:
                return config
        
        # Load config
        if domain not in self._configs:
            # Apply heuristics for unknown domains
            config = self._create_heuristic_config(domain)
            self._configs[domain] = config
        else:
            config = self._configs[domain]
        
        # Update cache
        self._cache[domain] = (config, now)
        return config
    
    def _create_heuristic_config(self, domain: str) -> TargetConfig:
        tld = domain.split('.')[-1] if '.' in domain else ''
        
        # Known high-risk TLDs/patterns
        high_risk_patterns = ['cloudflare', 'datadome', 'akamai', 'incapsula', 'f5']
        is_high_risk = any(pattern in domain.lower() for pattern in high_risk_patterns)
        
        # Default config with heuristics
        return TargetConfig(
            domain=domain,
            selectors={
                'default': '//body',
                'form': '//form',
                'input': '//input[@type=\"text\"]'
            },
            wait_strategies={
                'page_load': 10,
                'element': 5,
                'between_requests': 2 if is_high_risk else 1
            },
            rate_limits={
                'domain_per_minute': 3 if is_high_risk else 5,
                'ip_per_hour': 50 if is_high_risk else 100,
                'concurrent': 10 if is_high_risk else 20
            },
            circuit_breaker_settings={
                'failure_thresholds': [3, 5, 10],
                'backoff_times': [3600, 21600, 86400],
                'reset_timeout': 86400
            },
            heuristics={
                'risk_level': 'high' if is_high_risk else 'medium',
                'requires_stealth': is_high_risk,
                'detected_patterns': []
            }
        )
    
    def validate_safety(self, domain: str, client_ip: str = "127.0.0.1") -> Tuple[bool, Dict[str, Any]]:
        """Check all safety mechanisms before execution."""
        results = {
            'circuit_breaker': None,
            'rate_limiter': None,
            'config': None
        }
        
        # Circuit breaker check
        cb_allowed, cb_retry = self.circuit_breaker.check(domain)
        results['circuit_breaker'] = {
            'allowed': cb_allowed,
            'retry_after': cb_retry
        }
        
        if not cb_allowed:
            return False, results
        
        # Rate limiter check
        rl_allowed, rl_remaining, rl_reset = self.rate_limiter.acquire(domain, client_ip)
        results['rate_limiter'] = {
            'allowed': rl_allowed,
            'remaining': rl_remaining,
            'reset_after': rl_reset
        }
        
        if not rl_allowed:
            return False, results
        
        # Get config
        config = self.get_config(domain)
        results['config'] = config
        
        return True, results
    
    def record_failure(self, domain: str, error_type: str = "generic"):
        """Record failure for circuit breaker."""
        self.circuit_breaker.record_failure(domain, error_type)

def validate_configs(config_dir: str):
    """CLI validation command."""
    registry = TargetRegistry()
    registry.load_configs(config_dir)
    
    print(f"Loaded {len(registry._configs)} configurations:")
    for domain in sorted(registry._configs.keys()):
        print(f"  [OK] {domain}")
    
    # Benchmark tests
    import time
    
    test_urls = [
        "https://www.amazon.com/product/123",
        "https://api.stripe.com/v1/charges",
        "https://www.linkedin.com/in/johndoe",
        "https://mail.google.com/mail/u/0",
        "https://twitter.com/home",
        "https://www.walmart.com/cart"
    ]
    
    print("\nBenchmarking domain extraction:")
    for url in test_urls:
        start = time.perf_counter()
        domain = registry.get_domain(url)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  {url[:50]:50} -> {domain:20} ({elapsed:.2f}ms)")
    
    print("\nValidation complete.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "validate":
        validate_configs(sys.argv[2] if len(sys.argv) > 2 else "backend/app/execution/targets/configurations/")

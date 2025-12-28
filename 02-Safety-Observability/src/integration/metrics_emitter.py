# backend/app/execution/integration/metrics_emitter.py
import time
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from prometheus_client import (
    Counter, Gauge, Histogram, Summary, 
    generate_latest, REGISTRY, start_http_server
)

class MetricsEmitter:
    def __init__(self, port: int = 8080, namespace: str = "execution"):
        self.namespace = namespace
        self.port = port
        self.metrics = {}
        self._init_metrics()
    
    def _init_metrics(self):
        """Initialize all Prometheus metrics."""
        # Execution metrics
        self.metrics['execution_total'] = Counter(
            f'{self.namespace}_execution_total',
            'Total number of executions',
            ['domain', 'strategy', 'success']
        )
        
        self.metrics['execution_duration'] = Histogram(
            f'{self.namespace}_execution_duration_seconds',
            'Execution duration in seconds',
            ['domain', 'strategy'],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)
        )
        
        # Circuit breaker metrics
        self.metrics['circuit_breaker_state'] = Gauge(
            f'{self.namespace}_circuit_breaker_state',
            'Circuit breaker state (0=closed, 1=open, 2=half_open)',
            ['domain']
        )
        
        self.metrics['circuit_breaker_transitions'] = Counter(
            f'{self.namespace}_circuit_breaker_transitions_total',
            'Total circuit breaker state transitions',
            ['domain', 'from_state', 'to_state']
        )
        
        # Rate limiting metrics
        self.metrics['rate_limit_requests'] = Counter(
            f'{self.namespace}_rate_limit_requests_total',
            'Total rate limit requests',
            ['domain', 'type', 'allowed']
        )
        
        self.metrics['rate_limit_wait_time'] = Histogram(
            f'{self.namespace}_rate_limit_wait_seconds',
            'Rate limit wait time in seconds',
            ['domain', 'type'],
            buckets=(0.001, 0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0)
        )
        
        # Browser metrics
        self.metrics['browser_sessions'] = Gauge(
            f'{self.namespace}_browser_sessions',
            'Current number of browser sessions',
            []
        )
        
        self.metrics['browser_acquisition_time'] = Histogram(
            f'{self.namespace}_browser_acquisition_seconds',
            'Browser acquisition time in seconds',
            [],
            buckets=(0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0)
        )
        
        # Error metrics
        self.metrics['error_total'] = Counter(
            f'{self.namespace}_error_total',
            'Total errors by type',
            ['domain', 'error_type']
        )
        
        self.metrics['retry_total'] = Counter(
            f'{self.namespace}_retry_total',
            'Total retry attempts',
            ['domain', 'strategy']
        )
        
        # Memory service metrics
        self.metrics['memory_service_calls'] = Counter(
            f'{self.namespace}_memory_service_calls_total',
            'Memory service API calls',
            ['endpoint', 'status']
        )
        
        self.metrics['memory_service_duration'] = Histogram(
            f'{self.namespace}_memory_service_duration_seconds',
            'Memory service call duration in seconds',
            ['endpoint'],
            buckets=(0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0)
        )
        
        # Queue metrics
        self.metrics['queue_size'] = Gauge(
            f'{self.namespace}_queue_size',
            'Current job queue size',
            []
        )
        
        self.metrics['queue_wait_time'] = Histogram(
            f'{self.namespace}_queue_wait_seconds',
            'Job queue wait time in seconds',
            [],
            buckets=(0.1, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0)
        )
        
        # System metrics
        self.metrics['memory_usage'] = Gauge(
            f'{self.namespace}_memory_usage_bytes',
            'Memory usage in bytes',
            []
        )
        
        self.metrics['cpu_usage'] = Gauge(
            f'{self.namespace}_cpu_usage_percent',
            'CPU usage percentage',
            []
        )
    
    def record_execution(self, domain: str, strategy: str, success: bool, duration: float):
        """Record execution metrics."""
        self.metrics['execution_total'].labels(
            domain=domain,
            strategy=str(strategy),
            success=str(success).lower()
        ).inc()
        
        self.metrics['execution_duration'].labels(
            domain=domain,
            strategy=str(strategy)
        ).observe(duration)
    
    def record_circuit_state(self, domain: str, state: int, 
                           from_state: Optional[int] = None):
        """Record circuit breaker state."""
        self.metrics['circuit_breaker_state'].labels(domain=domain).set(state)
        
        if from_state is not None and from_state != state:
            self.metrics['circuit_breaker_transitions'].labels(
                domain=domain,
                from_state=str(from_state),
                to_state=str(state)
            ).inc()
    
    def record_rate_limit(self, domain: str, limit_type: str, allowed: bool, wait_time: float = 0):
        """Record rate limiting metrics."""
        self.metrics['rate_limit_requests'].labels(
            domain=domain,
            type=limit_type,
            allowed=str(allowed).lower()
        ).inc()
        
        if wait_time > 0:
            self.metrics['rate_limit_wait_time'].labels(
                domain=domain,
                type=limit_type
            ).observe(wait_time)
    
    def record_browser_session(self, count: int, acquisition_time: Optional[float] = None):
        """Record browser session metrics."""
        self.metrics['browser_sessions'].set(count)
        
        if acquisition_time is not None:
            self.metrics['browser_acquisition_time'].observe(acquisition_time)
    
    def record_error(self, domain: str, error_type: str):
        """Record error metrics."""
        self.metrics['error_total'].labels(
            domain=domain,
            error_type=error_type
        ).inc()
    
    def record_retry(self, domain: str, strategy: str):
        """Record retry metrics."""
        self.metrics['retry_total'].labels(
            domain=domain,
            strategy=strategy
        ).inc()
    
    def record_memory_service_call(self, endpoint: str, status: str, duration: float):
        """Record memory service call metrics."""
        self.metrics['memory_service_calls'].labels(
            endpoint=endpoint,
            status=str(status)
        ).inc()
        
        self.metrics['memory_service_duration'].labels(
            endpoint=endpoint
        ).observe(duration)
    
    def record_queue_metrics(self, size: int, wait_time: Optional[float] = None):
        """Record queue metrics."""
        self.metrics['queue_size'].set(size)
        
        if wait_time is not None:
            self.metrics['queue_wait_time'].observe(wait_time)
    
    def update_system_metrics(self):
        """Update system metrics."""
        import psutil
        import os
        
        # Memory usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        self.metrics['memory_usage'].set(memory_info.rss)
        
        # CPU usage
        cpu_percent = process.cpu_percent(interval=0.1)
        self.metrics['cpu_usage'].set(cpu_percent)
    
    def start_metrics_server(self):
        """Start Prometheus metrics server."""
        start_http_server(self.port)
        logging.info(f"Metrics server started on port {self.port}")
    
    def get_metrics(self) -> bytes:
        """Get current metrics as Prometheus exposition format."""
        return generate_latest(REGISTRY)
    
    def get_metrics_dict(self) -> Dict[str, Any]:
        """Get metrics as dictionary for JSON response."""
        from prometheus_client import CollectorRegistry
        from prometheus_client.openmetrics.exposition import generate_latest
        
        data = {}
        for metric_name, metric in self.metrics.items():
            samples = list(metric.collect()[0].samples)
            data[metric_name] = [
                {
                    'labels': sample.labels,
                    'value': sample.value,
                    'timestamp': sample.timestamp
                }
                for sample in samples
            ]
        
        return data
    
    def create_custom_metric(self, metric_type: str, name: str, 
                           description: str, labels: List[str] = None):
        """Create custom metric dynamically."""
        if labels is None:
            labels = []
        
        full_name = f'{self.namespace}_{name}'
        
        if metric_type == 'counter':
            metric = Counter(full_name, description, labels)
        elif metric_type == 'gauge':
            metric = Gauge(full_name, description, labels)
        elif metric_type == 'histogram':
            metric = Histogram(full_name, description, labels)
        elif metric_type == 'summary':
            metric = Summary(full_name, description, labels)
        else:
            raise ValueError(f"Unknown metric type: {metric_type}")
        
        self.metrics[name] = metric
        return metric

class MetricsMiddleware:
    def __init__(self, emitter: MetricsEmitter):
        self.emitter = emitter
    
    async def track_execution(self, domain: str, strategy: str, 
                            func, *args, **kwargs):
        """Decorator-like method to track function execution."""
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            success = True
            return result
        except Exception as e:
            success = False
            error_type = type(e).__name__
            self.emitter.record_error(domain, error_type)
            raise
        finally:
            duration = time.time() - start_time
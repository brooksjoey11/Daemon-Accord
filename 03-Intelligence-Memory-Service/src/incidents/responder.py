import asyncio
from datetime import datetime, timedelta
from collections import defaultdict, deque
import random
import hashlib
import json
from typing import Dict, List, Any, Tuple

class AutomatedResponder:
    def __init__(self, redis_client=None):
        self.response_registry = self._build_response_registry()
        self.execution_history = defaultdict(lambda: deque(maxlen=1000))
        self.domain_blacklist = {}
        self.circuit_breakers = {}
        self.redis = redis_client
        self.response_effectiveness = defaultdict(lambda: deque(maxlen=100))
        
    def _build_response_registry(self) -> Dict:
        """Build registry of response actions"""
        return {
            'circuit_breaker': {
                'function': self._activate_circuit_breaker,
                'timeout_ms': 100,
                'requires_domain': True
            },
            'domain_blacklist': {
                'function': self._blacklist_domain,
                'timeout_ms': 50,
                'requires_domain': True
            },
            'strategy_escalation': {
                'function': self._escalate_strategy,
                'timeout_ms': 150,
                'requires_domain': True
            },
            'auto_retry': {
                'function': self._auto_retry,
                'timeout_ms': 200,
                'requires_domain': False
            },
            'resource_scaling': {
                'function': self._scale_resources,
                'timeout_ms': 300,
                'requires_domain': True
            },
            'restart_service': {
                'function': self._restart_service,
                'timeout_ms': 500,
                'requires_domain': True
            },
            'credential_rotation': {
                'function': self._rotate_credentials,
                'timeout_ms': 400,
                'requires_domain': True
            },
            'data_restore': {
                'function': self._restore_data,
                'timeout_ms': 800,
                'requires_domain': True
            },
            'dependency_isolation': {
                'function': self._isolate_dependency,
                'timeout_ms': 250,
                'requires_domain': True
            },
            'human_alert': {
                'function': self._alert_human,
                'timeout_ms': 100,
                'requires_domain': True
            },
            'performance_optimization': {
                'function': self._optimize_performance,
                'timeout_ms': 350,
                'requires_domain': True
            },
            'monitoring_increase': {
                'function': self._increase_monitoring,
                'timeout_ms': 150,
                'requires_domain': True
            }
        }
    
    async def execute_response(self, incident_id: str, response_type: str, 
                              domain: str = None, context: Dict = None) -> Dict:
        """Execute response action with effectiveness scoring"""
        start_time = datetime.utcnow()
        
        if response_type not in self.response_registry:
            return {
                'success': False,
                'error': f'Unknown response type: {response_type}',
                'effectiveness': 0.0,
                'execution_time_ms': 0
            }
        
        response_config = self.response_registry[response_type]
        
        # Validate domain requirement
        if response_config['requires_domain'] and not domain:
            return {
                'success': False,
                'error': f'Response {response_type} requires domain parameter',
                'effectiveness': 0.0,
                'execution_time_ms': 0
            }
        
        # Check if domain is blacklisted
        if domain and self._is_domain_blacklisted(domain):
            if response_type != 'domain_blacklist':
                return {
                    'success': False,
                    'error': f'Domain {domain} is blacklisted',
                    'effectiveness': 0.0,
                    'execution_time_ms': 0
                }
        
        try:
            # Execute response
            result = await response_config['function'](incident_id, domain, context or {})
            
            # Calculate effectiveness
            effectiveness = self._calculate_effectiveness(
                response_type, domain, result, context
            )
            
            # Record execution
            execution_record = {
                'incident_id': incident_id,
                'response_type': response_type,
                'domain': domain,
                'success': result.get('success', False),
                'effectiveness': effectiveness,
                'timestamp': datetime.utcnow(),
                'execution_time_ms': (datetime.utcnow() - start_time).total_seconds() * 1000,
                'result': result
            }
            
            self.execution_history[response_type].append(execution_record)
            self.response_effectiveness[response_type].append(effectiveness)
            
            return {
                'success': True,
                'response_type': response_type,
                'domain': domain,
                'result': result,
                'effectiveness': effectiveness,
                'execution_time_ms': round(execution_record['execution_time_ms'], 2),
                'incident_id': incident_id,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'effectiveness': 0.0,
                'execution_time_ms': round((datetime.utcnow() - start_time).total_seconds() * 1000, 2)
            }
    
    async def _activate_circuit_breaker(self, incident_id: str, domain: str, context: Dict) -> Dict:
        """Activate circuit breaker for domain"""
        if domain in self.circuit_breakers:
            breaker = self.circuit_breakers[domain]
            if breaker['active_until'] > datetime.utcnow():
                return {
                    'success': False,
                    'message': f'Circuit breaker already active until {breaker["active_until"]}',
                    'already_active': True
                }
        
        # Determine timeout based on severity
        severity = context.get('severity', 'medium')
        timeouts = {'low': 60, 'medium': 300, 'high': 900, 'critical': 3600}
        timeout_seconds = timeouts.get(severity, 300)
        
        active_until = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        
        self.circuit_breakers[domain] = {
            'incident_id': incident_id,
            'activated_at': datetime.utcnow(),
            'active_until': active_until,
            'severity': severity,
            'failure_count': context.get('failure_count', 1)
        }
        
        # Store in Redis if available
        if self.redis:
            await self.redis.setex(
                f'circuit_breaker:{domain}',
                timeout_seconds,
                json.dumps(self.circuit_breakers[domain], default=str)
            )
        
        return {
            'success': True,
            'action': 'circuit_breaker_activated',
            'domain': domain,
            'active_until': active_until.isoformat(),
            'timeout_seconds': timeout_seconds,
            'incident_id': incident_id
        }
    
    async def _blacklist_domain(self, incident_id: str, domain: str, context: Dict) -> Dict:
        """Blacklist domain temporarily"""
        # Check if already blacklisted
        if domain in self.domain_blacklist:
            blacklist = self.domain_blacklist[domain]
            if blacklist['active_until'] > datetime.utcnow():
                return {
                    'success': False,
                    'message': f'Domain already blacklisted until {blacklist["active_until"]}',
                    'already_blacklisted': True
                }
        
        # Determine blacklist duration
        severity = context.get('severity', 'critical')
        durations = {'critical': 21600, 'high': 10800, 'medium': 3600}  # 6h, 3h, 1h
        duration_seconds = durations.get(severity, 21600)
        
        active_until = datetime.utcnow() + timedelta(seconds=duration_seconds)
        
        self.domain_blacklist[domain] = {
            'incident_id': incident_id,
            'blacklisted_at': datetime.utcnow(),
            'active_until': active_until,
            'severity': severity,
            'reason': context.get('reason', 'multiple_critical_incidents')
        }
        
        # Store in Redis
        if self.redis:
            await self.redis.setex(
                f'domain_blacklist:{domain}',
                duration_seconds,
                json.dumps(self.domain_blacklist[domain], default=str)
            )
        
        return {
            'success': True,
            'action': 'domain_blacklisted',
            'domain': domain,
            'active_until': active_until.isoformat(),
            'duration_hours': duration_seconds / 3600,
            'incident_id': incident_id,
            'reason': context.get('reason', 'multiple_critical_incidents')
        }
    
    async def _escalate_strategy(self, incident_id: str, domain: str, context: Dict) -> Dict:
        """Escalate strategy to more aggressive configuration"""
        current_strategy = context.get('current_strategy', {})
        severity = context.get('severity', 'medium')
        
        # Determine escalation level
        escalation_map = {
            'low': 'conservative',
            'medium': 'balanced',
            'high': 'aggressive',
            'critical': 'maximum'
        }
        escalation_level = escalation_map.get(severity, 'balanced')
        
        # Generate escalated strategy
        escalated_strategy = self._generate_escalated_strategy(
            current_strategy, escalation_level
        )
        
        return {
            'success': True,
            'action': 'strategy_escalated',
            'domain': domain,
            'escalation_level': escalation_level,
            'previous_strategy': current_strategy,
            'new_strategy': escalated_strategy,
            'changes': self._compare_strategies(current_strategy, escalated_strategy),
            'incident_id': incident_id
        }
    
    def _generate_escalated_strategy(self, current: Dict, level: str) -> Dict:
        """Generate escalated strategy configuration"""
        base_escalations = {
            'conservative': {
                'retry_count': 1,
                'timeout_ms': 3000,
                'backoff_factor': 1.0,
                'parallel_operations': 1
            },
            'balanced': {
                'retry_count': 3,
                'timeout_ms': 5000,
                'backoff_factor': 1.5,
                'parallel_operations': 4
            },
            'aggressive': {
                'retry_count': 5,
                'timeout_ms': 10000,
                'backoff_factor': 2.0,
                'parallel_operations': 8,
                'circuit_breaker': False
            },
            'maximum': {
                'retry_count': 10,
                'timeout_ms': 30000,
                'backoff_factor': 3.0,
                'parallel_operations': 16,
                'circuit_breaker': False,
                'bypass_checks': True
            }
        }
        
        escalated = current.copy()
        escalation = base_escalations.get(level, base_escalations['balanced'])
        
        for key, value in escalation.items():
            escalated[key] = value
        
        return escalated
    
    def _compare_strategies(self, old: Dict, new: Dict) -> List[str]:
        """Compare strategy changes"""
        changes = []
        for key in set(old.keys()) | set(new.keys()):
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changes.append(f"{key}: {old_val} -> {new_val}")
        return changes
    
    async def _auto_retry(self, incident_id: str, domain: str, context: Dict) -> Dict:
        """Execute automatic retry with backoff"""
        max_retries = context.get('max_retries', 3)
        base_delay = context.get('base_delay_ms', 1000)
        backoff_factor = context.get('backoff_factor', 1.5)
        
        attempts = []
        for attempt in range(max_retries):
            delay = base_delay * (backoff_factor ** attempt)
            await asyncio.sleep(delay / 1000)
            
            # Simulate retry attempt
            success = random.random() > 0.3  # 70% success rate
            
            attempts.append({
                'attempt': attempt + 1,
                'delay_ms': delay,
                'success': success
            })
            
            if success:
                break
        
        overall_success = any(attempt['success'] for attempt in attempts)
        
        return {
            'success': overall_success,
            'action': 'auto_retry_completed',
            'attempts': attempts,
            'total_attempts': len(attempts),
            'successful_attempt': next((i+1 for i, a in enumerate(attempts) if a['success']), None),
            'total_delay_ms': sum(a['delay_ms'] for a in attempts),
            'incident_id': incident_id
        }
    
    async def _scale_resources(self, incident_id: str, domain: str, context: Dict) -> Dict:
        """Scale resources for domain"""
        current_load = context.get('current_load', 0.5)
        target_load = context.get('target_load', 0.3)
        
        # Calculate scaling factor
        scaling_factor = current_load / target_load if target_load > 0 else 2.0
        
        # Apply scaling
        new_capacity = context.get('current_capacity', 1) * scaling_factor
        
        return {
            'success': True,
            'action': 'resources_scaled',
            'domain': domain,
            'current_load': current_load,
            'target_load': target_load,
            'scaling_factor': scaling_factor,
            'new_capacity': new_capacity,
            'incident_id': incident_id
        }
    
    async def _restart_service(self, incident_id: str, domain: str, context: Dict) -> Dict:
        """Restart service for domain"""
        service_name = context.get('service_name', domain)
        graceful = context.get('graceful', True)
        
        # Simulate restart
        restart_time = random.uniform(1.0, 5.0)
        await asyncio.sleep(restart_time)
        
        # 90% success rate
        success = random.random() > 0.1
        
        return {
            'success': success,
            'action': 'service_restarted',
            'domain': domain,
            'service_name': service_name,
            'graceful': graceful,
            'restart_time_seconds': restart_time,
            'incident_id': incident_id
        }
    
    async def _rotate_credentials(self, incident_id: str, domain: str, context: Dict) -> Dict:
        """Rotate credentials for domain"""
        credential_type = context.get('credential_type', 'api_key')
        new_credential = hashlib.sha256(f"{domain}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:32]
        
        return {
            'success': True,
            'action': 'credentials_rotated',
            'domain': domain,
            'credential_type': credential_type,
            'new_credential': new_credential[:8] + '...',  # Partial for security
            'rotation_time': datetime.utcnow().isoformat(),
            'incident_id': incident_id
        }
    
    async def _restore_data(self, incident_id: str, domain: str, context: Dict) -> Dict:
        """Restore data from backup"""
        backup_timestamp = context.get('backup_timestamp')
        if not backup_timestamp:
            # Find latest backup
            backup_timestamp = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        
        # Simulate restore
        restore_time = random.uniform(5.0, 30.0)
        await asyncio.sleep(min(restore_time, 1.0))  # Cap for demo
        
        data_size = context.get('data_size_mb', 100)
        restored_records = int(data_size * 1000 * random.uniform(0.9, 1.0))
        
        return {
            'success': True,
            'action': 'data_restored',
            'domain': domain,
            'backup_timestamp': backup_timestamp,
            'restore_time_seconds': restore_time,
            'data_size_mb': data_size,
            'restored_records': restored_records,
            'incident_id': incident_id
        }
    
    async def _isolate_dependency(self, incident_id: str, domain: str, context: Dict) -> Dict:
        """Isolate failing dependency"""
        dependency = context.get('dependency', 'unknown')
        isolation_duration = context.get('isolation_duration_seconds', 300)
        
        return {
            'success': True,
            'action': 'dependency_isolated',
            'domain': domain,
            'dependency': dependency,
            'isolation_duration_seconds': isolation_duration,
            'isolated_until': (datetime.utcnow() + timedelta(seconds=isolation_duration)).isoformat(),
            'incident_id': incident_id
        }
    
    async def _alert_human(self, incident_id: str, domain: str, context: Dict) -> Dict:
        """Alert human operator"""
        severity = context.get('severity', 'medium')
        message = context.get('message', f'Incident {incident_id} requires human attention')
        
        # Simulate alert delivery
        alert_channels = context.get('channels', ['slack', 'email'])
        
        return {
            'success': True,
            'action': 'human_alerted',
            'domain': domain,
            'severity': severity,
            'message': message,
            'channels': alert_channels,
            'alert_time': datetime.utcnow().isoformat(),
            'incident_id': incident_id
        }
    
    async def _optimize_performance(self, incident_id: str, domain: str, context: Dict) -> Dict:
        """Optimize performance settings"""
        optimizations = [
            'query_cache_enabled',
            'connection_pool_increased',
            'compression_enabled',
            'batch_size_optimized'
        ]
        
        applied = random.sample(optimizations, random.randint(1, len(optimizations)))
        
        return {
            'success': True,
            'action': 'performance_optimized',
            'domain': domain,
            'applied_optimizations': applied,
            'estimated_improvement': random.uniform(0.1, 0.5),
            'incident_id': incident_id
        }
    
    async def _increase_monitoring(self, incident_id: str, domain: str, context: Dict) -> Dict:
        """Increase monitoring frequency"""
        current_interval = context.get('current_interval_ms', 60000)
        new_interval = current_interval / 2
        
        metrics = context.get('metrics', ['response_time', 'error_rate', 'throughput'])
        
        return {
            'success': True,
            'action': 'monitoring_increased',
            'domain': domain,
            'previous_interval_ms': current_interval,
            'new_interval_ms': new_interval,
            'monitored_metrics': metrics,
            'incident_id': incident_id
        }
    
    def _calculate_effectiveness(self, response_type: str, domain: str, 
                                result: Dict, context: Dict) -> float:
        """Calculate response effectiveness score"""
        base_score = 0.5
        
        # Success factor
        if result.get('success', False):
            base_score += 0.3
        else:
            base_score -= 0.2
        
        # Domain history factor
        if domain and response_type in self.response_effectiveness:
            recent = list(self.response_effectiveness[response_type])[-10:]
            if recent:
                avg_historical = sum(recent)

import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict, deque
import hashlib
import json
import random
import asyncio
import aiohttp

class KnowledgeDistributor:
    def __init__(self, distribution_path: str = "/tmp/knowledge_distribution"):
        self.learning_packages = defaultdict(lambda: deque(maxlen=1000))
        self.distribution_history = defaultdict(lambda: deque(maxlen=1000))
        self.worker_fleet = {}
        self.adoption_rates = defaultdict(dict)
        self.distribution_path = distribution_path
        self._load_distribution_data()
        
        # Distribution strategies
        self.distribution_strategies = {
            'immediate': {'priority': 1, 'retry_attempts': 3, 'timeout_seconds': 10},
            'scheduled': {'priority': 2, 'retry_attempts': 2, 'timeout_seconds': 30},
            'batch': {'priority': 3, 'retry_attempts': 1, 'timeout_seconds': 60}
        }
        
        # Background distribution task
        self._start_distribution_task()
    
    def _load_distribution_data(self):
        """Load distribution data from storage"""
        try:
            import pickle
            filepath = f"{self.distribution_path}/distribution_data.pkl"
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
                self.learning_packages = defaultdict(
                    lambda: deque(maxlen=1000),
                    data.get('packages', {})
                )
                self.distribution_history = defaultdict(
                    lambda: deque(maxlen=1000),
                    data.get('history', {})
                )
                self.adoption_rates = data.get('adoption', defaultdict(dict))
        except:
            pass
    
    def _save_distribution_data(self):
        """Save distribution data to storage"""
        try:
            import pickle
            import os
            os.makedirs(self.distribution_path, exist_ok=True)
            filepath = f"{self.distribution_path}/distribution_data.pkl"
            with open(filepath, 'wb') as f:
                data = {
                    'packages': dict(self.learning_packages),
                    'history': dict(self.distribution_history),
                    'adoption': dict(self.adoption_rates),
                    'timestamp': datetime.utcnow()
                }
                pickle.dump(data, f)
        except:
            pass
    
    def _start_distribution_task(self):
        """Start background distribution task"""
        import threading
        
        def distribution_loop():
            while True:
                try:
                    self._process_distribution_queue()
                    self._cleanup_old_data()
                    self._save_distribution_data()
                except Exception as e:
                    print(f"Distribution error: {e}")
                threading.Event().wait(60)  # Run every minute
        
        thread = threading.Thread(target=distribution_loop, daemon=True)
        thread.start()
    
    def distribute_knowledge(self, learning_package: Dict, 
                           distribution_strategy: str = 'immediate') -> Dict:
        """Distribute learning package to worker fleet"""
        start_time = datetime.utcnow()
        
        # Validate learning package
        validation_result = self._validate_learning_package(learning_package)
        if not validation_result['valid']:
            return {
                'success': False,
                'error': f"Invalid learning package: {validation_result['errors']}",
                'distribution_report': {}
            }
        
        # Generate package ID
        package_id = self._generate_package_id(learning_package)
        
        # Store package
        package_entry = {
            'package_id': package_id,
            'learning_package': learning_package,
            'created_at': datetime.utcnow(),
            'distribution_strategy': distribution_strategy,
            'status': 'pending',
            'target_workers': learning_package.get('target_workers', 'all'),
            'priority': self.distribution_strategies.get(distribution_strategy, {}).get('priority', 2)
        }
        
        # Store in appropriate queue
        self.learning_packages[distribution_strategy].append(package_entry)
        
        # Process immediately if strategy is 'immediate'
        if distribution_strategy == 'immediate':
            distribution_result = self._distribute_to_workers(package_entry)
        else:
            distribution_result = {
                'status': 'queued',
                'distribution_strategy': distribution_strategy,
                'queued_at': datetime.utcnow().isoformat()
            }
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'success': True,
            'package_id': package_id,
            'distribution_report': distribution_result,
            'package_summary': self._summarize_learning_package(learning_package),
            'distribution_time_ms': round(elapsed, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _validate_learning_package(self, package: Dict) -> Dict:
        """Validate learning package structure"""
        errors = []
        
        required_fields = ['knowledge_type', 'content', 'source', 'confidence']
        
        for field in required_fields:
            if field not in package:
                errors.append(f"Missing required field: {field}")
        
        # Validate knowledge type
        valid_types = ['strategy_optimization', 'parameter_tuning', 'error_pattern', 
                      'performance_improvement', 'security_insight', 'configuration_update']
        
        if 'knowledge_type' in package and package['knowledge_type'] not in valid_types:
            errors.append(f"Invalid knowledge_type: {package['knowledge_type']}. Valid types: {valid_types}")
        
        # Validate confidence score
        if 'confidence' in package:
            confidence = package['confidence']
            if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                errors.append(f"Invalid confidence score: {confidence}. Must be between 0 and 1")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _generate_package_id(self, package: Dict) -> str:
        """Generate unique package ID"""
        package_str = json.dumps(package, sort_keys=True)
        timestamp = datetime.utcnow().isoformat()
        
        return hashlib.md5(f"{package_str}:{timestamp}".encode()).hexdigest()[:16]
    
    def _summarize_learning_package(self, package: Dict) -> Dict:
        """Create summary of learning package"""
        summary = {
            'knowledge_type': package.get('knowledge_type', 'unknown'),
            'source': package.get('source', 'unknown'),
            'confidence': package.get('confidence', 0.0),
            'created_at': package.get('created_at', datetime.utcnow().isoformat()),
            'impact_estimate': package.get('impact_estimate', 'unknown'),
            'applicable_domains': package.get('applicable_domains', ['all']),
            'content_type': type(package.get('content', {})).__name__,
            'content_size': len(str(package.get('content', {})))
        }
        
        # Add specific summary based on knowledge type
        if package['knowledge_type'] == 'strategy_optimization':
            content = package.get('content', {})
            summary.update({
                'strategy_type': content.get('strategy_type', 'unknown'),
                'parameters_optimized': list(content.get('optimized_parameters', {}).keys()),
                'expected_improvement': content.get('expected_improvement', 0.0)
            })
        elif package['knowledge_type'] == 'parameter_tuning':
            content = package.get('content', {})
            summary.update({
                'parameters_tuned': list(content.get('parameter_values', {}).keys()),
                'validation_score': content.get('validation_score', 0.0)
            })
        
        return summary
    
    def _process_distribution_queue(self):
        """Process distribution queue"""
        # Process by priority
        for strategy_name in ['immediate', 'scheduled', 'batch']:
            if strategy_name in self.learning_packages:
                packages = list(self.learning_packages[strategy_name])
                
                for package in packages:
                    if package['status'] == 'pending':
                        # Distribute to workers
                        distribution_result = self._distribute_to_workers(package)
                        
                        # Update package status
                        package['status'] = distribution_result.get('status', 'failed')
                        package['distribution_result'] = distribution_result
                        package['distributed_at'] = datetime.utcnow()
    
    def _distribute_to_workers(self, package: Dict) -> Dict:
        """Distribute package to worker fleet"""
        start_time = datetime.utcnow()
        
        package_id = package['package_id']
        learning_package = package['learning_package']
        strategy = package['distribution_strategy']
        target_workers = package['target_workers']
        
        # Get target workers
        if target_workers == 'all':
            workers = list(self.worker_fleet.keys())
        else:
            workers = target_workers if isinstance(target_workers, list) else [target_workers]
        
        if not workers:
            return {
                'status': 'failed',
                'reason': 'no_workers_available',
                'workers_reached': 0,
                'total_workers': 0
            }
        
        # Distribution results
        distribution_results = {
            'successful': [],
            'failed': [],
            'pending': []
        }
        
        # Distribute to each worker
        for worker_id in workers:
            if worker_id in self.worker_fleet:
                worker = self.worker_fleet[worker_id]
                
                # Check if worker can accept this package
                if self._should_distribute_to_worker(worker, learning_package):
                    distribution_result = self._send_to_worker(
                        worker, package_id, learning_package, strategy
                    )
                    
                    if distribution_result['success']:
                        distribution_results['successful'].append(worker_id)
                    else:
                        distribution_results['failed'].append({
                            'worker_id': worker_id,
                            'error': distribution_result.get('error', 'unknown')
                        })
                else:
                    distribution_results['pending'].append(worker_id)
        
        # Calculate adoption metrics
        total_workers = len(workers)
        successful_count = len(distribution_results['successful'])
        
        if total_workers > 0:
            adoption_rate = successful_count / total_workers
        else:
            adoption_rate = 0
        
        # Store adoption rate
        self.adoption_rates[package_id] = {
            'adoption_rate': adoption_rate,
            'successful_workers': distribution_results['successful'],
            'total_workers': total_workers,
            'calculated_at': datetime.utcnow()
        }
        
        # Store distribution history
        history_entry = {
            'package_id': package_id,
            'distribution_strategy': strategy,
            'distribution_time': datetime.utcnow(),
            'results': distribution_results,
            'adoption_rate': adoption_rate,
            'elapsed_ms': (datetime.utcnow() - start_time).total_seconds() * 1000
        }
        
        self.distribution_history[package_id].append(history_entry)
        
        # Determine overall status
        if successful_count > 0:
            status = 'partially_distributed' if successful_count < total_workers else 'fully_distributed'
        else:
            status = 'failed'
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'status': status,
            'distribution_results': distribution_results,
            'adoption_rate': round(adoption_rate, 4),
            'successful_workers': successful_count,
            'total_workers': total_workers,
            'distribution_time_ms': round(elapsed, 2),
            'package_id': package_id
        }
    
    def _should_distribute_to_worker(self, worker: Dict, learning_package: Dict) -> bool:
        """Check if package should be distributed to worker"""
        # Check worker status
        if worker.get('status') != 'active':
            return False
        
        # Check worker capabilities
        worker_capabilities = worker.get('capabilities', [])
        package_type = learning_package.get('knowledge_type')
        
        if package_type not in worker_capabilities:
            return False
        
        # Check worker load
        current_load = worker.get('current_load', 0)
        max_load = worker.get('max_load', 1.0)
        
        if current_load >= max_load:
            return False
        
        # Check if worker already has this knowledge
        worker_knowledge = worker.get('knowledge_base', [])
        package_content_hash = hashlib.md5(
            json.dumps(learning_package.get('content', {}), sort_keys=True).encode()
        ).hexdigest()[:8]
        
        if package_content_hash in worker_knowledge:
            return False
        
        return True
    
    def _send_to_worker(self, worker: Dict, package_id: str, 
                       learning_package: Dict, strategy: str) -> Dict:
        """Send package to worker"""
        # This would be async in production
        # For now, simulate distribution
        
        worker_id = worker.get('worker_id', 'unknown')
        worker_endpoint = worker.get('endpoint', '')
        
        # Simulate network delay
        network_delay = random.uniform(0.01, 0.5)
        
        # Simulate success/failure
        success_rate = 0.95  # 95% success rate
        
        if random.random() < success_rate:
            # Update worker knowledge
            if 'knowledge_base' not in worker:
                worker['knowledge_base'] = []
            
            package_content_hash = hashlib.md5(
                json.dumps(learning_package.get('content', {}), sort_keys=True).encode()
            ).hexdigest()[:8]
            
            worker['knowledge_base'].append(package_content_hash)
            
            # Update worker load
            worker['current_load'] = min(worker.get('current_load', 0) + 0.1, 1.0)
            
            return {
                'success': True,
                'worker_id': worker_id,
                'package_id': package_id,
                'network_delay_ms': round(network_delay * 1000, 2),
                'knowledge_applied': True
            }
        else:
            # Simulate failure
            failure_reasons = [
                'network_timeout', 'worker_busy', 'validation_failed', 'storage_full'
            ]
            
            return {
                'success': False,
                'worker_id': worker_id,
                'package_id': package_id,
                'error': random.choice(failure_reasons),
                'network_delay_ms': round(network_delay * 1000, 2)
            }
    
    def register_worker(self, worker_info: Dict) -> Dict:
        """Register a worker in the fleet"""
        worker_id = worker_info.get('worker_id')
        
        if not worker_id:
            worker_id = hashlib.md5(
                f"{worker_info.get('hostname', '')}:{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()[:16]
            worker_info['worker_id'] = worker_id
        
        # Set default values
        defaults = {
            'status': 'active',
            'capabilities': ['strategy_optimization', 'parameter_tuning'],
            'current_load': 0.0,
            'max_load': 1.0,
            'knowledge_base': [],
            'registered_at': datetime.utcnow(),
            'last_heartbeat': datetime.utcnow()
        }
        
        worker_info.update(defaults)
        
        # Register worker
        self.worker_fleet[worker_id] = worker_info
        
        return {
            'success': True,
            'worker_id': worker_id,
            'registration_time': datetime.utcnow().isoformat(),
            'fleet_size': len(self.worker_fleet)
        }
    
    def update_worker_status(self, worker_id: str, status_update: Dict) -> Dict:
        """Update worker status"""
        if worker_id not in self.worker_fleet:
            return {'success': False, 'error': 'Worker not found'}
        
        worker = self.worker_fleet[worker_id]
        
        # Update fields
        for key, value in status_update.items():
            if key in ['status', 'current_load', 'capabilities', 'knowledge_base']:
                worker[key] = value
        
        worker['last_heartbeat'] = datetime.utcnow()
        
        return {
            'success': True,
            'worker_id': worker_id,
            'updated_fields': list(status_update.keys()),
            'current_status': worker['status']
        }
    
    def get_worker_info(self, worker_id: str) -> Dict:
        """Get information about a worker"""
        if worker_id in self.worker_fleet:
            worker = self.worker_fleet[worker_id].copy()
            
            # Calculate worker health
            last_heartbeat = worker.get('last_heartbeat')
            if isinstance(last_heartbeat, datetime):
                seconds_since = (datetime.utcnow() - last_heartbeat).total_seconds()
                worker['health_status'] = 'healthy' if seconds_since < 60 else 'unhealthy'
                worker['seconds_since_heartbeat'] = round(seconds_since, 2)
            
            return {
                'success': True,
                'worker_info': worker,
                'knowledge_count': len(worker.get('knowledge_base', [])),
                'current_load_percentage': round(worker.get('current_load', 0) * 100, 1)
            }
        else:
            return {'success': False, 'error': 'Worker not found'}
    
    def get_distribution_report(self, package_id: str = None, 
                              time_window: str = '24h') -> Dict:
        """Get distribution report"""
        if package_id:
            # Get specific package report
            if package_id in self.distribution_history:
                history = list(self.distribution_history[package_id])
                
                if history:
                    latest = history[-1]
                    
                    return {
                        'package_id': package_id,
                        'distribution_status': latest.get('status', 'unknown'),
                        'adoption_rate': latest.get('adoption_rate', 0.0),
                        'distribution_time': latest['distribution_time'].isoformat() if isinstance(latest['distribution_time'], datetime) else latest['distribution_time'],
                        'distribution_strategy': latest.get('distribution_strategy', 'unknown'),
                        'results_summary': {
                            'successful_workers': len(latest.get('results', {}).get('successful', [])),
                            'failed_workers': len(latest.get('results', {}).get('failed', [])),
                            'pending_workers': len(latest.get('results', {}).get('pending', []))
                        },
                        'elapsed_ms': latest.get('elapsed_ms', 0)
                    }
            
            return {'error': 'Package not found'}
        
        else:
            # Get aggregate report for time window
            hours = self._parse_time_window(time_window)
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            total_distributions = 0
            successful_distributions = 0
            total_adoption = 0.0
            adoption_samples = 0
            
            for package_histories in self.distribution_history.values():
                for history in package_histories:
                    if history['distribution_time'] > cutoff:
                        total_distributions += 1
                        
                        if history.get('adoption_rate', 0) > 0.5:
                            successful_distributions += 1
                        
                        total_adoption += history.get('adoption_rate', 0)
                        adoption_samples += 1
            
            avg_adoption = total_adoption / adoption_samples if adoption_samples > 0 else 0
            
            return {
                'time_window': time_window,
                'window_hours': hours,
                'total_distributions': total_distributions,
                'successful_distributions': successful_distributions,
                'success_rate': round(successful_distributions / max(total_distributions, 1), 4),
                'average_adoption_rate': round(avg_adoption, 4),
                'active_learning_packages': sum(len(q) for q in self.learning_packages.values()),
                'worker_fleet_size': len(self.worker_fleet),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def _parse_time_window(self, window: str) -> int:
        """Parse time window string to hours"""
        if window.endswith('h'):
            return int(window[:-1])
        elif window.endswith('d'):
            return int(window[:-1]) * 24
        elif window == '1w':
            return 168
        else:
            return 24
    
    def get_adoption_rates(self, package_type: str = None, 
                          min_confidence: float = 0.0) -> Dict:
        """Get adoption rates for learning packages"""
        adoption_data = []
        
        for package_id, adoption_info in self.adoption_rates.items():
            # Find corresponding package
            package = None
            for strategy_packages in self.learning_packages.values():
                for pkg in strategy_packages:
                    if pkg['package_id'] == package_id:
                        package = pkg['learning_package']
                        break
                if package:
                    break
            
            if package:
                # Filter by type
                if package_type and package.get('knowledge_type') != package_type:
                    continue
                
                # Filter by confidence
                if package.get('confidence', 0) < min_confidence:
                    continue
                
                adoption_data.append({
                    'package_id': package_id,
                    'knowledge_type': package.get('knowledge_type'),
                    'confidence': package.get('confidence', 0.0),
                    'adoption_rate': adoption_info.get('adoption_rate', 0.0),
                    'successful_workers': len(adoption_info.get('successful_workers', [])),
                    'total_workers': adoption_info.get('total_workers', 0),
                    'calculated_at': adoption_info['calculated_at'].isoformat() if isinstance(adoption_info['calculated_at'], datetime) else adoption_info['calculated_at']
                })
        
        # Calculate statistics
        if adoption_data:
            adoption_rates = [d['adoption_rate'] for d in adoption_data]
            confidences = [d['confidence'] for d in adoption_data]
            
            stats = {
                'average_adoption_rate': round(np.mean(adoption_rates), 4),
                'median_adoption_rate': round(np.median(adoption_rates), 4),
                'std_adoption_rate': round(np.std(adoption_rates), 4),
                'min_adoption_rate': round(min(adoption_rates), 4),
                'max_adoption_rate': round(max(adoption_rates), 4),
                'average_confidence': round(np.mean(confidences), 4),
                'correlation': round(np.corrcoef(adoption_rates, confidences)[0,1], 4) if len(adoption_rates) > 1 else 0.0
            }
        else:
            stats = {}
        
        # Group by knowledge type
        by_type = defaultdict(list)
        for data in adoption_data:
            by_type[data['knowledge_type']].append(data['adoption_rate'])
        
        type_stats = {}
        for ktype, rates in by_type.items():
            if rates:
                type_stats[ktype] = {
                    'average': round(np.mean(rates), 4),
                    'count': len(rates),
                    'min': round(min(rates), 4),
                    'max': round(max(rates), 4)
                }
        
        return {
            'adoption_data': adoption_data[:50],  # Limit output
            'statistics': stats,
            'by_knowledge_type': type_stats,
            'total_packages_tracked': len(adoption_data),
            'filter_applied': {
                'package_type': package_type,
                'min_confidence': min_confidence
            },
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _cleanup_old_data(self, days_old: int = 30):
        """Cleanup old data"""
        cutoff = datetime.utcnow() - timedelta(days=days_old)
        
        # Clean old learning packages
        for strategy in list(self.learning_packages.keys()):
            packages = self.learning_packages[strategy]
            self.learning_packages[strategy] = deque(
                [p for p in packages if p['created_at'] > cutoff],
                maxlen=1000
            )
        
        # Clean old distribution history
        for package_id in list(self.distribution_history.keys()):
            history = self.distribution_history[package_id]
            self.distribution_history[package_id] = deque(
                [h for h in history if h['distribution_time'] > cutoff],
                maxlen=1000
            )
            
            # Remove empty histories
            if not self.distribution_history[package_id]:
                del self.distribution_history[package_id]
        
        # Clean old adoption rates
        package_ids_to_remove = []
        for package_id, adoption_info in self.adoption_rates.items():
            calculated_at = adoption_info.get('calculated_at')
            if isinstance(calculated_at, datetime) and calculated_at < cutoff:
                package_ids_to_remove.append(package_id)
        
        for package_id in package_ids_to_remove:
            del self.adoption_rates[package_id]
    
    def get_system_stats(self) -> Dict:
        """Get system statistics"""
        # Worker fleet stats
        active_workers = sum(1 for w in self.worker_fleet.values() 
                           if w.get('status') == 'active')
        
        worker_loads = [w.get('current_load', 0) for w in self.worker_fleet.values()]
        avg_worker_load = np.mean(worker_loads) if worker_loads else 0
        
        # Package stats
        pending_packages = sum(
            sum(1 for p in packages if p['status'] == 'pending')
            for packages in self.learning_packages.values()
        )
        
        total_packages = sum(len(packages) for packages in self.learning_packages.values())
        
        # Distribution stats
        total_distributions = sum(len(history) for history in self.distribution_history.values())
        
        # Adoption stats
        adoption_rates = list(self.adoption_rates.values())
        if adoption_rates:
            avg_adoption = np.mean([ar.get('adoption_rate', 0) for ar in adoption_rates])
            successful_adoptions = sum(1 for ar in adoption_rates if ar.get('adoption_rate', 0) > 0.5)
        else:
            avg_adoption = 0
            successful_adoptions = 0
        
        return {
            'worker_fleet': {
                'total_workers': len(self.worker_fleet),
                'active_workers': active_workers,
                'average_load': round(avg_worker_load, 4),
                'health_status': 'good' if active_workers > 0 else 'degraded'
            },
            'learning_packages': {
                'total_packages': total_packages,
                'pending_distribution': pending_packages,
                'by_strategy': {
                    strategy: len(packages)
                    for strategy, packages in self.learning_packages.items()
                }
            },
            'distribution': {
                'total_distributions': total_distributions,
                'unique_packages_distributed': len(self.distribution_history),
                'distribution_strategies': list(self.distribution_strategies.keys())
            },
            'adoption': {
                'packages_tracked': len(self.adoption_rates),
                'average_adoption_rate': round(avg_adoption, 4),
                'successful_adoptions': successful_adoptions,
                'success_rate': round(successful_adoptions / max(len(self.adoption_rates), 1), 4)
            },
            'system_health': {
                'storage_usage': 'normal',
                'processing_backlog': pending_packages,
                'worker_coverage': round(active_workers / max(len(self.worker_fleet), 1), 4),
                'recommendations': self._generate_system_recommendations(
                    active_workers, pending_packages, avg_adoption
                )
            },
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _generate_system_recommendations(self, active_workers: int,
                                        pending_packages: int,
                                        avg_adoption: float) -> List[str]:
        """Generate system recommendations"""
        recommendations = []
        
        if active_workers == 0:
            recommendations.append("No active workers. Register workers immediately.")
        
        if pending_packages > 100:
            recommendations.append(f"High backlog: {pending_packages} packages pending. Consider increasing distribution frequency.")
        
        if avg_adoption < 0.3:
            recommendations.append(f"Low adoption rate: {avg_adoption:.1%}. Review package relevance and worker targeting.")
        
        if len(self.worker_fleet) < 3:
            recommendations.append("Small worker fleet. Consider scaling for better distribution coverage.")
        
        return recommendations[:5]

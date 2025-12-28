from datetime import datetime, timedelta
from collections import defaultdict, deque
import numpy as np
import asyncio
from typing import Dict, List, Any, Optional
import hashlib

class RecoveryMonitor:
    def __init__(self):
        self.domain_recoveries = defaultdict(lambda: deque(maxlen=100))
        self.recovery_metrics = defaultdict(dict)
        self.learned_mitigations = defaultdict(lambda: deque(maxlen=50))
        self.baseline_metrics = {}
        self.active_monitors = {}
        self.recovery_patterns = {}
        
    async def monitor_recovery(self, domain: str, hours: int = 24) -> Dict:
        """Monitor post-incident recovery and extract learnings"""
        monitor_id = hashlib.md5(f"{domain}:{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16]
        
        # Start monitoring
        self.active_monitors[monitor_id] = {
            'domain': domain,
            'start_time': datetime.utcnow(),
            'duration_hours': hours,
            'status': 'active',
            'metrics_collected': []
        }
        
        # Collect initial baseline
        baseline = await self._collect_baseline_metrics(domain)
        
        # Monitor for specified duration
        recovery_data = await self._perform_monitoring(monitor_id, domain, hours, baseline)
        
        # Analyze recovery
        analysis = self._analyze_recovery(recovery_data, baseline)
        
        # Extract learnings
        learnings = self._extract_learnings(domain, recovery_data, analysis)
        
        # Store results
        recovery_report = {
            'monitor_id': monitor_id,
            'domain': domain,
            'monitoring_duration_hours': hours,
            'start_time': self.active_monitors[monitor_id]['start_time'].isoformat(),
            'end_time': datetime.utcnow().isoformat(),
            'baseline_metrics': baseline,
            'recovery_metrics': recovery_data,
            'analysis': analysis,
            'learned_mitigations': learnings,
            'recovery_successful': analysis['recovery_success_rate'] > 0.8,
            'recommendations': self._generate_recommendations(analysis, learnings)
        }
        
        # Store in history
        self.domain_recoveries[domain].append(recovery_report)
        
        # Clean up active monitor
        del self.active_monitors[monitor_id]
        
        return recovery_report
    
    async def _collect_baseline_metrics(self, domain: str) -> Dict:
        """Collect baseline metrics for domain"""
        # In production, this would query metrics databases
        # For now, simulate baseline collection
        
        return {
            'success_rate': 0.95,  # 95% success rate baseline
            'avg_response_time_ms': 150,
            'p95_response_time_ms': 300,
            'error_rate': 0.05,
            'throughput_rps': 100,
            'resource_utilization': 0.3,
            'timestamp': datetime.utcnow().isoformat(),
            'sample_duration_minutes': 5
        }
    
    async def _perform_monitoring(self, monitor_id: str, domain: str, 
                                 hours: int, baseline: Dict) -> List[Dict]:
        """Perform actual monitoring"""
        recovery_data = []
        monitoring_interval = 300  # 5 minutes in seconds
        total_intervals = (hours * 3600) // monitoring_interval
        
        for interval in range(total_intervals):
            # Check if monitoring was cancelled
            if monitor_id not in self.active_monitors:
                break
            
            # Collect metrics
            metrics = await self._collect_interval_metrics(domain, interval, baseline)
            recovery_data.append(metrics)
            
            # Update active monitor
            self.active_monitors[monitor_id]['metrics_collected'].append(metrics)
            
            # Wait for next interval
            await asyncio.sleep(min(monitoring_interval, 1))  # Cap for demo
        
        return recovery_data
    
    async def _collect_interval_metrics(self, domain: str, interval: int, 
                                       baseline: Dict) -> Dict:
        """Collect metrics for a single interval"""
        # Simulate metric collection
        now = datetime.utcnow()
        
        # Simulate recovery progression
        recovery_factor = min(interval / 12, 1.0)  # Full recovery after 12 intervals (1 hour)
        
        # Calculate metrics based on recovery
        success_rate = baseline['success_rate'] * 0.3 + baseline['success_rate'] * 0.7 * recovery_factor
        avg_response_time = baseline['avg_response_time_ms'] * (1.5 - 0.5 * recovery_factor)
        error_rate = baseline['error_rate'] * (3.0 - 2.0 * recovery_factor)
        
        # Add some noise
        noise = np.random.normal(0, 0.05)
        success_rate = max(0.0, min(1.0, success_rate + noise))
        
        return {
            'timestamp': now.isoformat(),
            'interval': interval,
            'success_rate': success_rate,
            'avg_response_time_ms': avg_response_time,
            'error_rate': error_rate,
            'throughput_rps': baseline['throughput_rps'] * recovery_factor,
            'resource_utilization': baseline['resource_utilization'] * (1.0 + 0.5 * (1 - recovery_factor)),
            'recovery_factor': recovery_factor,
            'incidents_in_interval': 0 if recovery_factor > 0.5 else np.random.poisson(0.1)
        }
    
    def _analyze_recovery(self, recovery_data: List[Dict], baseline: Dict) -> Dict:
        """Analyze recovery data"""
        if not recovery_data:
            return {'status': 'no_data', 'recovery_success_rate': 0.0}
        
        # Calculate recovery metrics
        success_rates = [m['success_rate'] for m in recovery_data]
        response_times = [m['avg_response_time_ms'] for m in recovery_data]
        error_rates = [m['error_rate'] for m in recovery_data]
        
        # Calculate recovery success
        final_success_rate = success_rates[-1]
        baseline_success = baseline['success_rate']
        recovery_success_rate = final_success_rate / baseline_success if baseline_success > 0 else 0.0
        
        # Calculate recovery speed
        recovery_threshold = baseline_success * 0.9  # 90% of baseline
        recovery_time = None
        for i, metrics in enumerate(recovery_data):
            if metrics['success_rate'] >= recovery_threshold:
                recovery_time = i * 5  # 5 minute intervals
                break
        
        # Calculate stability
        success_rate_std = np.std(success_rates)
        is_stable = success_rate_std < 0.05
        
        # Detect regressions
        regressions = []
        for i in range(1, len(recovery_data)):
            if recovery_data[i]['success_rate'] < recovery_data[i-1]['success_rate'] * 0.8:
                regressions.append({
                    'interval': i,
                    'drop_percentage': (1 - recovery_data[i]['success_rate'] / recovery_data[i-1]['success_rate']) * 100
                })
        
        return {
            'recovery_success_rate': min(recovery_success_rate, 1.0),
            'final_success_rate': final_success_rate,
            'baseline_success_rate': baseline_success,
            'recovery_time_minutes': recovery_time,
            'is_stable': is_stable,
            'stability_score': 1.0 - min(success_rate_std / 0.1, 1.0),
            'regression_count': len(regressions),
            'regressions': regressions[:5],
            'avg_response_time_ms': np.mean(response_times),
            'avg_error_rate': np.mean(error_rates),
            'recovery_trend': self._calculate_trend(success_rates),
            'analysis_timestamp': datetime.utcnow().isoformat()
        }
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend of values"""
        if len(values) < 2:
            return 'insufficient_data'
        
        # Simple linear trend
        x = list(range(len(values)))
        slope, intercept = np.polyfit(x, values, 1)
        
        if slope > 0.01:
            return 'improving'
        elif slope < -0.01:
            return 'deteriorating'
        else:
            return 'stable'
    
    def _extract_learnings(self, domain: str, recovery_data: List[Dict], 
                          analysis: Dict) -> List[Dict]:
        """Extract learnings from recovery"""
        learnings = []
        
        # Learning from recovery speed
        if analysis['recovery_time_minutes']:
            if analysis['recovery_time_minutes'] < 30:
                learnings.append({
                    'type': 'recovery_speed',
                    'insight': f'Fast recovery ({analysis["recovery_time_minutes"]} minutes)',
                    'recommendation': 'Maintain current recovery procedures',
                    'confidence': 0.8
                })
            else:
                learnings.append({
                    'type': 'recovery_speed',
                    'insight': f'Slow recovery ({analysis["recovery_time_minutes"]} minutes)',
                    'recommendation': 'Optimize recovery procedures and check dependencies',
                    'confidence': 0.9
                })
        
        # Learning from stability
        if analysis['is_stable']:
            learnings.append({
                'type': 'recovery_stability',
                'insight': 'Stable recovery with minimal fluctuations',
                'recommendation': 'Current stability measures are effective',
                'confidence': 0.7
            })
        else:
            learnings.append({
                'type': 'recovery_stability',
                'insight': 'Unstable recovery with significant fluctuations',
                'recommendation': 'Implement additional stabilization measures',
                'confidence': 0.85
            })
        
        # Learning from regressions
        if analysis['regression_count'] > 0:
            learnings.append({
                'type': 'recovery_regressions',
                'insight': f'Detected {analysis["regression_count"]} regression(s) during recovery',
                'recommendation': 'Investigate root causes of regressions',
                'confidence': 0.95,
                'regression_details': analysis['regressions']
            })
        
        # Learning from final state
        if analysis['recovery_success_rate'] >= 0.95:
            learnings.append({
                'type': 'recovery_effectiveness',
                'insight': 'Full recovery achieved',
                'recommendation': 'No changes needed to recovery procedures',
                'confidence': 0.9
            })
        elif analysis['recovery_success_rate'] >= 0.8:
            learnings.append({
                'type': 'recovery_effectiveness',
                'insight': 'Partial recovery achieved',
                'recommendation': 'Review and improve recovery procedures',
                'confidence': 0.8
            })
        else:
            learnings.append({
                'type': 'recovery_effectiveness',
                'insight': 'Incomplete recovery - may require manual intervention',
                'recommendation': 'Revise recovery procedures and add fallbacks',
                'confidence': 0.95
            })
        
        # Store learnings
        for learning in learnings:
            self.learned_mitigations[domain].append({
                **learning,
                'timestamp': datetime.utcnow(),
                'recovery_analysis': {k: v for k, v in analysis.items() if k != 'regressions'}
            })
        
        return learnings
    
    def _generate_recommendations(self, analysis: Dict, learnings: List[Dict]) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if analysis['recovery_success_rate'] < 0.8:
            recommendations.append("Implement additional recovery automation")
        
        if analysis['regression_count'] > 2:
            recommendations.append("Add regression detection and automatic rollback")
        
        if not analysis['is_stable']:
            recommendations.append("Improve stability through circuit breakers and bulkheads")
        
        if analysis['recovery_time_minutes'] and analysis['recovery_time_minutes'] > 60:
            recommendations.append("Optimize recovery procedures to reduce MTTR")
        
        # Add specific recommendations from learnings
        for learning in learnings:
            if learning['confidence'] > 0.8:
                recommendations.append(learning['recommendation'])
        
        return list(set(recommendations))[:10]  # Deduplicate and limit
    
    def get_domain_recovery_history(self, domain: str, limit: int = 10) -> List[Dict]:
        """Get recovery history for domain"""
        if domain not in self.domain_recoveries:
            return []
        
        return list(self.domain_recoveries[domain])[-limit:]
    
    def get_learned_mitigations(self, domain: str) -> List[Dict]:
        """Get learned mitigations for domain"""
        if domain not in self.learned_mitigations:
            return []
        
        return list(self.learned_mitigations[domain])
    
    def cancel_monitoring(self, monitor_id: str) -> bool:
        """Cancel active monitoring"""
        if monitor_id in self.active_monitors:
            self.active_monitors[monitor_id]['status'] = 'cancelled'
            self.active_monitors[monitor_id]['cancelled_at'] = datetime.utcnow()
            return True
        return False
    
    def get_active_monitors(self) -> List[Dict]:
        """Get list of active monitors"""
        return [
            {
                'monitor_id': mid,
                'domain': info['domain'],
                'start_time': info['start_time'].isoformat(),
                'duration_hours': info['duration_hours'],
                'status': info['status'],
                'metrics_collected': len(info['metrics_collected']),
                'elapsed_minutes': (datetime.utcnow() - info['start_time']).total_seconds() / 60
            }
            for mid, info in self.active_monitors.items()
        ]
    
    def analyze_recovery_patterns(self, domain: str = None) -> Dict:
        """Analyze recovery patterns across domains"""
        if domain:
            domains = [domain]
        else:
            domains = list(self.domain_recoveries.keys())
        
        patterns = {}
        for dom in domains:
            if dom in self.domain_recoveries and self.domain_recoveries[dom]:
                recoveries = list(self.domain_recoveries[dom])
                
                # Calculate average recovery metrics
                success_rates = [r['analysis']['recovery_success_rate'] for r in recoveries]
                recovery_times = [r['analysis'].get('recovery_time_minutes', 0) for r in recoveries]
                
                if success_rates:
                    patterns[dom] = {
                        'recovery_count': len(recoveries),
                        'avg_success_rate': np.mean(success_rates),
                        'median_success_rate': np.median(success_rates),
                        'avg_recovery_time_minutes': np.mean([t for t in recovery_times if t]),
                        'success_rate_std': np.std(success_rates),
                        'most_recent_recovery': recoveries[-1]['analysis']['recovery_success_rate'],
                        'trend': self._calculate_trend([r['analysis']['recovery_success_rate'] for r in recoveries[-5:]])
                    }
        
        return patterns
    
    def generate_recovery_report(self, domain: str, days: int = 7) -> Dict:
        """Generate comprehensive recovery report"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Filter recoveries in time range
        recoveries = []
        if domain in self.domain_recoveries:
            for recovery in self.domain_recoveries[domain]:
                recovery_date = datetime.fromisoformat(recovery['start_time'].replace('Z', '+00:00'))
                if start_date <= recovery_date <= end_date:
                    recoveries.append(recovery)
        
        if not recoveries:
            return {'domain': domain, 'period_days': days, 'recovery_count': 0}
        
        # Calculate statistics
        success_rates = [r['analysis']['recovery_success_rate'] for r in recoveries]
        recovery_times = [r['analysis'].get('recovery_time_minutes', 0) for r in recoveries]
        successful_recoveries = [r for r in recoveries if r['analysis']['recovery_success_rate'] > 0.8]
        
        # Extract common learnings
        all_learnings = []
        for recovery in recoveries:
            all_learnings.extend(recovery['learned_mitigations'])
        
        # Group learnings by type
        learning_types = defaultdict(list)
        for learning in all_learnings:
            learning_types[learning['type']].append(learning)
        
        common_learnings = []
        for ltype, learnings in learning_types.items():
            if len(learnings) >= 2:  # At least 2 occurrences
                common_learnings.append({
                    'type': ltype,
                    'count': len(learnings),
                    'common_recommendation': max(
                        set(l['recommendation'] for l in learnings),
                        key=lambda x: sum(1 for l in learnings if l['recommendation'] == x)
                    )
                })
        
        return {
            'domain': domain,
            'period_days': days,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'recovery_count': len(recoveries),
            'successful_recoveries': len(successful_recoveries),
            'success_rate_avg': np.mean(success_rates),
            'success_rate_median': np.median(success_rates),
            'recovery_time_avg_minutes': np.mean([t for t in recovery_times if t]),
            'recovery_time_median_minutes': np.median([t for t in recovery_times if t]),
            'common_learnings': common_learnings,
            'recent_learnings': all_learnings[-5:] if all_learnings else [],
            'recovery_trend': self._calculate_trend([r['analysis']['recovery_success_rate'] for r in recoveries[-3:]]),
            'recommended_actions': list(set(
                action for recovery in recoveries 
                for action in recovery.get('recommendations', [])
            ))[:10],
            'generated_at': datetime.utcnow().isoformat()
        }

from datetime import datetime, timedelta
from collections import defaultdict, deque
import numpy as np
from typing import Dict, List, Any, Tuple
import hashlib

class ReputationScoring:
    def __init__(self):
        self.reputation_scores = defaultdict(lambda: {
            'current_score': 0.5,
            'score_history': deque(maxlen=1000),
            'component_scores': {},
            'last_updated': datetime.min
        })
        self.domain_metrics = defaultdict(lambda: deque(maxlen=10000))
        self.component_weights = self._initialize_weights()
        self.decay_factor = 0.99  # Daily decay
    
    def _initialize_weights(self) -> Dict:
        """Initialize reputation component weights"""
        return {
            'success_rate': 0.35,
            'response_time': 0.20,
            'error_distribution': 0.15,
            'availability': 0.10,
            'consistency': 0.08,
            'fingerprint_stability': 0.07,
            'incident_history': 0.05
        }
    
    def calculate_reputation(self, domain: str, window: str = '24h') -> Dict:
        """Calculate reputation score for domain"""
        start_time = datetime.utcnow()
        
        # Determine time window
        window_hours = self._parse_window(window)
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        
        # Get metrics for window
        metrics = [m for m in self.domain_metrics[domain] if m['timestamp'] > cutoff]
        
        if not metrics:
            # Return cached score if available
            cached = self.reputation_scores[domain]
            if cached['last_updated'] > datetime.utcnow() - timedelta(hours=1):
                return {
                    'domain': domain,
                    'reputation_score': cached['current_score'],
                    'window': window,
                    'components': cached['component_scores'],
                    'metric_count': 0,
                    'source': 'cached'
                }
            else:
                return {
                    'domain': domain,
                    'reputation_score': 0.5,
                    'window': window,
                    'components': {},
                    'metric_count': 0,
                    'source': 'default'
                }
        
        # Calculate component scores
        component_scores = self._calculate_component_scores(metrics, window_hours)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(component_scores)
        
        # Apply decay for older data
        if window_hours > 24:
            age_factor = 24 / window_hours
            overall_score = 0.5 + (overall_score - 0.5) * age_factor
        
        # Store result
        self.reputation_scores[domain] = {
            'current_score': overall_score,
            'score_history': self.reputation_scores[domain]['score_history'],
            'component_scores': component_scores,
            'last_updated': datetime.utcnow()
        }
        self.reputation_scores[domain]['score_history'].append({
            'score': overall_score,
            'timestamp': datetime.utcnow(),
            'window': window
        })
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'domain': domain,
            'reputation_score': round(overall_score, 4),
            'window': window,
            'window_hours': window_hours,
            'components': component_scores,
            'metric_count': len(metrics),
            'calculation_time_ms': round(elapsed, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _parse_window(self, window: str) -> int:
        """Parse time window string"""
        if window.endswith('h'):
            return int(window[:-1])
        elif window.endswith('d'):
            return int(window[:-1]) * 24
        else:
            return 24  # Default 24 hours
    
    def _calculate_component_scores(self, metrics: List[Dict], window_hours: int) -> Dict:
        """Calculate scores for each component"""
        scores = {}
        
        # Success rate
        success_count = sum(1 for m in metrics if m.get('success', False))
        total_count = len(metrics)
        if total_count > 0:
            success_rate = success_count / total_count
            scores['success_rate'] = {
                'score': success_rate,
                'weight': self.component_weights['success_rate'],
                'raw_value': success_rate,
                'count': total_count,
                'success_count': success_count
            }
        
        # Response time
        response_times = [m.get('duration_ms', 0) for m in metrics if m.get('duration_ms', 0) > 0]
        if response_times:
            avg_response = np.mean(response_times)
            # Normalize: 0-100ms = 1.0, 1000ms = 0.5, 5000ms = 0.0
            response_score = max(0.0, min(1.0, 1.0 - (avg_response - 100) / 4900))
            scores['response_time'] = {
                'score': response_score,
                'weight': self.component_weights['response_time'],
                'raw_value': avg_response,
                'count': len(response_times),
                'p95': np.percentile(response_times, 95) if len(response_times) >= 5 else avg_response
            }
        
        # Error distribution
        errors = [m.get('error_message', '') for m in metrics if m.get('error_message')]
        if errors:
            unique_errors = len(set(errors))
            total_errors = len(errors)
            # Fewer unique errors relative to total is better
            if total_errors > 0:
                error_diversity = unique_errors / total_errors
                error_score = max(0.0, 1.0 - error_diversity)
                scores['error_distribution'] = {
                    'score': error_score,
                    'weight': self.component_weights['error_distribution'],
                    'raw_value': error_diversity,
                    'error_count': total_errors,
                    'unique_errors': unique_errors
                }
        
        # Availability (uptime)
        if window_hours >= 24:
            # Calculate hourly availability
            hours_metrics = defaultdict(list)
            for m in metrics:
                hour = m['timestamp'].replace(minute=0, second=0, microsecond=0)
                hours_metrics[hour].append(m)
            
            available_hours = sum(1 for hour_metrics in hours_metrics.values() 
                                if any(m.get('success', False) for m in hour_metrics))
            total_hours = len(hours_metrics)
            
            if total_hours > 0:
                availability = available_hours / total_hours
                scores['availability'] = {
                    'score': availability,
                    'weight': self.component_weights['availability'],
                    'raw_value': availability,
                    'available_hours': available_hours,
                    'total_hours': total_hours
                }
        
        # Consistency (variance in success rate)
        if len(metrics) >= 10:
            # Calculate success rate in chunks
            chunk_size = max(5, len(metrics) // 10)
            chunks = [metrics[i:i+chunk_size] for i in range(0, len(metrics), chunk_size)]
            chunk_success_rates = []
            
            for chunk in chunks:
                if chunk:
                    chunk_success = sum(1 for m in chunk if m.get('success', False))
                    chunk_success_rates.append(chunk_success / len(chunk))
            
            if chunk_success_rates:
                consistency_std = np.std(chunk_success_rates)
                consistency_score = max(0.0, 1.0 - consistency_std * 2)  # Lower std = higher score
                scores['consistency'] = {
                    'score': consistency_score,
                    'weight': self.component_weights['consistency'],
                    'raw_value': consistency_std,
                    'chunk_count': len(chunks),
                    'chunk_success_rates': [round(r, 3) for r in chunk_success_rates[:5]]
                }
        
        return scores
    
    def _calculate_overall_score(self, component_scores: Dict) -> float:
        """Calculate overall reputation score"""
        if not component_scores:
            return 0.5
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for component, data in component_scores.items():
            weight = data['weight']
            score = data['score']
            
            weighted_sum += score * weight
            total_weight += weight
        
        if total_weight > 0:
            overall = weighted_sum / total_weight
        else:
            overall = 0.5
        
        return overall
    
    def record_metric(self, domain: str, metric_data: Dict):
        """Record metric for reputation calculation"""
        metric_record = {
            'domain': domain,
            'timestamp': datetime.utcnow(),
            'success': metric_data.get('success', True),
            'duration_ms': metric_data.get('duration_ms', 0),
            'error_message': metric_data.get('error_message', ''),
            'status_code': metric_data.get('status_code', 0),
            'operation': metric_data.get('operation', ''),
            'parameters_hash': hashlib.md5(str(metric_data.get('parameters', {})).encode()).hexdigest()[:8]
        }
        
        self.domain_metrics[domain].append(metric_record)
        
        # Auto-decay old scores
        self._apply_decay(domain)
    
    def _apply_decay(self, domain: str):
        """Apply time decay to reputation score"""
        if domain in self.reputation_scores:
            last_updated = self.reputation_scores[domain]['last_updated']
            hours_since = (datetime.utcnow() - last_updated).total_seconds() / 3600
            
            if hours_since > 24:
                # Apply decay: score moves toward 0.5 (neutral)
                current_score = self.reputation_scores[domain]['current_score']
                decay_days = hours_since / 24
                decay_factor = self.decay_factor ** decay_days
                
                new_score = 0.5 + (current_score - 0.5) * decay_factor
                self.reputation_scores[domain]['current_score'] = new_score
                self.reputation_scores[domain]['last_updated'] = datetime.utcnow()
    
    def get_reputation_history(self, domain: str, limit: int = 100) -> List[Dict]:
        """Get reputation score history"""
        if domain not in self.reputation_scores:
            return []
        
        history = list(self.reputation_scores[domain]['score_history'])
        return [
            {
                'score': round(h['score'], 4),
                'timestamp': h['timestamp'].isoformat(),
                'window': h.get('window', '24h')
            }
            for h in history[-limit:]
        ]
    
    def compare_domains(self, domains: List[str], window: str = '24h') -> Dict:
        """Compare reputation scores of multiple domains"""
        comparisons = []
        
        for domain in domains:
            rep = self.calculate_reputation(domain, window)
            comparisons.append({
                'domain': domain,
                'reputation_score': rep['reputation_score'],
                'metric_count': rep['metric_count'],
                'components': {k: v['score'] for k, v in rep.get('components', {}).items()}
            })
        
        # Sort by score
        comparisons.sort(key=lambda x: x['reputation_score'], reverse=True)
        
        return {
            'comparisons': comparisons,
            'window': window,
            'domain_count': len(domains),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_top_domains(self, min_metrics: int = 10, limit: int = 50) -> List[Dict]:
        """Get top domains by reputation score"""
        qualified_domains = []
        
        for domain in self.domain_metrics:
            if len(self.domain_metrics[domain]) >= min_metrics:
                rep = self.calculate_reputation(domain, '24h')
                qualified_domains.append({
                    'domain': domain,
                    'reputation_score': rep['reputation_score'],
                    'metric_count': len(self.domain_metrics[domain]),
                    'last_metric': max(m['timestamp'] for m in self.domain_metrics[domain]).isoformat()
                })
        
        # Sort by score
        qualified_domains.sort(key=lambda x: x['reputation_score'], reverse=True)
        
        return qualified_domains[:limit]
    
    def get_reputation_stats(self) -> Dict:
        """Get global reputation statistics"""
        total_domains = len(self.domain_metrics)
        domains_with_metrics = sum(1 for metrics in self.domain_metrics.values() if len(metrics) >= 10)
        
        # Calculate average reputation for domains with enough metrics
        avg_reputation = 0.0
        count = 0
        
        for domain in self.domain_metrics:
            if len(self.domain_metrics[domain]) >= 10:
                rep = self.calculate_reputation(domain, '24h')
                avg_reputation += rep['reputation_score']
                count += 1
        
        if count > 0:
            avg_reputation /= count
        
        # Get distribution
        distribution = defaultdict(int)
        for domain in self.domain_metrics:
            if len(self.domain_metrics[domain]) >= 10:
                rep = self.calculate_reputation(domain, '24h')
                score = rep['reputation_score']
                if score >= 0.8:
                    distribution['excellent'] += 1
                elif score >= 0.6:
                    distribution['good'] += 1
                elif score >= 0.4:
                    distribution['fair'] += 1
                else:
                    distribution['poor'] += 1
        
        return {
            'total_domains_monitored': total_domains,
            'domains_with_sufficient_metrics': domains_with_metrics,
            'average_reputation_score': round(avg_reputation, 4),
            'reputation_distribution': dict(distribution),
            'total_metrics_stored': sum(len(metrics) for metrics in self.domain_metrics.values()),
            'timestamp': datetime.utcnow().isoformat()
        }

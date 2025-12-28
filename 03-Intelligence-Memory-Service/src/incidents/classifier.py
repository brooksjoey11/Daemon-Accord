import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict, deque
import hashlib
import json
from typing import Dict, List, Any, Tuple

class IncidentClassifier:
    def __init__(self):
        self.severity_thresholds = {
            'low': {'impact': 0.2, 'duration': 30000, 'error_count': 1},
            'medium': {'impact': 0.5, 'duration': 60000, 'error_count': 3},
            'high': {'impact': 0.8, 'duration': 120000, 'error_count': 10},
            'critical': {'impact': 0.9, 'duration': 300000, 'error_count': 20}
        }
        self.domain_history = defaultdict(lambda: deque(maxlen=1000))
        self.incident_patterns = {}
        self.load_patterns()
    
    def load_patterns(self):
        """Load known incident patterns"""
        self.incident_patterns = {
            'timeout_cascade': {
                'symptoms': ['timeout', 'connection_timeout', 'request_timeout'],
                'severity': 'high',
                'impact_factor': 0.7,
                'response': 'circuit_breaker'
            },
            'memory_exhaustion': {
                'symptoms': ['memory', 'out of memory', 'heap'],
                'severity': 'critical',
                'impact_factor': 0.9,
                'response': 'restart_service'
            },
            'permission_denied': {
                'symptoms': ['permission', 'access denied', 'unauthorized'],
                'severity': 'medium',
                'impact_factor': 0.4,
                'response': 'credential_rotation'
            },
            'resource_constraint': {
                'symptoms': ['resource', 'quota', 'limit exceeded'],
                'severity': 'medium',
                'impact_factor': 0.5,
                'response': 'resource_scaling'
            },
            'data_corruption': {
                'symptoms': ['corrupt', 'invalid data', 'checksum'],
                'severity': 'critical',
                'impact_factor': 0.95,
                'response': 'data_restore'
            }
        }
    
    def classify_incident(self, incident_data: Dict) -> Dict:
        """Classify incident severity and suggest response"""
        start_time = datetime.utcnow()
        
        # Extract features
        features = self._extract_features(incident_data)
        
        # Calculate base severity
        base_severity = self._calculate_base_severity(features)
        
        # Apply domain context
        domain = incident_data.get('domain', 'unknown')
        context_adjustment = self._apply_domain_context(domain, features)
        
        # Match known patterns
        pattern_match = self._match_known_patterns(features)
        
        # Calculate final severity
        severity_score = base_severity['score']
        if context_adjustment['adjustment'] != 0:
            severity_score += context_adjustment['adjustment']
        
        if pattern_match['matched']:
            severity_score = max(severity_score, pattern_match['severity_score'])
        
        # Map to severity level
        severity_level = self._map_to_severity_level(severity_score)
        
        # Calculate impact
        estimated_impact = self._estimate_impact(features, severity_level)
        
        # Suggest response
        suggested_response = self._suggest_response(
            severity_level, 
            pattern_match, 
            context_adjustment,
            features
        )
        
        # Record incident
        self._record_incident(domain, features, severity_level)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'incident_id': incident_data.get('id', hashlib.md5(str(incident_data).encode()).hexdigest()[:16]),
            'severity': severity_level,
            'severity_score': round(severity_score, 3),
            'suggested_response': suggested_response,
            'estimated_impact': estimated_impact,
            'pattern_matched': pattern_match['pattern'] if pattern_match['matched'] else None,
            'classification_time_ms': round(elapsed, 2),
            'features_used': list(features.keys()),
            'domain': domain,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _extract_features(self, incident_data: Dict) -> Dict:
        """Extract classification features"""
        features = {}
        
        # Duration impact
        duration = incident_data.get('duration_ms', 0)
        features['duration_normalized'] = min(duration / 300000, 1.0)  # 5min max
        
        # Error impact
        error_msg = str(incident_data.get('error_message', '')).lower()
        features['error_length'] = min(len(error_msg) / 1000, 1.0)
        
        # Parameter complexity
        params = incident_data.get('parameters', {})
        features['param_complexity'] = min(len(str(params)) / 5000, 1.0)
        
        # Success rate impact
        success = incident_data.get('success', True)
        features['success_impact'] = 0.0 if success else 1.0
        
        # Affected executions
        affected = incident_data.get('affected_executions', 1)
        features['affected_scale'] = min(affected / 100, 1.0)
        
        # Time-based features
        hour = datetime.utcnow().hour
        features['peak_hour'] = 1.0 if 9 <= hour <= 17 else 0.0
        
        # Resource indicators
        symptoms = incident_data.get('symptoms', {})
        features['resource_strain'] = symptoms.get('cpu_usage', 0) / 100
        features['memory_pressure'] = symptoms.get('memory_usage', 0) / 100
        
        # Dependency failures
        dependencies = symptoms.get('dependency_failures', 0)
        features['dependency_impact'] = min(dependencies / 10, 1.0)
        
        return features
    
    def _calculate_base_severity(self, features: Dict) -> Dict:
        """Calculate base severity score"""
        weights = {
            'duration_normalized': 0.15,
            'success_impact': 0.25,
            'affected_scale': 0.20,
            'dependency_impact': 0.15,
            'resource_strain': 0.10,
            'memory_pressure': 0.10,
            'peak_hour': 0.05
        }
        
        score = 0.0
        for feature, weight in weights.items():
            value = features.get(feature, 0.0)
            score += value * weight
        
        # Apply non-linear scaling
        if score > 0.7:
            score = 0.7 + (score - 0.7) * 1.5
        
        return {'score': min(score, 1.0), 'weights': weights}
    
    def _apply_domain_context(self, domain: str, features: Dict) -> Dict:
        """Apply domain-specific context adjustments"""
        if domain not in self.domain_history:
            return {'adjustment': 0.0, 'reason': 'no_history'}
        
        history = list(self.domain_history[domain])
        if len(history) < 5:
            return {'adjustment': 0.0, 'reason': 'insufficient_data'}
        
        # Calculate recent failure rate
        recent = [h for h in history if h['timestamp'] > datetime.utcnow() - timedelta(hours=1)]
        if not recent:
            return {'adjustment': 0.0, 'reason': 'no_recent'}
        
        failure_rate = sum(1 for h in recent if not h.get('success', True)) / len(recent)
        
        if failure_rate > 0.5:
            adjustment = min(failure_rate * 0.3, 0.3)
            return {'adjustment': adjustment, 'reason': f'high_failure_rate_{failure_rate:.2f}'}
        
        # Check for severity escalation pattern
        recent_severities = [h.get('severity_score', 0) for h in recent]
        if len(recent_severities) >= 3:
            trend = np.polyfit(range(len(recent_severities)), recent_severities, 1)[0]
            if trend > 0.1:
                adjustment = min(trend * 2, 0.4)
                return {'adjustment': adjustment, 'reason': f'escalating_severity_trend_{trend:.2f}'}
        
        return {'adjustment': 0.0, 'reason': 'normal'}
    
    def _match_known_patterns(self, features: Dict) -> Dict:
        """Match against known incident patterns"""
        error_msg = features.get('error_message', '')
        if not error_msg:
            return {'matched': False, 'pattern': None, 'severity_score': 0.0}
        
        error_lower = error_msg.lower()
        best_match = None
        best_score = 0.0
        
        for pattern_name, pattern in self.incident_patterns.items():
            score = 0.0
            for symptom in pattern['symptoms']:
                if symptom in error_lower:
                    score += 0.5
            
            if score > 0:
                # Additional feature matching
                if pattern_name == 'memory_exhaustion' and features.get('memory_pressure', 0) > 0.8:
                    score += 0.3
                elif pattern_name == 'resource_constraint' and features.get('resource_strain', 0) > 0.7:
                    score += 0.3
                
                if score > best_score:
                    best_score = score
                    best_match = pattern_name
        
        if best_match and best_score > 0.5:
            pattern = self.incident_patterns[best_match]
            severity_map = {'low': 0.3, 'medium': 0.5, 'high': 0.8, 'critical': 0.95}
            severity_score = severity_map.get(pattern['severity'], 0.5) * pattern['impact_factor']
            
            return {
                'matched': True,
                'pattern': best_match,
                'severity_score': severity_score,
                'response': pattern['response']
            }
        
        return {'matched': False, 'pattern': None, 'severity_score': 0.0}
    
    def _map_to_severity_level(self, score: float) -> str:
        """Map score to severity level"""
        if score >= 0.9:
            return 'critical'
        elif score >= 0.7:
            return 'high'
        elif score >= 0.4:
            return 'medium'
        else:
            return 'low'
    
    def _estimate_impact(self, features: Dict, severity: str) -> Dict:
        """Estimate business impact"""
        base_impact = {
            'low': {'downtime_min': 1, 'affected_users': 10, 'recovery_cost': 100},
            'medium': {'downtime_min': 15, 'affected_users': 100, 'recovery_cost': 1000},
            'high': {'downtime_min': 60, 'affected_users': 1000, 'recovery_cost': 10000},
            'critical': {'downtime_min': 240, 'affected_users': 10000, 'recovery_cost': 100000}
        }
        
        impact = base_impact.get(severity, base_impact['low']).copy()
        
        # Adjust based on features
        affected_scale = features.get('affected_scale', 0.0)
        impact['affected_users'] = int(impact['affected_users'] * (1 + affected_scale * 9))
        
        peak_hour = features.get('peak_hour', 0.0)
        if peak_hour > 0.5:
            impact['downtime_min'] *= 2
            impact['recovery_cost'] *= 1.5
        
        dependency_impact = features.get('dependency_impact', 0.0)
        if dependency_impact > 0.5:
            impact['downtime_min'] *= 1.5
            impact['recovery_cost'] *= 2
        
        return impact
    
    def _suggest_response(self, severity: str, pattern_match: Dict, 
                         context_adjustment: Dict, features: Dict) -> List[str]:
        """Suggest response actions"""
        responses = []
        
        # Severity-based responses
        if severity == 'critical':
            responses.extend(['circuit_breaker', 'domain_blacklist', 'strategy_escalation', 'human_alert'])
        elif severity == 'high':
            responses.extend(['circuit_breaker', 'strategy_escalation', 'performance_optimization'])
        elif severity == 'medium':
            responses.extend(['retry_with_backoff', 'resource_scaling', 'monitoring_increase'])
        else:
            responses.extend(['auto_retry', 'log_analysis'])
        
        # Pattern-specific responses
        if pattern_match['matched'] and 'response' in pattern_match:
            if pattern_match['response'] not in responses:
                responses.insert(0, pattern_match['response'])
        
        # Context-adjusted responses
        if context_adjustment['adjustment'] > 0.2:
            if 'circuit_breaker' not in responses:
                responses.append('circuit_breaker')
        
        # Feature-based responses
        if features.get('resource_strain', 0) > 0.8:
            responses.append('resource_scaling')
        
        if features.get('dependency_impact', 0) > 0.7:
            responses.append('dependency_isolation')
        
        return responses[:5]  # Return top 5 responses
    
    def _record_incident(self, domain: str, features: Dict, severity: str):
        """Record incident for historical analysis"""
        record = {
            'severity': severity,
            'severity_score': self._get_severity_score(severity),
            'success': features.get('success_impact', 1.0) < 0.5,
            'timestamp': datetime.utcnow(),
            'features': {k: v for k, v in features.items() if not isinstance(v, dict)}
        }
        self.domain_history[domain].append(record)
    
    def _get_severity_score(self, severity: str) -> float:
        """Convert severity level to numeric score"""
        scores = {'low': 0.3, 'medium': 0.5, 'high': 0.8, 'critical': 0.95}
        return scores.get(severity, 0.5)
    
    def get_domain_stats(self, domain: str, hours: int = 24) -> Dict:
        """Get incident statistics for domain"""
        if domain not in self.domain_history:
            return {'total': 0, 'by_severity': {}, 'trend': 'stable'}
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        incidents = [h for h in self.domain_history[domain] if h['timestamp'] > cutoff]
        
        if not incidents:
            return {'total': 0, 'by_severity': {}, 'trend': 'stable'}
        
        by_severity = defaultdict(int)
        for incident in incidents:
            by_severity[incident['severity']] += 1
        
        # Calculate trend
        if len(incidents) >= 3:
            # Split into thirds
            third = len(incidents) // 3
            first_third = incidents[:third]
            last_third = incidents[-third:]
            
            first_avg = np.mean([i['severity_score'] for i in first_third])
            last_avg = np.mean([i['severity_score'] for i in last_third])
            
            if last_avg > first_avg * 1.2:
                trend = 'escalating'
            elif last_avg < first_avg * 0.8:
                trend = 'improving'
            else:
                trend = 'stable'
        else:
            trend = 'insufficient_data'
        
        return {
            'total': len(incidents),
            'by_severity': dict(by_severity),
            'trend': trend,
            'avg_severity_score': np.mean([i['severity_score'] for i in incidents]),
            'timeframe_hours': hours
        }

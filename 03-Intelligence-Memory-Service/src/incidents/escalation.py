from datetime import datetime, timedelta
from collections import defaultdict, deque
import numpy as np
from typing import Dict, List, Any, Optional

class EscalationMatrix:
    def __init__(self):
        self.domain_incident_counts = defaultdict(lambda: deque(maxlen=1000))
        self.escalation_rules = self._initialize_escalation_rules()
        self.human_review_queue = deque(maxlen=10000)
        self.escalation_history = defaultdict(lambda: deque(maxlen=100))
        self.domain_state = defaultdict(lambda: {
            'incident_count_1h': 0,
            'incident_count_24h': 0,
            'last_incident_time': None,
            'escalation_level': 0,
            'blacklisted': False,
            'last_human_review': None
        })
        
    def _initialize_escalation_rules(self) -> Dict:
        """Initialize escalation rules"""
        return {
            'critical_incident_threshold': {
                'condition': lambda domain, state: state['incident_count_1h'] >= 5,
                'action': 'domain_blacklist',
                'cooldown_hours': 6,
                'requires_human': False
            },
            'high_severity_cluster': {
                'condition': lambda domain, state: (
                    state['incident_count_1h'] >= 3 and 
                    state['escalation_level'] >= 2
                ),
                'action': 'circuit_breaker_activate',
                'cooldown_hours': 2,
                'requires_human': False
            },
            'sustained_failure': {
                'condition': lambda domain, state: (
                    state['incident_count_24h'] >= 20 and
                    state['escalation_level'] >= 1
                ),
                'action': 'strategy_escalation_max',
                'cooldown_hours': 12,
                'requires_human': True
            },
            'new_domain_high_failure': {
                'condition': lambda domain, state: (
                    state['incident_count_1h'] >= 10 and
                    state['escalation_level'] == 0
                ),
                'action': 'domain_quarantine',
                'cooldown_hours': 24,
                'requires_human': True
            },
            'recovery_failure': {
                'condition': lambda domain, state: (
                    state['escalation_level'] >= 3 and
                    state['incident_count_1h'] >= 2
                ),
                'action': 'full_service_isolation',
                'cooldown_hours': 1,
                'requires_human': True
            },
            'human_review_threshold': {
                'condition': lambda domain, state: (
                    state['escalation_level'] >= 2 and
                    state['incident_count_24h'] >= 10
                ),
                'action': 'human_review_required',
                'cooldown_hours': 0,
                'requires_human': True
            }
        }
    
    def check_escalation_threshold(self, domain: str, incident_count: int = None) -> Optional[Dict]:
        """Check if escalation threshold is reached for domain"""
        now = datetime.utcnow()
        
        # Update domain state
        self._update_domain_state(domain, incident_count)
        state = self.domain_state[domain]
        
        # Check each escalation rule
        for rule_name, rule in self.escalation_rules.items():
            try:
                if rule['condition'](domain, state):
                    # Check cooldown
                    last_action = self._get_last_escalation(domain, rule_name)
                    if last_action:
                        cooldown_hours = rule.get('cooldown_hours', 1)
                        if (now - last_action['timestamp']) < timedelta(hours=cooldown_hours):
                            continue
                    
                    # Prepare escalation action
                    escalation_action = {
                        'domain': domain,
                        'rule_triggered': rule_name,
                        'action': rule['action'],
                        'requires_human': rule['requires_human'],
                        'timestamp': now,
                        'domain_state': state.copy(),
                        'incident_count_1h': state['incident_count_1h'],
                        'incident_count_24h': state['incident_count_24h'],
                        'escalation_level': state['escalation_level']
                    }
                    
                    # Increment escalation level
                    state['escalation_level'] = min(state['escalation_level'] + 1, 5)
                    
                    # Record escalation
                    self.escalation_history[domain].append(escalation_action)
                    
                    # Add to human review queue if required
                    if rule['requires_human']:
                        self.human_review_queue.append({
                            **escalation_action,
                            'queued_at': now,
                            'priority': self._calculate_priority(state)
                        })
                    
                    return escalation_action
                    
            except Exception as e:
                continue
        
        return None
    
    def _update_domain_state(self, domain: str, incident_count: int = None):
        """Update domain incident statistics"""
        now = datetime.utcnow()
        state = self.domain_state[domain]
        
        # Count incidents in last hour
        one_hour_ago = now - timedelta(hours=1)
        recent_incidents = [
            inc for inc in self.domain_incident_counts[domain]
            if inc['timestamp'] > one_hour_ago
        ]
        state['incident_count_1h'] = len(recent_incidents)
        
        # Count incidents in last 24 hours
        one_day_ago = now - timedelta(hours=24)
        daily_incidents = [
            inc for inc in self.domain_incident_counts[domain]
            if inc['timestamp'] > one_day_ago
        ]
        state['incident_count_24h'] = len(daily_incidents)
        
        # Update last incident time
        if self.domain_incident_counts[domain]:
            latest = max(self.domain_incident_counts[domain], key=lambda x: x['timestamp'])
            state['last_incident_time'] = latest['timestamp']
        
        # Auto-decay escalation level if no recent incidents
        if state['last_incident_time']:
            hours_since_last = (now - state['last_incident_time']).total_seconds() / 3600
            if hours_since_last > 6:
                state['escalation_level'] = max(0, state['escalation_level'] - 1)
        
        # Auto-unblacklist after 6 hours
        if state['blacklisted'] and state['last_incident_time']:
            hours_since_blacklist = (now - state['last_incident_time']).total_seconds() / 3600
            if hours_since_blacklist >= 6:
                state['blacklisted'] = False
                state['escalation_level'] = max(0, state['escalation_level'] - 2)
    
    def _get_last_escalation(self, domain: str, rule_name: str) -> Optional[Dict]:
        """Get last escalation for domain by rule"""
        if domain not in self.escalation_history:
            return None
        
        for escalation in reversed(self.escalation_history[domain]):
            if escalation['rule_triggered'] == rule_name:
                return escalation
        
        return None
    
    def _calculate_priority(self, state: Dict) -> int:
        """Calculate priority for human review queue"""
        priority = 0
        
        # Base priority on escalation level
        priority += state['escalation_level'] * 10
        
        # Increase priority for recent incidents
        priority += min(state['incident_count_1h'] * 2, 20)
        
        # Increase priority for high daily count
        priority += min(state['incident_count_24h'] // 5, 10)
        
        # Critical domains get extra priority
        if state['escalation_level'] >= 3:
            priority += 15
        
        return min(priority, 100)
    
    def record_incident(self, domain: str, severity: str, incident_data: Dict):
        """Record incident for escalation tracking"""
        now = datetime.utcnow()
        
        incident_record = {
            'domain': domain,
            'severity': severity,
            'timestamp': now,
            'data': {k: v for k, v in incident_data.items() if k not in ['parameters', 'result']},
            'severity_score': self._severity_to_score(severity)
        }
        
        self.domain_incident_counts[domain].append(incident_record)
        
        # Update domain state immediately
        self._update_domain_state(domain)
    
    def _severity_to_score(self, severity: str) -> float:
        """Convert severity to numeric score"""
        scores = {'low': 0.3, 'medium': 0.5, 'high': 0.8, 'critical': 0.95}
        return scores.get(severity, 0.5)
    
    def get_domain_escalation_status(self, domain: str) -> Dict:
        """Get current escalation status for domain"""
        state = self.domain_state[domain]
        
        # Calculate time since last incident
        time_since_last = None
        if state['last_incident_time']:
            time_since_last = (datetime.utcnow() - state['last_incident_time']).total_seconds() / 60
        
        # Get pending human reviews
        pending_reviews = [
            review for review in self.human_review_queue
            if review['domain'] == domain and not review.get('resolved', False)
        ]
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(state)
        
        return {
            'domain': domain,
            'escalation_level': state['escalation_level'],
            'risk_score': risk_score,
            'incident_count_1h': state['incident_count_1h'],
            'incident_count_24h': state['incident_count_24h'],
            'blacklisted': state['blacklisted'],
            'time_since_last_incident_min': round(time_since_last, 2) if time_since_last else None,
            'pending_human_reviews': len(pending_reviews),
            'last_human_review': state['last_human_review'],
            'escalation_history_count': len(self.escalation_history[domain]),
            'recommended_action': self._recommend_action(state, risk_score)
        }
    
    def _calculate_risk_score(self, state: Dict) -> float:
        """Calculate current risk score for domain"""
        score = 0.0
        
        # Base on escalation level
        score += state['escalation_level'] * 0.15
        
        # Recent incidents
        if state['incident_count_1h'] > 0:
            score += min(state['incident_count_1h'] * 0.05, 0.3)
        
        # Daily incidents
        if state['incident_count_24h'] > 10:
            score += min(state['incident_count_24h'] * 0.01, 0.2)
        
        # Blacklist status
        if state['blacklisted']:
            score += 0.3
        
        # Time decay if no recent incidents
        if state['last_incident_time']:
            hours_since = (datetime.utcnow() - state['last_incident_time']).total_seconds() / 3600
            if hours_since > 1:
                score *= max(0.5, 1.0 - (hours_since * 0.1))
        
        return min(score, 1.0)
    
    def _recommend_action(self, state: Dict, risk_score: float) -> str:
        """Recommend action based on current state"""
        if risk_score >= 0.8:
            return 'immediate_human_intervention'
        elif risk_score >= 0.6:
            return 'automated_containment'
        elif risk_score >= 0.4:
            return 'enhanced_monitoring'
        elif risk_score >= 0.2:
            return 'standard_monitoring'
        else:
            return 'no_action'
    
    def get_human_review_queue(self, limit: int = 100) -> List[Dict]:
        """Get items from human review queue"""
        items = []
        for item in self.human_review_queue:
            if not item.get('resolved', False):
                items.append(item)
                if len(items) >= limit:
                    break
        return items
    
    def resolve_human_review(self, domain: str, action_taken: str, notes: str = ''):
        """Mark human review as resolved"""
        for item in self.human_review_queue:
            if item['domain'] == domain and not item.get('resolved', False):
                item['resolved'] = True
                item['resolved_at'] = datetime.utcnow()
                item['action_taken'] = action_taken
                item['resolution_notes'] = notes
                
                # Update domain state
                self.domain_state[domain]['last_human_review'] = datetime.utcnow()
                # Reduce escalation level after human review
                self.domain_state[domain]['escalation_level'] = max(
                    0, self.domain_state[domain]['escalation_level'] - 1
                )
                break
    
    def force_escalation(self, domain: str, level: int, reason: str):
        """Force escalation to specific level"""
        state = self.domain_state[domain]
        previous_level = state['escalation_level']
        state['escalation_level'] = min(max(level, 0), 5)
        
        # Record forced escalation
        escalation_action = {
            'domain': domain,
            'rule_triggered': 'manual_override',
            'action': 'forced_escalation',
            'requires_human': True,
            'timestamp': datetime.utcnow(),
            'previous_level': previous_level,
            'new_level': state['escalation_level'],
            'reason': reason,
            'manual_override': True
        }
        
        self.escalation_history[domain].append(escalation_action)
        self.human_review_queue.append({
            **escalation_action,
            'queued_at': datetime.utcnow(),
            'priority': 100
        })
        
        return escalation_action
    
    def clear_escalation(self, domain: str, reason: str):
        """Clear all escalations for domain"""
        state = self.domain_state[domain]
        previous_level = state['escalation_level']
        state['escalation_level'] = 0
        state['blacklisted'] = False
        
        # Clear incident counts
        self.domain_incident_counts[domain].clear()
        
        # Record clearance
        clearance_record = {
            'domain': domain,
            'action': 'escalation_cleared',
            'timestamp': datetime.utcnow(),
            'previous_level': previous_level,
            'reason': reason,
            'manual_override': True
        }
        
        self.escalation_history[domain].append(clearance_record)
        
        return clearance_record
    
    def get_escalation_stats(self) -> Dict:
        """Get global escalation statistics"""
        total_domains = len(self.domain_state)
        escalated_domains = sum(1 for state in self.domain_state.values() if state['escalation_level'] > 0)
        blacklisted_domains = sum(1 for state in self.domain_state.values() if state['blacklisted'])
        
        avg_escalation_level = np.mean([state['escalation_level'] for state in self.domain_state.values()])
        pending_reviews = sum(1 for item in self.human_review_queue if not item.get('resolved', False))
        
        return {
            'total_domains_monitored': total_domains,
            'escalated_domains': escalated_domains,
            'blacklisted_domains': blacklisted_domains,
            'average_escalation_level': round(avg_escalation_level, 2),
            'pending_human_reviews': pending_reviews,
            'total_escalation_events': sum(len(history) for history in self.escalation_history.values()),
            'timestamp': datetime.utcnow().isoformat()
        }

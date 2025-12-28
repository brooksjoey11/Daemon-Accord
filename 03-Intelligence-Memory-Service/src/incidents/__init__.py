from .classifier import IncidentClassifier
from .responder import AutomatedResponder
from .escalation import EscalationMatrix
from .recovery_monitor import RecoveryMonitor

class IncidentManager:
    """Orchestrator for incident management system"""
    
    def __init__(self, redis_client=None):
        self.classifier = IncidentClassifier()
        self.responder = AutomatedResponder(redis_client)
        self.escalation = EscalationMatrix()
        self.recovery_monitor = RecoveryMonitor()
        self.incident_tracking = {}
        
    async def process_incident(self, incident_data: Dict) -> Dict:
        """Complete incident processing pipeline"""
        start_time = datetime.utcnow()
        
        # 1. Classify incident
        classification = self.classifier.classify_incident(incident_data)
        
        # 2. Record for escalation tracking
        domain = incident_data.get('domain', 'unknown')
        self.escalation.record_incident(
            domain, 
            classification['severity'], 
            incident_data
        )
        
        # 3. Check for escalation
        escalation_action = self.escalation.check_escalation_threshold(domain)
        
        # 4. Execute initial response
        initial_response = None
        if classification['suggested_response']:
            response_type = classification['suggested_response'][0]
            initial_response = await self.responder.execute_response(
                classification['incident_id'],
                response_type,
                domain,
                {
                    'severity': classification['severity'],
                    'estimated_impact': classification['estimated_impact']
                }
            )
        
        # 5. Start recovery monitoring if incident was significant
        if classification and classification.get('severity') in ['high', 'critical']:
            # Recovery monitoring logic would go here
            pass

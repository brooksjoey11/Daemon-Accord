from .graph_builder import DomainGraph
from .fingerprint import FingerprintEngine
from .reputation import ReputationScoring
from .predictor import PredictiveModel

class DomainIntelligence:
    """Main domain intelligence orchestrator"""
    
    def __init__(self, neo4j_config: Dict = None):
        self.graph = DomainGraph(
            neo4j_config.get('uri', 'bolt://localhost:7687'),
            neo4j_config.get('user', 'neo4j'),
            neo4j_config.get('password', 'password')
        )
        self.fingerprint = FingerprintEngine()
        self.reputation = ReputationScoring()
        self.predictor = PredictiveModel()
        self.domain_cache = {}
        
    async def process_domain_data(self, domain: str, domain_data: Dict) -> Dict:
        """Process complete domain intelligence pipeline"""
        results = {}
        
        # 1. Build graph
        graph_result = await self.graph.build_graph(domain_data)
        results['graph'] = graph_result
        
        # 2. Extract fingerprint
        fingerprint_result = self.fingerprint.extract_fingerprint(domain_data)
        results['fingerprint'] = fingerprint_result
        
        # 3. Update reputation metrics
        self.reputation.record_metric(domain, {
            'success': domain_data.get('success', True),
            'duration_ms': domain_data.get('duration_ms', 0),
            'error_message': domain_data.get('error_message', ''),
            'status_code': domain_data.get('status_code', 200)
        })
        
        # 4. Record training data
        if 'strategy' in domain_data:
            self.predictor.record_training_data(
                domain,
                domain_data,
                domain_data['strategy'],
                domain_data.get('success', True)
            )
        
        # Cache results
        self.domain_cache[domain] = {
            'graph': graph_result,
            'fingerprint': fingerprint_result,
            'updated_at': datetime.utcnow()
        }
        
        return results
    
    async def get_domain_intelligence(self, domain: str) -> Dict:
        """Get comprehensive domain intelligence"""
        # Check cache
        if domain in self.domain_cache:
            cached = self.domain_cache[domain]
            if datetime.utcnow() - cached['updated_at'] < timedelta(minutes=5):
                return {
                    'domain': domain,
                    'cached': True,
                    'graph': cached['graph'],
                    'fingerprint': cached['fingerprint'],
                    'reputation': self.reputation.calculate_reputation(domain),
                    'predictions': self.predictor.get_domain_predictions_summary(domain)
                }
        
        # Build fresh intelligence
        return {
            'domain': domain,
            'cached': False,
            'graph': await self.graph.query_relationships(domain, depth=2),
            'fingerprint': self.fingerprint.get_domain_fingerprint_history(domain),
            'reputation': self.reputation.calculate_reputation(domain),
            'predictions': self.predictor.get_domain_predictions_summary(domain),
            'neighbors': await self.graph.get_domain_neighbors(domain),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def cleanup_old_data(self, days_old: int = 30):
        """Cleanup old data"""
        # Clean graph
        asyncio.create_task(self.graph.clean_old_data(days_old))
        
        # Clean fingerprints (handled internally)
        
        # Clean cache
        cutoff = datetime.utcnow() - timedelta(days=days_old)
        domains_to_remove = [
            domain for domain, data in self.domain_cache.items()
            if data['updated_at'] < cutoff
        ]
        for domain in domains_to_remove:
            del self.domain_cache[domain]
    
    def get_system_stats(self) -> Dict:
        """Get system statistics"""
        return {
            'graph': self.graph.get_graph_stats(),
            'reputation': self.reputation.get_reputation_stats(),
            'cache_size': len(self.domain_cache),
            'timestamp': datetime.utcnow().isoformat()
        }

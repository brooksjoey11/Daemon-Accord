from .store import VectorStore
from .embeddings import EmbeddingGenerator
from .search import SemanticSearcher
from .retriever import MemoryRetriever

class VectorMemorySystem:
    """Main vector memory system orchestrator"""
    
    def __init__(self, db_config: Dict = None):
        self.db_config = db_config or {
            'host': 'localhost',
            'port': 5432,
            'name': 'vector_db',
            'user': 'postgres',
            'password': 'password'
        }
        
        # Initialize components
        self.store = VectorStore(**self.db_config)
        self.embeddings = EmbeddingGenerator()
        self.searcher = SemanticSearcher(self.store)
        self.retriever = MemoryRetriever(self.store, self.embeddings, self.searcher)
        
        # Performance tracking
        self.performance_stats = {
            'embedding_generation': [],
            'vector_search': [],
            'memory_retrieval': []
        }
    
    async def store_artifacts(self, artifacts: List[Dict]) -> Dict:
        """Complete pipeline: generate embeddings and store them"""
        start_time = datetime.utcnow()
        
        # Generate embeddings
        embedding_results = self.embeddings.generate_embeddings(artifacts)
        
        if embedding_results['successful'] == 0:
            return {
                'success': False,
                'error': 'No embeddings generated',
                'details': embedding_results
            }
        
        # Prepare artifacts for storage
        artifacts_to_store = []
        for result in embedding_results['embeddings']:
            if result.get('success', False):
                artifact = next(
                    (a for a in artifacts if a.get('id') == result.get('artifact_id')),
                    {}
                )
                
                artifacts_to_store.append({
                    'domain': artifact.get('domain', 'default'),
                    'artifact_type': artifact.get('type', 'text'),
                    'artifact_id': artifact.get('id'),
                    'content_hash': result.get('content_hash'),
                    'embedding': result.get('embedding'),
                    'model_version': result.get('model_version'),
                    'metadata': artifact.get('metadata', {})
                })
        
        # Store embeddings
        storage_results = self.store.store_embeddings(artifacts_to_store)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Update performance stats
        self.performance_stats['embedding_generation'].append({
            'time_ms': embedding_results['processing_time_ms'],
            'count': embedding_results['total_processed'],
            'timestamp': datetime.utcnow()
        })
        
        return {
            'success': True,
            'embedding_generation': embedding_results,
            'vector_storage': storage_results,
            'total_processing_time_ms': round(elapsed, 2),
            'stored_count': storage_results['stored_count'],
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def search_similar(self, query: Any, artifact_type: str = 'text',
                           top_k: int = 10, domain: str = None,
                           filters: Dict = None) -> Dict:
        """Search for similar artifacts"""
        start_time = datetime.utcnow()
        
        search_results = self.searcher.search_similar(
            query, artifact_type, top_k, domain, filters
        )
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Update performance stats
        self.performance_stats['vector_search'].append({
            'time_ms': elapsed,
            'artifact_type': artifact_type,
            'results_count': len(search_results.get('results', [])),
            'timestamp': datetime.utcnow()
        })
        
        return search_results
    
    async def find_patterns(self, vector_cluster: List[List[float]],
                          threshold: float = 0.8, min_samples: int = 3) -> Dict:
        """Find patterns in vector clusters"""
        vectors = [np.array(v, dtype=np.float32) for v in vector_cluster]
        
        pattern_results = self.searcher.find_patterns(
            vectors, threshold, min_samples
        )
        
        return pattern_results
    
    async def retrieve_context(self, domain: str, strategy: Dict,
                             limit: int = 5, context_type: str = 'strategy_planning') -> Dict:
        """Retrieve relevant context memories"""
        start_time = datetime.utcnow()
        
        retrieval_results = self.retriever.retrieve_context(
            domain, strategy, limit, context_type
        )
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Update performance stats
        self.performance_stats['memory_retrieval'].append({
            'time_ms': elapsed,
            'context_type': context_type,
            'results_count': retrieval_results.get('total_retrieved', 0),
            'timestamp': datetime.utcnow()
        })
        
        return retrieval_results
    
    def get_system_stats(self) -> Dict:
        """Get comprehensive system statistics"""
        # Store stats
        store_stats = self.store.get_embedding_stats()
        
        # Embedding stats
        embedding_stats = self.embeddings.get_model_info()
        
        # Search stats
        search_stats = self.searcher.get_search_stats()
        
        # Retrieval stats
        retrieval_stats = self.retriever.get_retrieval_stats()
        
        # Performance stats
        perf_stats = {}
        for category, entries in self.performance_stats.items():
            if entries:
                recent = entries[-min(100, len(entries)):]
                perf_stats[category] = {
                    'recent_count': len(recent),
                    'avg_time_ms': round(np.mean([e['time_ms'] for e in recent]), 2),
                    'p95_time_ms': round(np.percentile([e['time_ms'] for e in recent], 95), 2),
                    'last_hour': len([e for e in entries 
                                     if datetime.utcnow() - e['timestamp'] < timedelta(hours=1)])
                }
        
        # Connection stats
        conn_stats = self.store.get_connection_stats()
        
        return {
            'store': store_stats,
            'embeddings': embedding_stats,
            'search': search_stats,
            'retrieval': retrieval_stats,
            'performance': perf_stats,
            'connections': conn_stats,
            'system_status': 'operational',
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def perform_maintenance(self):
        """Perform system maintenance"""
        results = {}
        
        # Vector store maintenance
        try:
            self.store.vacuum_and_analyze()
            results['store_maintenance'] = 'completed'
        except Exception as e:
            results['store_maintenance'] = f'failed: {str(e)[:100]}'
        
        # Embedding cache cleanup
        try:
            self.embeddings.cleanup_old_cache(days_old=7)
            results['cache_cleanup'] = 'completed'
        except Exception as e:
            results['cache_cleanup'] = f'failed: {str(e)[:100]}'
        
        # Search cache cleanup (handled automatically)
        results['search_cache'] = 'auto_managed'
        
        # Model updates check
        try:
            # Check if text model needs update (monthly)
            text_model = self.embeddings.loaded_models.get('text', {})
            if text_model:
                last_update = datetime.strptime(
                    text_model['version'].split('-')[-1], 
                    '%Y%m%d'
                ) if '-' in text_model['version'] else datetime.utcnow() - timedelta(days=60)
                
                if datetime.utcnow() - last_update > timedelta(days=30):
                    results['model_update_check'] = 'text_model_update_recommended'
                else:
                    results['model_update_check'] = 'models_current'
        except:
            results['model_update_check'] = 'check_failed'
        
        return results
    
    def close(self):
        """Close all resources"""
        self.store.close()
        
        return {
            'closed': True,
            'timestamp': datetime.utcnow().isoformat()
        }

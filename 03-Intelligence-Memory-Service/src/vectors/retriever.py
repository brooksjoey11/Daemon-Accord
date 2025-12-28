import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import heapq
import hashlib

class MemoryRetriever:
    def __init__(self, vector_store, embedding_generator, searcher):
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator
        self.searcher = searcher
        self.retrieval_cache = defaultdict(dict)
        self.context_weights = self._initialize_context_weights()
        self.retrieval_strategies = self._initialize_retrieval_strategies()
    
    def _initialize_context_weights(self) -> Dict:
        """Initialize weights for different context components"""
        return {
            'recent_success': 0.25,
            'similar_domain': 0.20,
            'matching_strategy': 0.15,
            'error_pattern': 0.15,
            'performance_profile': 0.10,
            'temporal_relevance': 0.08,
            'metadata_completeness': 0.07
        }
    
    def _initialize_retrieval_strategies(self) -> Dict:
        """Initialize different retrieval strategies"""
        return {
            'strategy_planning': {
                'artifact_types': ['execution', 'strategy', 'pattern'],
                'time_window': '7d',
                'min_similarity': 0.7,
                'max_results': 10
            },
            'error_analysis': {
                'artifact_types': ['error', 'incident', 'failure'],
                'time_window': '30d',
                'min_similarity': 0.8,
                'max_results': 20
            },
            'performance_optimization': {
                'artifact_types': ['performance', 'metrics', 'timing'],
                'time_window': '14d',
                'min_similarity': 0.6,
                'max_results': 15
            },
            'domain_adaptation': {
                'artifact_types': ['domain', 'fingerprint', 'pattern'],
                'time_window': '30d',
                'min_similarity': 0.75,
                'max_results': 25
            }
        }
    
    def retrieve_context(self, domain: str, strategy: Dict, 
                        limit: int = 5, context_type: str = 'strategy_planning') -> Dict:
        """Retrieve relevant memories for strategy planning"""
        start_time = datetime.utcnow()
        
        # Validate inputs
        if not domain:
            return {'error': 'Domain is required', 'memories': []}
        
        if context_type not in self.retrieval_strategies:
            context_type = 'strategy_planning'
        
        strategy_config = self.retrieval_strategies[context_type]
        
        # Check cache
        cache_key = self._generate_retrieval_key(domain, strategy, limit, context_type)
        if cache_key in self.retrieval_cache[context_type]:
            cached = self.retrieval_cache[context_type][cache_key]
            if datetime.utcnow() - cached['timestamp'] < timedelta(minutes=10):
                return {
                    **cached['results'],
                    'cache_hit': True,
                    'retrieval_time_ms': 0
                }
        
        # Generate context query
        context_query = self._build_context_query(domain, strategy, context_type)
        
        # Perform multi-faceted retrieval
        retrieval_results = self._perform_faceted_retrieval(
            context_query, domain, strategy, strategy_config, limit
        )
        
        # Score and rank memories
        scored_memories = self._score_and_rank_memories(
            retrieval_results, domain, strategy, context_type
        )
        
        # Apply limit
        top_memories = scored_memories[:limit]
        
        # Format results
        results = self._format_retrieval_results(
            top_memories, domain, strategy, context_type
        )
        
        # Update cache
        self.retrieval_cache[context_type][cache_key] = {
            'results': results,
            'timestamp': datetime.utcnow()
        }
        
        # Clean old cache entries
        self._clean_retrieval_cache()
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            **results,
            'cache_hit': False,
            'retrieval_time_ms': round(elapsed, 2),
            'context_type': context_type,
            'strategy_used': strategy.get('type', 'unknown'),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _generate_retrieval_key(self, domain: str, strategy: Dict, 
                               limit: int, context_type: str) -> str:
        """Generate cache key for retrieval"""
        import json
        
        strategy_str = json.dumps(strategy, sort_keys=True)
        key_data = f"{domain}:{strategy_str}:{limit}:{context_type}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _build_context_query(self, domain: str, strategy: Dict, 
                            context_type: str) -> Dict:
        """Build context-aware query for retrieval"""
        query = {
            'domain': domain,
            'strategy_type': strategy.get('type', 'unknown'),
            'strategy_params': strategy,
            'context_type': context_type,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Add context-specific elements
        if context_type == 'error_analysis':
            query['focus'] = 'error_patterns_and_resolutions'
        elif context_type == 'performance_optimization':
            query['focus'] = 'performance_metrics_and_optimizations'
        elif context_type == 'domain_adaptation':
            query['focus'] = 'domain_specific_patterns'
        else:  # strategy_planning
            query['focus'] = 'execution_strategies_and_outcomes'
        
        return query
    
    def _perform_faceted_retrieval(self, context_query: Dict, domain: str,
                                  strategy: Dict, strategy_config: Dict,
                                  limit: int) -> List[Dict]:
        """Perform multi-faceted retrieval using different approaches"""
        all_memories = []
        
        # 1. Similar domain retrievals
        domain_memories = self._retrieve_by_domain_similarity(
            domain, strategy_config
        )
        all_memories.extend(domain_memories)
        
        # 2. Strategy-based retrievals
        strategy_memories = self._retrieve_by_strategy_similarity(
            strategy, strategy_config
        )
        all_memories.extend(strategy_memories)
        
        # 3. Error pattern retrievals (if relevant)
        if strategy.get('has_error_context', False) or 'error' in context_query.get('focus', ''):
            error_memories = self._retrieve_error_patterns(
                domain, strategy_config
            )
            all_memories.extend(error_memories)
        
        # 4. Performance profile retrievals
        perf_memories = self._retrieve_performance_profiles(
            domain, strategy_config
        )
        all_memories.extend(perf_memories)
        
        # 5. Recent successful executions
        recent_memories = self._retrieve_recent_successes(
            domain, strategy_config
        )
        all_memories.extend(recent_memories)
        
        # Remove duplicates
        unique_memories = self._deduplicate_memories(all_memories)
        
        return unique_memories
    
    def _retrieve_by_domain_similarity(self, domain: str, 
                                      strategy_config: Dict) -> List[Dict]:
        """Retrieve memories from similar domains"""
        # Search for similar domain embeddings
        domain_embedding_result = self.embedding_generator.generate_embedding({
            'type': 'text',
            'content': domain,
            'id': f'domain_query_{domain}'
        })
        
        if not domain_embedding_result.get('success', False):
            return []
        
        domain_embedding = np.array(domain_embedding_result['embedding'], dtype=np.float32)
        
        # Search for domain-related artifacts
        search_results = self.searcher._perform_vector_search(
            query_embedding=domain_embedding,
            artifact_type='domain',
            top_k=strategy_config['max_results'],
            domain=None,
            filters={'status': 'active'},
            similarity_threshold=strategy_config['min_similarity']
        )
        
        # Extract related memories
        memories = []
        for result in search_results:
            memories.append({
                'id': result['id'],
                'domain': result.get('domain', 'unknown'),
                'artifact_type': result['artifact_type'],
                'similarity': result['similarity'],
                'metadata': result.get('metadata', {}),
                'retrieval_source': 'domain_similarity',
                'relevance_explanation': f"Similar domain pattern (similarity: {result['similarity']:.3f})"
            })
        
        return memories
    
    def _retrieve_by_strategy_similarity(self, strategy: Dict,
                                        strategy_config: Dict) -> List[Dict]:
        """Retrieve memories with similar strategies"""
        # Generate strategy embedding
        strategy_embedding_result = self.embedding_generator.generate_embedding({
            'type': 'structured',
            'content': strategy,
            'id': f'strategy_query_{hash(strategy)}'
        })
        
        if not strategy_embedding_result.get('success', False):
            return []
        
        strategy_embedding = np.array(strategy_embedding_result['embedding'], dtype=np.float32)
        
        # Search for strategy-related artifacts
        search_results = self.searcher._perform_vector_search(
            query_embedding=strategy_embedding,
            artifact_type='strategy',
            top_k=strategy_config['max_results'],
            domain=None,
            filters={'status': 'successful'},
            similarity_threshold=strategy_config['min_similarity']
        )
        
        # Extract related memories
        memories = []
        for result in search_results:
            memories.append({
                'id': result['id'],
                'strategy_type': result.get('metadata', {}).get('strategy_type', 'unknown'),
                'success_rate': result.get('metadata', {}).get('success_rate', 0.0),
                'similarity': result['similarity'],
                'metadata': result.get('metadata', {}),
                'retrieval_source': 'strategy_similarity',
                'relevance_explanation': f"Similar strategy pattern (similarity: {result['similarity']:.3f})"
            })
        
        return memories
    
    def _retrieve_error_patterns(self, domain: str,
                                strategy_config: Dict) -> List[Dict]:
        """Retrieve error-related memories"""
        # Search for recent errors in this domain
        import psycopg2
        from psycopg2.extras import Json
        
        conn = self.vector_store.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, domain, artifact_type, artifact_id, metadata, 
                           created_at, embedding
                    FROM embeddings
                    WHERE domain = %s 
                    AND artifact_type IN ('error', 'incident', 'failure')
                    AND created_at > NOW() - INTERVAL %s
                    AND metadata->>'severity' IN ('high', 'critical')
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (domain, strategy_config['time_window'], strategy_config['max_results']))
                
                memories = []
                for row in cur.fetchall():
                    memories.append({
                        'id': str(row[0]),
                        'domain': row[1],
                        'artifact_type': row[2],
                        'artifact_id': row[3],
                        'metadata': row[4],
                        'created_at': row[5].isoformat() if row[5] else None,
                        'has_embedding': row[6] is not None,
                        'retrieval_source': 'error_patterns',
                        'relevance_explanation': f"Recent error/incident in domain"
                    })
                
                return memories
                
        finally:
            self.vector_store.pool.putconn(conn)
    
    def _retrieve_performance_profiles(self, domain: str,
                                      strategy_config: Dict) -> List[Dict]:
        """Retrieve performance-related memories"""
        # Search for performance artifacts
        import psycopg2
        
        conn = self.vector_store.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, domain, artifact_type, artifact_id, metadata, 
                           created_at, embedding
                    FROM embeddings
                    WHERE domain = %s 
                    AND artifact_type IN ('performance', 'metrics', 'timing')
                    AND created_at > NOW() - INTERVAL %s
                    AND metadata->>'success' = 'true'
                    ORDER BY (metadata->>'response_time')::float ASC
                    LIMIT %s
                """, (domain, strategy_config['time_window'], strategy_config['max_results']))
                
                memories = []
                for row in cur.fetchall():
                    memories.append({
                        'id': str(row[0]),
                        'domain': row[1],
                        'artifact_type': row[2],
                        'artifact_id': row[3],
                        'metadata': row[4],
                        'created_at': row[5].isoformat() if row[5] else None,
                        'has_embedding': row[6] is not None,
                        'retrieval_source': 'performance_profiles',
                        'relevance_explanation': f"Performance profile for domain"
                    })
                
                return memories
                
        finally:
            self.vector_store.pool.putconn(conn)
    
    def _retrieve_recent_successes(self, domain: str,
                                  strategy_config: Dict) -> List[Dict]:
        """Retrieve recent successful executions"""
        import psycopg2
        
        conn = self.vector_store.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, domain, artifact_type, artifact_id, metadata, 
                           created_at, embedding
                    FROM embeddings
                    WHERE domain = %s 
                    AND artifact_type = 'execution'
                    AND created_at > NOW() - INTERVAL %s
                    AND metadata->>'success' = 'true'
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (domain, strategy_config['time_window'], strategy_config['max_results']))
                
                memories = []
                for row in cur.fetchall():
                    memories.append({
                        'id': str(row[0]),
                        'domain': row[1],
                        'artifact_type': row[2],
                        'artifact_id': row[3],
                        'metadata': row[4],
                        'created_at': row[5].isoformat() if row[5] else None,
                        'has_embedding': row[6] is not None,
                        'retrieval_source': 'recent_successes',
                        'relevance_explanation': f"Recent successful execution"
                    })
                
                return memories
                
        finally:
            self.vector_store.pool.putconn(conn)
    
    def _deduplicate_memories(self, memories: List[Dict]) -> List[Dict]:
        """Remove duplicate memories based on content and similarity"""
        unique_memories = {}
        
        for memory in memories:
            # Create unique key based on content
            if 'content_hash' in memory.get('metadata', {}):
                key = memory['metadata']['content_hash']
            else:
                key = f"{memory.get('artifact_id', '')}:{memory.get('retrieval_source', '')}"
            
            if key not in unique_memories:
                unique_memories[key] = memory
            else:
                # Keep the one with higher similarity or more recent
                existing = unique_memories[key]
                if memory.get('similarity', 0) > existing.get('similarity', 0):
                    unique_memories[key] = memory
        
        return list(unique_memories.values())
    
    def _score_and_rank_memories(self, memories: List[Dict], 
                                domain: str, strategy: Dict,
                                context_type: str) -> List[Dict]:
        """Score and rank memories based on multiple factors"""
        scored_memories = []
        
        for memory in memories:
            score = 0.0
            scoring_factors = {}
            
            # 1. Recent success factor
            if memory.get('retrieval_source') == 'recent_successes':
                recency_score = self._calculate_recency_score(memory)
                score += recency_score * self.context_weights['recent_success']
                scoring_factors['recent_success'] = recency_score
            
            # 2. Domain similarity factor
            if memory.get('similarity'):
                domain_score = memory['similarity']
                score += domain_score * self.context_weights['similar_domain']
                scoring_factors['domain_similarity'] = domain_score
            
            # 3. Strategy matching factor
            if memory.get('metadata', {}).get('strategy_type') == strategy.get('type'):
                strategy_score = 1.0
                score += strategy_score * self.context_weights['matching_strategy']
                scoring_factors['strategy_match'] = strategy_score
            elif memory.get('strategy_type') == strategy.get('type'):
                strategy_score = 0.8
                score += strategy_score * self.context_weights['matching_strategy']
                scoring_factors['strategy_match'] = strategy_score
            
            # 4. Error pattern relevance
            if 'error' in memory.get('artifact_type', '') and context_type == 'error_analysis':
                error_score = self._calculate_error_relevance(memory, strategy)
                score += error_score * self.context_weights['error_pattern']
                scoring_factors['error_relevance'] = error_score
            
            # 5. Performance profile match
            if 'performance' in memory.get('artifact_type', '') and context_type == 'performance_optimization':
                perf_score = self._calculate_performance_relevance(memory, strategy)
                score += perf_score * self.context_weights['performance_profile']
                scoring_factors['performance_relevance'] = perf_score
            
            # 6. Temporal relevance
            temporal_score = self._calculate_temporal_relevance(memory)
            score += temporal_score * self.context_weights['temporal_relevance']
            scoring_factors['temporal_relevance'] = temporal_score
            
            # 7. Metadata completeness
            metadata_score = self._calculate_metadata_completeness(memory)
            score += metadata_score * self.context_weights['metadata_completeness']
            scoring_factors['metadata_completeness'] = metadata_score
            
            # Add scoring information
            memory['relevance_score'] = round(score, 4)
            memory['scoring_factors'] = scoring_factors
            memory['normalized_score'] = round(score / sum(self.context_weights.values()), 4)
            
            scored_memories.append(memory)
        
        # Sort by relevance score
        scored_memories.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return scored_memories
    
    def _calculate_recency_score(self, memory: Dict) -> float:
        """Calculate score based on recency"""
        if 'created_at' not in memory:
            return 0.5
        
        try:
            created = datetime.fromisoformat(memory['created_at'].replace('Z', '+00:00'))
            hours_old = (datetime.utcnow() - created).total_seconds() / 3600
            
            # Exponential decay: half-life of 24 hours
            recency = 0.5 ** (hours_old / 24)
            return min(recency, 1.0)
        except:
            return 0.5
    
    def _calculate_error_relevance(self, memory: Dict, strategy: Dict) -> float:
        """Calculate error pattern relevance"""
        metadata = memory.get('metadata', {})
        
        # Check if error matches strategy context
        error_severity = metadata.get('severity', 'medium')
        strategy_risk = strategy.get('risk_tolerance', 'medium')
        
        severity_map = {'critical': 1.0, 'high': 0.8, 'medium': 0.6, 'low': 0.4}
        risk_map = {'high': 1.0, 'medium': 0.7, 'low': 0.4}
        
        severity_score = severity_map.get(error_severity, 0.5)
        risk_score = risk_map.get(strategy_risk, 0.5)
        
        # Higher relevance for matching risk profiles
        if (error_severity == 'critical' and strategy_risk == 'low'):
            return 0.3  # Low relevance
        elif (error_severity == 'low' and strategy_risk == 'high'):
            return 0.6  # Medium relevance
        else:
            return (severity_score + risk_score) / 2
    
    def _calculate_performance_relevance(self, memory: Dict, strategy: Dict) -> float:
        """Calculate performance relevance"""
        metadata = memory.get('metadata', {})
        
        # Check performance metrics
        response_time = metadata.get('response_time', 0)
        success_rate = metadata.get('success_rate', 0.0)
        
        # Normalize response time (lower is better)
        if response_time > 0:
            time_score = max(0.0, 1.0 - (response_time / 5000))  # 5s threshold
        else:
            time_score = 0.5
        
        # Success rate score
        success_score = success_rate
        
        # Strategy performance requirements
        strategy_perf = strategy.get('performance_requirement', 'balanced')
        
        if strategy_perf == 'high':
            return (time_score * 0.7 + success_score * 0.3)
        elif strategy_perf == 'balanced':
            return (time_score * 0.5 + success_score * 0.5)
        else:  # 'reliable'
            return (time_score * 0.3 + success_score * 0.7)
    
    def _calculate_temporal_relevance(self, memory: Dict) -> float:
        """Calculate temporal relevance (time of day, day of week patterns)"""
        if 'created_at' not in memory:
            return 0.5
        
        try:
            created = datetime.fromisoformat(memory['created_at'].replace('Z', '+00:00'))
            current = datetime.utcnow()
            
            # Same hour of day bonus
            if created.hour == current.hour:
                hour_score = 0.8
            # Within 3 hours
            elif abs(created.hour - current.hour) <= 3:
                hour_score = 0.6
            else:
                hour_score = 0.4
            
            # Same day of week bonus
            if created.weekday() == current.weekday():
                day_score = 0.7
            else:
                day_score = 0.5
            
            return (hour_score + day_score) / 2
            
        except:
            return 0.5
    
    def _calculate_metadata_completeness(self, memory: Dict) -> float:
        """Calculate metadata completeness score"""
        metadata = memory.get('metadata', {})
        
        required_fields = ['domain', 'artifact_type', 'timestamp', 'success']
        optional_fields = ['response_time', 'error_message', 'strategy_type', 'parameters']
        
        present_required = sum(1 for field in required_fields if field in metadata and metadata[field])
        present_optional = sum(1 for field in optional_fields if field in metadata and metadata[field])
        
        required_score = present_required / len(required_fields)
        optional_score = present_optional / len(optional_fields)
        
        return (required_score * 0.7 + optional_score * 0.3)
    
    def _format_retrieval_results(self, memories: List[Dict], domain: str,
                                 strategy: Dict, context_type: str) -> Dict:
        """Format retrieval results"""
        if not memories:
            return {
                'memories': [],
                'total_retrieved': 0,
                'max_relevance': 0.0,
                'avg_relevance': 0.0,
                'context_type': context_type,
                'domain': domain,
                'strategy_type': strategy.get('type', 'unknown')
            }
        
        relevance_scores = [m['relevance_score'] for m in memories]
        
        # Group by retrieval source
        sources = defaultdict(list)
        for memory in memories:
            sources[memory.get('retrieval_source', 'unknown')].append(memory['id'][:8])
        
        return {
            'memories': [
                {
                    'id': m['id'],
                    'artifact_type': m.get('artifact_type', 'unknown'),
                    'relevance_score': m['relevance_score'],
                    'normalized_score': m.get('normalized_score', 0.0),
                    'retrieval_source': m.get('retrieval_source', 'unknown'),
                    'relevance_explanation': m.get('relevance_explanation', ''),
                    'scoring_factors': m.get('scoring_factors', {}),
                    'metadata_summary': {
                        k: v for k, v in m.get('metadata', {}).items() 
                        if k in ['success', 'response_time', 'error_type', 'strategy_type']
                    } if m.get('metadata') else {},
                    'created_at': m.get('created_at')
                }
                for m in memories
            ],
            'total_retrieved': len(memories),
            'max_relevance': round(max(relevance_scores), 4),
            'min_relevance': round(min(relevance_scores), 4),
            'avg_relevance': round(np.mean(relevance_scores), 4),
            'retrieval_sources': dict(sources),
            'context_type': context_type,
            'domain': domain,
            'strategy_type': strategy.get('type', 'unknown'),
            'retrieval_strategy': self.retrieval_strategies.get(context_type, {})
        }
    
    def _clean_retrieval_cache(self):
        """Clean old retrieval cache entries"""
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        
        for context_type in list(self.retrieval_cache.keys()):
            cache = self.retrieval_cache[context_type]
            
            to_remove = []
            for key, entry in cache.items():
                if entry['timestamp'] < cutoff:
                    to_remove.append(key)
            
            for key in to_remove:
                del cache[key]
    
    def get_retrieval_stats(self) -> Dict:
        """Get retrieval statistics"""
        stats = {
            'total_retrievals': 0,
            'by_context_type': {},
            'cache_sizes': {},
            'avg_relevance_scores': {}
        }
        
        # Count retrievals by analyzing cache
        for context_type, cache in self.retrieval_cache.items():
            stats['cache_sizes'][context_type] = len(cache)
            stats['total_retrievals'] += len(cache)
            
            # Calculate average relevance from cached results
            relevance_scores = []
            for entry in cache.values():
                if 'results' in entry and 'memories' in entry['results']:
                    for memory in entry['results']['memories']:
                        if 'relevance_score' in memory:
                            relevance_scores.append(memory['relevance_score'])
            
            if relevance_scores:
                stats['avg_relevance_scores'][context_type] = round(np.mean(relevance_scores), 4)
        
        return {
            **stats,
            'retrieval_strategies': list(self.retrieval_strategies.keys()),
            'context_weights': self.context_weights,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def clear_cache(self, context_type: str = None):
        """Clear retrieval cache"""
        if context_type:
            if context_type in self.retrieval_cache:
                self.retrieval_cache[context_type].clear()
        else:
            self.retrieval_cache.clear()
        
        return {
            'cleared': True,
            'context_type': context_type or 'all',
            'timestamp': datetime.utcnow().isoformat()
        }

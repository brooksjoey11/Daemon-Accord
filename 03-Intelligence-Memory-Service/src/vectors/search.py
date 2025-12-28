import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import heapq

class SemanticSearcher:
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.search_cache = defaultdict(dict)
        self.search_stats = defaultdict(lambda: {'count': 0, 'avg_time': 0})
        self._initialize_search_algorithms()
    
    def _initialize_search_algorithms(self):
        """Initialize search algorithms and parameters"""
        self.search_params = {
            'default': {
                'top_k': 10,
                'similarity_threshold': 0.7,
                'max_distance': 1.0
            },
            'error': {
                'top_k': 20,
                'similarity_threshold': 0.8,
                'max_distance': 0.5
            },
            'html': {
                'top_k': 15,
                'similarity_threshold': 0.75,
                'max_distance': 0.6
            },
            'network': {
                'top_k': 25,
                'similarity_threshold': 0.65,
                'max_distance': 0.7
            }
        }
    
    def search_similar(self, query: Any, artifact_type: str = 'text', 
                      top_k: int = 10, domain: str = None, 
                      filters: Dict = None) -> Dict:
        """Search for similar artifacts using semantic similarity"""
        start_time = datetime.utcnow()
        
        # Validate inputs
        if not query:
            return {'error': 'No query provided', 'results': []}
        
        # Get search parameters
        params = self.search_params.get(artifact_type, self.search_params['default'])
        if top_k > 100:
            top_k = 100
        
        # Check cache
        cache_key = self._generate_cache_key(query, artifact_type, top_k, domain, filters)
        if cache_key in self.search_cache[artifact_type]:
            cached = self.search_cache[artifact_type][cache_key]
            if datetime.utcnow() - cached['timestamp'] < timedelta(minutes=5):
                return {
                    **cached['results'],
                    'cache_hit': True,
                    'search_time_ms': 0
                }
        
        # Generate query embedding
        from .embeddings import EmbeddingGenerator
        embedder = EmbeddingGenerator()
        
        query_artifact = {
            'type': artifact_type,
            'content': query,
            'id': 'search_query'
        }
        
        embedding_result = embedder.generate_embedding(query_artifact)
        if not embedding_result.get('success', False):
            return {
                'error': f'Failed to generate embedding: {embedding_result.get("error")}',
                'results': []
            }
        
        query_embedding = np.array(embedding_result['embedding'], dtype=np.float32)
        
        # Perform search
        search_results = self._perform_vector_search(
            query_embedding=query_embedding,
            artifact_type=artifact_type,
            top_k=top_k,
            domain=domain,
            filters=filters,
            similarity_threshold=params['similarity_threshold']
        )
        
        # Apply post-processing
        processed_results = self._process_search_results(
            search_results, 
            query_embedding, 
            artifact_type
        )
        
        # Update cache
        self.search_cache[artifact_type][cache_key] = {
            'results': processed_results,
            'timestamp': datetime.utcnow()
        }
        
        # Clean old cache entries
        self._clean_search_cache()
        
        # Update statistics
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        self._update_search_stats(artifact_type, elapsed)
        
        return {
            **processed_results,
            'cache_hit': False,
            'search_time_ms': round(elapsed, 2),
            'query_embedding_dimension': len(query_embedding),
            'model_version': embedding_result['model_version'],
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _generate_cache_key(self, query: Any, artifact_type: str, 
                           top_k: int, domain: str, filters: Dict) -> str:
        """Generate cache key for search query"""
        import hashlib
        import json
        
        query_str = str(query) if not isinstance(query, (dict, list)) else json.dumps(query, sort_keys=True)
        filters_str = json.dumps(filters, sort_keys=True) if filters else ''
        
        key_data = f"{artifact_type}:{query_str}:{top_k}:{domain}:{filters_str}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _perform_vector_search(self, query_embedding: np.ndarray, 
                              artifact_type: str, top_k: int,
                              domain: str, filters: Dict,
                              similarity_threshold: float) -> List[Dict]:
        """Perform vector similarity search in database"""
        import psycopg2
        from psycopg2.extras import Json
        
        conn = self.vector_store.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Build query
                conditions = ["artifact_type = %s", "embedding IS NOT NULL"]
                params = [artifact_type, query_embedding]
                
                if domain:
                    conditions.append("domain = %s")
                    params.insert(1, domain)
                
                if filters:
                    # Add metadata filters
                    for key, value in filters.items():
                        conditions.append(f"metadata->>%s = %s")
                        params.extend([key, str(value)])
                
                # Add similarity threshold
                conditions.append("embedding <=> %s < %s")
                params.extend([query_embedding, 1.0 - similarity_threshold])
                
                query = f"""
                    SELECT id, domain, artifact_type, artifact_id, content_hash,
                           embedding, model_version, metadata, created_at,
                           embedding <=> %s as similarity
                    FROM embeddings
                    WHERE {' AND '.join(conditions)}
                    ORDER BY embedding <=> %s
                    LIMIT %s
                """
                
                params.extend([query_embedding, query_embedding, top_k])
                
                cur.execute(query, params)
                results = []
                
                for row in cur.fetchall():
                    similarity = float(row[9])
                    if similarity <= 1.0 - similarity_threshold:
                        results.append({
                            'id': str(row[0]),
                            'domain': row[1],
                            'artifact_type': row[2],
                            'artifact_id': row[3],
                            'content_hash': row[4],
                            'embedding': row[5].tolist() if row[5] is not None else None,
                            'model_version': row[6],
                            'metadata': row[7],
                            'created_at': row[8].isoformat() if row[8] else None,
                            'similarity': round(1.0 - similarity, 4),
                            'distance': round(similarity, 4)
                        })
                
                return results
                
        finally:
            self.vector_store.pool.putconn(conn)
    
    def _process_search_results(self, results: List[Dict], 
                               query_embedding: np.ndarray,
                               artifact_type: str) -> Dict:
        """Process and enhance search results"""
        if not results:
            return {
                'results': [],
                'total_matches': 0,
                'max_similarity': 0.0,
                'avg_similarity': 0.0
            }
        
        # Calculate statistics
        similarities = [r['similarity'] for r in results]
        
        # Enhance results with additional information
        enhanced_results = []
        for result in results:
            enhanced = result.copy()
            
            # Add relevance score (combination of similarity and recency)
            similarity_score = enhanced['similarity']
            
            # Recency factor (more recent = higher score)
            if enhanced.get('created_at'):
                created = datetime.fromisoformat(enhanced['created_at'].replace('Z', '+00:00'))
                hours_old = (datetime.utcnow() - created).total_seconds() / 3600
                recency_factor = max(0.5, 1.0 - (hours_old / 168))  # 1 week half-life
            else:
                recency_factor = 0.5
            
            # Metadata quality factor
            metadata = enhanced.get('metadata', {})
            quality_factor = 1.0
            if metadata:
                # Check for completeness
                complete_fields = sum(1 for v in metadata.values() if v)
                quality_factor = min(1.0, complete_fields / 5)
            
            # Calculate combined relevance
            relevance = similarity_score * 0.6 + recency_factor * 0.3 + quality_factor * 0.1
            enhanced['relevance'] = round(relevance, 4)
            
            # Add similarity explanation
            enhanced['similarity_explanation'] = self._explain_similarity(
                similarity_score, artifact_type
            )
            
            enhanced_results.append(enhanced)
        
        # Sort by relevance
        enhanced_results.sort(key=lambda x: x['relevance'], reverse=True)
        
        # Cluster similar results
        if len(enhanced_results) > 5:
            clustered_results = self._cluster_similar_results(enhanced_results)
        else:
            clustered_results = enhanced_results
        
        return {
            'results': clustered_results[:50],  # Limit output
            'total_matches': len(results),
            'max_similarity': round(max(similarities), 4),
            'min_similarity': round(min(similarities), 4),
            'avg_similarity': round(np.mean(similarities), 4),
            'artifact_type': artifact_type,
            'query_dimension': len(query_embedding)
        }
    
    def _explain_similarity(self, similarity: float, artifact_type: str) -> str:
        """Generate human-readable similarity explanation"""
        if similarity >= 0.9:
            return "Very high similarity - near duplicate"
        elif similarity >= 0.8:
            return "High similarity - very closely related"
        elif similarity >= 0.7:
            return "Good similarity - related content"
        elif similarity >= 0.6:
            return "Moderate similarity - somewhat related"
        elif similarity >= 0.5:
            return "Low similarity - minimal relation"
        else:
            return "Very low similarity - likely unrelated"
    
    def _cluster_similar_results(self, results: List[Dict], 
                                cluster_threshold: float = 0.9) -> List[Dict]:
        """Cluster highly similar results"""
        if len(results) <= 1:
            return results
        
        # Simple clustering by similarity
        clusters = []
        used_indices = set()
        
        for i, result_i in enumerate(results):
            if i in used_indices:
                continue
            
            cluster = [result_i]
            used_indices.add(i)
            
            for j, result_j in enumerate(results[i+1:], start=i+1):
                if j in used_indices:
                    continue
                
                # Check similarity between results
                if abs(result_i['similarity'] - result_j['similarity']) < 0.05:
                    cluster.append(result_j)
                    used_indices.add(j)
            
            clusters.append(cluster)
        
        # Select representative from each cluster
        representative_results = []
        for cluster in clusters:
            if len(cluster) == 1:
                representative_results.append(cluster[0])
            else:
                # Select the result with highest relevance
                representative = max(cluster, key=lambda x: x['relevance'])
                representative['cluster_size'] = len(cluster)
                representative['cluster_members'] = [
                    {'id': r['id'], 'similarity': r['similarity']} 
                    for r in cluster[:3]  # Include top 3 cluster members
                ]
                representative_results.append(representative)
        
        return representative_results
    
    def _clean_search_cache(self):
        """Clean old search cache entries"""
        cutoff = datetime.utcnow() - timedelta(minutes=30)
        
        for artifact_type in list(self.search_cache.keys()):
            cache = self.search_cache[artifact_type]
            
            to_remove = []
            for key, entry in cache.items():
                if entry['timestamp'] < cutoff:
                    to_remove.append(key)
            
            for key in to_remove:
                del cache[key]
    
    def _update_search_stats(self, artifact_type: str, elapsed_ms: float):
        """Update search statistics"""
        stats = self.search_stats[artifact_type]
        stats['count'] += 1
        stats['avg_time'] = (stats['avg_time'] * (stats['count'] - 1) + elapsed_ms) / stats['count']
    
    def find_patterns(self, vector_cluster: List[np.ndarray], 
                     threshold: float = 0.8, min_samples: int = 3) -> Dict:
        """Find patterns in vector clusters"""
        start_time = datetime.utcnow()
        
        if len(vector_cluster) < min_samples:
            return {
                'patterns_found': 0,
                'clusters': [],
                'message': f'Insufficient vectors (need {min_samples}, got {len(vector_cluster)})'
            }
        
        try:
            # Use DBSCAN for clustering
            from sklearn.cluster import DBSCAN
            from sklearn.preprocessing import StandardScaler
            
            # Prepare data
            X = np.array(vector_cluster)
            
            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Apply DBSCAN
            eps_value = 1.0 - threshold  # Convert similarity threshold to distance
            dbscan = DBSCAN(eps=eps_value, min_samples=min_samples, metric='cosine')
            labels = dbscan.fit_predict(X_scaled)
            
            # Analyze clusters
            unique_labels = set(labels)
            n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
            n_noise = list(labels).count(-1)
            
            # Extract cluster information
            clusters = []
            for label in unique_labels:
                if label == -1:
                    continue  # Skip noise
                
                cluster_indices = np.where(labels == label)[0]
                cluster_vectors = X[cluster_indices]
                
                # Calculate centroid
                centroid = np.mean(cluster_vectors, axis=0)
                
                # Calculate cluster radius (max distance from centroid)
                distances = np.linalg.norm(cluster_vectors - centroid, axis=1)
                radius = np.max(distances)
                
                # Calculate density
                density = len(cluster_indices) / (radius + 1e-10)
                
                clusters.append({
                    'cluster_id': int(label),
                    'size': len(cluster_indices),
                    'centroid': centroid.tolist(),
                    'radius': float(radius),
                    'density': float(density),
                    'indices': cluster_indices.tolist(),
                    'avg_similarity': float(1.0 - np.mean(distances))
                })
            
            # Sort clusters by size
            clusters.sort(key=lambda x: x['size'], reverse=True)
            
            elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return {
                'patterns_found': n_clusters,
                'clusters': clusters,
                'noise_points': n_noise,
                'total_vectors': len(vector_cluster),
                'threshold': threshold,
                'min_samples': min_samples,
                'processing_time_ms': round(elapsed, 2),
                'algorithm': 'DBSCAN',
                'metric': 'cosine',
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'patterns_found': 0,
                'clusters': [],
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def find_similar_patterns_in_db(self, query_pattern: Dict, 
                                   artifact_type: str = 'structured',
                                   threshold: float = 0.8) -> Dict:
        """Find similar patterns in database"""
        # Extract or generate pattern embedding
        pattern_embedding = None
        if 'embedding' in query_pattern:
            pattern_embedding = np.array(query_pattern['embedding'], dtype=np.float32)
        elif 'centroid' in query_pattern:
            pattern_embedding = np.array(query_pattern['centroid'], dtype=np.float32)
        else:
            # Generate embedding from pattern data
            from .embeddings import EmbeddingGenerator
            embedder = EmbeddingGenerator()
            
            embedding_result = embedder.generate_embedding({
                'type': artifact_type,
                'content': query_pattern,
                'id': 'pattern_query'
            })
            
            if not embedding_result.get('success', False):
                return {'error': 'Failed to generate pattern embedding'}
            
            pattern_embedding = np.array(embedding_result['embedding'], dtype=np.float32)
        
        # Search for similar vectors
        search_results = self._perform_vector_search(
            query_embedding=pattern_embedding,
            artifact_type=artifact_type,
            top_k=50,
            domain=None,
            filters=None,
            similarity_threshold=threshold
        )
        
        # Cluster the search results
        if search_results:
            vectors = [np.array(r['embedding']) for r in search_results if r['embedding']]
            
            if len(vectors) >= 3:
                pattern_analysis = self.find_patterns(vectors, threshold, min_samples=2)
                
                return {
                    'pattern_query': {
                        'dimension': len(pattern_embedding),
                        'similarity_to_query': [r['similarity'] for r in search_results[:5]]
                    },
                    'search_results': {
                        'total_found': len(search_results),
                        'top_similarities': [r['similarity'] for r in search_results[:5]]
                    },
                    'pattern_analysis': pattern_analysis,
                    'timestamp': datetime.utcnow().isoformat()
                }
        
        return {
            'pattern_query': {'dimension': len(pattern_embedding)},
            'search_results': {'total_found': len(search_results)},
            'pattern_analysis': {'patterns_found': 0, 'clusters': []},
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_search_stats(self) -> Dict:
        """Get search statistics"""
        total_searches = 0
        total_time = 0.0
        
        for artifact_type, stats in self.search_stats.items():
            total_searches += stats['count']
            total_time += stats['avg_time'] * stats['count']
        
        avg_total_time = total_time / total_searches if total_searches > 0 else 0
        
        return {
            'total_searches': total_searches,
            'by_artifact_type': {
                artifact_type: {
                    'count': stats['count'],
                    'avg_time_ms': round(stats['avg_time'], 2)
                }
                for artifact_type, stats in self.search_stats.items()
            },
            'overall_avg_time_ms': round(avg_total_time, 2),
            'cache_sizes': {
                artifact_type: len(cache)
                for artifact_type, cache in self.search_cache.items()
            },
            'timestamp': datetime.utcnow().isoformat()
        }

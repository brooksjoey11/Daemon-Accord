import numpy as np
from typing import Dict, List, Any, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors
import json
import asyncio
from datetime import datetime
import hashlib
from collections import defaultdict

embedder = SentenceTransformer('all-MiniLM-L6-v2')

class PatternMatcher:
    def __init__(self):
        self.pattern_index = {}
        self.embedding_cache = {}
        self.knn_models = defaultdict(lambda: NearestNeighbors(n_neighbors=5, metric='cosine'))
        self.domain_patterns = defaultdict(list)
        self.similarity_cache = {}
        
    async def match_pattern(self, execution_data: Dict) -> List[Dict]:
        domain = execution_data.get('domain', 'unknown')
        
        text_for_embedding = self._prepare_text_for_embedding(execution_data)
        current_embedding = embedder.encode(text_for_embedding).reshape(1, -1)
        
        cache_key = hashlib.md5(text_for_embedding.encode()).hexdigest()
        
        if cache_key in self.similarity_cache:
            cached = self.similarity_cache[cache_key]
            if (datetime.now() - cached['timestamp']).total_seconds() < 300:
                return cached['matches']
        
        if domain not in self.pattern_index or len(self.pattern_index[domain]) < 5:
            return []
        
        domain_patterns = self.pattern_index[domain]
        pattern_embeddings = np.array([p['embedding'] for p in domain_patterns])
        
        if domain not in self.knn_models:
            self.knn_models[domain] = NearestNeighbors(n_neighbors=min(10, len(domain_patterns)), 
                                                      metric='cosine')
            self.knn_models[domain].fit(pattern_embeddings)
        
        distances, indices = self.knn_models[domain].kneighbors(current_embedding)
        
        matches = []
        for dist, idx in zip(distances[0], indices[0]):
            pattern = domain_patterns[idx]
            similarity = 1.0 - dist
            
            if similarity > 0.7 and pattern.get('success', False):
                match_info = {
                    'pattern_id': pattern.get('id', 'unknown'),
                    'similarity': float(similarity),
                    'strategy': pattern.get('strategy', ''),
                    'success_rate': pattern.get('success_rate', 0.0),
                    'avg_latency': pattern.get('avg_metrics', {}).get('latency', 0),
                    'sample_size': pattern.get('sample_size', 1),
                    'last_used': pattern.get('last_used', '')
                }
                matches.append(match_info)
        
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        result = matches[:5]
        
        self.similarity_cache[cache_key] = {
            'matches': result,
            'timestamp': datetime.now()
        }
        
        if len(self.similarity_cache) > 10000:
            oldest = min(self.similarity_cache.items(), key=lambda x: x[1]['timestamp'])
            del self.similarity_cache[oldest[0]]
        
        return result
    
    def _prepare_text_for_embedding(self, execution: Dict) -> str:
        components = [
            execution.get('domain', ''),
            execution.get('strategy', ''),
            json.dumps(execution.get('action', {}), sort_keys=True),
            json.dumps(execution.get('result', {}), sort_keys=True),
            str(execution.get('metrics', {}).get('success', False))
        ]
        
        if 'artifacts' in execution:
            components.append(' '.join(execution['artifacts']))
        
        return ' '.join(components)
    
    def index_pattern(self, pattern: Dict):
        domain = pattern.get('domain', 'unknown')
        pattern_id = pattern.get('id', hashlib.md5(json.dumps(pattern, sort_keys=True).encode()).hexdigest())
        
        text_for_embedding = self._prepare_text_for_embedding(pattern)
        embedding = embedder.encode(text_for_embedding).tolist()
        
        indexed_pattern = {
            'id': pattern_id,
            'domain': domain,
            'strategy': pattern.get('strategy', ''),
            'embedding': embedding,
            'success': pattern.get('success', False),
            'success_rate': pattern.get('success_rate', 0.0),
            'avg_metrics': pattern.get('avg_metrics', {}),
            'sample_size': pattern.get('sample_size', 1),
            'last_used': datetime.now().isoformat()
        }
        
        if domain not in self.pattern_index:
            self.pattern_index[domain] = []
        
        existing_idx = None
        for i, p in enumerate(self.pattern_index[domain]):
            if p['id'] == pattern_id:
                existing_idx = i
                break
        
        if existing_idx is not None:
            self.pattern_index[domain][existing_idx] = indexed_pattern
        else:
            self.pattern_index[domain].append(indexed_pattern)
        
        if len(self.pattern_index[domain]) > 1000:
            self.pattern_index[domain].sort(key=lambda x: x.get('last_used', ''), reverse=True)
            self.pattern_index[domain] = self.pattern_index[domain][:800]
        
        self.knn_models.pop(domain, None)
    
    async def batch_index(self, patterns: List[Dict]):
        for pattern in patterns:
            self.index_pattern(pattern)
        
        await asyncio.sleep(0)
    
    def find_similar_across_domains(self, embedding: List[float], threshold: float = 0.8) -> List[Dict]:
        all_matches = []
        
        for domain, patterns in self.pattern_index.items():
            if not patterns:
                continue
            
            pattern_embeddings = np.array([p['embedding'] for p in patterns])
            current_embedding = np.array(embedding).reshape(1, -1)
            
            distances = np.linalg.norm(pattern_embeddings - current_embedding, axis=1)
            similarities = 1.0 / (1.0 + distances)
            
            for i, similarity in enumerate(similarities):
                if similarity > threshold:
                    pattern = patterns[i]
                    if pattern.get('success_rate', 0) > 0.7:
                        all_matches.append({
                            'domain': domain,
                            'similarity': float(similarity),
                            'pattern': pattern
                        })
        
        all_matches.sort(key=lambda x: x['similarity'], reverse=True)
        return all_matches[:10]

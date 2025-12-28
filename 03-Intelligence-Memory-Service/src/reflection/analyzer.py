import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Tuple
import json
import asyncio
from datetime import datetime, timedelta
import pickle
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

embedder = SentenceTransformer('all-MiniLM-L6-v2')

class ReflectionAnalyzer:
    def __init__(self):
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self.scaler = StandardScaler()
        self.domain_models = {}
        self.pattern_cache = {}
        self.last_training = {}
        
    async def analyze_execution(self, execution_record: Dict) -> List[Dict]:
        analysis_start = datetime.now()
        
        features = self._extract_features(execution_record)
        features_scaled = self.scaler.transform([features])
        
        anomaly_score = float(self.anomaly_detector.score_samples(features_scaled)[0])
        is_anomaly = anomaly_score < -0.5
        
        domain = execution_record.get('domain', 'unknown')
        if domain not in self.domain_models:
            self.domain_models[domain] = {'clusterer': DBSCAN(eps=0.3, min_samples=5)}
        
        clusterer = self.domain_models[domain]['clusterer']
        
        text_embedding = embedder.encode(
            f"{execution_record.get('strategy', '')} " 
            f"{json.dumps(execution_record.get('action', {}))} " 
            f"{json.dumps(execution_record.get('result', {}))}"
        ).reshape(1, -1)
        
        if 'embeddings' not in self.domain_models[domain]:
            self.domain_models[domain]['embeddings'] = text_embedding
        else:
            self.domain_models[domain]['embeddings'] = np.vstack([
                self.domain_models[domain]['embeddings'],
                text_embedding
            ])
        
        if self.domain_models[domain]['embeddings'].shape[0] > 10:
            clusters = clusterer.fit_predict(self.domain_models[domain]['embeddings'])
            cluster_id = int(clusters[-1]) if clusters[-1] != -1 else -1
        else:
            cluster_id = -1
        
        reflections = []
        
        if is_anomaly:
            reflections.append({
                'type': 'anomaly_detected',
                'confidence': max(0.8, 1.0 + anomaly_score),
                'details': {
                    'anomaly_score': anomaly_score,
                    'features': features.tolist()
                },
                'timestamp': datetime.now().isoformat()
            })
        
        if cluster_id != -1:
            cluster_size = np.sum(clusters == cluster_id)
            if cluster_size > 5:
                reflections.append({
                    'type': 'pattern_recurrence',
                    'confidence': min(0.95, cluster_size / 100.0),
                    'details': {
                        'cluster_id': cluster_id,
                        'cluster_size': int(cluster_size)
                    },
                    'timestamp': datetime.now().isoformat()
                })
        
        metrics = execution_record.get('metrics', {})
        if metrics.get('success', False):
            efficiency = metrics.get('latency', 1000) / max(metrics.get('resource_usage', 1), 1)
            if efficiency < 0.5:
                reflections.append({
                    'type': 'high_efficiency',
                    'confidence': 0.9,
                    'details': {'efficiency_score': float(efficiency)},
                    'timestamp': datetime.now().isoformat()
                })
        
        execution_time = (datetime.now() - analysis_start).total_seconds() * 1000
        if execution_time > 400:
            reflections.append({
                'type': 'performance_degradation',
                'confidence': 0.7,
                'details': {'analysis_ms': execution_time},
                'timestamp': datetime.now().isoformat()
            })
        
        return reflections
    
    def _extract_features(self, execution: Dict) -> np.ndarray:
        metrics = execution.get('metrics', {})
        features = [
            float(metrics.get('latency', 0)),
            float(metrics.get('resource_usage', 0)),
            1.0 if metrics.get('success', False) else 0.0,
            len(str(execution.get('action', {}))),
            len(str(execution.get('result', {}))),
            len(execution.get('artifacts', [])),
            hash(execution.get('strategy', '')) % 100 / 100.0,
            execution.get('metrics', {}).get('error_count', 0),
            execution.get('metrics', {}).get('retry_count', 0),
            execution.get('metrics', {}).get('cache_hits', 0)
        ]
        return np.array(features)
    
    async def batch_analyze(self, executions: List[Dict]) -> Dict[str, List[Dict]]:
        results = {}
        semaphore = asyncio.Semaphore(100)
        
        async def analyze_with_semaphore(execution):
            async with semaphore:
                return await self.analyze_execution(execution)
        
        tasks = [analyze_with_semaphore(exec) for exec in executions]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(all_results):
            if not isinstance(result, Exception):
                results[str(i)] = result
        
        return results
    
    def train_models(self, execution_data: List[Dict]):
        if len(execution_data) < 100:
            return
        
        features = np.array([self._extract_features(exec) for exec in execution_data])
        
        self.scaler.fit(features)
        features_scaled = self.scaler.transform(features)
        
        self.anomaly_detector.fit(features_scaled)
        
        for domain in set(exec['domain'] for exec in execution_data):
            domain_execs = [exec for exec in execution_data if exec['domain'] == domain]
            if len(domain_execs) > 10:
                text_data = [
                    f"{exec.get('strategy', '')} " 
                    f"{json.dumps(exec.get('action', {}))} " 
                    f"{json.dumps(exec.get('result', {}))}"
                    for exec in domain_execs
                ]
                embeddings = embedder.encode(text_data)
                
                self.domain_models[domain] = {
                    'clusterer': DBSCAN(eps=0.3, min_samples=5),
                    'embeddings': embeddings
                }
                self.domain_models[domain]['clusterer'].fit(embeddings)
        
        self.last_training['timestamp'] = datetime.now()
        self.last_training['sample_size'] = len(execution_data)

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func
from . import models
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import json

embedder = SentenceTransformer('all-MiniLM-L6-v2')

class MemoryStore:
    def __init__(self, db: Session):
        self.db = db
    
    def create_execution(self, domain: str, strategy: str, action: Dict, 
                        result: Dict, metrics: Dict, artifacts: List[str]) -> models.Execution:
        text_for_embedding = f"{domain} {strategy} {json.dumps(action)} {json.dumps(result)}"
        embedding = embedder.encode(text_for_embedding).tolist()
        
        execution = models.Execution(
            domain=domain,
            strategy=strategy,
            action=action,
            result=result,
            metrics=metrics,
            artifacts=artifacts,
            embedding=embedding
        )
        
        self.db.add(execution)
        self.db.flush()
        
        if self.db.query(models.Execution).filter(models.Execution.cold_storage == False).count() > 100000:
            oldest = self.db.query(models.Execution).filter(
                models.Execution.cold_storage == False
            ).order_by(models.Execution.created_at).first()
            if oldest:
                oldest.cold_storage = True
        
        self.db.commit()
        return execution
    
    def find_similar_executions(self, embedding: List[float], domain: str, limit: int = 10) -> List[models.Execution]:
        return self.db.query(models.Execution).filter(
            models.Execution.domain == domain,
            models.Execution.cold_storage == False
        ).order_by(
            func.array_distance(models.Execution.embedding, embedding)
        ).limit(limit).all()
    
    def create_incident(self, domain: str, trigger: Dict, response: Dict, severity: int = 1) -> models.Incident:
        ltree_path = f"{domain}.{trigger.get('type', 'unknown')}"
        
        if severity >= 3:
            similar = self.db.query(models.Incident).filter(
                models.Incident.domain == domain,
                models.Incident.severity >= 3,
                models.Incident.resolved == False
            ).count()
            if similar > 0:
                severity = 4
        
        incident = models.Incident(
            domain=domain,
            severity=severity,
            trigger=trigger,
            response=response,
            ltree_path=ltree_path
        )
        
        self.db.add(incident)
        self.db.commit()
        return incident
    
    def create_reflection(self, execution_id: str, insight: str, adaptation: Dict, confidence: float) -> models.Reflection:
        reflection = models.Reflection(
            execution_id=execution_id,
            insight=insight,
            adaptation=adaptation,
            confidence=confidence
        )
        
        self.db.add(reflection)
        
        domain = self.db.query(models.Execution.domain).filter(
            models.Execution.id == execution_id
        ).scalar()
        
        existing = self.db.query(models.DomainInsight).filter(
            models.DomainInsight.domain == domain
        ).order_by(desc(models.DomainInsight.confidence)).first()
        
        if not existing or confidence > existing.confidence:
            insight_record = models.DomainInsight(
                domain=domain,
                pattern=adaptation,
                confidence=confidence,
                frequency=1
            )
            self.db.add(insight_record)
        
        self.db.commit()
        return reflection
    
    def get_domain_insights(self, domain: str, min_confidence: float = 0.7) -> List[models.DomainInsight]:
        return self.db.query(models.DomainInsight).filter(
            models.DomainInsight.domain == domain,
            models.DomainInsight.confidence >= min_confidence
        ).order_by(desc(models.DomainInsight.confidence)).all()
    
    def cluster_strategy_patterns(self, strategy: str, min_cluster_size: int = 5) -> List[models.StrategyPattern]:
        executions = self.db.query(models.Execution).filter(
            models.Execution.strategy == strategy,
            models.Execution.cold_storage == False
        ).all()
        
        if len(executions) < min_cluster_size:
            return []
        
        embeddings = np.array([e.embedding for e in executions])
        from sklearn.cluster import DBSCAN
        clusters = DBSCAN(eps=0.3, min_samples=min_cluster_size).fit_predict(embeddings)
        
        patterns = []
        for cluster_id in set(clusters):
            if cluster_id == -1:
                continue
            
            cluster_executions = [e for e, c in zip(executions, clusters) if c == cluster_id]
            cluster_center = np.mean([e.embedding for e in cluster_executions], axis=0).tolist()
            
            success_count = sum(1 for e in cluster_executions if e.metrics.get('success', False))
            success_rate = success_count / len(cluster_executions)
            
            avg_metrics = {}
            if cluster_executions:
                all_metrics = [e.metrics for e in cluster_executions]
                for key in all_metrics[0].keys():
                    if isinstance(all_metrics[0][key], (int, float)):
                        avg_metrics[key] = np.mean([m.get(key, 0) for m in all_metrics])
            
            pattern = models.StrategyPattern(
                strategy=strategy,
                cluster_center=cluster_center,
                executions=[e.id for e in cluster_executions],
                success_rate=success_rate,
                avg_metrics=avg_metrics
            )
            self.db.add(pattern)
            patterns.append(pattern)
        
        self.db.commit()
        return patterns

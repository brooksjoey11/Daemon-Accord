from .analyzer import ReflectionAnalyzer
from .recommender import StrategyRecommender
from .matcher import PatternMatcher
from .learning_loop import LearningLoop

class ReflectionEngine:
    """Main reflection engine orchestrator"""
    
    def __init__(self, model_storage_path: str = "/tmp/reflection_models"):
        self.analyzer = ReflectionAnalyzer(f"{model_storage_path}/analyzer.pkl")
        self.recommender = StrategyRecommender()
        self.matcher = PatternMatcher()
        self.learning_loop = LearningLoop(f"{model_storage_path}/learning.pkl")
        
        # Performance monitoring
        self.analysis_times = deque(maxlen=1000)
        self.recommendation_times = deque(maxlen=1000)
    
    async def analyze_execution(self, execution_record: Dict) -> List[Dict]:
        """Analyze execution with timing"""
        import time
        start = time.time()
        
        result = self.analyzer.analyze_execution(execution_record)
        
        elapsed = (time.time() - start) * 1000
        self.analysis_times.append(elapsed)
        
        # Add timing info
        for event in result:
            event['analysis_time_ms'] = elapsed
        
        return result
    
    async def recommend_strategy(self, domain: str, context: Dict) -> Dict:
        """Recommend strategy with timing"""
        import time
        start = time.time()
        
        result = self.recommender.recommend_strategy(domain, context)
        
        elapsed = (time.time() - start) * 1000
        self.recommendation_times.append(elapsed)
        result['recommendation_time_ms'] = elapsed
        
        return result
    
    async def match_pattern(self, execution_data: Dict) -> List[Dict]:
        """Match patterns with timing"""
        import time
        start = time.time()
        
        result = self.matcher.match_pattern(execution_data)
        
        elapsed = (time.time() - start) * 1000
        
        # Add timing and store successful patterns
        for match in result:
            match['matching_time_ms'] = elapsed
            if match['similarity'] > 0.8:
                self.matcher.add_pattern(execution_data)
        
        return result
    
    async def update_weights(self, feedback: Dict) -> Dict:
        """Update learning weights"""
        return self.learning_loop.update_weights(feedback)
    
    def get_performance_stats(self) -> Dict:
        """Get performance statistics"""
        return {
            'analysis': {
                'avg_ms': np.mean(self.analysis_times) if self.analysis_times else 0,
                'p95_ms': np.percentile(self.analysis_times, 95) if self.analysis_times else 0,
                'count': len(self.analysis_times)
            },
            'recommendation': {
                'avg_ms': np.mean(self.recommendation_times) if self.recommendation_times else 0,
                'p95_ms': np.percentile(self.recommendation_times, 95) if self.recommendation_times else 0,
                'count': len(self.recommendation_times)
            }
        }
    
    def retrain_models(self, executions: List[Dict]):
        """Retrain all models on execution batch"""
        print(f"Starting retraining on {len(executions)} executions")
        
        # Retrain analyzer
        for exec in executions[:50000]:
            self.analyzer.analyze_execution(exec)
        
        # Retrain learning loop
        self.learning_loop.retrain_on_batch(executions)
        
        # Save models
        self.analyzer.save_models()
        self.learning_loop.save_model()
        
        print("Retraining completed")

# Factory function for dependency injection
def create_reflection_engine() -> ReflectionEngine:
    return ReflectionEngine()

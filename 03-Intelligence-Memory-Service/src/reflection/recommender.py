import numpy as np
from typing import Dict, List, Any, Tuple
import json
from datetime import datetime, timedelta
import hashlib
from collections import defaultdict
import asyncio

class StrategyRecommender:
    def __init__(self):
        self.domain_fingerprints = {}
        self.strategy_weights = defaultdict(lambda: defaultdict(lambda: 1.0))
        self.strategy_performance = defaultdict(lambda: defaultdict(list))
        self.context_cache = {}
        self.recommendation_history = defaultdict(list)
        
    async def recommend_strategy(self, domain: str, context: Dict) -> Dict:
        start_time = datetime.now()
        
        context_hash = hashlib.md5(json.dumps(context, sort_keys=True).encode()).hexdigest()
        
        if domain in self.context_cache and context_hash in self.context_cache[domain]:
            cached = self.context_cache[domain][context_hash]
            if (datetime.now() - cached['timestamp']).total_seconds() < 300:
                return cached['recommendation']
        
        fingerprint = self._extract_fingerprint(domain, context)
        available_strategies = self._get_available_strategies(domain)
        
        if not available_strategies:
            default_rec = {
                'strategy': 'adaptive_baseline',
                'config': {'mode': 'exploratory'},
                'success_probability': 0.5,
                'confidence': 0.3
            }
            return default_rec
        
        scored_strategies = []
        for strategy in available_strategies:
            score = self._calculate_strategy_score(domain, strategy, fingerprint, context)
            scored_strategies.append((strategy, score))
        
        scored_strategies.sort(key=lambda x: x[1], reverse=True)
        
        best_strategy, best_score = scored_strategies[0]
        
        config = self._generate_strategy_config(best_strategy, domain, context)
        
        success_prob = self._estimate_success_probability(domain, best_strategy, context)
        
        recommendation = {
            'strategy': best_strategy,
            'config': config,
            'success_probability': float(success_prob),
            'confidence': float(min(0.95, best_score / 100.0)),
            'alternatives': [
                {'strategy': s, 'score': float(sc)}
                for s, sc in scored_strategies[1:4]
            ]
        }
        
        self.context_cache.setdefault(domain, {})[context_hash] = {
            'recommendation': recommendation,
            'timestamp': datetime.now()
        }
        
        if len(self.context_cache[domain]) > 1000:
            oldest = min(self.context_cache[domain].items(), 
                        key=lambda x: x[1]['timestamp'])
            del self.context_cache[domain][oldest[0]]
        
        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        if elapsed > 90:
            asyncio.create_task(self._optimize_cache(domain))
        
        return recommendation
    
    def _extract_fingerprint(self, domain: str, context: Dict) -> str:
        fingerprint_data = {
            'domain': domain,
            'context_keys': sorted(context.keys()),
            'timestamp': datetime.now().hour,
            'day_of_week': datetime.now().weekday()
        }
        
        if 'headers' in context:
            headers = context.get('headers', {})
            fingerprint_data['header_pattern'] = hashlib.md5(
                str(sorted(headers.items())).encode()
            ).hexdigest()[:8]
        
        if 'environment' in context:
            env = context.get('environment', {})
            fingerprint_data['env_hash'] = hashlib.md5(
                json.dumps(env, sort_keys=True).encode()
            ).hexdigest()[:12]
        
        return hashlib.md5(
            json.dumps(fingerprint_data, sort_keys=True).encode()
        ).hexdigest()
    
    def _get_available_strategies(self, domain: str) -> List[str]:
        base_strategies = [
            'stealth_progressive',
            'aggressive_burst',
            'distributed_fallback',
            'adaptive_baseline',
            'mimicry_pattern',
            'randomized_delay',
            'batch_processing'
        ]
        
        if domain in self.domain_fingerprints:
            successful = [
                s for s, perfs in self.strategy_performance[domain].items()
                if len(perfs) > 3 and np.mean([p.get('success', 0) for p in perfs[-3:]]) > 0.7
            ]
            if successful:
                return successful + base_strategies
        
        return base_strategies
    
    def _calculate_strategy_score(self, domain: str, strategy: str, 
                                 fingerprint: str, context: Dict) -> float:
        score = 100.0
        
        weight = self.strategy_weights[domain][strategy]
        score *= weight
        
        if domain in self.strategy_performance and strategy in self.strategy_performance[domain]:
            perfs = self.strategy_performance[domain][strategy]
            if perfs:
                recent = perfs[-10:]
                success_rate = np.mean([p.get('success', 0) for p in recent])
                avg_latency = np.mean([p.get('latency', 1000) for p in recent])
                
                score *= success_rate * 1.5
                if avg_latency < 500:
                    score *= 1.2
                elif avg_latency > 2000:
                    score *= 0.8
        
        if 'constraints' in context:
            constraints = context['constraints']
            if constraints.get('stealth_required', False) and 'stealth' not in strategy:
                score *= 0.3
            if constraints.get('speed_required', False) and 'aggressive' not in strategy:
                score *= 1.3
        
        time_factor = datetime.now().hour / 24.0
        if 'nocturnal' in strategy and 6 <= datetime.now().hour <= 18:
            score *= 0.7
        
        return max(1.0, score)
    
    def _generate_strategy_config(self, strategy: str, domain: str, context: Dict) -> Dict:
        config_templates = {
            'stealth_progressive': {
                'mode': 'progressive',
                'delay_ms': np.random.randint(100, 500),
                'jitter': True,
                'max_retries': 3,
                'timeout_seconds': 30
            },
            'aggressive_burst': {
                'mode': 'burst',
                'concurrent': 5,
                'delay_ms': 10,
                'timeout_seconds': 10,
                'fail_fast': True
            },
            'distributed_fallback': {
                'mode': 'distributed',
                'fallback_strategy': 'adaptive_baseline',
                'distribution_factor': 0.7,
                'health_check': True
            },
            'adaptive_baseline': {
                'mode': 'adaptive',
                'learning_rate': 0.1,
                'exploration_factor': 0.3,
                'window_size': 100
            },
            'mimicry_pattern': {
                'mode': 'mimicry',
                'reference_pattern': self._get_reference_pattern(domain),
                'deviation_threshold': 0.2
            }
        }
        
        base_config = config_templates.get(strategy, config_templates['adaptive_baseline'])
        
        if domain in self.strategy_performance and strategy in self.strategy_performance[domain]:
            perfs = self.strategy_performance[domain][strategy]
            if perfs:
                last_config = perfs[-1].get('config', {})
                base_config.update(last_config)
        
        if 'requirements' in context:
            reqs = context['requirements']
            if 'max_latency' in reqs:
                base_config['timeout_seconds'] = min(
                    base_config.get('timeout_seconds', 30),
                    reqs['max_latency'] / 1000
                )
        
        return base_config
    
    def _estimate_success_probability(self, domain: str, strategy: str, context: Dict) -> float:
        if domain in self.strategy_performance and strategy in self.strategy_performance[domain]:
            perfs = self.strategy_performance[domain][strategy]
            if len(perfs) >= 5:
                recent_success = [p.get('success', 0) for p in perfs[-5:]]
                base_prob = np.mean(recent_success)
            else:
                base_prob = 0.6
        else:
            base_prob = 0.5
        
        context_boost = 0.0
        if 'environment' in context:
            env = context['environment']
            if env.get('stability', 0) > 0.8:
                context_boost += 0.15
            if env.get('complexity', 0) < 0.3:
                context_boost += 0.1
        
        fingerprint_match = 0.0
        if domain in self.recommendation_history:
            similar = [h for h in self.recommendation_history[domain][-10:] 
                      if h.get('success', False)]
            if similar:
                fingerprint_match = len(similar) / 10.0
        
        return min(0.95, base_prob + context_boost + fingerprint_match * 0.2)
    
    async def _optimize_cache(self, domain: str):
        await asyncio.sleep(0.1)
        if domain in self.context_cache:
            self.context_cache[domain] = dict(
                list(self.context_cache[domain].items())[-500:]
            )
    
    def _get_reference_pattern(self, domain: str) -> Dict:
        return {}

import numpy as np
from collections import defaultdict, deque
import random
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import asyncio
import pickle
import os

class LearningLoop:
    def __init__(self, model_path: str = None):
        self.q_table = defaultdict(lambda: defaultdict(float))
        self.state_action_history = defaultdict(list)
        self.reward_trajectories = defaultdict(lambda: deque(maxlen=1000))
        self.policy = defaultdict(lambda: defaultdict(float))
        self.exploration_rate = 0.3
        self.discount_factor = 0.9
        self.learning_rate = 0.1
        self.model_path = model_path
        
        self.load_model()
        self._initialize_policies()
    
    def _initialize_policies(self):
        """Initialize default policies"""
        self.default_policies = {
            'evasion': {
                'retry_count': {'weights': [0.3, 0.4, 0.3], 'values': [1, 3, 5]},
                'timeout_ms': {'weights': [0.2, 0.3, 0.3, 0.2], 'values': [1000, 3000, 5000, 10000]},
                'backoff_factor': {'weights': [0.4, 0.3, 0.3], 'values': [1.0, 1.5, 2.0]}
            },
            'stealth': {
                'request_spacing_ms': {'weights': [0.3, 0.4, 0.3], 'values': [500, 1000, 2000]},
                'random_delay': {'weights': [0.7, 0.3], 'values': [True, False]},
                'user_agent_rotation': {'weights': [0.8, 0.2], 'values': [True, False]}
            },
            'performance': {
                'parallel_operations': {'weights': [0.2, 0.3, 0.3, 0.2], 'values': [2, 4, 8, 16]},
                'batch_size': {'weights': [0.3, 0.4, 0.3], 'values': [50, 100, 200]},
                'cache_enabled': {'weights': [0.9, 0.1], 'values': [True, False]}
            }
        }
    
    def load_model(self):
        """Load trained model from disk"""
        if self.model_path and os.path.exists(self.model_path):
            try:
                with open(self.model_path, 'rb') as f:
                    data = pickle.load(f)
                    self.q_table = data.get('q_table', defaultdict(lambda: defaultdict(float)))
                    self.policy = data.get('policy', defaultdict(lambda: defaultdict(float)))
                    self.exploration_rate = data.get('exploration_rate', 0.3)
            except:
                pass
    
    def save_model(self):
        """Save current model to disk"""
        if self.model_path:
            data = {
                'q_table': dict(self.q_table),
                'policy': dict(self.policy),
                'exploration_rate': self.exploration_rate,
                'timestamp': datetime.utcnow()
            }
            with open(self.model_path, 'wb') as f:
                pickle.dump(data, f)
    
    def update_weights(self, feedback: Dict) -> Dict:
        """Update strategy weights based on feedback using RL"""
        state = self._encode_state(feedback.get('state', {}))
        action = self._encode_action(feedback.get('action', {}))
        reward = self._calculate_reward(feedback)
        next_state = self._encode_state(feedback.get('next_state', {}))
        
        # Q-learning update
        current_q = self.q_table[state].get(action, 0.0)
        max_future_q = max(self.q_table[next_state].values()) if self.q_table[next_state] else 0.0
        
        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_future_q - current_q
        )
        
        self.q_table[state][action] = new_q
        
        # Update policy
        self._update_policy(state)
        
        # Record trajectory
        trajectory = {
            'state': state,
            'action': action,
            'reward': reward,
            'next_state': next_state,
            'timestamp': datetime.utcnow()
        }
        domain = feedback.get('domain', 'default')
        self.reward_trajectories[domain].append(trajectory)
        
        # Decay exploration rate
        self.exploration_rate *= 0.9995
        self.exploration_rate = max(self.exploration_rate, 0.05)
        
        # Periodically save model
        if random.random() < 0.01:  # 1% chance on each update
            self.save_model()
        
        return {
            'state': state,
            'action': action,
            'reward': reward,
            'new_q_value': new_q,
            'exploration_rate': self.exploration_rate,
            'domain': domain,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _encode_state(self, state_data: Dict) -> str:
        """Encode state as hash string"""
        # Extract relevant features
        features = {
            'domain': state_data.get('domain', 'unknown'),
            'success_rate': min(round(state_data.get('success_rate', 0.5) * 10) / 10, 0.9),
            'avg_duration': self._categorize_value(state_data.get('avg_duration_ms', 0), 
                                                  [0, 100, 500, 1000, 5000]),
            'error_frequency': self._categorize_value(state_data.get('error_count', 0),
                                                     [0, 1, 3, 10]),
            'time_of_day': datetime.utcnow().hour // 6
        }
        
        state_str = json.dumps(features, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]
    
    def _encode_action(self, action_data: Dict) -> str:
        """Encode action as hash string"""
        # Normalize action parameters
        normalized = {}
        for key, value in action_data.items():
            if isinstance(value, bool):
                normalized[key] = 'true' if value else 'false'
            elif isinstance(value, (int, float)):
                # Round to significant categories
                if key.endswith('_ms'):
                    normalized[key] = self._categorize_value(value, [100, 500, 1000, 5000, 10000])
                elif key.endswith('_count'):
                    normalized[key] = self._categorize_value(value, [1, 3, 5, 10])
                elif 'factor' in key:
                    normalized[key] = round(value * 2) / 2
                else:
                    normalized[key] = round(value)
            else:
                normalized[key] = str(value)
        
        action_str = json.dumps(normalized, sort_keys=True)
        return hashlib.sha256(action_str.encode()).hexdigest()[:16]
    
    def _categorize_value(self, value: float, categories: List[float]) -> str:
        """Categorize continuous value"""
        for i, cat in enumerate(categories):
            if value <= cat:
                return f"cat_{i}"
        return f"cat_{len(categories)}"
    
    def _calculate_reward(self, feedback: Dict) -> float:
        """Calculate reward from feedback"""
        base_reward = 0.0
        
        # Success reward
        if feedback.get('success', False):
            base_reward += 1.0
            
            # Efficiency bonus
            duration = feedback.get('duration_ms', 0)
            if duration < 100:
                base_reward += 0.5
            elif duration < 1000:
                base_reward += 0.2
        else:
            base_reward -= 1.0
            
            # Failure analysis penalty
            error = feedback.get('error_severity', 1)
            base_reward -= error * 0.2
        
        # Stealth reward
        if feedback.get('stealth_required', False) and feedback.get('stealth_maintained', False):
            base_reward += 0.3
        
        # Resource efficiency
        resource_usage = feedback.get('resource_usage', 0.5)
        if resource_usage < 0.3:
            base_reward += 0.2
        elif resource_usage > 0.8:
            base_reward -= 0.2
        
        # Consistency reward
        domain = feedback.get('domain', '')
        if domain in self.reward_trajectories and len(self.reward_trajectories[domain]) > 10:
            recent_rewards = [t['reward'] for t in list(self.reward_trajectories[domain])[-10:]]
            if np.std(recent_rewards) < 0.2:  # Low variance
                base_reward += 0.1
        
        return base_reward
    
    def _update_policy(self, state: str):
        """Update policy based on Q-values"""
        if state not in self.q_table or not self.q_table[state]:
            return
        
        # Softmax policy update
        q_values = list(self.q_table[state].values())
        actions = list(self.q_table[state].keys())
        
        # Temperature parameter for exploration
        temperature = max(0.1, self.exploration_rate * 2)
        
        # Softmax probabilities
        exp_values = np.exp(np.array(q_values) / temperature)
        probabilities = exp_values / np.sum(exp_values)
        
        # Update policy
        for action, prob in zip(actions, probabilities):
            self.policy[state][action] = prob
    
    def select_action(self, state_data: Dict, strategy_type: str) -> Dict:
        """Select action based on current policy"""
        state = self._encode_state(state_data)
        
        # Exploration vs exploitation
        if random.random() < self.exploration_rate:
            return self._explore_action(strategy_type)
        else:
            return self._exploit_action(state, strategy_type)
    
    def _explore_action(self, strategy_type: str) -> Dict:
        """Explore new actions"""
        action_config = {}
        
        if strategy_type in self.default_policies:
            for param, policy in self.default_policies[strategy_type].items():
                # Random selection based on weights
                value = random.choices(policy['values'], weights=policy['weights'])[0]
                action_config[param] = value
        
        # Add some random variations
        if random.random() < 0.3:
            mutation_param = random.choice(list(action_config.keys()))
            if isinstance(action_config[mutation_param], (int, float)):
                action_config[mutation_param] *= random.uniform(0.8, 1.2)
                if isinstance(action_config[mutation_param], int):
                    action_config[mutation_param] = int(action_config[mutation_param])
        
        return action_config
    
    def _exploit_action(self, state: str, strategy_type: str) -> Dict:
        """Exploit learned policy"""
        if state not in self.policy or not self.policy[state]:
            return self._explore_action(strategy_type)
        
        # Select action based on policy probabilities
        actions = list(self.policy[state].keys())
        probabilities = list(self.policy[state].values())
        
        if not actions:
            return self._explore_action(strategy_type)
        
        selected_action = random.choices(actions, weights=probabilities)[0]
        
        # Decode action from hash (simplified - in practice would maintain mapping)
        action_config = self._decode_action(selected_action, strategy_type)
        
        return action_config
    
    def _decode_action(self, action_hash: str, strategy_type: str) -> Dict:
        """Decode action hash to configuration"""
        # Simplified decoding - would maintain proper mapping in production
        action_config = {}
        
        if strategy_type in self.default_policies:
            # Use hash to deterministically generate parameters
            hash_int = int(action_hash[:8], 16)
            random.seed(hash_int)
            
            for param, policy in self.default_policies[strategy_type].items():
                value = random.choices(policy['values'], weights=policy['weights'])[0]
                action_config[param] = value
        
        return action_config
    
    def get_state_value(self, state_data: Dict) -> float:
        """Get value of current state"""
        state = self._encode_state(state_data)
        
        if state in self.q_table and self.q_table[state]:
            return max(self.q_table[state].values())
        
        return 0.0
    
    def get_action_value(self, state_data: Dict, action_data: Dict) -> float:
        """Get Q-value for state-action pair"""
        state = self._encode_state(state_data)
        action = self._encode_action(action_data)
        
        return self.q_table[state].get(action, 0.0)
    
    def get_policy_entropy(self, state_data: Dict) -> float:
        """Calculate entropy of policy for given state"""
        state = self._encode_state(state_data)
        
        if state not in self.policy or not self.policy[state]:
            return 1.0  # Maximum entropy for uniform distribution
        
        probabilities = list(self.policy[state].values())
        
        # Calculate Shannon entropy
        entropy = -sum(p * np.log(p + 1e-10) for p in probabilities)
        
        return float(entropy)
    
    async def batch_update(self, feedback_list: List[Dict]) -> List[Dict]:
        """Batch update weights"""
        results = []
        for feedback in feedback_list:
            result = self.update_weights(feedback)
            results.append(result)
        
        return results
    
    def get_learning_stats(self, domain: str = None) -> Dict:
        """Get learning statistics"""
        stats = {
            'exploration_rate': self.exploration_rate,
            'states_learned': len(self.q_table),
            'total_updates': sum(len(actions) for actions in self.q_table.values()),
            'avg_q_value': 0.0,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Calculate average Q-value
        all_q_values = []
        for state_actions in self.q_table.values():
            all_q_values.extend(state_actions.values())
        
        if all_q_values:
            stats['avg_q_value'] = float(np.mean(all_q_values))
            stats['max_q_value'] = float(max(all_q_values))
            stats['min_q_value'] = float(min(all_q_values))
        
        # Domain-specific stats
        if domain and domain in self.reward_trajectories:
            trajectories = list(self.reward_trajectories[domain])
            if trajectories:
                recent_rewards = [t['reward'] for t in trajectories[-100:]]
                stats['domain_reward_avg'] = float(np.mean(recent_rewards))
                stats['domain_reward_std'] = float(np.std(recent_rewards))
                stats['domain_updates'] = len(trajectories)
        
        return stats
    
    def retrain_on_batch(self, executions: List[Dict]):
        """Retrain on batch of historical executions"""
        if len(executions) > 50000:
            executions = random.sample(executions, 50000)
        
        print(f"Retraining on {len(executions)} executions...")
        
        # Group by domain
        executions_by_domain = defaultdict(list)
        for exec in executions:
            domain = exec.get('domain', 'default')
            executions_by_domain[domain].append(exec)
        
        # Process each domain
        for domain, domain_execs in executions_by_domain.items():
            print(f"Processing domain: {domain} ({len(domain_execs)} executions)")
            
            # Create synthetic feedback for training
            feedback_batch = []
            for i in range(0, len(domain_execs), 10):
                batch = domain_execs[i:i+10]
                if len(batch) >= 2:
                    # Create state-action-reward tuples
                    for j in range(len(batch) - 1):
                        feedback = self._create_feedback_from_executions(
                            batch[j], batch[j+1], domain
                        )
                        feedback_batch.append(feedback)
            
            # Batch update
            if feedback_batch:
                for feedback in feedback_batch:
                    self.update_weights(feedback)
        
        print("Retraining completed")
        self.save_model()
    
    def _create_feedback_from_executions(self, exec1: Dict, exec2: Dict, domain: str) -> Dict:
        """Create feedback from consecutive executions"""
        state = {
            'domain': domain,
            'success_rate': 1.0 if exec1.get('success', True) else 0.0,
            'avg_duration_ms': exec1.get('duration_ms', 0),
            'error_count': 0 if exec1.get('success', True) else 1
        }
        
        # Extract action from execution parameters
        action = exec1.get('parameters', {}).get('strategy_config', {})
        
        next_state = {
            'domain': domain,
            'success_rate': 1.0 if exec2.get('success', True) else 0.0,
            'avg_duration_ms': exec2.get('duration_ms', 0),
            'error_count': 0 if exec2.get('success', True) else 1
        }
        
        # Calculate reward
        success = exec2.get('success', True)
        duration = exec2.get('duration_ms', 0)
        
        reward = 1.0 if success else -1.0
        if success and duration < 1000:
            reward += 0.2
        elif not success and 'timeout' in str(exec2.get('error_message', '')).lower():
            reward -= 0.5
        
        return {
            'state': state,
            'action': action,
            'next_state': next_state,
            'reward': reward,
            'success': success,
            'duration_ms': duration,
            'domain': domain,
            'stealth_required': exec2.get('parameters', {}).get('stealth_mode', False),
            'stealth_maintained': success and duration < 2000,
            'resource_usage': min(duration / 5000, 1.0) if duration else 0.5
        }

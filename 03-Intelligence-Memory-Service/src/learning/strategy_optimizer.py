import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict, deque
import hashlib
import json
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')

class StrategyOptimizer:
    def __init__(self, optimization_path: str = "/tmp/strategy_optimization"):
        self.optimization_history = defaultdict(lambda: deque(maxlen=1000))
        self.parameter_bounds = self._initialize_parameter_bounds()
        self.optimization_algorithms = self._initialize_algorithms()
        self.validation_results = defaultdict(dict)
        self.optimization_path = optimization_path
        self._load_optimization_data()
    
    def _initialize_parameter_bounds(self) -> Dict:
        """Initialize parameter bounds for optimization"""
        return {
            'timeout_ms': {'min': 100, 'max': 30000, 'default': 5000, 'type': 'int'},
            'retry_count': {'min': 0, 'max': 10, 'default': 3, 'type': 'int'},
            'backoff_factor': {'min': 1.0, 'max': 5.0, 'default': 1.5, 'type': 'float'},
            'delay_ms': {'min': 0, 'max': 10000, 'default': 1000, 'type': 'int'},
            'parallel_operations': {'min': 1, 'max': 32, 'default': 4, 'type': 'int'},
            'batch_size': {'min': 1, 'max': 1000, 'default': 100, 'type': 'int'},
            'viewport_width': {'min': 320, 'max': 3840, 'default': 1920, 'type': 'int'},
            'viewport_height': {'min': 240, 'max': 2160, 'default': 1080, 'type': 'int'},
            'user_agent_rotation': {'min': 0, 'max': 1, 'default': 0, 'type': 'binary'},
            'random_delay': {'min': 0, 'max': 1, 'default': 1, 'type': 'binary'},
            'circuit_breaker': {'min': 0, 'max': 1, 'default': 1, 'type': 'binary'}
        }
    
    def _initialize_algorithms(self) -> Dict:
        """Initialize optimization algorithms"""
        return {
            'bayesian': {
                'description': 'Bayesian optimization for expensive evaluations',
                'max_iterations': 50,
                'exploration_weight': 0.1
            },
            'gradient': {
                'description': 'Gradient-based optimization for smooth objectives',
                'max_iterations': 100,
                'learning_rate': 0.1
            },
            'evolutionary': {
                'description': 'Evolutionary algorithm for complex search spaces',
                'population_size': 50,
                'generations': 20
            },
            'random_search': {
                'description': 'Random search for baseline comparison',
                'max_iterations': 100
            }
        }
    
    def _load_optimization_data(self):
        """Load optimization data from storage"""
        try:
            import pickle
            filepath = f"{self.optimization_path}/optimization_data.pkl"
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
                self.optimization_history = defaultdict(
                    lambda: deque(maxlen=1000),
                    data.get('history', {})
                )
                self.validation_results = data.get('validation', defaultdict(dict))
        except:
            pass
    
    def _save_optimization_data(self):
        """Save optimization data to storage"""
        try:
            import pickle
            import os
            os.makedirs(self.optimization_path, exist_ok=True)
            filepath = f"{self.optimization_path}/optimization_data.pkl"
            with open(filepath, 'wb') as f:
                data = {
                    'history': dict(self.optimization_history),
                    'validation': dict(self.validation_results),
                    'timestamp': datetime.utcnow()
                }
                pickle.dump(data, f)
        except:
            pass
    
    def optimize_strategy(self, strategy_type: str, feedback_data: Dict, 
                         optimization_method: str = 'bayesian') -> Dict:
        """Optimize strategy parameters based on feedback"""
        start_time = datetime.utcnow()
        
        # Validate inputs
        if not feedback_data or 'executions' not in feedback_data:
            return {
                'success': False,
                'error': 'No feedback data provided',
                'optimized_parameters': {}
            }
        
        executions = feedback_data['executions']
        if len(executions) < 10:
            return {
                'success': False,
                'error': f'Insufficient data: {len(executions)} executions (need at least 10)',
                'optimized_parameters': {}
            }
        
        # Extract relevant parameters for this strategy type
        relevant_params = self._get_relevant_parameters(strategy_type)
        
        # Prepare optimization data
        optimization_data = self._prepare_optimization_data(executions, relevant_params)
        
        if not optimization_data:
            return {
                'success': False,
                'error': 'Could not prepare optimization data',
                'optimized_parameters': {}
            }
        
        # Run optimization
        optimization_result = self._run_optimization(
            optimization_data, relevant_params, optimization_method
        )
        
        # Generate optimized parameters
        optimized_params = self._generate_optimized_parameters(
            optimization_result, relevant_params, strategy_type
        )
        
        # Validate optimized parameters
        validation_result = self._validate_optimized_parameters(
            optimized_params, executions, strategy_type
        )
        
        # Store optimization history
        self._store_optimization_history(
            strategy_type, optimized_params, validation_result, optimization_method
        )
        
        # Save data
        self._save_optimization_data()
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'success': True,
            'strategy_type': strategy_type,
            'optimized_parameters': optimized_params,
            'optimization_method': optimization_method,
            'validation_result': validation_result,
            'improvement_metrics': self._calculate_improvement_metrics(
                executions, optimized_params, validation_result
            ),
            'optimization_time_ms': round(elapsed, 2),
            'data_points_used': len(executions),
            'parameters_optimized': len(relevant_params),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _get_relevant_parameters(self, strategy_type: str) -> List[str]:
        """Get relevant parameters for strategy type"""
        parameter_groups = {
            'evasion': ['timeout_ms', 'retry_count', 'backoff_factor', 'delay_ms', 'circuit_breaker'],
            'stealth': ['delay_ms', 'random_delay', 'user_agent_rotation'],
            'performance': ['parallel_operations', 'batch_size', 'timeout_ms'],
            'resilience': ['retry_count', 'backoff_factor', 'circuit_breaker', 'timeout_ms'],
            'crawler': ['viewport_width', 'viewport_height', 'delay_ms', 'timeout_ms'],
            'api': ['timeout_ms', 'retry_count', 'backoff_factor', 'batch_size']
        }
        
        return parameter_groups.get(strategy_type, ['timeout_ms', 'retry_count', 'backoff_factor'])
    
    def _prepare_optimization_data(self, executions: List[Dict], 
                                  relevant_params: List[str]) -> Dict:
        """Prepare data for optimization"""
        # Extract parameter values and outcomes
        param_values = {param: [] for param in relevant_params}
        outcomes = []
        durations = []
        
        for exec in executions:
            strategy = exec.get('strategy', {})
            success = exec.get('success', False)
            duration = exec.get('duration_ms', 0)
            
            # Extract parameter values
            for param in relevant_params:
                if param in strategy:
                    value = strategy[param]
                    # Normalize based on parameter type
                    if param in self.parameter_bounds:
                        bounds = self.parameter_bounds[param]
                        if bounds['type'] == 'binary':
                            value = 1 if value else 0
                        elif bounds['type'] == 'int':
                            value = int(value)
                        elif bounds['type'] == 'float':
                            value = float(value)
                    
                    param_values[param].append(value)
                else:
                    # Use default if parameter not present
                    default = self.parameter_bounds.get(param, {}).get('default', 0)
                    param_values[param].append(default)
            
            # Store outcomes
            outcomes.append(1 if success else 0)
            durations.append(duration if duration > 0 else 1)
        
        # Check data quality
        for param, values in param_values.items():
            if len(values) != len(executions):
                return {}
        
        return {
            'param_values': param_values,
            'outcomes': outcomes,
            'durations': durations,
            'sample_size': len(executions)
        }
    
    def _run_optimization(self, optimization_data: Dict, 
                         relevant_params: List[str],
                         method: str = 'bayesian') -> Dict:
        """Run optimization algorithm"""
        if method not in self.optimization_algorithms:
            method = 'bayesian'
        
        algorithm_config = self.optimization_algorithms[method]
        
        if method == 'bayesian':
            return self._bayesian_optimization(optimization_data, relevant_params, algorithm_config)
        elif method == 'gradient':
            return self._gradient_optimization(optimization_data, relevant_params, algorithm_config)
        elif method == 'evolutionary':
            return self._evolutionary_optimization(optimization_data, relevant_params, algorithm_config)
        else:  # random_search
            return self._random_search_optimization(optimization_data, relevant_params, algorithm_config)
    
    def _bayesian_optimization(self, data: Dict, params: List[str], 
                              config: Dict) -> Dict:
        """Bayesian optimization"""
        # Simplified Bayesian optimization
        # In production, use libraries like scikit-optimize
        
        param_values = data['param_values']
        outcomes = data['outcomes']
        durations = data['durations']
        
        # Objective function: maximize success rate while minimizing duration
        def objective(x):
            # x is parameter values
            score = 0.0
            for i, outcome in enumerate(outcomes):
                # Calculate similarity between x and observed parameters
                similarity = 1.0
                for j, param in enumerate(params):
                    observed_val = param_values[param][i]
                    proposed_val = x[j]
                    
                    # Normalize based on bounds
                    bounds = self.parameter_bounds.get(param, {'min': 0, 'max': 1})
                    norm_observed = (observed_val - bounds['min']) / (bounds['max'] - bounds['min'])
                    norm_proposed = (proposed_val - bounds['min']) / (bounds['max'] - bounds['min'])
                    
                    similarity *= (1.0 - abs(norm_observed - norm_proposed))
                
                # Weight by outcome
                if outcome == 1:
                    score += similarity * (1.0 / (durations[i] / 1000 + 1))
                else:
                    score -= similarity * 0.5
            
            return -score  # Minimize negative score
        
        # Initial guess (average of successful executions)
        initial_guess = []
        for param in params:
            successful_values = []
            for i, outcome in enumerate(outcomes):
                if outcome == 1:
                    successful_values.append(param_values[param][i])
            
            if successful_values:
                initial_guess.append(np.mean(successful_values))
            else:
                bounds = self.parameter_bounds.get(param, {'min': 0, 'max': 1})
                initial_guess.append((bounds['min'] + bounds['max']) / 2)
        
        # Bounds
        bounds_list = []
        for param in params:
            bounds = self.parameter_bounds.get(param, {'min': 0, 'max': 1})
            bounds_list.append((bounds['min'], bounds['max']))
        
        # Run optimization
        result = minimize(
            objective,
            initial_guess,
            method='L-BFGS-B',
            bounds=bounds_list,
            options={'maxiter': config['max_iterations']}
        )
        
        return {
            'optimal_values': result.x.tolist(),
            'optimal_score': -result.fun,
            'success': result.success,
            'iterations': result.nit,
            'message': result.message,
            'algorithm': 'bayesian'
        }
    
    def _gradient_optimization(self, data: Dict, params: List[str], 
                              config: Dict) -> Dict:
        """Gradient-based optimization"""
        # Simplified gradient optimization
        param_values = data['param_values']
        outcomes = data['outcomes']
        
        # Use linear regression to find optimal parameters
        X = []
        y = []
        
        for i in range(len(outcomes)):
            features = []
            for param in params:
                val = param_values[param][i]
                # Normalize
                bounds = self.parameter_bounds.get(param, {'min': 0, 'max': 1})
                norm_val = (val - bounds['min']) / (bounds['max'] - bounds['min'])
                features.append(norm_val)
            
            X.append(features)
            y.append(outcomes[i])
        
        # Linear regression
        X_array = np.array(X)
        y_array = np.array(y)
        
        # Add bias term
        X_with_bias = np.c_[np.ones(X_array.shape[0]), X_array]
        
        try:
            # Normal equation
            theta = np.linalg.inv(X_with_bias.T @ X_with_bias) @ X_with_bias.T @ y_array
            
            # Extract optimal normalized values (ignore bias term)
            optimal_normalized = theta[1:]  # Skip bias
            
            # Convert back to original scale
            optimal_values = []
            for j, param in enumerate(params):
                bounds = self.parameter_bounds.get(param, {'min': 0, 'max': 1})
                optimal_val = optimal_normalized[j] * (bounds['max'] - bounds['min']) + bounds['min']
                
                # Clip to bounds
                optimal_val = max(bounds['min'], min(bounds['max'], optimal_val))
                optimal_values.append(optimal_val)
            
            # Predict success rate
            predicted_success = X_with_bias @ theta
            avg_success = np.mean(predicted_success)
            
            return {
                'optimal_values': optimal_values,
                'optimal_score': avg_success,
                'success': True,
                'algorithm': 'gradient'
            }
            
        except np.linalg.LinAlgError:
            # Fallback to average of successful executions
            return self._fallback_optimization(data, params)
    
    def _evolutionary_optimization(self, data: Dict, params: List[str], 
                                 config: Dict) -> Dict:
        """Evolutionary algorithm optimization"""
        # Simplified evolutionary algorithm
        population_size = config['population_size']
        generations = config['generations']
        
        # Initialize population
        population = []
        for _ in range(population_size):
            individual = []
            for param in params:
                bounds = self.parameter_bounds.get(param, {'min': 0, 'max': 1})
                individual.append(np.random.uniform(bounds['min'], bounds['max']))
            population.append(individual)
        
        # Evolution loop
        best_individual = None
        best_fitness = -float('inf')
        
        for generation in range(generations):
            # Evaluate fitness
            fitness_scores = []
            for individual in population:
                fitness = self._evaluate_individual_fitness(individual, data, params)
                fitness_scores.append(fitness)
                
                if fitness > best_fitness:
                    best_fitness = fitness
                    best_individual = individual
            
            # Selection (tournament)
            new_population = []
            for _ in range(population_size):
                # Tournament selection
                tournament = np.random.choice(range(population_size), size=3, replace=False)
                tournament_fitness = [fitness_scores[i] for i in tournament]
                winner_idx = tournament[np.argmax(tournament_fitness)]
                new_population.append(population[winner_idx].copy())
            
            # Crossover and mutation
            population = self._evolve_population(new_population, params, generation, generations)
        
        return {
            'optimal_values': best_individual,
            'optimal_score': best_fitness,
            'success': True,
            'generations': generations,
            'population_size': population_size,
            'algorithm': 'evolutionary'
        }
    
    def _evaluate_individual_fitness(self, individual: List[float], 
                                    data: Dict, params: List[str]) -> float:
        """Evaluate fitness of an individual"""
        param_values = data['param_values']
        outcomes = data['outcomes']
        durations = data['durations']
        
        fitness = 0.0
        weights = 0.0
        
        for i, outcome in enumerate(outcomes):
            # Calculate parameter similarity
            similarity = 1.0
            for j, param in enumerate(params):
                observed_val = param_values[param][i]
                proposed_val = individual[j]
                
                bounds = self.parameter_bounds.get(param, {'min': 0, 'max': 1})
                norm_observed = (observed_val - bounds['min']) / (bounds['max'] - bounds['min'])
                norm_proposed = (proposed_val - bounds['min']) / (bounds['max'] - bounds['min'])
                
                similarity *= (1.0 - abs(norm_observed - norm_proposed))
            
            # Weight by outcome and duration
            if outcome == 1:
                fitness += similarity * (1.0 / (durations[i] / 1000 + 1))
                weights += 1.0 / (durations[i] / 1000 + 1)
            else:
                fitness -= similarity * 0.5
                weights += 0.5
        
        if weights > 0:
            fitness /= weights
        
        return fitness
    
    def _evolve_population(self, population: List[List[float]], 
                          params: List[str], 
                          generation: int, max_generations: int) -> List[List[float]]:
        """Evolve population through crossover and mutation"""
        evolved = []
        
        # Elitism: keep best 10%
        elite_size = max(1, len(population) // 10)
        elite = sorted(population, key=lambda ind: self._evaluate_individual_fitness(
            ind, {'param_values': {}, 'outcomes': [], 'durations': []}, params
        ), reverse=True)[:elite_size]
        
        evolved.extend(elite)
        
        # Generate rest through crossover and mutation
        while len(evolved) < len(population):
            # Select parents
            parent1 = np.random.choice(population)
            parent2 = np.random.choice(population)
            
            # Crossover
            child = []
            for j in range(len(params)):
                if np.random.random() < 0.5:
                    child.append(parent1[j])
                else:
                    child.append(parent2[j])
            
            # Mutation (decreases over generations)
            mutation_rate = 0.1 * (1 - generation / max_generations)
            for j in range(len(params)):
                if np.random.random() < mutation_rate:
                    bounds = self.parameter_bounds.get(params[j], {'min': 0, 'max': 1})
                    child[j] = np.random.uniform(bounds['min'], bounds['max'])
            
            evolved.append(child)
        
        return evolved
    
    def _random_search_optimization(self, data: Dict, params: List[str],
                                   config: Dict) -> Dict:
        """Random search optimization"""
        max_iterations = config['max_iterations']
        
        best_individual = None
        best_fitness = -float('inf')
        
        for iteration in range(max_iterations):
            # Generate random individual
            individual = []
            for param in params:
                bounds = self.parameter_bounds.get(param, {'min': 0, 'max': 1})
                individual.append(np.random.uniform(bounds['min'], bounds['max']))
            
            # Evaluate fitness
            fitness = self._evaluate_individual_fitness(individual, data, params)
            
            if fitness > best_fitness:
                best_fitness = fitness
                best_individual = individual
        
        return {
            'optimal_values': best_individual,
            'optimal_score': best_fitness,
            'success': True,
            'iterations': max_iterations,
            'algorithm': 'random_search'
        }
    
    def _fallback_optimization(self, data: Dict, params: List[str]) -> Dict:
        """Fallback optimization when other methods fail"""
        param_values = data['param_values']
        outcomes = data['outcomes']
        
        optimal_values = []
        for param in params:
            # Average of successful executions
            successful_values = []
            for i, outcome in enumerate(outcomes):
                if outcome == 1:
                    successful_values.append(param_values[param][i])
            
            if successful_values:
                optimal_val = np.mean(successful_values)
            else:
                bounds = self.parameter_bounds.get(param, {'min': 0, 'max': 1})
                optimal_val = (bounds['min'] + bounds['max']) / 2
            
            optimal_values.append(optimal_val)
        
        return {
            'optimal_values': optimal_values,
            'optimal_score': 0.5,  # Unknown
            'success': True,
            'algorithm': 'fallback_average'
        }
    
    def _generate_optimized_parameters(self, optimization_result: Dict,
                                      relevant_params: List[str],
                                      strategy_type: str) -> Dict:
        """Generate optimized parameters from optimization result"""
        optimized_params = {}
        optimal_values = optimization_result.get('optimal_values', [])
        
        for i, param in enumerate(relevant_params):
            if i < len(optimal_values):
                value = optimal_values[i]
                bounds = self.parameter_bounds.get(param)
                
                if bounds:
                    # Apply type conversion
                    if bounds['type'] == 'int':
                        value = int(round(value))
                    elif bounds['type'] == 'binary':
                        value = bool(round(value))
                    
                    # Clip to bounds
                    value = max(bounds['min'], min(bounds['max'], value))
                
                optimized_params[param] = value
        
        # Add strategy type
        optimized_params['optimized_strategy_type'] = strategy_type
        optimized_params['optimization_timestamp'] = datetime.utcnow().isoformat()
        optimized_params['optimization_algorithm'] = optimization_result.get('algorithm', 'unknown')
        
        return optimized_params
    
    def _validate_optimized_parameters(self, optimized_params: Dict,
                                      executions: List[Dict],
                                      strategy_type: str) -> Dict:
        """Validate optimized parameters"""
        # Compare with historical data
        successful_executions = [e for e in executions if e.get('success', False)]
        
        if not successful_executions:
            return {
                'validation_passed': False,
                'reason': 'No successful executions for comparison',
                'confidence': 0.0
            }
        
        # Calculate parameter similarity with successful executions
        similarities = []
        for exec in successful_executions:
            strategy = exec.get('strategy', {})
            similarity = 0.0
            compared_params = 0
            
            for param, optimized_value in optimized_params.items():
                if param in strategy and param in self.parameter_bounds:
                    current_value = strategy[param]
                    bounds = self.parameter_bounds[param]
                    
                    # Normalize values
                    norm_optimized = (optimized_value - bounds['min']) / (bounds['max'] - bounds['min'])
                    norm_current = (current_value - bounds['min']) / (bounds['max'] - bounds['min'])
                    
                    similarity += 1.0 - abs(norm_optimized - norm_current)
                    compared_params += 1
            
            if compared_params > 0:
                similarities.append(similarity / compared_params)
        
        avg_similarity = np.mean(similarities) if similarities else 0.0
        
        # Calculate expected success rate
        baseline_success_rate = len(successful_executions) / len(executions)
        expected_improvement = min(avg_similarity * 0.3, 0.3)  # Up to 30% improvement
        
        validation_passed = avg_similarity > 0.6  # Similar to successful executions
        
        validation_key = f"{strategy_type}:{hashlib.md5(json.dumps(optimized_params, sort_keys=True).encode()).hexdigest()[:16]}"
        
        self.validation_results[validation_key] = {
            'optimized_params': optimized_params,
            'avg_similarity': avg_similarity,
            'baseline_success_rate': baseline_success_rate,
            'expected_improvement': expected_improvement,
            'validation_passed': validation_passed,
            'validation_timestamp': datetime.utcnow(),
            'sample_size': len(executions)
        }
        
        return {
            'validation_passed': validation_passed,
            'avg_similarity_to_successful': round(avg_similarity, 4),
            'baseline_success_rate': round(baseline_success_rate, 4),
            'expected_success_rate': round(baseline_success_rate + expected_improvement, 4),
            'expected_improvement': round(expected_improvement, 4),
            'confidence': round(avg_similarity, 4),
            'successful_executions_compared': len(successful_executions),
            'validation_key': validation_key
        }
    
    def _calculate_improvement_metrics(self, executions: List[Dict],
                                      optimized_params: Dict,
                                      validation_result: Dict) -> Dict:
        """Calculate improvement metrics"""
        # Extract current performance
        current_success_rate = len([e for e in executions if e.get('success', False)]) / len(executions)
        current_durations = [e.get('duration_ms', 0) for e in executions if e.get('duration_ms', 0) > 0]
        current_avg_duration = np.mean(current_durations) if current_durations else 0
        
        # Expected improvements
        expected_success_rate = validation_result.get('expected_success_rate', current_success_rate)
        expected_improvement = validation_result.get('expected_improvement', 0.0)
        
        # Calculate potential resource savings
        # Assume faster executions with better parameters
        potential_duration_reduction = expected_improvement * 0.5  # Up to 50% of success improvement
        
        return {
            'current_success_rate': round(current_success_rate, 4),
            'expected_success_rate': round(expected_success_rate, 4),
            'absolute_improvement': round(expected_success_rate - current_success_rate, 4),
            'relative_improvement': round((expected_success_rate - current_success_rate) / max(current_success_rate, 0.01), 4),
            'current_avg_duration_ms': round(current_avg_duration, 2),
            'potential_duration_reduction': round(potential_duration_reduction * 100, 1),  # Percentage
            'improvement_confidence': validation_result.get('confidence', 0.0),
            'estimated_impact': 'high' if expected_improvement > 0.2 else 'medium' if expected_improvement > 0.1 else 'low'
        }
    
    def _store_optimization_history(self, strategy_type: str,
                                   optimized_params: Dict,
                                   validation_result: Dict,
                                   optimization_method: str):
        """Store optimization history"""
        history_entry = {
            'strategy_type': strategy_type,
            'optimized_params': optimized_params,
            'validation_result': validation_result,
            'optimization_method': optimization_method,
            'timestamp': datetime.utcnow()
        }
        
        self.optimization_history[strategy_type].append(history_entry)
    
    def get_optimization_history(self, strategy_type: str = None, 
                                limit: int = 20) -> Dict:
        """Get optimization history"""
        if strategy_type:
            if strategy_type in self.optimization_history:
                history = list(self.optimization_history[strategy_type])[-limit:]
            else:
                history = []
        else:
            # Get recent optimizations across all strategies
            history = []
            for strategy, entries in self.optimization_history.items():
                history.extend(list(entries)[-5:])  # Last 5 per strategy
        
        # Sort by timestamp
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        formatted_history = []
        for entry in history[:limit]:
            formatted_history.append({
                'strategy_type': entry['strategy_type'],
                'optimization_method': entry['optimization_method'],
                'timestamp': entry['timestamp'].isoformat(),
                'validation_passed': entry['validation_result'].get('validation_passed', False),
                'expected_improvement': entry['validation_result'].get('expected_improvement', 0.0),
                'parameters_optimized': list(entry['optimized_params'].keys()),
                'optimization_key': hashlib.md5(
                    json.dumps(entry['optimized_params'], sort_keys=True).encode()
                ).hexdigest()[:16]
            })
        
        return {
            'optimization_history': formatted_history,
            'total_optimizations_tracked': sum(len(h) for h in self.optimization_history.values()),
            'strategies_optimized': list(self.optimization_history.keys()),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_optimization_stats(self) -> Dict:
        """Get optimization statistics"""
        stats = {
            'total_optimizations': 0,
            'by_strategy': {},
            'success_rate': 0,
            'average_improvement': 0.0
        }
        
        successful_optimizations = 0
        total_improvement = 0.0
        improvement_count = 0
        
        for strategy_type, history in self.optimization_history.items():
            strategy_history = list(history)
            stats['by_strategy'][strategy_type] = len(strategy_history)
            stats['total_optimizations'] += len(strategy_history)
            
            for entry in strategy_history:
                if entry['validation_result'].get('validation_passed', False):
                    successful_optimizations += 1
                
                improvement = entry['validation_result'].get('expected_improvement', 0.0)
                if improvement > 0:
                    total_improvement += improvement
                    improvement_count += 1
        
        if stats['total_optimizations'] > 0:
            stats['success_rate'] = round(successful_optimizations / stats['total_optimizations'], 4)
        
        if improvement_count > 0:
            stats['average_improvement'] = round(total_improvement / improvement_count, 4)
        
        # Validation statistics
        validation_stats = {
            'total_validations': len(self.validation_results),
            'passed_validations': sum(1 for v in self.validation_results.values() if v.get('validation_passed', False)),
            'average_confidence': np.mean([v.get('avg_similarity', 0) for v in self.validation_results.values()]) if self.validation_results else 0.0
        }
        
        return {
            'optimization_statistics': stats,
            'validation_statistics': validation_stats,
            'parameter_bounds_defined': len(self.parameter_bounds),
            'optimization_algorithms': list(self.optimization_algorithms.keys()),
            'timestamp': datetime.utcnow().isoformat()
        }

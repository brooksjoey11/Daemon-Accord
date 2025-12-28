import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict, deque
import hashlib
import json
import random
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class A_BTestRunner:
    def __init__(self, experiment_path: str = "/tmp/ab_experiments"):
        self.active_experiments = {}
        self.experiment_history = defaultdict(lambda: deque(maxlen=100))
        self.experiment_traffic_allocation = 0.05  # 5% of traffic
        self.significance_level = 0.05  # p < 0.05
        self.minimum_sample_size = 100
        self.experiment_path = experiment_path
        self._load_experiment_data()
        
    def _load_experiment_data(self):
        """Load experiment data from storage"""
        try:
            import pickle
            filepath = f"{self.experiment_path}/experiment_data.pkl"
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
                self.experiment_history = defaultdict(
                    lambda: deque(maxlen=100),
                    data.get('history', {})
                )
        except:
            pass
    
    def _save_experiment_data(self):
        """Save experiment data to storage"""
        try:
            import pickle
            import os
            os.makedirs(self.experiment_path, exist_ok=True)
            filepath = f"{self.experiment_path}/experiment_data.pkl"
            with open(filepath, 'wb') as f:
                data = {
                    'history': dict(self.experiment_history),
                    'timestamp': datetime.utcnow()
                }
                pickle.dump(data, f)
        except:
            pass
    
    def run_experiment(self, domain: str, strategy_variants: List[Dict], 
                      experiment_config: Dict = None) -> Dict:
        """Run A/B test experiment with multiple strategy variants"""
        start_time = datetime.utcnow()
        
        # Validate inputs
        if not domain:
            return {'success': False, 'error': 'Domain is required'}
        
        if len(strategy_variants) < 2:
            return {'success': False, 'error': 'Need at least 2 strategy variants'}
        
        # Create experiment
        experiment_id = hashlib.md5(
            f"{domain}:{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:16]
        
        # Default configuration
        config = {
            'traffic_percentage': self.experiment_traffic_allocation,
            'significance_level': self.significance_level,
            'minimum_sample_size': self.minimum_sample_size,
            'max_duration_hours': 24,
            'primary_metric': 'success_rate',
            'secondary_metrics': ['avg_duration_ms', 'error_rate'],
            'randomization_seed': random.randint(1, 10000)
        }
        
        if experiment_config:
            config.update(experiment_config)
        
        # Initialize experiment
        experiment = {
            'experiment_id': experiment_id,
            'domain': domain,
            'variants': self._initialize_variants(strategy_variants),
            'config': config,
            'start_time': datetime.utcnow(),
            'status': 'active',
            'assignments': defaultdict(int),
            'results': defaultdict(lambda: defaultdict(list)),
            'statistical_tests': {}
        }
        
        # Store experiment
        self.active_experiments[experiment_id] = experiment
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'success': True,
            'experiment_id': experiment_id,
            'domain': domain,
            'variants_count': len(strategy_variants),
            'traffic_allocation': config['traffic_percentage'],
            'minimum_sample_size': config['minimum_sample_size'],
            'expected_duration_hours': config['max_duration_hours'],
            'setup_time_ms': round(elapsed, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _initialize_variants(self, strategy_variants: List[Dict]) -> List[Dict]:
        """Initialize experiment variants"""
        variants = []
        
        for i, variant in enumerate(strategy_variants):
            variant_id = hashlib.md5(
                json.dumps(variant, sort_keys=True).encode()
            ).hexdigest()[:16]
            
            variants.append({
                'variant_id': variant_id,
                'variant_name': f"variant_{i+1}",
                'strategy_config': variant,
                'allocation_percentage': 1.0 / len(strategy_variants),  # Equal allocation
                'assigned_count': 0,
                'success_count': 0,
                'total_count': 0,
                'performance_metrics': {}
            })
        
        return variants
    
    def assign_to_experiment(self, domain: str, execution_context: Dict) -> Optional[Dict]:
        """Assign execution to an active experiment"""
        # Check if domain has active experiments
        domain_experiments = [
            exp for exp in self.active_experiments.values() 
            if exp['domain'] == domain and exp['status'] == 'active'
        ]
        
        if not domain_experiments:
            return None
        
        # Random selection based on traffic allocation
        for experiment in domain_experiments:
            if random.random() < experiment['config']['traffic_percentage']:
                # Select variant based on allocation percentages
                variant = self._select_variant(experiment)
                
                if variant:
                    experiment['assignments'][variant['variant_id']] += 1
                    variant['assigned_count'] += 1
                    
                    return {
                        'experiment_id': experiment['experiment_id'],
                        'variant_id': variant['variant_id'],
                        'variant_name': variant['variant_name'],
                        'strategy_config': variant['strategy_config'],
                        'assignment_timestamp': datetime.utcnow().isoformat()
                    }
        
        return None
    
    def _select_variant(self, experiment: Dict) -> Optional[Dict]:
        """Select variant for assignment"""
        variants = experiment['variants']
        
        # Calculate total assignments
        total_assignments = sum(v['assigned_count'] for v in variants)
        
        if total_assignments == 0:
            # First assignment, use allocation percentages
            allocation_sum = 0.0
            random_value = random.random()
            
            for variant in variants:
                allocation_sum += variant['allocation_percentage']
                if random_value <= allocation_sum:
                    return variant
        
        # Use adaptive allocation based on performance
        # (Multi-armed bandit style)
        return self._adaptive_variant_selection(variants)
    
    def _adaptive_variant_selection(self, variants: List[Dict]) -> Dict:
        """Adaptive variant selection using Thompson sampling"""
        # Calculate success rates with pseudocounts
        variant_scores = []
        
        for variant in variants:
            alpha = variant['success_count'] + 1  # Successes + pseudocount
            beta = variant['total_count'] - variant['success_count'] + 1  # Failures + pseudocount
            
            # Sample from Beta distribution
            sampled_success_rate = np.random.beta(alpha, beta)
            variant_scores.append((sampled_success_rate, variant))
        
        # Select variant with highest sampled success rate
        variant_scores.sort(key=lambda x: x[0], reverse=True)
        return variant_scores[0][1]
    
    def record_experiment_result(self, experiment_id: str, variant_id: str, 
                                execution_result: Dict):
        """Record experiment execution result"""
        if experiment_id not in self.active_experiments:
            return
        
        experiment = self.active_experiments[experiment_id]
        
        # Find variant
        variant = None
        for v in experiment['variants']:
            if v['variant_id'] == variant_id:
                variant = v
                break
        
        if not variant:
            return
        
        # Update variant statistics
        variant['total_count'] += 1
        
        if execution_result.get('success', False):
            variant['success_count'] += 1
        
        # Record detailed results
        result_entry = {
            'timestamp': datetime.utcnow(),
            'success': execution_result.get('success', False),
            'duration_ms': execution_result.get('duration_ms', 0),
            'error_type': self._extract_error_type(execution_result),
            'resource_usage': execution_result.get('resource_usage', {}),
            'metadata': {k: v for k, v in execution_result.items() 
                        if k not in ['success', 'duration_ms', 'error_type', 'resource_usage']}
        }
        
        experiment['results'][variant_id]['executions'].append(result_entry)
        
        # Check if experiment should be concluded
        self._check_experiment_conclusion(experiment)
    
    def _extract_error_type(self, execution_result: Dict) -> str:
        """Extract error type from execution result"""
        if execution_result.get('success', True):
            return 'none'
        
        error_msg = str(execution_result.get('error_message', '')).lower()
        
        if 'timeout' in error_msg:
            return 'timeout'
        elif 'connection' in error_msg:
            return 'network'
        elif 'permission' in error_msg:
            return 'permission'
        else:
            return 'other'
    
    def _check_experiment_conclusion(self, experiment: Dict):
        """Check if experiment should be concluded"""
        # Check sample size
        total_samples = sum(v['total_count'] for v in experiment['variants'])
        if total_samples < experiment['config']['minimum_sample_size']:
            return
        
        # Check duration
        hours_running = (datetime.utcnow() - experiment['start_time']).total_seconds() / 3600
        if hours_running > experiment['config']['max_duration_hours']:
            self._conclude_experiment(experiment['experiment_id'])
            return
        
        # Check statistical significance
        if self._check_statistical_significance(experiment):
            self._conclude_experiment(experiment['experiment_id'])
    
    def _check_statistical_significance(self, experiment: Dict) -> bool:
        """Check if results are statistically significant"""
        variants = experiment['variants']
        
        if len(variants) < 2:
            return False
        
        # Get primary metric data
        success_rates = []
        sample_sizes = []
        
        for variant in variants:
            if variant['total_count'] > 0:
                success_rate = variant['success_count'] / variant['total_count']
                success_rates.append(success_rate)
                sample_sizes.append(variant['total_count'])
        
        if len(success_rates) < 2:
            return False
        
        # Perform chi-square test for independence
        # Create contingency table
        contingency_table = []
        for variant in variants:
            if variant['total_count'] > 0:
                contingency_table.append([
                    variant['success_count'],
                    variant['total_count'] - variant['success_count']
                ])
        
        if len(contingency_table) >= 2:
            try:
                chi2, p_value, _, _ = stats.chi2_contingency(contingency_table)
                
                experiment['statistical_tests']['chi_square'] = {
                    'chi2_statistic': round(chi2, 4),
                    'p_value': round(p_value, 6),
                    'significant': p_value < experiment['config']['significance_level']
                }
                
                return p_value < experiment['config']['significance_level']
            except:
                pass
        
        return False
    
    def _conclude_experiment(self, experiment_id: str):
        """Conclude experiment and analyze results"""
        if experiment_id not in self.active_experiments:
            return
        
        experiment = self.active_experiments[experiment_id]
        experiment['status'] = 'concluded'
        experiment['end_time'] = datetime.utcnow()
        
        # Perform final analysis
        analysis_results = self._analyze_experiment_results(experiment)
        experiment['analysis'] = analysis_results
        
        # Determine winner
        winner = self._determine_experiment_winner(experiment, analysis_results)
        experiment['winner'] = winner
        
        # Store in history
        domain = experiment['domain']
        self.experiment_history[domain].append(experiment)
        
        # Save data
        self._save_experiment_data()
        
        # Remove from active experiments
        del self.active_experiments[experiment_id]
    
    def _analyze_experiment_results(self, experiment: Dict) -> Dict:
        """Analyze experiment results comprehensively"""
        variants = experiment['variants']
        
        analysis = {
            'variant_comparisons': [],
            'statistical_tests': {},
            'practical_significance': {},
            'confidence_intervals': {},
            'duration_analysis': {},
            'error_analysis': {}
        }
        
        # Compare each variant
        for i, variant in enumerate(variants):
            if variant['total_count'] == 0:
                continue
            
            variant_analysis = self._analyze_variant_results(variant, experiment)
            analysis['variant_comparisons'].append(variant_analysis)
        
        # Perform statistical tests
        analysis['statistical_tests'] = self._perform_statistical_tests(variants)
        
        # Calculate practical significance
        analysis['practical_significance'] = self._calculate_practical_significance(variants)
        
        # Calculate confidence intervals
        analysis['confidence_intervals'] = self._calculate_confidence_intervals(variants)
        
        # Analyze duration differences
        analysis['duration_analysis'] = self._analyze_duration_differences(experiment)
        
        # Analyze error patterns
        analysis['error_analysis'] = self._analyze_error_patterns(experiment)
        
        return analysis
    
    def _analyze_variant_results(self, variant: Dict, experiment: Dict) -> Dict:
        """Analyze results for a single variant"""
        success_rate = variant['success_count'] / variant['total_count'] if variant['total_count'] > 0 else 0
        
        # Calculate confidence interval for success rate
        if variant['total_count'] > 0:
            ci_lower, ci_upper = self._calculate_proportion_ci(
                variant['success_count'], variant['total_count']
            )
        else:
            ci_lower = ci_upper = 0
        
        # Calculate other metrics
        executions = experiment['results'][variant['variant_id']]['executions']
        durations = [e['duration_ms'] for e in executions if e['duration_ms'] > 0]
        
        if durations:
            avg_duration = np.mean(durations)
            p95_duration = np.percentile(durations, 95)
        else:
            avg_duration = p95_duration = 0
        
        # Error analysis
        error_counts = defaultdict(int)
        for execution in executions:
            if not execution['success']:
                error_counts[execution['error_type']] += 1
        
        return {
            'variant_id': variant['variant_id'],
            'variant_name': variant['variant_name'],
            'sample_size': variant['total_count'],
            'success_rate': round(success_rate, 4),
            'success_count': variant['success_count'],
            'failure_count': variant['total_count'] - variant['success_count'],
            'success_rate_ci': [round(ci_lower, 4), round(ci_upper, 4)],
            'avg_duration_ms': round(avg_duration, 2),
            'p95_duration_ms': round(p95_duration, 2),
            'error_distribution': dict(error_counts)
        }
    
    def _calculate_proportion_ci(self, successes: int, total: int, 
                                confidence: float = 0.95) -> Tuple[float, float]:
        """Calculate confidence interval for proportion"""
        if total == 0:
            return 0.0, 0.0
        
        p = successes / total
        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        
        margin = z * np.sqrt(p * (1 - p) / total)
        
        lower = max(0, p - margin)
        upper = min(1, p + margin)
        
        return lower, upper
    
    def _perform_statistical_tests(self, variants: List[Dict]) -> Dict:
        """Perform statistical tests on variant results"""
        tests = {}
        
        if len(variants) < 2:
            return tests
        
        # Prepare data for tests
        variant_data = []
        for variant in variants:
            if variant['total_count'] > 0:
                # Create binary success/failure array
                successes = [1] * variant['success_count']
                failures = [0] * (variant['total_count'] - variant['success_count'])
                variant_data.append(successes + failures)
        
        if len(variant_data) >= 2:
            # Chi-square test
            contingency_table = []
            for variant in variants:
                if variant['total_count'] > 0:
                    contingency_table.append([
                        variant['success_count'],
                        variant['total_count'] - variant['success_count']
                    ])
            
            if len(contingency_table) >= 2:
                try:
                    chi2, p_value, _, _ = stats.chi2_contingency(contingency_table)
                    tests['chi_square_test'] = {
                        'statistic': round(chi2, 4),
                        'p_value': round(p_value, 6),
                        'significant': p_value < 0.05,
                        'degrees_of_freedom': (len(contingency_table) - 1) * (2 - 1)
                    }
                except:
                    pass
            
            # ANOVA for durations (if we had duration data)
            # This would require actual duration arrays
        
        return tests
    
    def _calculate_practical_significance(self, variants: List[Dict]) -> Dict:
        """Calculate practical significance measures"""
        if len(variants) < 2:
            return {}
        
        # Find best and worst performing variants
        variants_with_data = [v for v in variants if v['total_count'] > 0]
        
        if len(variants_with_data) < 2:
            return {}
        
        # Calculate success rates
        success_rates = []
        for variant in variants_with_data:
            success_rate = variant['success_count'] / variant['total_count']
            success_rates.append((success_rate, variant['variant_name']))
        
        success_rates.sort(key=lambda x: x[0], reverse=True)
        
        best_rate, best_name = success_rates[0]
        worst_rate, worst_name = success_rates[-1]
        
        # Calculate effect sizes
        absolute_difference = best_rate - worst_rate
        relative_improvement = absolute_difference / max(worst_rate, 0.01)
        
        # Number Needed to Treat (NNT)
        nnt = 1 / absolute_difference if absolute_difference > 0 else float('inf')
        
        return {
            'best_performer': best_name,
            'worst_performer': worst_name,
            'absolute_difference': round(absolute_difference, 4),
            'relative_improvement': round(relative_improvement, 4),
            'number_needed_to_treat': round(nnt, 2) if nnt != float('inf') else 'infinite',
            'practical_significance': 'high' if absolute_difference > 0.1 else 'medium' if absolute_difference > 0.05 else 'low'
        }
    
    def _calculate_confidence_intervals(self, variants: List[Dict]) -> Dict:
        """Calculate confidence intervals for all variants"""
        ci_results = {}
        
        for variant in variants:
            if variant['total_count'] > 0:
                ci_lower, ci_upper = self._calculate_proportion_ci(
                    variant['success_count'], variant['total_count']
                )
                
                ci_results[variant['variant_name']] = {
                    'point_estimate': round(variant['success_count'] / variant['total_count'], 4),
                    'confidence_interval': [round(ci_lower, 4), round(ci_upper, 4)],
                    'interval_width': round(ci_upper - ci_lower, 4),
                    'sample_size': variant['total_count']
                }
        
        return ci_results
    
    def _analyze_duration_differences(self, experiment: Dict) -> Dict:
        """Analyze duration differences between variants"""
        analysis = {
            'duration_comparisons': [],
            'statistical_tests': {}
        }
        
        variants = experiment['variants']
        
        # Collect duration data
        duration_data = {}
        for variant in variants:
            executions = experiment['results'][variant['variant_id']]['executions']
            durations = [e['duration_ms'] for e in executions if e['duration_ms'] > 0]
            
            if durations:
                duration_data[variant['variant_name']] = durations
        
        # Compare durations
        if len(duration_data) >= 2:
            variant_names = list(duration_data.keys())
            
            for i in range(len(variant_names)):
                for j in range(i + 1, len(variant_names)):
                    name1 = variant_names[i]
                    name2 = variant_names[j]
                    
                    durations1 = duration_data[name1]
                    durations2 = duration_data[name2]
                    
                    if len(durations1) >= 5 and len(durations2) >= 5:
                        # Calculate statistics
                        mean1 = np.mean(durations1)
                        mean2 = np.mean(durations2)
                        
                        # Perform t-test
                        try:
                            t_stat, p_value = stats.ttest_ind(durations1, durations2, equal_var=False)
                            
                            analysis['duration_comparisons'].append({
                                'comparison': f"{name1} vs {name2}",
                                'mean_difference': round(mean1 - mean2, 2),
                                'relative_difference': round((mean1 - mean2) / max(mean1, mean2), 4),
                                't_statistic': round(t_stat, 4),
                                'p_value': round(p_value, 6),
                                'significant': p_value < 0.05
                            })
                        except:
                            pass
        
        return analysis
    
    def _analyze_error_patterns(self, experiment: Dict) -> Dict:
        """Analyze error patterns across variants"""
        error_analysis = {
            'error_distributions': {},
            'error_rate_comparisons': []
        }
        
        variants = experiment['variants']
        
        # Calculate error rates by variant
        for variant in variants:
            if variant['total_count'] > 0:
                error_rate = 1 - (variant['success_count'] / variant['total_count'])
                
                # Get error types
                executions = experiment['results'][variant['variant_id']]['executions']
                error_types = defaultdict(int)
                
                for execution in executions:
                    if not execution['success']:
                        error_types[execution['error_type']] += 1
                
                error_analysis['error_distributions'][variant['variant_name']] = {
                    'error_rate': round(error_rate, 4),
                    'total_errors': variant['total_count'] - variant['success_count'],
                    'error_types': dict(error_types)
                }
        
        # Compare error rates
        variant_names = list(error_analysis['error_distributions'].keys())
        
        for i in range(len(variant_names)):
            for j in range(i + 1, len(variant_names)):
                name1 = variant_names[i]
                name2 = variant_names[j]
                
                data1 = error_analysis['error_distributions'][name1]
                data2 = error_analysis['error_distributions'][name2]
                
                error_rate_diff = data1['error_rate'] - data2['error_rate']
                relative_diff = error_rate_diff / max(data1['error_rate'], data2['error_rate'], 0.01)
                
                error_analysis['error_rate_comparisons'].append({
                    'comparison': f"{name1} vs {name2}",
                    'absolute_difference': round(error_rate_diff, 4),
                    'relative_difference': round(relative_diff, 4),
                    'lower_error_rate_variant': name1 if data1['error_rate'] < data2['error_rate'] else name2
                })
        
        return error_analysis
    
    def _determine_experiment_winner(self, experiment: Dict, analysis: Dict) -> Dict:
        """Determine experiment winner based on analysis"""
        variants = experiment['variants']
        
        if not variants:
            return {'winner': 'none', 'reason': 'no_variants'}
        
        # Find variant with highest success rate and sufficient sample size
        valid_variants = []
        for variant in variants:
            if variant['total_count'] >= 10:  # Minimum samples for consideration
                success_rate = variant['success_count'] / variant['total_count']
                valid_variants.append((success_rate, variant['variant_name'], variant['variant_id']))
        
        if not valid_variants:
            return {'winner': 'none', 'reason': 'insufficient_samples'}
        
        # Sort by success rate
        valid_variants.sort(key=lambda x: x[0], reverse=True)
        
        best_rate, best_name, best_id = valid_variants[0]
        
        # Check if best is significantly better than others
        statistical_tests = analysis.get('statistical_tests', {})
        chi_square_test = statistical_tests.get('chi_square_test', {})
        
        if chi_square_test.get('significant', False):
            # Statistically significant winner
            return {
                'winner': best_name,
                'winner_id': best_id,
                'success_rate': round(best_rate, 4),
                'confidence': 'high',
                'reason': 'statistically_significant',
                'p_value': chi_square_test.get('p_value', 1.0)
            }
        else:
            # No statistical significance, but practical significance
            practical_sig = analysis.get('practical_significance', {})
            absolute_diff = practical_sig.get('absolute_difference', 0)
            
            if absolute_diff > 0.05:  # 5% practical difference
                return {
                    'winner': best_name,
                    'winner_id': best_id,
                    'success_rate': round(best_rate, 4),
                    'confidence': 'medium',
                    'reason': 'practically_significant',
                    'absolute_difference': round(absolute_diff, 4)
                }
            else:
                return {
                    'winner': 'none',
                    'reason': 'no_significant_difference',
                    'best_performer': best_name,
                    'best_success_rate': round(best_rate, 4),
                    'recommendation': 'continue_with_current_strategy'
                }
    
    def get_experiment_results(self, experiment_id: str) -> Dict:
        """Get results for a specific experiment"""
        # Check active experiments
        if experiment_id in self.active_experiments:
            experiment = self.active_experiments[experiment_id]
            return self._format_experiment_results(experiment)
        
        # Check history
        for domain, experiments in self.experiment_history.items():
            for exp in experiments:
                if exp.get('experiment_id') == experiment_id:
                    return self._format_experiment_results(exp)
        
        return {'error': 'Experiment not found'}
    
    def _format_experiment_results(self, experiment: Dict) -> Dict:
        """Format experiment results for output"""
        status = experiment.get('status', 'unknown')
        
        result = {
            'experiment_id': experiment['experiment_id'],
            'domain': experiment['domain'],
            'status': status,
            'start_time': experiment['start_time'].isoformat() if isinstance(experiment['start_time'], datetime) else experiment['start_time'],
            'variants_count': len(experiment['variants']),
            'traffic_allocation': experiment['config']['traffic_percentage'],
            'sample_sizes': {
                v['variant_name']: v['total_count']
                for v in experiment['variants']
            }
        }
        
        if status == 'concluded':
            result.update({
                'end_time': experiment['end_time'].isoformat() if isinstance(experiment['end_time'], datetime) else experiment['end_time'],
                'duration_hours': round(
                    (experiment['end_time'] - experiment['start_time']).total_seconds() / 3600, 2
                ) if isinstance(experiment['end_time'], datetime) and isinstance(experiment['start_time'], datetime) else 0,
                'winner': experiment.get('winner', {}),
                'analysis_summary': self._summarize_analysis(experiment.get('analysis', {})),
                'total_executions': sum(v['total_count'] for v in experiment['variants'])
            })
        elif status == 'active':
            result.update({
                'current_progress': self._calculate_experiment_progress(experiment),
                'estimated_completion': self._estimate_completion_time(experiment)
            })
        
        return result
    
    def _summarize_analysis(self, analysis: Dict) -> Dict:
        """Summarize experiment analysis"""
        summary = {
            'statistical_significance': False,
            'practical_significance': 'low',
            'key_findings': []
        }
        
        # Check statistical significance
        tests = analysis.get('statistical_tests', {})
        chi_test = tests.get('chi_square_test', {})
        
        if chi_test.get('significant', False):
            summary['statistical_significance'] = True
            summary['p_value'] = chi_test.get('p_value', 1.0)
        
        # Check practical significance
        practical = analysis.get('practical_significance', {})
        summary['practical_significance'] = practical.get('practical_significance', 'low')
        summary['best_performer'] = practical.get('best_performer', 'unknown')
        summary['absolute_difference'] = practical.get('absolute_difference', 0.0)
        
        # Generate key findings
        if summary['statistical_significance']:
            summary['key_findings'].append(
                f"Statistically significant difference found (p = {chi_test.get('p_value', 0.0):.4f})"
            )
        
        if summary['practical_significance'] in ['high', 'medium']:
            summary['key_findings'].append(
                f"Practically significant improvement: {practical.get('absolute_difference', 0.0):.2%}"
            )
        
        # Add duration findings
        duration_analysis = analysis.get('duration_analysis', {})
        for comparison in duration_analysis.get('duration_comparisons', []):
            if comparison.get('significant', False):
                summary['key_findings'].append(
                    f"Significant duration difference: {comparison['comparison']} "
                    f"(mean diff: {comparison['mean_difference']:.0f}ms)"
                )
        
        return summary
    
    def _calculate_experiment_progress(self, experiment: Dict) -> Dict:
        """Calculate experiment progress"""
        total_samples = sum(v['total_count'] for v in experiment['variants'])
        target_samples = experiment['config']['minimum_sample_size']
        
        hours_running = (datetime.utcnow() - experiment['start_time']).total_seconds() / 3600
        max_hours = experiment['config']['max_duration_hours']
        
        sample_progress = min(total_samples / target_samples, 1.0) if target_samples > 0 else 0
        time_progress = min(hours_running / max_hours, 1.0) if max_hours > 0 else 0
        
        overall_progress = max(sample_progress, time_progress)
        
        return {
            'sample_progress': round(sample_progress, 4),
            'time_progress': round(time_progress, 4),
            'overall_progress': round(overall_progress, 4),
            'current_samples': total_samples,
            'target_samples': target_samples,
            'hours_elapsed': round(hours_running, 2),
            'max_hours': max_hours,
            'completion_estimate_hours': round((target_samples - total_samples) * max_hours / max(total_samples, 1), 2) if total_samples > 0 else max_hours
        }
    
    def _estimate_completion_time(self, experiment: Dict) -> str:
        """Estimate experiment completion time"""
        progress = self._calculate_experiment_progress(experiment)
        
        if progress['overall_progress'] >= 1.0:
            return 'ready_for_analysis'
        
        remaining_hours = progress['completion_estimate_hours']
        
        if remaining_hours < 1:
            return f"{int(remaining_hours * 60)} minutes"
        elif remaining_hours < 24:
            return f"{remaining_hours:.1f} hours"
        else:
            return f"{remaining_hours/24:.1f} days"
    
    def get_active_experiments(self) -> List[Dict]:
        """Get list of active experiments"""
        active = []
        
        for experiment_id, experiment in self.active_experiments.items():
            if experiment['status'] == 'active':
                active.append({
                    'experiment_id': experiment_id,
                    'domain': experiment['domain'],
                    'start_time': experiment['start_time'].isoformat() if isinstance(experiment['start_time'], datetime) else experiment['start_time'],
                    'variants_count': len(experiment['variants']),
                    'total_assignments': sum(experiment['assignments'].values()),
                    'progress': self._calculate_experiment_progress(experiment)
                })
        
        return active
    
    def get_experiment_history(self, domain: str = None, limit: int = 20) -> Dict:
        """Get experiment history"""
        history = []
        
        if domain:
            if domain in self.experiment_history:
                history = list(self.experiment_history[domain])[-limit:]
        else:
            # Get from all domains
            all_experiments = []
            for domain_exps in self.experiment_history.values():
                all_experiments.extend(list(domain_exps)[-5:])
            
            history = sorted(all_experiments, key=lambda x: x['start_time'], reverse=True)[:limit]
        
        formatted_history = []
        for exp in history:
            winner = exp.get('winner', {})
            formatted_history.append({
                'experiment_id': exp['experiment_id'],
                'domain': exp['domain'],
                'status': exp['status'],
                'start_time': exp['start_time'].isoformat() if isinstance(exp['start_time'], datetime) else exp['start_time'],
                'end_time': exp.get('end_time', '').isoformat() if isinstance(exp.get('end_time'), datetime) else exp.get('end_time', ''),
                'variants_count': len(exp['variants']),
                'total_executions': sum(v['total_count'] for v in exp['variants']),
                'winner': winner.get('winner', 'none'),
                'winner_confidence': winner.get('confidence', 'none'),
                'success_rate_improvement': winner.get('absolute_difference', 0.0) if isinstance(winner, dict) else 0.0
            })
        
        return {
            'experiment_history': formatted_history,
            'total_experiments': sum(len(exps) for exps in self.experiment_history.values()),
            'domains_with_history': list(self.experiment_history.keys()),
            'active_experiments_count': len(self.active_experiments),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_experiment_stats(self) -> Dict:
        """Get experiment statistics"""
        total_concluded = sum(len(exps) for exps in self.experiment_history.values())
        
        # Calculate success rates
        winning_experiments = 0
        significant_experiments = 0
        
        for domain_exps in self.experiment_history.values():
            for exp in domain_exps:
                winner = exp.get('winner', {})
                if isinstance(winner, dict) and winner.get('winner') != 'none':
                    winning_experiments += 1
                
                if winner.get('confidence') == 'high':
                    significant_experiments += 1
        
        success_rate = winning_experiments / total_concluded if total_concluded > 0 else 0
        significance_rate = significant_experiments / total_concluded if total_concluded > 0 else 0
        
        # Traffic allocation impact
        total_assignments = 0
        for experiment in self.active_experiments.values():
            total_assignments += sum(experiment['assignments'].values())
        
        return {
            'active_experiments': len(self.active_experiments),
            'concluded_experiments': total_concluded,
            'winning_experiments': winning_experiments,
            'significant_experiments': significant_experiments,
            'experiment_success_rate': round(success_rate, 4),
            'statistical_significance_rate': round(significance_rate, 4),
            'current_traffic_allocation': self.experiment_traffic_allocation,
            'current_assignments': total_assignments,
            'minimum_sample_size': self.minimum_sample_size,
            'significance_level': self.significance_level,
            'timestamp': datetime.utcnow().isoformat()
        }

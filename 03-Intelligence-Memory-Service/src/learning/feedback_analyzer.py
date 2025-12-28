import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import List, Dict, Any, Tuple, Optional
import hashlib
import json
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class FeedbackAnalyzer:
    def __init__(self, storage_path: str = "/tmp/feedback_analysis"):
        self.feedback_store = defaultdict(lambda: deque(maxlen=10000))
        self.correlation_cache = {}
        self.impact_scores = defaultdict(dict)
        self.learning_opportunities = deque(maxlen=1000)
        self.storage_path = storage_path
        self._load_analysis_data()
        
    def _load_analysis_data(self):
        """Load analysis data from storage"""
        try:
            import pickle
            filepath = f"{self.storage_path}/feedback_analysis.pkl"
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
                self.correlation_cache = data.get('correlation_cache', {})
                self.impact_scores = data.get('impact_scores', defaultdict(dict))
        except:
            pass
    
    def _save_analysis_data(self):
        """Save analysis data to storage"""
        try:
            import pickle
            import os
            os.makedirs(self.storage_path, exist_ok=True)
            filepath = f"{self.storage_path}/feedback_analysis.pkl"
            with open(filepath, 'wb') as f:
                data = {
                    'correlation_cache': self.correlation_cache,
                    'impact_scores': dict(self.impact_scores),
                    'timestamp': datetime.utcnow()
                }
                pickle.dump(data, f)
        except:
            pass
    
    def analyze_feedback(self, execution_batch: List[Dict]) -> Dict:
        """Analyze feedback from execution batch for improvement opportunities"""
        start_time = datetime.utcnow()
        
        if not execution_batch:
            return {
                'opportunities_found': 0,
                'analysis_time_ms': 0,
                'message': 'Empty execution batch'
            }
        
        # Store feedback
        for execution in execution_batch:
            self._store_feedback(execution)
        
        # Analyze correlations
        correlations = self._analyze_correlations(execution_batch)
        
        # Identify improvement opportunities
        opportunities = self._identify_improvement_opportunities(correlations, execution_batch)
        
        # Calculate impact scores
        scored_opportunities = self._score_improvement_opportunities(opportunities)
        
        # Store learning opportunities
        for opp in scored_opportunities:
            if opp['impact_score'] > 0.6:  # High impact
                self.learning_opportunities.append({
                    **opp,
                    'discovered_at': datetime.utcnow()
                })
        
        # Save analysis
        self._save_analysis_data()
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'execution_batch_size': len(execution_batch),
            'opportunities_found': len(scored_opportunities),
            'improvement_opportunities': scored_opportunities[:20],  # Limit output
            'correlation_analysis': correlations.get('summary', {}),
            'high_impact_count': sum(1 for o in scored_opportunities if o['impact_score'] > 0.7),
            'analysis_time_ms': round(elapsed, 2),
            'analysis_rate_per_sec': round(len(execution_batch) / (elapsed / 1000), 2) if elapsed > 0 else 0,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _store_feedback(self, execution: Dict):
        """Store execution feedback for analysis"""
        domain = execution.get('domain', 'default')
        strategy_type = execution.get('strategy', {}).get('type', 'unknown')
        
        feedback_key = f"{domain}:{strategy_type}"
        
        feedback_record = {
            'timestamp': datetime.utcnow(),
            'success': execution.get('success', False),
            'duration_ms': execution.get('duration_ms', 0),
            'error_type': self._extract_error_type(execution),
            'strategy_params': execution.get('strategy', {}),
            'parameters': execution.get('parameters', {}),
            'environment': execution.get('environment', {}),
            'resource_usage': execution.get('resource_usage', {}),
            'metadata': {
                k: v for k, v in execution.items() 
                if k not in ['strategy', 'parameters', 'environment', 'resource_usage']
            }
        }
        
        self.feedback_store[feedback_key].append(feedback_record)
    
    def _extract_error_type(self, execution: Dict) -> str:
        """Extract error type from execution"""
        if execution.get('success', True):
            return 'none'
        
        error_msg = str(execution.get('error_message', '')).lower()
        
        if 'timeout' in error_msg:
            return 'timeout'
        elif 'connection' in error_msg or 'network' in error_msg:
            return 'network'
        elif 'permission' in error_msg or 'access' in error_msg:
            return 'permission'
        elif 'memory' in error_msg:
            return 'memory'
        elif 'validation' in error_msg:
            return 'validation'
        else:
            return 'other'
    
    def _analyze_correlations(self, execution_batch: List[Dict]) -> Dict:
        """Analyze correlations between strategy parameters and outcomes"""
        if len(execution_batch) < 10:
            return {'insufficient_data': True, 'sample_size': len(execution_batch)}
        
        # Group by domain and strategy
        grouped_executions = defaultdict(list)
        for exec in execution_batch:
            key = f"{exec.get('domain', 'default')}:{exec.get('strategy', {}).get('type', 'unknown')}"
            grouped_executions[key].append(exec)
        
        correlations = {
            'by_group': {},
            'global': {},
            'summary': {}
        }
        
        # Analyze each group
        for group_key, executions in grouped_executions.items():
            if len(executions) >= 5:
                group_corr = self._analyze_group_correlations(executions)
                correlations['by_group'][group_key] = group_corr
        
        # Global correlation analysis
        if len(execution_batch) >= 20:
            global_corr = self._analyze_global_correlations(execution_batch)
            correlations['global'] = global_corr
        
        # Generate summary
        correlations['summary'] = self._generate_correlation_summary(correlations)
        
        # Cache results
        cache_key = hashlib.md5(json.dumps(correlations['summary'], sort_keys=True).encode()).hexdigest()[:16]
        self.correlation_cache[cache_key] = {
            'correlations': correlations,
            'timestamp': datetime.utcnow(),
            'sample_size': len(execution_batch)
        }
        
        return correlations
    
    def _analyze_group_correlations(self, executions: List[Dict]) -> Dict:
        """Analyze correlations within a domain/strategy group"""
        # Extract numerical parameters and outcomes
        param_values = defaultdict(list)
        outcomes = []
        
        for exec in executions:
            # Success outcome (1 for success, 0 for failure)
            outcomes.append(1 if exec.get('success', False) else 0)
            
            # Extract strategy parameters
            strategy = exec.get('strategy', {})
            for param_name, param_value in strategy.items():
                if isinstance(param_value, (int, float)):
                    param_values[param_name].append(param_value)
        
        # Calculate correlations
        correlations = {}
        for param_name, values in param_values.items():
            if len(values) >= 5 and len(values) == len(outcomes):
                try:
                    # Pearson correlation
                    correlation, p_value = stats.pearsonr(values, outcomes)
                    
                    # Spearman for monotonic relationships
                    spearman_corr, spearman_p = stats.spearmanr(values, outcomes)
                    
                    correlations[param_name] = {
                        'pearson_correlation': round(correlation, 4),
                        'pearson_p_value': round(p_value, 6),
                        'spearman_correlation': round(spearman_corr, 4),
                        'spearman_p_value': round(spearman_p, 6),
                        'sample_size': len(values),
                        'param_range': [min(values), max(values)],
                        'param_mean': round(np.mean(values), 2),
                        'success_rate_by_quartile': self._calculate_success_by_quartile(values, outcomes)
                    }
                except:
                    continue
        
        return {
            'parameter_correlations': correlations,
            'sample_size': len(executions),
            'success_rate': round(sum(outcomes) / len(outcomes), 4),
            'avg_duration': round(np.mean([e.get('duration_ms', 0) for e in executions]), 2)
        }
    
    def _calculate_success_by_quartile(self, values: List[float], outcomes: List[int]) -> Dict:
        """Calculate success rate by parameter quartile"""
        if len(values) < 4:
            return {}
        
        # Sort by parameter value
        sorted_data = sorted(zip(values, outcomes), key=lambda x: x[0])
        n = len(sorted_data)
        quartile_size = n // 4
        
        quartile_success = {}
        for i in range(4):
            start = i * quartile_size
            end = (i + 1) * quartile_size if i < 3 else n
            
            quartile_values = [v for v, _ in sorted_data[start:end]]
            quartile_outcomes = [o for _, o in sorted_data[start:end]]
            
            if quartile_outcomes:
                success_rate = sum(quartile_outcomes) / len(quartile_outcomes)
                quartile_success[f'q{i+1}'] = {
                    'success_rate': round(success_rate, 4),
                    'param_range': [min(quartile_values), max(quartile_values)],
                    'sample_size': len(quartile_outcomes)
                }
        
        return quartile_success
    
    def _analyze_global_correlations(self, executions: List[Dict]) -> Dict:
        """Analyze global correlations across all executions"""
        # Analyze error patterns
        error_patterns = defaultdict(int)
        success_by_error_type = defaultdict(lambda: {'success': 0, 'total': 0})
        
        for exec in executions:
            error_type = self._extract_error_type(exec)
            error_patterns[error_type] += 1
            
            success_by_error_type[error_type]['total'] += 1
            if exec.get('success', False):
                success_by_error_type[error_type]['success'] += 1
        
        # Calculate success rates by error type
        error_success_rates = {}
        for error_type, counts in success_by_error_type.items():
            if counts['total'] > 0:
                error_success_rates[error_type] = round(counts['success'] / counts['total'], 4)
        
        # Analyze time-based patterns
        hour_success = defaultdict(lambda: {'success': 0, 'total': 0})
        for exec in executions:
            hour = exec.get('timestamp', datetime.utcnow()).hour
            hour_success[hour]['total'] += 1
            if exec.get('success', False):
                hour_success[hour]['success'] += 1
        
        hour_success_rates = {}
        for hour, counts in hour_success.items():
            if counts['total'] > 0:
                hour_success_rates[hour] = round(counts['success'] / counts['total'], 4)
        
        return {
            'error_patterns': dict(error_patterns),
            'success_by_error_type': error_success_rates,
            'hourly_success_patterns': hour_success_rates,
            'total_executions': len(executions),
            'global_success_rate': round(sum(1 for e in executions if e.get('success', False)) / len(executions), 4)
        }
    
    def _generate_correlation_summary(self, correlations: Dict) -> Dict:
        """Generate summary of correlation analysis"""
        summary = {
            'strong_correlations': [],
            'weak_correlations': [],
            'actionable_insights': [],
            'data_quality': {}
        }
        
        # Analyze group correlations
        for group_key, group_data in correlations.get('by_group', {}).items():
            param_corrs = group_data.get('parameter_correlations', {})
            
            for param_name, corr_data in param_corrs.items():
                pearson_corr = abs(corr_data.get('pearson_correlation', 0))
                p_value = corr_data.get('pearson_p_value', 1.0)
                
                if p_value < 0.05:  # Statistically significant
                    if pearson_corr > 0.5:
                        summary['strong_correlations'].append({
                            'parameter': param_name,
                            'group': group_key,
                            'correlation': corr_data['pearson_correlation'],
                            'p_value': p_value,
                            'impact': 'high'
                        })
                    elif pearson_corr > 0.3:
                        summary['weak_correlations'].append({
                            'parameter': param_name,
                            'group': group_key,
                            'correlation': corr_data['pearson_correlation'],
                            'p_value': p_value,
                            'impact': 'medium'
                        })
        
        # Generate actionable insights
        summary['actionable_insights'] = self._generate_actionable_insights(correlations)
        
        # Data quality assessment
        total_groups = len(correlations.get('by_group', {}))
        groups_with_data = sum(1 for g in correlations.get('by_group', {}).values() 
                              if g.get('sample_size', 0) >= 5)
        
        summary['data_quality'] = {
            'total_groups_analyzed': total_groups,
            'groups_with_sufficient_data': groups_with_data,
            'data_coverage': round(groups_with_data / max(total_groups, 1), 4),
            'total_correlations_found': len(summary['strong_correlations']) + len(summary['weak_correlations'])
        }
        
        return summary
    
    def _generate_actionable_insights(self, correlations: Dict) -> List[Dict]:
        """Generate actionable insights from correlation analysis"""
        insights = []
        
        # Analyze parameter correlations for insights
        for group_key, group_data in correlations.get('by_group', {}).items():
            domain, strategy = group_key.split(':')
            param_corrs = group_data.get('parameter_correlations', {})
            
            for param_name, corr_data in param_corrs.items():
                pearson_corr = corr_data.get('pearson_correlation', 0)
                p_value = corr_data.get('pearson_p_value', 1.0)
                
                if p_value < 0.05 and abs(pearson_corr) > 0.3:
                    # Check success by quartile
                    quartile_data = corr_data.get('success_rate_by_quartile', {})
                    if len(quartile_data) >= 2:
                        # Find best performing quartile
                        best_quartile = max(quartile_data.items(), 
                                          key=lambda x: x[1]['success_rate'])
                        worst_quartile = min(quartile_data.items(), 
                                           key=lambda x: x[1]['success_rate'])
                        
                        if best_quartile[1]['success_rate'] - worst_quartile[1]['success_rate'] > 0.2:
                            insights.append({
                                'domain': domain,
                                'strategy': strategy,
                                'parameter': param_name,
                                'insight': f"Adjust {param_name} to range {best_quartile[1]['param_range']} for better success",
                                'current_success_rate': round(group_data.get('success_rate', 0), 4),
                                'potential_improvement': round(best_quartile[1]['success_rate'] - worst_quartile[1]['success_rate'], 4),
                                'confidence': round(1 - p_value, 4),
                                'evidence': f"Success rate: {worst_quartile[1]['success_rate']} → {best_quartile[1]['success_rate']} across parameter range"
                            })
        
        # Global insights from error patterns
        global_data = correlations.get('global', {})
        error_patterns = global_data.get('error_patterns', {})
        error_success = global_data.get('success_by_error_type', {})
        
        for error_type, success_rate in error_success.items():
            if success_rate < 0.3 and error_patterns.get(error_type, 0) > 10:
                insights.append({
                    'domain': 'global',
                    'strategy': 'all',
                    'parameter': 'error_handling',
                    'insight': f"Improve handling of {error_type} errors",
                    'current_success_rate': round(success_rate, 4),
                    'potential_improvement': round(0.7 - success_rate, 4),
                    'confidence': 0.8,
                    'evidence': f"{error_patterns[error_type]} occurrences with {success_rate} success rate"
                })
        
        return insights[:10]  # Limit to top 10 insights
    
    def _identify_improvement_opportunities(self, correlations: Dict, 
                                          execution_batch: List[Dict]) -> List[Dict]:
        """Identify specific improvement opportunities"""
        opportunities = []
        
        # Extract insights from correlation analysis
        insights = correlations.get('summary', {}).get('actionable_insights', [])
        
        for insight in insights:
            opportunity = {
                'type': 'parameter_optimization',
                'domain': insight['domain'],
                'strategy': insight['strategy'],
                'parameter': insight['parameter'],
                'description': insight['insight'],
                'evidence': insight['evidence'],
                'current_performance': insight['current_success_rate'],
                'potential_improvement': insight['potential_improvement'],
                'confidence': insight['confidence'],
                'estimated_impact': min(insight['potential_improvement'] * insight['confidence'], 0.5)
            }
            opportunities.append(opportunity)
        
        # Identify performance degradation
        perf_opportunities = self._identify_performance_degradation(execution_batch)
        opportunities.extend(perf_opportunities)
        
        # Identify error pattern opportunities
        error_opportunities = self._identify_error_pattern_opportunities(execution_batch)
        opportunities.extend(error_opportunities)
        
        # Identify resource optimization opportunities
        resource_opportunities = self._identify_resource_opportunities(execution_batch)
        opportunities.extend(resource_opportunities)
        
        return opportunities
    
    def _identify_performance_degradation(self, executions: List[Dict]) -> List[Dict]:
        """Identify performance degradation opportunities"""
        opportunities = []
        
        # Group by domain and strategy
        grouped = defaultdict(list)
        for exec in executions:
            key = f"{exec.get('domain', 'default')}:{exec.get('strategy', {}).get('type', 'unknown')}"
            grouped[key].append(exec)
        
        for group_key, group_execs in grouped.items():
            if len(group_execs) >= 10:
                domain, strategy = group_key.split(':')
                
                # Calculate performance trend
                durations = []
                timestamps = []
                
                for exec in group_execs:
                    duration = exec.get('duration_ms', 0)
                    if duration > 0:
                        durations.append(duration)
                        timestamps.append(exec.get('timestamp', datetime.utcnow()))
                
                if len(durations) >= 5:
                    # Sort by time
                    sorted_data = sorted(zip(timestamps, durations), key=lambda x: x[0])
                    _, sorted_durations = zip(*sorted_data)
                    
                    # Calculate trend
                    if len(sorted_durations) >= 3:
                        # Split into halves
                        half = len(sorted_durations) // 2
                        first_half = sorted_durations[:half]
                        second_half = sorted_durations[half:]
                        
                        avg_first = np.mean(first_half)
                        avg_second = np.mean(second_half)
                        
                        if avg_second > avg_first * 1.3:  # 30% degradation
                            opportunities.append({
                                'type': 'performance_degradation',
                                'domain': domain,
                                'strategy': strategy,
                                'description': f"Performance degradation detected: {round(avg_first)}ms → {round(avg_second)}ms",
                                'evidence': f"30% increase in response time over {len(group_execs)} executions",
                                'current_performance': round(avg_second, 2),
                                'potential_improvement': round((avg_second - avg_first) / avg_second, 4),
                                'confidence': 0.7,
                                'estimated_impact': 0.4
                            })
        
        return opportunities
    
    def _identify_error_pattern_opportunities(self, executions: List[Dict]) -> List[Dict]:
        """Identify error pattern improvement opportunities"""
        opportunities = []
        
        # Group errors by type and domain
        error_counts = defaultdict(lambda: defaultdict(int))
        
        for exec in executions:
            if not exec.get('success', True):
                domain = exec.get('domain', 'default')
                error_type = self._extract_error_type(exec)
                error_counts[domain][error_type] += 1
        
        # Identify recurring error patterns
        for domain, errors in error_counts.items():
            total_errors = sum(errors.values())
            
            for error_type, count in errors.items():
                error_rate = count / len([e for e in executions if e.get('domain') == domain])
                
                if error_rate > 0.1 and count >= 5:  # 10% error rate with at least 5 occurrences
                    opportunities.append({
                        'type': 'error_pattern',
                        'domain': domain,
                        'strategy': 'all',
                        'description': f"High frequency of {error_type} errors",
                        'evidence': f"{count} occurrences ({round(error_rate*100, 1)}% error rate)",
                        'current_performance': round(1 - error_rate, 4),
                        'potential_improvement': round(error_rate * 0.8, 4),  # Can fix 80% of errors
                        'confidence': 0.6,
                        'estimated_impact': round(error_rate * 0.5, 4)
                    })
        
        return opportunities
    
    def _identify_resource_opportunities(self, executions: List[Dict]) -> List[Dict]:
        """Identify resource optimization opportunities"""
        opportunities = []
        
        # Analyze resource usage patterns
        resource_data = defaultdict(list)
        
        for exec in executions:
            resource_usage = exec.get('resource_usage', {})
            for resource, usage in resource_usage.items():
                if isinstance(usage, (int, float)):
                    resource_data[resource].append({
                        'usage': usage,
                        'success': exec.get('success', False),
                        'duration': exec.get('duration_ms', 0)
                    })
        
        for resource, usages in resource_data.items():
            if len(usages) >= 10:
                # Calculate correlation between resource usage and success
                usage_values = [u['usage'] for u in usages]
                success_values = [1 if u['success'] else 0 for u in usages]
                
                try:
                    correlation, p_value = stats.pearsonr(usage_values, success_values)
                    
                    if p_value < 0.1 and correlation < -0.3:  # Negative correlation
                        # High usage with low success
                        high_usage_threshold = np.percentile(usage_values, 75)
                        high_usage = [u for u in usages if u['usage'] > high_usage_threshold]
                        
                        if high_usage:
                            high_usage_success = sum(1 for u in high_usage if u['success']) / len(high_usage)
                            
                            if high_usage_success < 0.5:
                                opportunities.append({
                                    'type': 'resource_optimization',
                                    'domain': 'multiple',
                                    'strategy': 'resource_management',
                                    'description': f"High {resource} usage correlates with failure",
                                    'evidence': f"Success rate drops to {round(high_usage_success*100, 1)}% when {resource} > {round(high_usage_threshold, 2)}",
                                    'current_performance': round(high_usage_success, 4),
                                    'potential_improvement': round(0.7 - high_usage_success, 4),
                                    'confidence': round(1 - p_value, 4),
                                    'estimated_impact': 0.3
                                })
                except:
                    continue
        
        return opportunities
    
    def _score_improvement_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        """Score improvement opportunities based on impact"""
        scored_opportunities = []
        
        for opp in opportunities:
            # Calculate impact score
            impact_score = self._calculate_impact_score(opp)
            
            # Calculate feasibility score
            feasibility_score = self._calculate_feasibility_score(opp)
            
            # Calculate priority score
            priority_score = impact_score * 0.6 + feasibility_score * 0.4
            
            scored_opportunity = opp.copy()
            scored_opportunity.update({
                'impact_score': round(impact_score, 4),
                'feasibility_score': round(feasibility_score, 4),
                'priority_score': round(priority_score, 4),
                'priority_level': self._get_priority_level(priority_score),
                'recommended_action': self._get_recommended_action(opp, priority_score)
            })
            
            # Store impact score
            opp_key = f"{opp['type']}:{opp['domain']}:{opp.get('parameter', 'general')}"
            self.impact_scores[opp_key] = {
                'impact_score': impact_score,
                'last_updated': datetime.utcnow(),
                'evidence_count': self.impact_scores.get(opp_key, {}).get('evidence_count', 0) + 1
            }
            
            scored_opportunities.append(scored_opportunity)
        
        # Sort by priority score
        scored_opportunities.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return scored_opportunities
    
    def _calculate_impact_score(self, opportunity: Dict) -> float:
        """Calculate impact score for opportunity"""
        base_score = opportunity.get('estimated_impact', 0.3)
        confidence = opportunity.get('confidence', 0.5)
        potential_improvement = opportunity.get('potential_improvement', 0.1)
        
        # Domain importance factor (would integrate with domain intelligence)
        domain = opportunity.get('domain', 'default')
        domain_factor = 1.0
        if domain == 'critical':
            domain_factor = 1.5
        elif domain == 'low_priority':
            domain_factor = 0.7
        
        # Evidence strength factor
        evidence_factor = min(confidence * 1.5, 1.0)
        
        # Calculate impact
        impact = base_score * confidence * potential_improvement * domain_factor * evidence_factor
        
        return min(max(impact, 0.0), 1.0)
    
    def _calculate_feasibility_score(self, opportunity: Dict) -> float:
        """Calculate feasibility score for opportunity"""
        opp_type = opportunity.get('type', '')
        
        # Type-based feasibility
        type_scores = {
            'parameter_optimization': 0.9,
            'performance_degradation': 0.7,
            'error_pattern': 0.6,
            'resource_optimization': 0.5
        }
        
        base_feasibility = type_scores.get(opp_type, 0.5)
        
        # Domain expertise factor
        domain = opportunity.get('domain', 'default')
        domain_factor = 1.0
        if domain in ['well_known', 'frequently_used']:
            domain_factor = 1.2
        elif domain in ['new', 'unfamiliar']:
            domain_factor = 0.8
        
        # Evidence clarity factor
        evidence = opportunity.get('evidence', '')
        clarity_factor = 1.0
        if '→' in evidence or '%' in evidence:  # Quantitative evidence
            clarity_factor = 1.2
        elif len(evidence) < 20:  # Vague evidence
            clarity_factor = 0.8
        
        return base_feasibility * domain_factor * clarity_factor
    
    def _get_priority_level(self, priority_score: float) -> str:
        """Get priority level based on score"""
        if priority_score >= 0.8:
            return 'critical'
        elif priority_score >= 0.6:
            return 'high'
        elif priority_score >= 0.4:
            return 'medium'
        elif priority_score >= 0.2:
            return 'low'
        else:
            return 'monitor'
    
    def _get_recommended_action(self, opportunity: Dict, priority_score: float) -> str:
        """Get recommended action based on opportunity"""
        opp_type = opportunity.get('type', '')
        
        if priority_score >= 0.7:
            action = "Immediate implementation recommended"
        elif priority_score >= 0.5:
            action = "Schedule for next sprint"
        elif priority_score >= 0.3:
            action = "Consider for future planning"
        else:
            action = "Monitor and gather more data"
        
        if opp_type == 'parameter_optimization':
            param = opportunity.get('parameter', '')
            return f"Optimize {param} parameter. {action}"
        elif opp_type == 'performance_degradation':
            return f"Investigate performance regression. {action}"
        elif opp_type == 'error_pattern':
            return f"Implement error handling improvements. {action}"
        elif opp_type == 'resource_optimization':
            return f"Optimize resource usage. {action}"
        else:
            return action
    
    def get_improvement_insights(self, domain: str = None, limit: int = 20) -> Dict:
        """Get improvement insights from analysis"""
        insights = []
        
        # Get recent learning opportunities
        for opp in list(self.learning_opportunities)[-limit:]:
            if domain is None or opp.get('domain') == domain:
                insights.append({
                    'type': opp['type'],
                    'domain': opp['domain'],
                    'strategy': opp['strategy'],
                    'description': opp['description'],
                    'impact_score': opp['impact_score'],
                    'priority_level': opp['priority_level'],
                    'discovered_at': opp['discovered_at'].isoformat() if isinstance(opp['discovered_at'], datetime) else opp['discovered_at'],
                    'age_days': (datetime.utcnow() - opp['discovered_at']).days if isinstance(opp['discovered_at'], datetime) else 0
                })
        
        # Get correlation insights
        correlation_insights = []
        for cache_key, cache_data in list(self.correlation_cache.items())[-10:]:
            summary = cache_data['correlations'].get('summary', {})
            for insight in summary.get('actionable_insights', [])[:5]:
                correlation_insights.append({
                    'domain': insight['domain'],
                    'insight': insight['insight'],
                    'confidence': insight['confidence'],
                    'sample_size': cache_data['sample_size']
                })
        
        return {
            'improvement_opportunities': insights,
            'correlation_insights': correlation_insights[:10],
            'high_impact_opportunities': [i for i in insights if i['impact_score'] > 0.7],
            'total_opportunities_tracked': len(self.learning_opportunities),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_analysis_stats(self) -> Dict:
        """Get analysis statistics"""
        total_feedback = sum(len(store) for store in self.feedback_store.values())
        domains_tracked = len(self.feedback_store)
        
        # Calculate average feedback per domain
        avg_feedback_per_domain = total_feedback / max(domains_tracked, 1)
        
        # Recent activity
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_feedback = 0
        for store in self.feedback_store.values():
            for feedback in store:
                if feedback['timestamp'] > recent_cutoff:
                    recent_feedback += 1
        
        return {
            'total_feedback_stored': total_feedback,
            'domains_tracked': domains_tracked,
            'average_feedback_per_domain': round(avg_feedback_per_domain, 2),
            'recent_feedback_24h': recent_feedback,
            'correlation_cache_size': len(self.correlation_cache),
            'learning_opportunities_tracked': len(self.learning_opportunities),
            'impact_scores_tracked': len(self.impact_scores),
            'storage_health': 'good' if total_feedback < 1000000 else 'warning',
            'timestamp': datetime.utcnow().isoformat()
        }

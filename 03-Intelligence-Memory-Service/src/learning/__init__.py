from .feedback_analyzer import FeedbackAnalyzer
from .strategy_optimizer import StrategyOptimizer
from .experiment_runner import A_BTestRunner
from .knowledge_distributor import KnowledgeDistributor

class LearningFeedbackLoop:
    """Main learning feedback loop orchestrator"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Initialize components
        self.feedback_analyzer = FeedbackAnalyzer(
            self.config.get('feedback_storage', '/tmp/feedback_analysis')
        )
        self.strategy_optimizer = StrategyOptimizer(
            self.config.get('optimization_storage', '/tmp/strategy_optimization')
        )
        self.experiment_runner = A_BTestRunner(
            self.config.get('experiment_storage', '/tmp/ab_experiments')
        )
        self.knowledge_distributor = KnowledgeDistributor(
            self.config.get('distribution_storage', '/tmp/knowledge_distribution')
        )
        
        # Learning loop state
        self.learning_cycles = deque(maxlen=1000)
        self.improvement_tracking = defaultdict(dict)
        self.performance_metrics = {
            'feedback_analysis': [],
            'strategy_optimization': [],
            'experiment_execution': [],
            'knowledge_distribution': []
        }
        
        # Start background learning loop
        self._start_learning_loop()
    
    def _start_learning_loop(self):
        """Start background learning loop"""
        import threading
        
        def learning_loop():
            while True:
                try:
                    self._run_learning_cycle()
                except Exception as e:
                    print(f"Learning loop error: {e}")
                threading.Event().wait(300)  # Run every 5 minutes
        
        thread = threading.Thread(target=learning_loop, daemon=True)
        thread.start()
    
    def _run_learning_cycle(self):
        """Run a single learning cycle"""
        cycle_start = datetime.utcnow()
        cycle_id = hashlib.md5(cycle_start.isoformat().encode()).hexdigest()[:16]
        
        cycle_results = {
            'cycle_id': cycle_id,
            'start_time': cycle_start,
            'steps': [],
            'improvements_found': 0,
            'optimizations_applied': 0,
            'experiments_conducted': 0,
            'knowledge_distributed': 0
        }
        
        # Step 1: Analyze recent feedback
        feedback_analysis = self._analyze_recent_feedback()
        cycle_results['steps'].append({
            'step': 'feedback_analysis',
            'results': feedback_analysis,
            'timestamp': datetime.utcnow()
        })
        
        if feedback_analysis.get('high_impact_count', 0) > 0:
            cycle_results['improvements_found'] += feedback_analysis['high_impact_count']
            
            # Step 2: Optimize strategies based on feedback
            optimization_results = self._optimize_strategies_from_feedback(feedback_analysis)
            cycle_results['steps'].append({
                'step': 'strategy_optimization',
                'results': optimization_results,
                'timestamp': datetime.utcnow()
            })
            cycle_results['optimizations_applied'] += optimization_results.get('optimizations_applied', 0)
            
            # Step 3: Run experiments for high-impact opportunities
            experiment_results = self._run_experiments_for_opportunities(feedback_analysis)
            cycle_results['steps'].append({
                'step': 'experiment_execution',
                'results': experiment_results,
                'timestamp': datetime.utcnow()
            })
            cycle_results['experiments_conducted'] += experiment_results.get('experiments_started', 0)
            
            # Step 4: Distribute validated learnings
            if optimization_results.get('optimizations_applied', 0) > 0:
                distribution_results = self._distribute_validated_learnings(optimization_results)
                cycle_results['steps'].append({
                    'step': 'knowledge_distribution',
                    'results': distribution_results,
                    'timestamp': datetime.utcnow()
                })
                cycle_results['knowledge_distributed'] += distribution_results.get('packages_distributed', 0)
        
        cycle_results['end_time'] = datetime.utcnow()
        cycle_results['duration_seconds'] = (cycle_results['end_time'] - cycle_start).total_seconds()
        
        # Store cycle results
        self.learning_cycles.append(cycle_results)
        
        # Update improvement tracking
        self._update_improvement_tracking(cycle_results)
        
        # Update performance metrics
        self._update_performance_metrics(cycle_results)
        
        return cycle_results
    
    def _analyze_recent_feedback(self, hours: int = 1) -> Dict:
        """Analyze feedback from recent executions"""
        # In production, this would query recent executions from the database
        # For now, return analysis from stored feedback
        
        # Get recent feedback statistics
        feedback_stats = self.feedback_analyzer.get_analysis_stats()
        
        # Get recent improvement opportunities
        recent_insights = self.feedback_analyzer.get_improvement_insights(limit=20)
        
        return {
            'feedback_analyzed': feedback_stats.get('recent_feedback_24h', 0),
            'improvement_opportunities': len(recent_insights.get('improvement_opportunities', [])),
            'high_impact_count': len(recent_insights.get('high_impact_opportunities', [])),
            'recent_insights': recent_insights.get('improvement_opportunities', [])[:5],
            'analysis_timestamp': datetime.utcnow().isoformat()
        }
    
    def _optimize_strategies_from_feedback(self, feedback_analysis: Dict) -> Dict:
        """Optimize strategies based on feedback analysis"""
        opportunities = feedback_analysis.get('recent_insights', [])
        
        optimizations_applied = 0
        optimization_results = []
        
        for opportunity in opportunities:
            if opportunity.get('impact_score', 0) > 0.7:  # High impact
                # Extract strategy type and domain
                strategy_type = opportunity.get('strategy', 'evasion')
                domain = opportunity.get('domain', 'default')
                
                # Get feedback data for this domain/strategy
                # In production, this would query specific executions
                
                # Run optimization
                optimization_result = self.strategy_optimizer.optimize_strategy(
                    strategy_type=strategy_type,
                    feedback_data={
                        'executions': [],  # Would be populated with actual data
                        'domain': domain
                    },
                    optimization_method='bayesian'
                )
                
                if optimization_result.get('success', False):
                    optimizations_applied += 1
                    optimization_results.append({
                        'strategy_type': strategy_type,
                        'domain': domain,
                        'optimization_result': optimization_result
                    })
        
        return {
            'optimizations_applied': optimizations_applied,
            'optimization_results': optimization_results[:5],  # Limit output
            'total_opportunities_considered': len(opportunities),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _run_experiments_for_opportunities(self, feedback_analysis: Dict) -> Dict:
        """Run experiments for high-impact opportunities"""
        opportunities = feedback_analysis.get('recent_insights', [])
        
        experiments_started = 0
        experiment_results = []
        
        for opportunity in opportunities:
            if opportunity.get('impact_score', 0) > 0.8:  # Very high impact
                domain = opportunity.get('domain', 'default')
                strategy_type = opportunity.get('strategy', 'evasion')
                
                # Create strategy variants based on opportunity
                strategy_variants = self._create_experiment_variants(opportunity)
                
                if len(strategy_variants) >= 2:
                    # Run experiment
                    experiment_result = self.experiment_runner.run_experiment(
                        domain=domain,
                        strategy_variants=strategy_variants,
                        experiment_config={
                            'traffic_percentage': 0.05,  # 5% of traffic
                            'minimum_sample_size': 100,
                            'max_duration_hours': 12
                        }
                    )
                    
                    if experiment_result.get('success', False):
                        experiments_started += 1
                        experiment_results.append({
                            'domain': domain,
                            'opportunity': opportunity.get('description', ''),
                            'experiment_id': experiment_result.get('experiment_id'),
                            'variants_count': len(strategy_variants)
                        })
        
        return {
            'experiments_started': experiments_started,
            'experiment_results': experiment_results,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _create_experiment_variants(self, opportunity: Dict) -> List[Dict]:
        """Create experiment variants based on opportunity"""
        variants = []
        
        # Base strategy
        strategy_type = opportunity.get('strategy', 'evasion')
        
        # Create 3 variants
        for i in range(3):
            variant = {
                'type': strategy_type,
                'variant_name': f"variant_{i+1}"
            }
            
            # Add parameter variations based on opportunity type
            if opportunity.get('type') == 'parameter_optimization':
                param = opportunity.get('parameter', 'timeout_ms')
                
                # Vary the parameter
                if param == 'timeout_ms':
                    variant[param] = [1000, 3000, 5000][i]
                elif param == 'retry_count':
                    variant[param] = [1, 3, 5][i]
                elif param == 'backoff_factor':
                    variant[param] = [1.0, 1.5, 2.0][i]
            
            variants.append(variant)
        
        return variants
    
    def _distribute_validated_learnings(self, optimization_results: Dict) -> Dict:
        """Distribute validated learnings to worker fleet"""
        optimizations = optimization_results.get('optimization_results', [])
        
        packages_distributed = 0
        distribution_results = []
        
        for optimization in optimizations:
            opt_result = optimization.get('optimization_result', {})
            
            if opt_result.get('success', False) and opt_result.get('validation_result', {}).get('validation_passed', False):
                # Create learning package
                learning_package = {
                    'knowledge_type': 'strategy_optimization',
                    'content': {
                        'strategy_type': optimization['strategy_type'],
                        'domain': optimization['domain'],
                        'optimized_parameters': opt_result.get('optimized_parameters', {}),
                        'validation_result': opt_result.get('validation_result', {}),
                        'improvement_metrics': opt_result.get('improvement_metrics', {})
                    },
                    'source': 'learning_feedback_loop',
                    'confidence': opt_result.get('validation_result', {}).get('confidence', 0.5),
                    'impact_estimate': opt_result.get('improvement_metrics', {}).get('relative_improvement', 0.0),
                    'applicable_domains': [optimization['domain'], 'similar_domains'],
                    'created_at': datetime.utcnow().isoformat()
                }
                
                # Distribute knowledge
                distribution_result = self.knowledge_distributor.distribute_knowledge(
                    learning_package=learning_package,
                    distribution_strategy='immediate'
                )
                
                if distribution_result.get('success', False):
                    packages_distributed += 1
                    distribution_results.append({
                        'package_id': distribution_result.get('package_id'),
                        'distribution_report': distribution_result.get('distribution_report', {})
                    })
        
        return {
            'packages_distributed': packages_distributed,
            'distribution_results': distribution_results[:5],  # Limit output
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _update_improvement_tracking(self, cycle_results: Dict):
        """Update improvement tracking"""
        cycle_id = cycle_results['cycle_id']
        
        self.improvement_tracking[cycle_id] = {
            'improvements_found': cycle_results['improvements_found'],
            'optimizations_applied': cycle_results['optimizations_applied'],
            'experiments_conducted': cycle_results['experiments_conducted'],
            'knowledge_distributed': cycle_results['knowledge_distributed'],
            'cycle_duration': cycle_results['duration_seconds'],
            'timestamp': cycle_results['start_time']
        }
    
    def _update_performance_metrics(self, cycle_results: Dict):
        """Update performance metrics"""
        for step in cycle_results['steps']:
            step_name = step['step']
            results = step['results']
            
            if step_name == 'feedback_analysis':
                self.performance_metrics['feedback_analysis'].append({
                    'improvements_found': results.get('improvement_opportunities', 0),
                    'timestamp': datetime.utcnow()
                })
            elif step_name == 'strategy_optimization':
                self.performance_metrics['strategy_optimization'].append({
                    'optimizations_applied': results.get('optimizations_applied', 0),
                    'timestamp': datetime.utcnow()
                })
            elif step_name == 'experiment_execution':
                self.performance_metrics['experiment_execution'].append({
                    'experiments_started': results.get('experiments_started', 0),
                    'timestamp': datetime.utcnow()
                })
            elif step_name == 'knowledge_distribution':
                self.performance_metrics['knowledge_distribution'].append({
                    'packages_distributed': results.get('packages_distributed', 0),
                    'timestamp': datetime.utcnow()
                })
    
    def get_learning_stats(self) -> Dict:
        """Get learning system statistics"""
        total_cycles = len(self.learning_cycles)
        
        if total_cycles > 0:
            recent_cycles = list(self.learning_cycles)[-min(10, total_cycles):]
            
            avg_improvements = np.mean([c['improvements_found'] for c in recent_cycles])
            avg_optimizations = np.mean([c['optimizations_applied'] for c in recent_cycles])
            avg_experiments = np.mean([c['experiments_conducted'] for c in recent_cycles])
            avg_distributions = np.mean([c['knowledge_distributed'] for c in recent_cycles])
            avg_duration = np.mean([c['duration_seconds'] for c in recent_cycles])
        else:
            avg_improvements = avg_optimizations = avg_experiments = avg_distributions = avg_duration = 0
        
        # Component statistics
        feedback_stats = self.feedback_analyzer.get_analysis_stats()
        optimization_stats = self.strategy_optimizer.get_optimization_stats()
        experiment_stats = self.experiment_runner.get_experiment_stats()
        distribution_stats = self.knowledge_distributor.get_system_stats()
        
        # Calculate learning velocity
        if total_cycles >= 2:
            cycles_per_day = 24 * 3600 / avg_duration if avg_duration > 0 else 0
            improvements_per_day = cycles_per_day * avg_improvements
        else:
            cycles_per_day = improvements_per_day = 0
        
        return {
            'learning_loop': {
                'total_cycles_completed': total_cycles,
                'average_cycle_duration_seconds': round(avg_duration, 2),
                'cycles_per_day': round(cycles_per_day, 2),
                'average_improvements_per_cycle': round(avg_improvements, 2),
                'average_optimizations_per_cycle': round(avg_optimizations, 2),
                'average_experiments_per_cycle': round(avg_experiments, 2),
                'average_distributions_per_cycle': round(avg_distributions, 2),
                'estimated_improvements_per_day': round(improvements_per_day, 2),
                'current_cycle_active': False,  # Would track if a cycle is running
                'learning_velocity': 'high' if improvements_per_day > 10 else 'medium' if improvements_per_day > 5 else 'low'
            },
            'components': {
                'feedback_analyzer': feedback_stats,
                'strategy_optimizer': optimization_stats,
                'experiment_runner': experiment_stats,
                'knowledge_distributor': distribution_stats
            },
            'performance_metrics': {
                component: {
                    'recent_activity': len(metrics[-10:]),
                    'trend': self._calculate_trend([m.get('improvements_found', m.get('optimizations_applied', m.get('experiments_started', m.get('packages_distributed', 0)))) for m in metrics[-5:]])
                }
                for component, metrics in self.performance_metrics.items()
            },
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend from values"""
        if len(values) < 2:
            return 'insufficient_data'
        
        # Simple linear trend
        x = list(range(len(values)))
        slope, _ = np.polyfit(x, values, 1)
        
        if slope > 0.1:
            return 'improving'
        elif slope < -0.1:
            return 'declining'
        else:
            return 'stable'
    
    def get_recent_learnings(self, limit: int = 20) -> Dict:
        """Get recent learnings and improvements"""
        recent_cycles = list(self.learning_cycles)[-limit:]
        
        learnings = []
        for cycle in recent_cycles:
            learnings.append({
                'cycle_id': cycle['cycle_id'],
                'start_time': cycle['start_time'].isoformat() if isinstance(cycle['start_time'], datetime) else cycle['start_time'],
                'improvements_found': cycle['improvements_found'],
                'optimizations_applied': cycle['optimizations_applied'],
                'experiments_conducted': cycle['experiments_conducted'],
                'knowledge_distributed': cycle['knowledge_distributed'],
                'duration_seconds': cycle['duration_seconds'],
                'key_improvements': self._extract_key_improvements(cycle)
            })
        
        # Get recent improvement opportunities
        recent_opportunities = self.feedback_analyzer.get_improvement_insights(limit=10)
        
        # Get recent optimizations
        recent_optimizations = self.strategy_optimizer.get_optimization_history(limit=10)
        
        # Get recent experiments
        recent_experiments = self.experiment_runner.get_experiment_history(limit=10)
        
        return {
            'recent_learning_cycles': learnings,
            'recent_improvement_opportunities': recent_opportunities.get('improvement_opportunities', []),
            'recent_optimizations': recent_optimizations.get('optimization_history', []),
            'recent_experiments': recent_experiments.get('experiment_history', []),
            'learning_velocity': self._calculate_learning_velocity(recent_cycles),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _extract_key_improvements(self, cycle: Dict) -> List[str]:
        """Extract key improvements from learning cycle"""
        improvements = []
        
        for step in cycle.get('steps', []):
            if step['step'] == 'feedback_analysis':
                results = step['results']
                if results.get('high_impact_count', 0) > 0:
                    improvements.append(f"Found {results['high_impact_count']} high-impact improvement opportunities")
            
            elif step['step'] == 'strategy_optimization':
                results = step['results']
                if results.get('optimizations_applied', 0) > 0:
                    improvements.append(f"Applied {results['optimizations_applied']} strategy optimizations")
            
            elif step['step'] == 'experiment_execution':
                results = step['results']
                if results.get('experiments_started', 0) > 0:
                    improvements.append(f"Started {results['experiments_started']} experiments")
            
            elif step['step'] == 'knowledge_distribution':
                results = step['results']
                if results.get('packages_distributed', 0) > 0:
                    improvements.append(f"Distributed {results['packages_distributed']} knowledge packages")
        
        return improvements[:5]
    
    def _calculate_learning_velocity(self, recent_cycles: List[Dict]) -> Dict:
        """Calculate learning velocity metrics"""
        if len(recent_cycles) < 2:
            return {'velocity': 'unknown', 'trend': 'insufficient_data'}
        
        # Calculate improvements per day
        improvements = [c['improvements_found'] for c in recent_cycles]
        durations = [c['duration_seconds'] for c in recent_cycles]
        
        total_improvements = sum(improvements)
        total_duration = sum(durations)
        
        if total_duration > 0:
            improvements_per_hour = total_improvements / (total_duration / 3600)
            improvements_per_day = improvements_per_hour * 24
        else:
            improvements_per_day = 0
        
        # Calculate trend
        if len(improvements) >= 3:
            slope, _ = np.polyfit(range(len(improvements)), improvements, 1)
            trend = 'accelerating' if slope > 0.5 else 'stable' if slope > -0.5 else 'decelerating'
        else:
            trend = 'unknown'
        
        return {
            'improvements_per_day': round(improvements_per_day, 2),
            'velocity': 'high' if improvements_per_day > 20 else 'medium' if improvements_per_day > 10 else 'low',
            'trend': trend,
            'recent_improvements': improvements[-5:]
        }
    
    def trigger_manual_learning_cycle(self) -> Dict:
        """Trigger a manual learning cycle"""
        cycle_results = self._run_learning_cycle()
        
        return {
            'success': True,
            'cycle_id': cycle_results['cycle_id'],
            'improvements_found': cycle_results['improvements_found'],
            'optimizations_applied': cycle_results['optimizations_applied'],
            'experiments_conducted': cycle_results['experiments_conducted'],
            'knowledge_distributed': cycle_results['knowledge_distributed'],
            'duration_seconds': cycle_results['duration_seconds'],
            'timestamp': datetime.utcnow().isoformat()
        }

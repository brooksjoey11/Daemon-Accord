import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

class ReflectionPublisher:
    def __init__(self, memory_hook=None, redis_client=None):
        self.memory_hook = memory_hook
        self.redis = redis_client
        self.learning_cache = {}
        self.strategy_adjustments = {}
        
    async def analyze(self, result: Any, job: Any = None) -> List[Dict[str, Any]]:
        """Analyze execution result and generate reflection events."""
        events = []
        
        # Only analyze if we have a result
        if not hasattr(result, 'success'):
            return events
        
        # Analyze execution time
        if hasattr(result, 'timing'):
            time_event = await self._analyze_timing(result, job)
            if time_event:
                events.append(time_event)
        
        # Analyze errors
        if not result.success and hasattr(result, 'error'):
            error_event = await self._analyze_error(result, job)
            if error_event:
                events.append(error_event)
        
        # Analyze success patterns
        if result.success:
            success_event = await self._analyze_success(result, job)
            if success_event:
                events.append(success_event)
        
        # Analyze evasion effectiveness
        if job and hasattr(job, 'payload'):
            evasion_event = await self._analyze_evasion(result, job)
            if evasion_event:
                events.append(evasion_event)
        
        # Analyze domain patterns
        if job and hasattr(job, 'url'):
            domain_event = await self._analyze_domain_patterns(result, job)
            if domain_event:
                events.append(domain_event)
        
        # Store reflections in memory
        for event in events:
            if self.memory_hook:
                await self.memory_hook.store_reflection(event)
        
        return events
    
    async def _analyze_timing(self, result: Any, job: Any = None) -> Optional[Dict[str, Any]]:
        """Analyze execution timing."""
        timing = result.timing if hasattr(result, 'timing') else {}
        total_ms = timing.get('total_ms', 0)
        
        if not total_ms:
            return None
        
        # Determine if timing is abnormal
        domain = job.domain if job and hasattr(job, 'domain') else "unknown"
        
        # Get historical timing for comparison
        historical_avg = await self._get_historical_timing(domain, job)
        
        event = {
            "type": "timing_analysis",
            "domain": domain,
            "execution_time_ms": total_ms,
            "historical_average_ms": historical_avg,
            "deviation_percent": self._calculate_deviation(total_ms, historical_avg) if historical_avg else None,
            "classification": self._classify_timing(total_ms, historical_avg),
            "recommendation": self._generate_timing_recommendation(total_ms, historical_avg),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Cache timing for future analysis
        await self._store_timing_metric(domain, total_ms, job)
        
        return event
    
    async def _analyze_error(self, result: Any, job: Any = None) -> Optional[Dict[str, Any]]:
        """Analyze error patterns."""
        error = result.error
        if not error:
            return None
        
        domain = job.domain if job and hasattr(job, 'domain') else "unknown"
        
        # Classify error
        error_type = self._classify_error(error)
        
        # Count error frequency
        error_key = f"error:{domain}:{error_type}"
        frequency = await self._increment_counter(error_key, 3600)  # 1 hour TTL
        
        event = {
            "type": "error_analysis",
            "domain": domain,
            "error_type": error_type,
            "error_message": error[:500],  # Truncate long messages
            "frequency_last_hour": frequency,
            "suggested_action": self._suggest_error_action(error_type, frequency),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # If high frequency, suggest escalation
        if frequency >= 3:
            event["requires_attention"] = True
            event["suggested_action"] = "circuit_breaker_activation"
            
            # Publish incident
            if self.memory_hook:
                incident_context = {
                    "error_type": error_type,
                    "frequency": frequency,
                    "domain": domain,
                    "suggested_action": "circuit_breaker_activation"
                }
                await self.memory_hook.publish_incident(domain, error_type, incident_context)
        
        return event
    
    async def _analyze_success(self, result: Any, job: Any = None) -> Optional[Dict[str, Any]]:
        """Analyze successful execution patterns."""
        domain = job.domain if job and hasattr(job, 'domain') else "unknown"
        
        # Track success rate
        success_key = f"success:{domain}"
        await self._increment_counter(success_key, 86400)  # 24 hour TTL
        
        # Calculate success streak
        streak_key = f"success_streak:{domain}"
        current_streak = await self._increment_counter(streak_key, 3600)
        
        # Get data metrics if available
        data_metrics = {}
        if hasattr(result, 'data') and result.data:
            data_size = sum(len(str(v)) for v in result.data.values())
            data_metrics = {
                "data_size_bytes": data_size,
                "field_count": len(result.data)
            }
        
        event = {
            "type": "success_analysis",
            "domain": domain,
            "success_streak": current_streak,
            "data_metrics": data_metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # If long streak, consider reducing evasion
        if current_streak >= 10:
            event["recommendation"] = "consider_reducing_evasion_level"
            event["reason"] = f"Success streak of {current_streak} consecutive executions"
        
        return event
    
    async def _analyze_evasion(self, result: Any, job: Any) -> Optional[Dict[str, Any]]:
        """Analyze evasion technique effectiveness."""
        if not job.payload:
            return None
        
        evasion_level = job.payload.get('evasion_level', 0)
        techniques = job.payload.get('evasion_techniques', [])
        
        domain = job.domain if hasattr(job, 'domain') else "unknown"
        
        # Track effectiveness
        success = result.success if hasattr(result, 'success') else False
        effectiveness_key = f"evasion:{domain}:{evasion_level}:{success}"
        await self._increment_counter(effectiveness_key, 86400)
        
        # Calculate success rate for this evasion level
        success_counts = await self._get_evasion_success_counts(domain, evasion_level)
        
        event = {
            "type": "evasion_analysis",
            "domain": domain,
            "evasion_level": evasion_level,
            "techniques_used": techniques,
            "success": success,
            "historical_success_rate": self._calculate_success_rate(success_counts),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Generate recommendations
        if success_counts:
            total = success_counts.get('success', 0) + success_counts.get('failure', 0)
            if total >= 5:  # Enough data for recommendation
                success_rate = success_counts.get('success', 0) / total
                
                if success_rate > 0.8 and evasion_level > 0:
                    event["recommendation"] = "consider_reducing_evasion"
                    event["reason"] = f"High success rate ({success_rate:.0%}) with current evasion"
                elif success_rate < 0.3 and evasion_level < 2:
                    event["recommendation"] = "consider_increasing_evasion"
                    event["reason"] = f"Low success rate ({success_rate:.0%}) with current evasion"
        
        return event
    
    async def _analyze_domain_patterns(self, result: Any, job: Any) -> Optional[Dict[str, Any]]:
        """Analyze domain-specific patterns."""
        domain = job.domain if hasattr(job, 'domain') else "unknown"
        
        # Track execution count
        execution_key = f"execution_count:{domain}"
        count = await self._increment_counter(execution_key, 86400)
        
        # Track execution times by hour
        hour = datetime.utcnow().hour
        hour_key = f"execution_hour:{domain}:{hour}"
        hour_count = await self._increment_counter(hour_key, 86400)
        
        event = {
            "type": "domain_pattern_analysis",
            "domain": domain,
            "total_executions": count,
            "current_hour_executions": hour_count,
            "peak_hours": await self._get_peak_hours(domain),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Detect unusual patterns
        if count > 100 and hour_count > count * 0.3:  # More than 30% of executions in this hour
            event["pattern_warning"] = "unusual_execution_concentration"
            event["warning_details"] = f"{hour_count} executions in hour {hour} ({hour_count/count:.0%} of total)"
        
        return event
    
    async def _get_historical_timing(self, domain: str, job: Any = None) -> Optional[float]:
        """Get historical average timing for domain."""
        cache_key = f"timing_avg:{domain}"
        
        if cache_key in self.learning_cache:
            cached = self.learning_cache[cache_key]
            if datetime.utcnow() - cached['timestamp'] < timedelta(minutes=5):
                return cached['value']
        
        if self.redis:
            try:
                # Get from Redis
                timing_key = f"timing_history:{domain}"
                count = await self.redis.llen(timing_key)
                
                if count > 0:
                    # Get recent timings
                    timings = await self.redis.lrange(timing_key, 0, min(10, count))
                    timings = [float(t) for t in timings]
                    
                    if timings:
                        avg = sum(timings) / len(timings)
                        
                        # Cache result
                        self.learning_cache[cache_key] = {
                            'value': avg,
                            'timestamp': datetime.utcnow()
                        }
                        
                        return avg
            except:
                pass
        
        return None
    
    async def _store_timing_metric(self, domain: str, timing_ms: float, job: Any = None):
        """Store timing metric for historical analysis."""
        if self.redis:
            try:
                timing_key = f"timing_history:{domain}"
                
                # Store in Redis list (keep last 100)
                await self.redis.lpush(timing_key, str(timing_ms))
                await self.redis.ltrim(timing_key, 0, 99)
                
                # Set expiry
                await self.redis.expire(timing_key, 86400)  # 24 hours
            except:
                pass
    
    async def _increment_counter(self, key: str, ttl: int) -> int:
        """Increment counter in Redis with TTL."""
        if not self.redis:
            return 0
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl)
            results = await pipe.execute()
            return results[0]
        except:
            return 0
    
    async def _get_evasion_success_counts(self, domain: str, evasion_level: int) -> Dict[str, int]:
        """Get success/failure counts for evasion level."""
        if not self.redis:
            return {}
        
        try:
            success_key = f"evasion:{domain}:{evasion_level}:true"
            failure_key = f"evasion:{domain}:{evasion_level}:false"
            
            pipe = self.redis.pipeline()
            pipe.get(success_key)
            pipe.get(failure_key)
            results = await pipe.execute()
            
            counts = {
                'success': int(results[0] or 0),
                'failure': int(results[1] or 0)
            }
            
            return counts
        except:
            return {}
    
    async def _get_peak_hours(self, domain: str) -> List[Dict[str, Any]]:
        """Get peak execution hours for domain."""
        if not self.redis:
            return []
        
        try:
            peak_hours = []
            
            for hour in range(24):
                key = f"execution_hour:{domain}:{hour}"
                count = await self.redis.get(key)
                
                if count:
                    peak_hours.append({
                        'hour': hour,
                        'count': int(count),
                        'hour_label': f"{hour:02d}:00"
                    })
            
            # Sort by count descending
            peak_hours.sort(key=lambda x: x['count'], reverse=True)
            
            return peak_hours[:3]  # Top 3 hours
        except:
            return []
    
    def _calculate_deviation(self, current: float, historical: float) -> float:
        """Calculate percentage deviation from historical average."""
        if not historical:
            return 0
        return ((current - historical) / historical) * 100
    
    def _classify_timing(self, current: float, historical: float) -> str:
        """Classify timing as normal, slow, or fast."""
        if not historical:
            return "unknown"
        
        deviation = self._calculate_deviation(current, historical)
        
        if deviation > 50:
            return "very_slow"
        elif deviation > 20:
            return "slow"
        elif deviation < -20:
            return "fast"
        elif deviation < -50:
            return "very_fast"
        else:
            return "normal"
    
    def _classify_error(self, error: str) -> str:
        """Classify error type."""
        error_lower = error.lower()
        
        if "timeout" in error_lower:
            return "timeout"
        elif "network" in error_lower or "connection" in error_lower:
            return "network"
        elif "not found" in error_lower or "404" in error:
            return "not_found"
        elif "forbidden" in error_lower or "403" in error:
            return "forbidden"
        elif "captcha" in error_lower:
            return "captcha"
        elif "blocked" in error_lower:
            return "blocked"
        elif "invalid" in error_lower:
            return "invalid"
        elif "javascript" in error_lower:
            return "javascript"
        elif "selector" in error_lower:
            return "selector_not_found"
        else:
            return "generic"
    
    def _suggest_error_action(self, error_type: str, frequency: int) -> str:
        """Suggest action based on error type and frequency."""
        actions = {
            "timeout": "increase_timeout_or_retry",
            "network": "check_connectivity_or_retry",
            "not_found": "verify_url_or_skip",
            "forbidden": "increase_evasion_or_skip",
            "captcha": "activate_captcha_solver_or_skip",
            "blocked": "increase_evasion_or_circuit_breaker",
            "invalid": "validate_input_or_skip",
            "javascript": "wait_longer_or_retry",
            "selector_not_found": "update_selectors_or_skip",
            "generic": "retry_or_escalate"
        }
        
        base_action = actions.get(error_type, "retry_or_escalate")
        
        if frequency >= 3:
            return f"circuit_breaker_then_{base_action}"
        elif frequency >= 2:
            return f"exponential_backoff_then_{base_action}"
        else:
            return base_action
    
    def _calculate_success_rate(self, success_counts: Dict[str, int]) -> Optional[float]:
        """Calculate success rate from counts."""
        success = success_counts.get('success', 0)
        failure = success_counts.get('failure', 0)
        total = success + failure
        
        if total > 0:
            return success / total
        return None
    
    def _generate_timing_recommendation(self, current: float, historical: float) -> Optional[str]:
        """Generate timing optimization recommendation."""
        if not historical:
            return None
        
        deviation = self._calculate_deviation(current, historical)
        
        if deviation > 100:
            return "investigate_performance_degradation"
        elif deviation > 50:
            return "consider_timeout_increase_or_strategy_change"
        elif deviation < -50:
            return "consider_timeout_decrease_for_efficiency"
        elif deviation > 20:
            return "monitor_for_trends"
        else:
            return "performance_normal"

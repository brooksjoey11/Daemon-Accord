import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Any, Tuple
import pickle
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class PredictiveModel:
    def __init__(self, model_path: str = "/tmp/predictive_models"):
        self.success_models = defaultdict(lambda: RandomForestRegressor(n_estimators=50, random_state=42))
        self.time_models = defaultdict(lambda: RandomForestRegressor(n_estimators=50, random_state=42))
        self.scalers = defaultdict(StandardScaler)
        self.training_data = defaultdict(lambda: deque(maxlen=10000))
        self.model_path = model_path
        self.load_models()
        
    def load_models(self):
        """Load trained models from storage"""
        try:
            with open(f"{self.model_path}/models.pkl", 'rb') as f:
                data = pickle.load(f)
                self.success_models = defaultdict(lambda: RandomForestRegressor(), data.get('success_models', {}))
                self.time_models = defaultdict(lambda: RandomForestRegressor(), data.get('time_models', {}))
                self.scalers = defaultdict(StandardScaler, data.get('scalers', {}))
        except:
            pass
    
    def save_models(self):
        """Save trained models to storage"""
        data = {
            'success_models': dict(self.success_models),
            'time_models': dict(self.time_models),
            'scalers': dict(self.scalers),
            'timestamp': datetime.utcnow()
        }
        with open(f"{self.model_path}/models.pkl", 'wb') as f:
            pickle.dump(data, f)
    
    def predict_success(self, domain: str, strategy: Dict, time_of_day: int) -> Dict:
        """Predict success probability for domain"""
        start_time = datetime.utcnow()
        
        # Prepare features
        features = self._prepare_features(domain, strategy, time_of_day)
        
        # Get or train model
        model = self.success_models[domain]
        
        if self._has_enough_training_data(domain, 'success'):
            try:
                # Scale features
                if domain in self.scalers:
                    features_scaled = self.scalers[domain].transform([features])
                else:
                    features_scaled = [features]
                
                # Predict
                prediction = model.predict(features_scaled)[0]
                confidence = self._calculate_confidence(domain, 'success', features)
                
                # Apply constraints
                prediction = max(0.0, min(1.0, prediction))
                confidence = max(0.1, min(0.95, confidence))
                
            except Exception as e:
                # Fallback to historical average
                prediction = self._fallback_prediction(domain, 'success')
                confidence = 0.3
        else:
            # Not enough data
            prediction = 0.5
            confidence = 0.1
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'domain': domain,
            'strategy': strategy.get('type', 'unknown'),
            'time_of_day': time_of_day,
            'success_probability': round(prediction, 4),
            'confidence': round(confidence, 4),
            'features_used': len(features),
            'prediction_time_ms': round(elapsed, 2),
            'model_used': 'trained' if self._has_enough_training_data(domain, 'success') else 'fallback',
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def predict_optimal_time(self, domain: str, strategy: Dict) -> Dict:
        """Predict optimal execution time for domain"""
        start_time = datetime.utcnow()
        
        # Test different times of day
        predictions = []
        for hour in range(24):
            features = self._prepare_features(domain, strategy, hour)
            
            if self._has_enough_training_data(domain, 'success'):
                try:
                    if domain in self.scalers:
                        features_scaled = self.scalers[domain].transform([features])
                    else:
                        features_scaled = [features]
                    
                    prediction = self.success_models[domain].predict(features_scaled)[0]
                    predictions.append((hour, prediction))
                except:
                    predictions.append((hour, 0.5))
            else:
                predictions.append((hour, 0.5))
        
        # Find optimal time
        if predictions:
            optimal_hour, max_prob = max(predictions, key=lambda x: x[1])
            
            # Calculate confidence
            avg_prob = np.mean([p for _, p in predictions])
            std_prob = np.std([p for _, p in predictions])
            confidence = min(0.95, std_prob * 2) if std_prob > 0 else 0.5
            
            # Get time window (hours with probability within 5% of max)
            optimal_window = [h for h, p in predictions if p >= max_prob - 0.05]
        else:
            optimal_hour = 12  # Default noon
            max_prob = 0.5
            confidence = 0.1
            optimal_window = [optimal_hour]
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'domain': domain,
            'strategy': strategy.get('type', 'unknown'),
            'optimal_hour': optimal_hour,
            'success_probability': round(max_prob, 4),
            'confidence': round(confidence, 4),
            'optimal_window_hours': optimal_window,
            'all_predictions': [{'hour': h, 'probability': round(p, 4)} for h, p in predictions],
            'prediction_time_ms': round(elapsed, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _prepare_features(self, domain: str, strategy: Dict, time_of_day: int) -> List[float]:
        """Prepare features for prediction"""
        features = []
        
        # Time features
        features.append(time_of_day / 24.0)
        features.append(1.0 if 9 <= time_of_day <= 17 else 0.0)  # Business hours
        features.append(1.0 if 0 <= time_of_day <= 5 else 0.0)  # Night hours
        
        # Day of week
        day_of_week = datetime.utcnow().weekday()
        features.append(day_of_week / 7.0)
        features.append(1.0 if day_of_week < 5 else 0.0)  # Weekday
        
        # Strategy features
        strategy_type = strategy.get('type', 'unknown')
        type_encoding = {'evasion': 0.1, 'stealth': 0.3, 'performance': 0.5, 'resilience': 0.7}
        features.append(type_encoding.get(strategy_type, 0.5))
        
        # Strategy parameters
        features.append(strategy.get('retry_count', 3) / 10.0)
        features.append(strategy.get('timeout_ms', 5000) / 30000.0)
        features.append(strategy.get('parallel_operations', 4) / 32.0)
        features.append(1.0 if strategy.get('circuit_breaker', True) else 0.0)
        
        # Historical features from training data
        hist_features = self._get_historical_features(domain, time_of_day, strategy_type)
        features.extend(hist_features)
        
        return features
    
    def _get_historical_features(self, domain: str, time_of_day: int, strategy_type: str) -> List[float]:
        """Get historical performance features"""
        features = []
        
        if domain in self.training_data and self.training_data[domain]:
            data = list(self.training_data[domain])
            
            # Filter by time of day
            time_filtered = [d for d in data if d['time_of_day'] == time_of_day]
            
            # Success rate at this hour
            if time_filtered:
                success_rate = sum(1 for d in time_filtered if d['success']) / len(time_filtered)
                features.append(success_rate)
                features.append(len(time_filtered) / 100.0)  # Sample size
            else:
                features.extend([0.5, 0.0])
            
            # Filter by strategy type
            strategy_filtered = [d for d in data if d['strategy_type'] == strategy_type]
            
            if strategy_filtered:
                strategy_success = sum(1 for d in strategy_filtered if d['success']) / len(strategy_filtered)
                features.append(strategy_success)
                features.append(len(strategy_filtered) / 100.0)
            else:
                features.extend([0.5, 0.0])
            
            # Recent performance (last 24 hours)
            cutoff = datetime.utcnow() - timedelta(hours=24)
            recent = [d for d in data if d['timestamp'] > cutoff]
            
            if recent:
                recent_success = sum(1 for d in recent if d['success']) / len(recent)
                features.append(recent_success)
                features.append(len(recent) / 100.0)
            else:
                features.extend([0.5, 0.0])
            
        else:
            # No historical data
            features.extend([0.5, 0.0, 0.5, 0.0, 0.5, 0.0])
        
        return features
    
    def _has_enough_training_data(self, domain: str, model_type: str) -> bool:
        """Check if enough training data exists"""
        if domain not in self.training_data:
            return False
        
        data_count = len(self.training_data[domain])
        
        # Different thresholds for different models
        if model_type == 'success':
            return data_count >= 50
        elif model_type == 'time':
            return data_count >= 100
        else:
            return data_count >= 50
    
    def _calculate_confidence(self, domain: str, model_type: str, features: List[float]) -> float:
        """Calculate prediction confidence"""
        if domain not in self.training_data:
            return 0.1
        
        data = list(self.training_data[domain])
        
        # Base confidence on data quantity
        data_count = len(data)
        quantity_confidence = min(data_count / 200.0, 0.7)
        
        # Confidence based on feature similarity
        if data_count >= 10:
            # Calculate average distance to training samples
            distances = []
            for sample in data[-50:]:  # Recent samples
                sample_features = self._prepare_features(
                    domain, 
                    sample['strategy'], 
                    sample['time_of_day']
                )
                if len(sample_features) == len(features):
                    distance = np.linalg.norm(np.array(features) - np.array(sample_features))
                    distances.append(distance)
            
            if distances:
                avg_distance = np.mean(distances)
                similarity_confidence = max(0.0, 1.0 - avg_distance * 5)  # Scale factor
            else:
                similarity_confidence = 0.3
        else:
            similarity_confidence = 0.1
        
        # Combine confidences
        confidence = quantity_confidence * 0.6 + similarity_confidence * 0.4
        
        return min(max(confidence, 0.1), 0.95)
    
    def _fallback_prediction(self, domain: str, model_type: str) -> float:
        """Fallback prediction when model not trained"""
        if domain in self.training_data and self.training_data[domain]:
            data = list(self.training_data[domain])
            success_rate = sum(1 for d in data if d['success']) / len(data)
            return success_rate
        else:
            return 0.5
    
    def record_training_data(self, domain: str, execution_record: Dict, 
                            strategy: Dict, success: bool):
        """Record data for model training"""
        timestamp = datetime.utcnow()
        time_of_day = timestamp.hour
        
        training_sample = {
            'domain': domain,
            'timestamp': timestamp,
            'time_of_day': time_of_day,
            'strategy': strategy,
            'strategy_type': strategy.get('type', 'unknown'),
            'success': success,
            'duration_ms': execution_record.get('duration_ms', 0),
            'features': self._prepare_features(domain, strategy, time_of_day)
        }
        
        self.training_data[domain].append(training_sample)
        
        # Retrain model periodically
        if len(self.training_data[domain]) % 100 == 0:
            self._retrain_model(domain)
    
    def _retrain_model(self, domain: str):
        """Retrain prediction models for domain"""
        if domain not in self.training_data or len(self.training_data[domain]) < 50:
            return
        
        data = list(self.training_data[domain])
        
        # Prepare features and labels
        X = []
        y_success = []
        y_time = []
        
        for sample in data:
            features = sample['features']
            X.append(features)
            y_success.append(1.0 if sample['success'] else 0.0)
            y_time.append(sample['duration_ms'])
        
        X = np.array(X)
        y_success = np.array(y_success)
        y_time = np.array(y_time)
        
        # Train/update scaler
        self.scalers[domain] = StandardScaler()
        X_scaled = self.scalers[domain].fit_transform(X)
        
        # Train success model
        self.success_models[domain].fit(X_scaled, y_success)
        
        # Train time model (only if we have enough varied data)
        if len(set(y_time)) > 5:
            self.time_models[domain].fit(X_scaled, y_time)
        
        # Save updated models
        self.save_models()
    
    def get_model_info(self, domain: str) -> Dict:
        """Get information about trained models"""
        has_success_model = self._has_enough_training_data(domain, 'success')
        has_time_model = self._has_enough_training_data(domain, 'time')
        
        training_count = len(self.training_data[domain]) if domain in self.training_data else 0
        
        if has_success_model and domain in self.success_models:
            model = self.success_models[domain]
            feature_importance = list(model.feature_importances_)[:10] if hasattr(model, 'feature_importances_') else []
        else:
            feature_importance = []
        
        return {
            'domain': domain,
            'success_model_trained': has_success_model,
            'time_model_trained': has_time_model,
            'training_samples': training_count,
            'last_retrained': self._get_last_retrain_time(domain),
            'feature_importance': [round(f, 4) for f in feature_importance],
            'prediction_accuracy': self._estimate_accuracy(domain) if has_success_model else None,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _get_last_retrain_time(self, domain: str) -> str:
        """Get last retrain time for domain"""
        # Simplified - would track actual retrain times
        if domain in self.training_data and self.training_data[domain]:
            latest = max(d['timestamp'] for d in self.training_data[domain])
            return latest.isoformat()
        return 'never'
    
    def _estimate_accuracy(self, domain: str) -> float:
        """Estimate model accuracy"""
        if domain not in self.training_data or len(self.training_data[domain]) < 20:
            return 0.0
        
        data = list(self.training_data[domain])
        
        # Simple hold-out validation
        split_idx = len(data) * 4 // 5
        train_data = data[:split_idx]
        test_data = data[split_idx:]
        
        if len(test_data) < 5:
            return 0.5
        
        # Train temporary model
        temp_model = RandomForestRegressor(n_estimators=20, random_state=42)
        X_train = [d['features'] for d in train_data]
        y_train = [1.0 if d['success'] else 0.0 for d in train_data]
        
        if len(set(y_train)) < 2:
            return 0.5
        
        temp_model.fit(X_train, y_train)
        
        # Test
        X_test = [d['features'] for d in test_data]
        y_test = [1.0 if d['success'] else 0.0 for d in test_data]
        predictions = temp_model.predict(X_test)
        
        # Calculate accuracy
        correct = sum(1 for p, a in zip(predictions, y_test) if abs(p - a) < 0.5)
        accuracy = correct / len(test_data)
        
        return round(accuracy, 4)
    
    def batch_predict(self, predictions: List[Dict]) -> List[Dict]:
        """Batch predict success probabilities"""
        results = []
        
        for pred_request in predictions:
            domain = pred_request.get('domain', '')
            strategy = pred_request.get('strategy', {})
            time_of_day = pred_request.get('time_of_day', 12)
            
            if domain and strategy:
                result = self.predict_success(domain, strategy, time_of_day)
                results.append(result)
        
        return results
    
    def get_domain_predictions_summary(self, domain: str) -> Dict:
        """Get summary of predictions for domain"""
        if domain not in self.training_data or not self.training_data[domain]:
            return {'domain': domain, 'prediction_data_available': False}
        
        data = list(self.training_data[domain])
        
        # Calculate hourly success rates
        hourly_success = defaultdict(list)
        for sample in data:
            hourly_success[sample['time_of_day']].append(1.0 if sample['success'] else 0.0)
        
        hourly_summary = []
        for hour in range(24):
            if hour in hourly_success:
                success_rate = np.mean(hourly_success[hour])
                sample_count = len(hourly_success[hour])
            else:
                success_rate = 0.5
                sample_count = 0
            
            hourly_summary.append({
                'hour': hour,
                'success_rate': round(success_rate, 4),
                'sample_count': sample_count
            })
        
        # Strategy performance
        strategy_performance = defaultdict(list)
        for sample in data:
            strategy_type = sample.get('strategy_type', 'unknown')
            strategy_performance[strategy_type].append(1.0 if sample['success'] else 0.0)
        
        strategy_summary = []
        for strategy_type, successes in strategy_performance.items():
            if successes:
                strategy_summary.append({
                    'strategy': strategy_type,
                    'success_rate': round(np.mean(successes), 4),
                    'sample_count': len(successes)
                })
        
        # Recent trend
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        cutoff_7d = datetime.utcnow() - timedelta(days=7)
        
        recent_24h = [d for d in data if d['timestamp'] > cutoff_24h]
        recent_7d = [d for d in data if d['timestamp'] > cutoff_7d]
        
        success_24h = sum(1 for d in recent_24h if d['success']) / len(recent_24h) if recent_24h else 0.0
        success_7d = sum(1 for d in recent_7d if d['success']) / len(recent_7d) if recent_7d else 0.0
        
        return {
            'domain': domain,
            'prediction_data_available': True,
            'total_samples': len(data),
            'overall_success_rate': round(sum(1 for d in data if d['success']) / len(data), 4),
            'hourly_performance': hourly_summary,
            'strategy_performance': strategy_summary,
            'recent_success_24h': round(success_24h, 4),
            'recent_success_7d': round(success_7d, 4),
            'trend': 'improving' if success_24h > success_7d else 'stable' if success_24h == success_7d else 'declining',
            'optimal_hour_prediction': self.predict_optimal_time(domain, {'type': 'evasion'}),
            'timestamp': datetime.utcnow().isoformat()
        }

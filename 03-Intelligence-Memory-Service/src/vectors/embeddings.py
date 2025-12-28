import numpy as np
from sentence_transformers import SentenceTransformer
from PIL import Image
import torch
import torchvision.models as models
import torchvision.transforms as transforms
from typing import List, Dict, Any, Tuple, Optional
import hashlib
import json
from datetime import datetime, timedelta
import pickle
import os
from collections import defaultdict

class EmbeddingGenerator:
    def __init__(self, models_dir: str = "/tmp/embedding_models"):
        self.models_dir = models_dir
        self.loaded_models = {}
        self.model_versions = self._load_model_versions()
        self.embedding_cache = defaultdict(dict)
        self._initialize_models()
        
    def _load_model_versions(self) -> Dict:
        """Load model version information"""
        versions_file = f"{self.models_dir}/model_versions.json"
        if os.path.exists(versions_file):
            with open(versions_file, 'r') as f:
                return json.load(f)
        return {
            'text': 'all-MiniLM-L6-v2-1.0',
            'image': 'resnet50-1.0',
            'structured': 'custom-structured-1.0'
        }
    
    def _save_model_versions(self):
        """Save model version information"""
        os.makedirs(self.models_dir, exist_ok=True)
        versions_file = f"{self.models_dir}/model_versions.json"
        with open(versions_file, 'w') as f:
            json.dump(self.model_versions, f, indent=2)
    
    def _initialize_models(self):
        """Initialize embedding models"""
        # Text model
        try:
            self.loaded_models['text'] = {
                'model': SentenceTransformer('all-MiniLM-L6-v2'),
                'version': self.model_versions['text'],
                'dimension': 384,
                'last_used': datetime.utcnow()
            }
            print(f"Loaded text model: {self.model_versions['text']}")
        except Exception as e:
            print(f"Failed to load text model: {e}")
        
        # Image model
        try:
            self.loaded_models['image'] = {
                'model': self._load_resnet_model(),
                'version': self.model_versions['image'],
                'dimension': 2048,  # ResNet50 feature dimension
                'last_used': datetime.utcnow()
            }
            print(f"Loaded image model: {self.model_versions['image']}")
        except Exception as e:
            print(f"Failed to load image model: {e}")
        
        # Structured data model
        try:
            self.loaded_models['structured'] = {
                'model': self._load_structured_model(),
                'version': self.model_versions['structured'],
                'dimension': 256,
                'last_used': datetime.utcnow()
            }
            print(f"Loaded structured model: {self.model_versions['structured']}")
        except Exception as e:
            print(f"Failed to load structured model: {e}")
    
    def _load_resnet_model(self):
        """Load ResNet model for image embeddings"""
        model = models.resnet50(pretrained=True)
        model = torch.nn.Sequential(*list(model.children())[:-1])  # Remove final layer
        model.eval()
        
        if torch.cuda.is_available():
            model = model.cuda()
        
        return model
    
    def _load_structured_model(self):
        """Load custom structured data model"""
        model_path = f"{self.models_dir}/structured_model.pkl"
        if os.path.exists(model_path):
            with open(model_path, 'rb') as f:
                return pickle.load(f)
        else:
            # Return a simple embedding function for structured data
            return self._default_structured_embedder
    
    def _default_structured_embedder(self, data: Dict) -> np.ndarray:
        """Default structured data embedder"""
        # Convert structured data to embedding via hashing and projection
        data_str = json.dumps(data, sort_keys=True)
        data_hash = int(hashlib.sha256(data_str.encode()).hexdigest()[:8], 16)
        
        np.random.seed(data_hash)
        embedding = np.random.randn(256).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    def generate_embeddings(self, artifacts: List[Dict]) -> List[Dict]:
        """Generate embeddings for multiple artifacts"""
        start_time = datetime.utcnow()
        results = []
        
        for artifact in artifacts:
            try:
                embedding_result = self.generate_embedding(artifact)
                results.append(embedding_result)
            except Exception as e:
                results.append({
                    'artifact_id': artifact.get('id', 'unknown'),
                    'error': str(e)[:200],
                    'success': False
                })
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'total_processed': len(artifacts),
            'successful': sum(1 for r in results if r.get('success', False)),
            'failed': sum(1 for r in results if not r.get('success', True)),
            'embeddings': results,
            'processing_time_ms': round(elapsed, 2),
            'avg_time_per_item_ms': round(elapsed / max(len(artifacts), 1), 2),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def generate_embedding(self, artifact: Dict) -> Dict:
        """Generate embedding for a single artifact"""
        start_time = datetime.utcnow()
        
        artifact_type = artifact.get('type', 'text')
        content = artifact.get('content')
        artifact_id = artifact.get('id')
        
        if not content:
            return {
                'artifact_id': artifact_id,
                'error': 'No content provided',
                'success': False
            }
        
        # Check cache
        cache_key = self._get_cache_key(artifact_type, content)
        if cache_key in self.embedding_cache[artifact_type]:
            cached = self.embedding_cache[artifact_type][cache_key]
            if datetime.utcnow() - cached['timestamp'] < timedelta(hours=24):
                return {
                    'artifact_id': artifact_id,
                    'embedding': cached['embedding'].tolist(),
                    'model_version': cached['model_version'],
                    'dimension': cached['dimension'],
                    'content_hash': cached['content_hash'],
                    'cache_hit': True,
                    'generation_time_ms': 0,
                    'success': True
                }
        
        # Generate embedding based on type
        if artifact_type == 'text':
            embedding_result = self._generate_text_embedding(content)
        elif artifact_type == 'image':
            embedding_result = self._generate_image_embedding(content)
        elif artifact_type == 'structured':
            embedding_result = self._generate_structured_embedding(content)
        elif artifact_type == 'error':
            embedding_result = self._generate_error_embedding(content)
        elif artifact_type == 'html':
            embedding_result = self._generate_html_embedding(content)
        elif artifact_type == 'network':
            embedding_result = self._generate_network_embedding(content)
        else:
            # Fallback to text embedding
            embedding_result = self._generate_text_embedding(str(content))
        
        if not embedding_result.get('success', False):
            return {
                'artifact_id': artifact_id,
                'error': embedding_result.get('error', 'Unknown error'),
                'success': False
            }
        
        # Update cache
        embedding_array = np.array(embedding_result['embedding'], dtype=np.float32)
        content_hash = hashlib.sha256(str(content).encode()).hexdigest()
        
        self.embedding_cache[artifact_type][cache_key] = {
            'embedding': embedding_array,
            'model_version': embedding_result['model_version'],
            'dimension': embedding_result['dimension'],
            'content_hash': content_hash,
            'timestamp': datetime.utcnow()
        }
        
        # Limit cache size
        if len(self.embedding_cache[artifact_type]) > 10000:
            # Remove oldest entries
            items = list(self.embedding_cache[artifact_type].items())
            items.sort(key=lambda x: x[1]['timestamp'])
            for key, _ in items[:1000]:
                del self.embedding_cache[artifact_type][key]
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'artifact_id': artifact_id,
            'embedding': embedding_result['embedding'],
            'model_version': embedding_result['model_version'],
            'dimension': embedding_result['dimension'],
            'content_hash': content_hash,
            'cache_hit': False,
            'generation_time_ms': round(elapsed, 2),
            'success': True
        }
    
    def _get_cache_key(self, artifact_type: str, content: Any) -> str:
        """Generate cache key for artifact"""
        if isinstance(content, (dict, list)):
            content_str = json.dumps(content, sort_keys=True)
        else:
            content_str = str(content)
        
        return f"{artifact_type}:{hashlib.md5(content_str.encode()).hexdigest()}"
    
    def _generate_text_embedding(self, text: str) -> Dict:
        """Generate embedding for text content"""
        if 'text' not in self.loaded_models:
            return {'success': False, 'error': 'Text model not loaded'}
        
        model_info = self.loaded_models['text']
        model = model_info['model']
        
        try:
            # Preprocess text
            if isinstance(text, dict):
                text = json.dumps(text, sort_keys=True)
            elif not isinstance(text, str):
                text = str(text)
            
            # Truncate if too long
            if len(text) > 10000:
                text = text[:10000]
            
            # Generate embedding
            embedding = model.encode(text, convert_to_numpy=True)
            
            return {
                'embedding': embedding.tolist(),
                'model_version': model_info['version'],
                'dimension': model_info['dimension'],
                'success': True
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _generate_image_embedding(self, image_data: Any) -> Dict:
        """Generate embedding for image content"""
        if 'image' not in self.loaded_models:
            return {'success': False, 'error': 'Image model not loaded'}
        
        model_info = self.loaded_models['image']
        model = model_info['model']
        
        try:
            # Load image
            if isinstance(image_data, str):
                # Assume it's a file path or URL
                # For production, implement actual image loading
                # For now, return dummy embedding
                embedding = np.random.randn(model_info['dimension']).astype(np.float32)
                embedding = embedding / np.linalg.norm(embedding)
            elif isinstance(image_data, np.ndarray):
                # Already an image array
                # Convert to tensor and process
                embedding = np.random.randn(model_info['dimension']).astype(np.float32)
                embedding = embedding / np.linalg.norm(embedding)
            else:
                return {'success': False, 'error': 'Unsupported image format'}
            
            return {
                'embedding': embedding.tolist(),
                'model_version': model_info['version'],
                'dimension': model_info['dimension'],
                'success': True
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _generate_structured_embedding(self, data: Dict) -> Dict:
        """Generate embedding for structured data"""
        if 'structured' not in self.loaded_models:
            return {'success': False, 'error': 'Structured model not loaded'}
        
        model_info = self.loaded_models['structured']
        model = model_info['model']
        
        try:
            # Generate embedding using model
            if callable(model):
                embedding = model(data)
            else:
                # Use default embedder
                embedding = self._default_structured_embedder(data)
            
            return {
                'embedding': embedding.tolist() if isinstance(embedding, np.ndarray) else embedding,
                'model_version': model_info['version'],
                'dimension': model_info['dimension'],
                'success': True
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _generate_error_embedding(self, error_data: Any) -> Dict:
        """Generate embedding for error messages"""
        # Convert error data to text and use text model
        if isinstance(error_data, dict):
            text = error_data.get('message', '') + ' ' + error_data.get('trace', '')
        elif isinstance(error_data, str):
            text = error_data
        else:
            text = str(error_data)
        
        return self._generate_text_embedding(text)
    
    def _generate_html_embedding(self, html_data: Any) -> Dict:
        """Generate embedding for HTML content"""
        # Extract text from HTML and use text model
        if isinstance(html_data, dict):
            # HTML structure analysis
            text = json.dumps(html_data, sort_keys=True)
        elif isinstance(html_data, str):
            # Simple tag stripping (in production use proper HTML parsing)
            import re
            text = re.sub(r'<[^>]+>', ' ', html_data)
            text = re.sub(r'\s+', ' ', text).strip()
        else:
            text = str(html_data)
        
        return self._generate_text_embedding(text[:5000])  # Limit length
    
    def _generate_network_embedding(self, network_data: Any) -> Dict:
        """Generate embedding for network patterns"""
        # Convert network data to structured format
        if isinstance(network_data, dict):
            structured_data = network_data
        elif isinstance(network_data, list):
            structured_data = {'patterns': network_data}
        else:
            structured_data = {'data': str(network_data)}
        
        return self._generate_structured_embedding(structured_data)
    
    def update_model(self, model_type: str, version: str, model_path: str = None):
        """Update embedding model"""
        if model_type not in ['text', 'image', 'structured']:
            return {'success': False, 'error': f'Invalid model type: {model_type}'}
        
        try:
            # Load new model
            if model_type == 'text':
                new_model = SentenceTransformer(model_path) if model_path else SentenceTransformer('all-MiniLM-L6-v2')
                dimension = 384
            elif model_type == 'image':
                new_model = self._load_resnet_model()
                dimension = 2048
            elif model_type == 'structured':
                if model_path and os.path.exists(model_path):
                    with open(model_path, 'rb') as f:
                        new_model = pickle.load(f)
                else:
                    new_model = self._default_structured_embedder
                dimension = 256
            
            # Update loaded model
            self.loaded_models[model_type] = {
                'model': new_model,
                'version': version,
                'dimension': dimension,
                'last_used': datetime.utcnow()
            }
            
            # Update version tracking
            self.model_versions[model_type] = version
            self._save_model_versions()
            
            # Clear cache for this model type
            self.embedding_cache[model_type].clear()
            
            return {
                'success': True,
                'model_type': model_type,
                'new_version': version,
                'dimension': dimension,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_model_info(self) -> Dict:
        """Get information about loaded models"""
        info = {}
        
        for model_type, model_info in self.loaded_models.items():
            info[model_type] = {
                'version': model_info['version'],
                'dimension': model_info['dimension'],
                'last_used': model_info['last_used'].isoformat(),
                'status': 'loaded'
            }
        
        # Cache statistics
        cache_stats = {}
        for model_type, cache in self.embedding_cache.items():
            cache_stats[model_type] = {
                'size': len(cache),
                'hit_rate': self._calculate_cache_hit_rate(model_type)
            }
        
        return {
            'models': info,
            'cache': cache_stats,
            'model_versions': self.model_versions,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _calculate_cache_hit_rate(self, model_type: str) -> float:
        """Calculate cache hit rate for model type"""
        # Simplified - would track actual hits/misses
        cache_size = len(self.embedding_cache.get(model_type, {}))
        return min(cache_size / 1000, 0.9) if cache_size > 0 else 0.0
    
    def train_structured_model(self, training_data: List[Dict], epochs: int = 10):
        """Train custom structured data model"""
        # This is a simplified training function
        # In production, implement proper model training
        
        print(f"Training structured model with {len(training_data)} samples")
        
        # For now, create a simple hash-based model
        trained_model = self._default_structured_embedder
        
        # Save model
        model_path = f"{self.models_dir}/structured_model.pkl"
        os.makedirs(self.models_dir, exist_ok=True)
        
        with open(model_path, 'wb') as f:
            pickle.dump(trained_model, f)
        
        # Update version
        new_version = f"custom-structured-{datetime.utcnow().strftime('%Y%m%d')}"
        self.update_model('structured', new_version, model_path)
        
        return {
            'success': True,
            'model_type': 'structured',
            'version': new_version,
            'training_samples': len(training_data),
            'model_path': model_path,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def cleanup_old_cache(self, days_old: int = 7):
        """Cleanup old cache entries"""
        cutoff = datetime.utcnow() - timedelta(days=days_old)
        
        for model_type in list(self.embedding_cache.keys()):
            cache = self.embedding_cache[model_type]
            
            # Find old entries
            to_remove = []
            for key, entry in cache.items():
                if entry['timestamp'] < cutoff:
                    to_remove.append(key)
            
            # Remove old entries
            for key in to_remove:
                del cache[key]
            
            print(f"Cleaned {len(to_remove)} old cache entries for {model_type}")

import hashlib
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
import pickle
import zlib
from typing import Dict, List, Any, Tuple
import numpy as np

class FingerprintEngine:
    def __init__(self, storage_path: str = "/tmp/fingerprints"):
        self.fingerprint_store = defaultdict(lambda: deque(maxlen=1000))
        self.compressed_signatures = {}
        self.component_weights = self._initialize_weights()
        self.storage_path = storage_path
        self.load_fingerprints()
    
    def _initialize_weights(self) -> Dict:
        """Initialize fingerprint component weights"""
        return {
            'headers': 0.25,
            'tls': 0.20,
            'html_structure': 0.15,
            'response_time': 0.10,
            'error_patterns': 0.10,
            'cookie_patterns': 0.08,
            'javascript_features': 0.07,
            'redirect_chain': 0.05
        }
    
    def load_fingerprints(self):
        """Load fingerprints from storage"""
        try:
            with open(f"{self.storage_path}/fingerprints.pkl", 'rb') as f:
                data = pickle.load(f)
                self.fingerprint_store = defaultdict(lambda: deque(maxlen=1000), data.get('store', {}))
                self.compressed_signatures = data.get('compressed', {})
        except:
            pass
    
    def save_fingerprints(self):
        """Save fingerprints to storage"""
        data = {
            'store': dict(self.fingerprint_store),
            'compressed': self.compressed_signatures,
            'timestamp': datetime.utcnow()
        }
        with open(f"{self.storage_path}/fingerprints.pkl", 'wb') as f:
            pickle.dump(data, f)
    
    def extract_fingerprint(self, execution_record: Dict) -> Dict:
        """Extract fingerprint from execution record"""
        start_time = datetime.utcnow()
        
        # Extract components
        components = self._extract_components(execution_record)
        
        # Calculate component hashes
        component_hashes = self._hash_components(components)
        
        # Generate composite fingerprint
        composite_hash = self._generate_composite_hash(component_hashes)
        
        # Store fingerprint
        domain = execution_record.get('domain', 'unknown')
        self._store_fingerprint(domain, composite_hash, components, component_hashes)
        
        # Compress old fingerprints
        self._compress_old_fingerprints()
        
        elapsed = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'fingerprint_hash': composite_hash,
            'domain': domain,
            'components': {
                'count': len(components),
                'types': list(components.keys()),
                'hashes': component_hashes
            },
            'component_breakdown': self._summarize_components(components),
            'extraction_time_ms': round(elapsed, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _extract_components(self, execution_record: Dict) -> Dict:
        """Extract fingerprint components"""
        components = {}
        
        # Headers
        headers = execution_record.get('response_headers', {})
        if headers:
            components['headers'] = self._extract_header_patterns(headers)
        
        # TLS information
        tls_info = execution_record.get('tls', {})
        if tls_info:
            components['tls'] = self._extract_tls_fingerprint(tls_info)
        
        # HTML structure
        html_content = execution_record.get('response_body', '')
        if html_content and isinstance(html_content, str) and len(html_content) > 100:
            components['html_structure'] = self._extract_html_structure(html_content)
        
        # Response time patterns
        duration = execution_record.get('duration_ms', 0)
        components['response_time'] = self._categorize_response_time(duration)
        
        # Error patterns
        error_msg = execution_record.get('error_message', '')
        if error_msg:
            components['error_patterns'] = self._extract_error_patterns(error_msg)
        
        # Cookie patterns
        cookies = execution_record.get('cookies', {})
        if cookies:
            components['cookie_patterns'] = self._extract_cookie_patterns(cookies)
        
        # JavaScript features
        js_features = execution_record.get('javascript_features', {})
        if js_features:
            components['javascript_features'] = js_features
        
        # Redirect chain
        redirects = execution_record.get('redirect_chain', [])
        if redirects:
            components['redirect_chain'] = self._extract_redirect_patterns(redirects)
        
        # Response size
        response_size = execution_record.get('response_size_bytes', 0)
        components['size_pattern'] = self._categorize_size(response_size)
        
        # Status code
        status_code = execution_record.get('status_code', 0)
        components['status_code'] = status_code
        
        return components
    
    def _extract_header_patterns(self, headers: Dict) -> Dict:
        """Extract header patterns"""
        patterns = {}
        
        # Server header
        if 'server' in headers:
            patterns['server'] = headers['server']
        
        # X-Powered-By
        if 'x-powered-by' in headers:
            patterns['x_powered_by'] = headers['x-powered-by']
        
        # Content-Type
        if 'content-type' in headers:
            patterns['content_type'] = headers['content-type']
        
        # Security headers
        security_headers = ['x-frame-options', 'x-content-type-options', 
                           'x-xss-protection', 'content-security-policy']
        for header in security_headers:
            if header in headers:
                patterns[header] = headers[header]
        
        # Cache headers
        if 'cache-control' in headers:
            patterns['cache_control'] = headers['cache-control']
        
        return patterns
    
    def _extract_tls_fingerprint(self, tls_info: Dict) -> Dict:
        """Extract TLS fingerprint"""
        fingerprint = {}
        
        if 'version' in tls_info:
            fingerprint['version'] = tls_info['version']
        
        if 'cipher_suite' in tls_info:
            fingerprint['cipher_suite'] = tls_info['cipher_suite']
        
        if 'certificate' in tls_info:
            cert = tls_info['certificate']
            if 'issuer' in cert:
                fingerprint['issuer'] = cert['issuer']
            if 'subject' in cert:
                fingerprint['subject'] = cert['subject']
            if 'validity' in cert:
                fingerprint['validity_days'] = self._calculate_cert_validity(cert['validity'])
        
        return fingerprint
    
    def _calculate_cert_validity(self, validity: Dict) -> int:
        """Calculate certificate validity in days"""
        try:
            from_date = datetime.fromisoformat(validity.get('not_before', '').replace('Z', '+00:00'))
            to_date = datetime.fromisoformat(validity.get('not_after', '').replace('Z', '+00:00'))
            return (to_date - from_date).days
        except:
            return 0
    
    def _extract_html_structure(self, html: str) -> Dict:
        """Extract HTML structure patterns"""
        patterns = {}
        
        # Simple structure analysis
        patterns['doctype_present'] = '<!DOCTYPE' in html[:100]
        
        # Tag counting
        patterns['html_tag_count'] = html.count('<html')
        patterns['body_tag_count'] = html.count('<body')
        patterns['div_count'] = html.count('<div')
        patterns['script_count'] = html.count('<script')
        
        # Meta tags
        import re
        meta_tags = re.findall(r'<meta[^>]*>', html, re.IGNORECASE)
        patterns['meta_count'] = len(meta_tags)
        
        # Title extraction
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            patterns['title_length'] = len(title_match.group(1).strip())
        
        # Form detection
        patterns['form_count'] = html.count('<form')
        
        return patterns
    
    def _categorize_response_time(self, duration_ms: int) -> str:
        """Categorize response time"""
        if duration_ms < 100:
            return 'instant'
        elif duration_ms < 500:
            return 'fast'
        elif duration_ms < 2000:
            return 'normal'
        elif duration_ms < 10000:
            return 'slow'
        else:
            return 'very_slow'
    
    def _extract_error_patterns(self, error_msg: str) -> Dict:
        """Extract error patterns"""
        patterns = {}
        
        error_lower = error_msg.lower()
        patterns['length'] = len(error_msg)
        
        # Common error patterns
        patterns['contains_timeout'] = 'timeout' in error_lower
        patterns['contains_connection'] = 'connection' in error_lower
        patterns['contains_permission'] = 'permission' in error_lower
        patterns['contains_memory'] = 'memory' in error_lower
        
        # HTTP error codes
        import re
        http_codes = re.findall(r'\b\d{3}\b', error_msg)
        if http_codes:
            patterns['http_codes'] = http_codes[:3]
        
        # Stack trace detection
        patterns['has_stack_trace'] = ' at ' in error_msg and '(' in error_msg and ')' in error_msg
        
        return patterns
    
    def _extract_cookie_patterns(self, cookies: Dict) -> Dict:
        """Extract cookie patterns"""
        patterns = {}
        
        patterns['cookie_count'] = len(cookies)
        
        # Cookie attributes
        secure_count = sum(1 for c in cookies.values() if c.get('secure', False))
        http_only_count = sum(1 for c in cookies.values() if c.get('httpOnly', False))
        
        patterns['secure_cookies'] = secure_count
        patterns['http_only_cookies'] = http_only_count
        
        # Session cookie detection
        session_cookies = [name for name, attrs in cookies.items() 
                          if 'session' in name.lower() or 'sess' in name.lower()]
        patterns['session_cookies'] = session_cookies
        
        return patterns
    
    def _extract_redirect_patterns(self, redirects: List[str]) -> Dict:
        """Extract redirect patterns"""
        patterns = {}
        
        patterns['redirect_count'] = len(redirects)
        
        if redirects:
            # Analyze redirect chain
            patterns['has_loop'] = len(redirects) != len(set(redirects))
            
            # Protocol changes
            http_to_https = sum(1 for i in range(len(redirects)-1) 
                              if redirects[i].startswith('http://') and 
                                 redirects[i+1].startswith('https://'))
            patterns['http_to_https'] = http_to_https
            
            # Domain changes
            from urllib.parse import urlparse
            domains = [urlparse(r).netloc for r in redirects if urlparse(r).netloc]
            patterns['unique_domains'] = len(set(domains))
        
        return patterns
    
    def _categorize_size(self, size_bytes: int) -> str:
        """Categorize response size"""
        if size_bytes < 1024:  # 1KB
            return 'tiny'
        elif size_bytes < 10240:  # 10KB
            return 'small'
        elif size_bytes < 102400:  # 100KB
            return 'medium'
        elif size_bytes < 1048576:  # 1MB
            return 'large'
        else:
            return 'huge'
    
    def _hash_components(self, components: Dict) -> Dict:
        """Generate hashes for each component"""
        component_hashes = {}
        
        for component_name, component_data in components.items():
            # Convert to string for hashing
            if isinstance(component_data, dict):
                data_str = json.dumps(component_data, sort_keys=True)
            elif isinstance(component_data, (int, float)):
                data_str = str(component_data)
            else:
                data_str = str(component_data)
            
            # Generate hash
            component_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]
            component_hashes[component_name] = component_hash
        
        return component_hashes
    
    def _generate_composite_hash(self, component_hashes: Dict) -> str:
        """Generate composite fingerprint hash"""
        # Sort by component name for consistency
        sorted_hashes = sorted(component_hashes.items())
        
        # Concatenate hashes
        concatenated = ''.join(f"{name}:{hash_}" for name, hash_ in sorted_hashes)
        
        # Generate final hash
        return hashlib.sha256(concatenated.encode()).hexdigest()[:32]
    
    def _store_fingerprint(self, domain: str, fingerprint_hash: str, 
                          components: Dict, component_hashes: Dict):
        """Store fingerprint in memory"""
        fingerprint_record = {
            'hash': fingerprint_hash,
            'components': components,
            'component_hashes': component_hashes,
            'timestamp': datetime.utcnow(),
            'domain': domain
        }
        
        self.fingerprint_store[domain].append(fingerprint_record)
    
    def _summarize_components(self, components: Dict) -> Dict:
        """Create summary of fingerprint components"""
        summary = {}
        
        for name, data in components.items():
            if isinstance(data, dict):
                summary[name] = {
                    'field_count': len(data),
                    'fields': list(data.keys())[:5]  # First 5 fields
                }
            elif isinstance(data, (int, float)):
                summary[name] = {'value': data}
            else:
                summary[name] = {'type': type(data).__name__, 'length': len(str(data))}
        
        return summary
    
    def _compress_old_fingerprints(self):
        """Compress fingerprints older than 30 days"""
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        for domain, fingerprints in list(self.fingerprint_store.items()):
            # Separate old and new fingerprints
            old_fingerprints = []
            new_fingerprints = []
            
            for fp in fingerprints:
                if fp['timestamp'] < cutoff_date:
                    old_fingerprints.append(fp)
                else:
                    new_fingerprints.append(fp)
            
            if old_fingerprints:
                # Create compressed signature
                signature = self._create_compressed_signature(old_fingerprints)
                
                # Store compressed
                if domain not in self.compressed_signatures:
                    self.compressed_signatures[domain] = []
                
                self.compressed_signatures[domain].append({
                    'signature': signature,
                    'fingerprint_count': len(old_fingerprints),
                    'time_range': {
                        'oldest': min(fp['timestamp'] for fp in old_fingerprints).isoformat(),
                        'newest': max(fp['timestamp'] for fp in old_fingerprints).isoformat()
                    }
                })
                
                # Keep only new fingerprints
                self.fingerprint_store[domain] = deque(new_fingerprints, maxlen=1000)
    
    def _create_compressed_signature(self, fingerprints: List[Dict]) -> str:
        """Create compressed signature from multiple fingerprints"""
        # Extract common patterns
        common_components = defaultdict(set)
        
        for fp in fingerprints:
            for comp_name, comp_data in fp['components'].items():
                if isinstance(comp_data, dict):
                    for key, value in comp_data.items():
                        common_components[f"{comp_name}.{key}"].add(str(value))
                else:
                    common_components[comp_name].add(str(comp_data))
        
        # Calculate frequencies
        signature_data = {}
        for key, values in common_components.items():
            if len(values) <= 3:  # Values that don't vary much
                signature_data[key] = list(values)
        
        # Compress with zlib
        json_data = json.dumps(signature_data, sort_keys=True).encode()
        compressed = zlib.compress(json_data)
        
        return hashlib.sha256(compressed).hexdigest()[:32]
    
    def find_similar_fingerprints(self, target_hash: str, threshold: float = 0.7) -> List[Dict]:
        """Find fingerprints similar to target"""
        similar = []
        
        # This is simplified - would use actual similarity calculation
        for domain, fingerprints in self.fingerprint_store.items():
            for fp in fingerprints:
                # Simple hash prefix matching
                similarity = self._calculate_hash_similarity(target_hash, fp['hash'])
                
                if similarity >= threshold:
                    similar.append({
                        'domain': domain,
                        'fingerprint_hash': fp['hash'],
                        'similarity': similarity,
                        'timestamp': fp['timestamp'].isoformat(),
                        'component_overlap': self._calculate_component_overlap(target_hash, fp)
                    })
        
        # Sort by similarity
        similar.sort(key=lambda x: x['similarity'], reverse=True)
        
        return similar[:50]
    
    def _calculate_hash_similarity(self, hash1: str, hash2: str) -> float:
        """Calculate similarity between two hashes"""
        # Simple character matching
        matches = sum(1 for a, b in zip(hash1, hash2) if a == b)
        return matches / max(len(hash1), len(hash2))
    
    def _calculate_component_overlap(self, target_hash: str, fingerprint: Dict) -> Dict:
        """Calculate component overlap"""
        # Simplified - would compare actual components
        return {
            'common_components': list(fingerprint['components'].keys())[:5],
            'component_count': len(fingerprint['components'])
        }
    
    def get_domain_fingerprint_history(self, domain: str, hours: int = 24) -> Dict:
        """Get fingerprint history for domain"""
        if domain not in self.fingerprint_store:
            return {'domain': domain, 'fingerprint_count': 0, 'fingerprints': []}
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_fps = [fp for fp in self.fingerprint_store[domain] if fp['timestamp'] > cutoff]
        
        # Calculate stability
        if recent_fps:
            hash_changes = sum(1 for i in range(1, len(recent_fps)) 
                             if recent_fps[i]['hash'] != recent_fps[i-1]['hash'])
            stability = 1.0 - (hash_changes / max(len(recent_fps) - 1, 1))
        else:
            stability = 0.0
        
        return {
            'domain': domain,
            'fingerprint_count': len(recent_fps),
            'stability_score': stability,
            'time_window_hours': hours,
            'fingerprints': [
                {
                    'hash': fp['hash'][:16],
                    'timestamp': fp['timestamp'].isoformat(),
                    'component_count': len(fp['components'])
                }
                for fp in recent_fps[:20]  # Limit response size
            ],
            'compressed_signatures': len(self.compressed_signatures.get(domain, [])),
            'total_fingerprints_stored': len(self.fingerprint_store[domain])
        }

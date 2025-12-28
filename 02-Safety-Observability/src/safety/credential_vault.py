import os
import json
import hashlib
from typing import Optional, Dict, Any, Tuple
import base64
import hmac
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

class CredentialVault:
    def __init__(self, redis_client=None, encryption_key: Optional[str] = None):
        self.redis = redis_client
        self.env_prefix = "CRED_"
        
        # Initialize encryption
        self.fernet = None
        if encryption_key:
            self._init_encryption(encryption_key)
        
        # In-memory cache
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        
    def _init_encryption(self, key: str):
        """Initialize Fernet encryption with key derivation."""
        salt = b'credential_vault_salt'  # Should be stored securely in production
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key_material = kdf.derive(key.encode())
        fernet_key = base64.urlsafe_b64encode(key_material)
        self.fernet = Fernet(fernet_key)
    
    def _domain_to_env_key(self, domain: str, credential_type: str) -> str:
        """Convert domain and credential type to environment variable name."""
        # Normalize domain
        domain_clean = domain.replace('.', '_').replace('-', '_').upper()
        
        # Build key
        if credential_type == "username":
            return f"{self.env_prefix}{domain_clean}_USERNAME"
        elif credential_type == "password":
            return f"{self.env_prefix}{domain_clean}_PASSWORD"
        elif credential_type == "api_key":
            return f"{self.env_prefix}{domain_clean}_API_KEY"
        elif credential_type == "token":
            return f"{self.env_prefix}{domain_clean}_TOKEN"
        else:
            # Generic credential
            type_clean = credential_type.upper().replace('-', '_')
            return f"{self.env_prefix}{domain_clean}_{type_clean}"
    
    async def get_credential(self, domain: str, credential_type: str = "password", 
                           placeholder: Optional[str] = None) -> Optional[str]:
        """
        Retrieve credential from environment variables with fallback.
        
        Priority:
        1. Redis cache (encrypted)
        2. Environment variable
        3. Placeholder value
        4. Generated placeholder
        """
        cache_key = f"cred:{domain}:{credential_type}"
        
        # Check cache first
        if cache_key in self._cache:
            cached_data = self._cache[cache_key]
            if cached_data['expires'] > os.times().elapsed:
                return cached_data['value']
        
        # Try environment variable
        env_key = self._domain_to_env_key(domain, credential_type)
        env_value = os.environ.get(env_key)
        
        if env_value:
            # Decrypt if necessary
            if env_value.startswith('enc:'):
                if self.fernet:
                    try:
                        encrypted = env_value[4:]
                        decrypted = self.fernet.decrypt(encrypted.encode()).decode()
                        value = decrypted
                    except:
                        value = env_value
                else:
                    value = env_value
            else:
                value = env_value
            
            # Cache the value
            self._cache[cache_key] = {
                'value': value,
                'expires': os.times().elapsed + self._cache_ttl,
                'source': 'env'
            }
            
            return value
        
        # Try Redis
        if self.redis:
            try:
                redis_key = f"vault:{domain}:{credential_type}"
                redis_value = await self.redis.get(redis_key)
                
                if redis_value:
                    if self.fernet:
                        try:
                            decrypted = self.fernet.decrypt(redis_value).decode()
                            value = decrypted
                        except:
                            value = redis_value.decode()
                    else:
                        value = redis_value.decode()
                    
                    self._cache[cache_key] = {
                        'value': value,
                        'expires': os.times().elapsed + self._cache_ttl,
                        'source': 'redis'
                    }
                    
                    return value
            except:
                pass
        
        # Use placeholder or generate one
        if placeholder:
            value = placeholder
        else:
            value = self._generate_placeholder(domain, credential_type)
        
        # Cache placeholder
        self._cache[cache_key] = {
            'value': value,
            'expires': os.times().elapsed + self._cache_ttl,
            'source': 'placeholder'
        }
        
        return value
    
    async def get_credentials(self, domain: str, types: list = None) -> Dict[str, str]:
        """Get multiple credentials for a domain."""
        if types is None:
            types = ['username', 'password']
        
        credentials = {}
        for cred_type in types:
            value = await self.get_credential(domain, cred_type)
            if value:
                credentials[cred_type] = value
        
        return credentials
    
    async def set_credential(self, domain: str, credential_type: str, value: str, 
                           ttl: int = 0, encrypt: bool = True) -> bool:
        """Store credential in Redis (encrypted)."""
        if not self.redis:
            return False
        
        try:
            redis_key = f"vault:{domain}:{credential_type}"
            
            # Encrypt value
            if encrypt and self.fernet:
                encrypted = self.fernet.encrypt(value.encode())
                store_value = encrypted
            else:
                store_value = value.encode()
            
            # Store in Redis
            if ttl > 0:
                await self.redis.setex(redis_key, ttl, store_value)
            else:
                await self.redis.set(redis_key, store_value)
            
            # Update cache
            cache_key = f"cred:{domain}:{credential_type}"
            self._cache[cache_key] = {
                'value': value,
                'expires': os.times().elapsed + self._cache_ttl,
                'source': 'redis'
            }
            
            return True
            
        except:
            return False
    
    async def delete_credential(self, domain: str, credential_type: str) -> bool:
        """Delete credential from Redis."""
        if not self.redis:
            return False
        
        try:
            redis_key = f"vault:{domain}:{credential_type}"
            await self.redis.delete(redis_key)
            
            # Clear cache
            cache_key = f"cred:{domain}:{credential_type}"
            if cache_key in self._cache:
                del self._cache[cache_key]
            
            return True
        except:
            return False
    
    async def list_credentials(self, domain: Optional[str] = None) -> Dict[str, list]:
        """List all available credentials."""
        if not self.redis:
            return {}
        
        try:
            if domain:
                pattern = f"vault:{domain}:*"
            else:
                pattern = "vault:*"
            
            keys = []
            cursor = 0
            
            while True:
                cursor, found_keys = await self.redis.scan(cursor, match=pattern, count=100)
                keys.extend(found_keys)
                
                if cursor == 0:
                    break
            
            # Group by domain
            credentials = {}
            for key in keys:
                key_str = key.decode()
                parts = key_str.split(':')
                
                if len(parts) >= 3:
                    domain_name = parts[1]
                    cred_type = parts[2]
                    
                    if domain_name not in credentials:
                        credentials[domain_name] = []
                    
                    credentials[domain_name].append(cred_type)
            
            return credentials
            
        except:
            return {}
    
    def _generate_placeholder(self, domain: str, credential_type: str) -> str:
        """Generate a deterministic placeholder value."""
        seed = f"{domain}:{credential_type}"
        
        if credential_type == "username":
            # Generate username-like placeholder
            hash_val = hashlib.md5(seed.encode()).hexdigest()[:8]
            return f"user_{hash_val}"
        
        elif credential_type == "password":
            # Generate password-like placeholder
            hash_val = hashlib.sha256(seed.encode()).hexdigest()[:16]
            return f"pwd_{hash_val}"
        
        elif credential_type == "api_key":
            # Generate API key-like placeholder
            hash_val = hashlib.sha512(seed.encode()).hexdigest()[:32]
            return f"api_{hash_val}"
        
        elif credential_type == "token":
            # Generate token-like placeholder
            hash_val = hashlib.sha384(seed.encode()).hexdigest()[:48]
            return f"tok_{hash_val}"
        
        else:
            # Generic placeholder
            hash_val = hashlib.md5(seed.encode()).hexdigest()[:12]
            return f"cred_{hash_val}"
    
    async def validate_credential(self, domain: str, credential_type: str, 
                                value: str) -> Tuple[bool, Optional[str]]:
        """Validate if credential matches stored value."""
        stored = await self.get_credential(domain, credential_type)
        
        if not stored:
            return False, "No stored credential found"
        
        if stored == value:
            return True, "Valid"
        elif stored.startswith('pwd_') or stored.startswith('user_'):
            return False, "Using placeholder credential"
        else:
            return False, "Mismatch"
    
    async def rotate_credentials(self, domain: str, new_credentials: Dict[str, str], 
                               old_ttl: int = 3600) -> bool:
        """Rotate credentials, keeping old ones temporarily."""
        if not self.redis:
            return False
        
        try:
            # Store new credentials
            for cred_type, value in new_credentials.items():
                await self.set_credential(domain, cred_type, value, ttl=0)
            
            # Mark old credentials for expiration
            for cred_type in new_credentials.keys():
                old_key = f"vault:{domain}:{cred_type}:old"
                current = await self.get_credential(domain, cred_type)
                
                if current and not current.startswith('pwd_') and not current.startswith('user_'):
                    await self.redis.setex(old_key, old_ttl, current.encode())
            
            return True
            
        except:
            return False

class CredentialManager:
    def __init__(self, redis_client=None, encryption_key: Optional[str] = None):
        self.vault = CredentialVault(redis_client, encryption_key)
    
    async def get_for_job(self, job: Any) -> Dict[str, str]:
        """Get credentials for a job based on domain and configuration."""
        domain = job.domain if hasattr(job, 'domain') else self._extract_domain(job.url)
        
        if job.payload and job.payload.get('auth_config'):
            auth_config = job.payload['auth_config']
            cred_types = []
            
            if auth_config.get('type') == 'form':
                cred_types = ['username', 'password']
            elif auth_config.get('type') == 'api':
                cred_types = ['api_key']
            elif auth_config.get('type') == 'token':
                cred_types = ['token']
            
            # Override with explicit types if provided
            if auth_config.get('credential_types'):
                cred_types = auth_config['credential_types']
            
            credentials = await self.vault.get_credentials(domain, cred_types)
            
            # Apply any overrides from job payload
            if auth_config.get('username'):
                credentials['username'] = auth_config['username']
            if auth_config.get('password'):
                credentials['password'] = auth_config['password']
            if auth_config.get('api_key'):
                credentials['api_key'] = auth_config['api_key']
            
            return credentials
        
        return {}
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Remove www prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return domain

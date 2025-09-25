"""
Advanced Redis caching service for high-performance document generation
"""

import json
import gzip
import base64
import hashlib
import pickle
import time
import asyncio
import logging
import zlib
from typing import Any, Dict, List, Optional, Union, Callable
from functools import wraps
from datetime import datetime, timedelta
from dataclasses import dataclass

import redis.asyncio as aioredis
from config import settings

# Configure logging
cache_logger = logging.getLogger('cache_service')

@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    hit_count: int = 0
    miss_count: int = 0
    total_requests: int = 0
    average_response_time: float = 0.0
    memory_usage: int = 0
    eviction_count: int = 0
    compression_ratio: float = 0.0

@dataclass
class CacheConfig:
    """Advanced cache configuration"""
    default_ttl: int = 3600  # 1 hour
    max_memory: str = "2gb"
    eviction_policy: str = "allkeys-lru"
    compression_enabled: bool = True
    compression_threshold: int = 1024  # 1KB
    cluster_enabled: bool = False
    replication_enabled: bool = False
    persistence_enabled: bool = True
    key_prefix: str = "mytypist:"


class CacheService:
    """
    Enterprise-grade caching service with advanced features:
    - Multi-layer caching (L1: Memory, L2: Redis)
    - Intelligent cache warming and prefetching
    - Automatic cache invalidation with dependency tracking
    - Performance monitoring and analytics
    - Distributed cache management
    - Compression and serialization optimization
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.redis: Optional[aioredis.Redis] = None
        self.compression_threshold = self.config.compression_threshold
        self.metrics = CacheMetrics()
        self.cache_dependencies: Dict[str, List[str]] = {}
        self.cache_tags: Dict[str, List[str]] = {}
        self.warming_tasks: Dict[str, asyncio.Task] = {}

        # L1 Cache (In-memory)
        self.l1_cache: Dict[str, Dict[str, Any]] = {}
        self.l1_max_size = 1000
        self.l1_ttl = 300  # 5 minutes

    async def initialize(self):
        """Initialize Redis connection"""
        try:
            self.redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=False,  # Keep binary for compression
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                socket_keepalive_options={},
                max_connections=20
            )
            await self.redis.ping()
            return True
        except Exception as e:
            print(f"Redis initialization failed: {e}")
            return False

    def _serialize_data(self, data: Any) -> bytes:
        """Serialize and optionally compress data"""
        try:
            # Serialize to JSON first
            json_data = json.dumps(data, default=str).encode('utf-8')

            # Compress if data is large enough
            if len(json_data) > self.compression_threshold:
                return gzip.compress(json_data)
            return json_data
        except Exception as e:
            cache_logger.error(f"Serialization error: {e}")
            return None

    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize and decompress data"""
        try:
            # Check if data is compressed
            if data.startswith(b'\x1f\x8b'):  # gzip magic number
                data = gzip.decompress(data)
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            cache_logger.error(f"Deserialization error: {e}")
            return None

    async def cache_template(self, template: Any, ttl: int = None) -> bool:
        """Cache a template with metadata"""
        try:
            cache_key = f"{self.config.key_prefix}template:{template.id}:v{template.version}"
            template_data = {
                "id": template.id,
                "name": template.name,
                "content": template.content,
                "version": template.version,
                "placeholders": template.placeholders,
                "metadata": {
                    "category": template.category,
                    "type": template.type,
                    "language": template.language,
                    "is_premium": template.is_premium,
                    "price": template.price
                }
            }
            serialized = self._serialize_data(template_data)
            if not serialized:
                return False
                
            await self.redis.setex(
                cache_key,
                ttl or self.config.default_ttl,
                serialized
            )
            
            # Track template dependencies
            await self.track_dependencies([cache_key], [f"template:{template.id}"])
            return True
            
        except Exception as e:
            cache_logger.error(f"Template cache error: {e}")
            return False

    async def get_cached_template(self, template_id: int, version: str = None) -> Optional[dict]:
        """Get template from cache with versioning support"""
        try:
            pattern = f"{self.config.key_prefix}template:{template_id}"
            if version:
                pattern += f":v{version}"
            else:
                pattern += ":v*"
                
            keys = await self.redis.keys(pattern)
            if not keys:
                return None
                
            # Get latest version if no specific version requested
            key = keys[-1] if not version else keys[0]
            raw_data = await self.redis.get(key)
            if not raw_data:
                return None
                
            return self._deserialize_data(raw_data)
            
        except Exception as e:
            cache_logger.error(f"Template cache get error: {e}")
            return None
            
    async def invalidate_template(self, template_id: int) -> bool:
        """Invalidate all versions of a template"""
        try:
            # Invalidate by dependency
            await self.invalidate_by_tag(f"template:{template_id}")
            return True
        except Exception as e:
            cache_logger.error(f"Template cache invalidation error: {e}")
            return False
            
    async def bulk_cache_templates(self, templates: List[Any], ttl: int = None) -> bool:
        """Cache multiple templates efficiently"""
        try:
            pipe = self.redis.pipeline()
            dependencies = []
            
            for template in templates:
                cache_key = f"{self.config.key_prefix}template:{template.id}:v{template.version}"
                dependencies.append((cache_key, f"template:{template.id}"))
                
                template_data = {
                    "id": template.id,
                    "name": template.name,
                    "content": template.content,
                    "version": template.version,
                    "placeholders": template.placeholders,
                    "metadata": {
                        "category": template.category,
                        "type": template.type,
                        "language": template.language,
                        "is_premium": template.is_premium,
                        "price": template.price
                    }
                }
                
                serialized = self._serialize_data(template_data)
                if serialized:
                    pipe.setex(
                        cache_key,
                        ttl or self.config.default_ttl,
                        serialized
                    )
                    
            # Execute all cache operations
            await pipe.execute()
            
            # Track all dependencies
            for key, tag in dependencies:
                await self.track_dependencies([key], [tag])
                
            return True
            
        except Exception as e:
            cache_logger.error(f"Bulk template cache error: {e}")
            return False

    async def track_dependencies(self, keys: List[str], tags: List[str]) -> bool:
        """Track cache key dependencies for invalidation"""
        try:
            # Store key -> tag mapping
            for key in keys:
                self.cache_dependencies[key] = tags
                
            # Store tag -> key mapping
            for tag in tags:
                if tag not in self.cache_tags:
                    self.cache_tags[tag] = []
                self.cache_tags[tag].extend(keys)
                
            return True
        except Exception as e:
            cache_logger.error(f"Error tracking dependencies: {e}")
            return False

    async def invalidate_by_tag(self, tag: str) -> bool:
        """Invalidate all cache entries with the given tag"""
        try:
            if tag not in self.cache_tags:
                return True
                
            # Get all keys for this tag
            keys = self.cache_tags[tag]
            if not keys:
                return True
                
            # Delete all keys
            await self.redis.delete(*keys)
            
            # Clean up tracking
            del self.cache_tags[tag]
            for key in keys:
                if key in self.cache_dependencies:
                    del self.cache_dependencies[key]
                    
            return True
        except Exception as e:
            cache_logger.error(f"Error invalidating by tag: {e}")
            return False
            
            # Compress if data is large enough
            if len(json_data) > self.compression_threshold:
                compressed = gzip.compress(json_data)
                # Mark as compressed with prefix
                return b'GZIP:' + compressed
            else:
                return b'JSON:' + json_data

        except Exception:
            # Fallback to pickle for complex objects
            pickled = pickle.dumps(data)
            if len(pickled) > self.compression_threshold:
                compressed = gzip.compress(pickled)
                return b'GZIP_PICKLE:' + compressed
            else:
                return b'PICKLE:' + pickled

    def _deserialize_data(self, data: bytes) -> Any:
        """Deserialize and decompress data"""
        try:
            if data.startswith(b'GZIP:'):
                decompressed = gzip.decompress(data[5:])
                return json.loads(decompressed.decode('utf-8'))
            elif data.startswith(b'JSON:'):
                return json.loads(data[5:].decode('utf-8'))
            elif data.startswith(b'GZIP_PICKLE:'):
                decompressed = gzip.decompress(data[12:])
                return pickle.loads(decompressed)
            elif data.startswith(b'PICKLE:'):
                return pickle.loads(data[7:])
            else:
                # Legacy format
                return json.loads(data.decode('utf-8'))
        except Exception:
            return None

    async def set(self,
                  key: str,
                  value: Any,
                  expire: int = 300,
                  namespace: str = "",
                  tags: List[str] = None,
                  dependencies: Optional[List[str]] = None) -> bool:
        """
        Set value in multi-layer cache with advanced features
        """
        cache_key = self._generate_cache_key(key, namespace) if namespace else key
        ttl = expire or self.config.default_ttl

        try:
            # Store in L1 cache
            self._set_to_l1(cache_key, value, ttl)

            # Store in L2 cache (Redis)
            if self.redis:
                serialized = self._serialize_data(value)
                success = await self.redis.setex(cache_key, ttl, serialized)
                if not success:
                    return False

                # Add tags for grouped invalidation
                if tags and success:
                    for tag in tags:
                        await self.redis.sadd(f"tag:{tag}", cache_key)
                        await self.redis.expire(f"tag:{tag}", ttl + 60)

                        # Update local tag registry
                        if tag not in self.cache_tags:
                            self.cache_tags[tag] = []
                        self.cache_tags[tag].append(cache_key)

                # Handle dependencies for cascade invalidation
                if dependencies:
                    self._register_dependencies(cache_key, dependencies)

            return True

        except Exception as e:
            cache_logger.error(f"Cache set failed for key {cache_key}: {e}")
            return False

    def _generate_cache_key(self, key: str, namespace: str = "") -> str:
        """Generate standardized cache key with namespace"""
        prefix = self.config.key_prefix
        if namespace:
            prefix += f"{namespace}:"
        return f"{prefix}{key}"

    def _get_from_l1(self, key: str) -> Any:
        """Get from L1 (memory) cache"""
        if key in self.l1_cache:
            entry = self.l1_cache[key]
            if entry['expires_at'] > time.time():
                return entry['value']
            else:
                # Expired, remove from L1
                del self.l1_cache[key]
        return None

    def _set_to_l1(self, key: str, value: Any, ttl: int = None):
        """Set to L1 (memory) cache with LRU eviction"""
        # Implement LRU eviction if cache is full
        if len(self.l1_cache) >= self.l1_max_size:
            # Remove oldest entry
            oldest_key = min(self.l1_cache.keys(),
                           key=lambda k: self.l1_cache[k]['created_at'])
            del self.l1_cache[oldest_key]

        ttl = ttl or self.l1_ttl
        self.l1_cache[key] = {
            'value': value,
            'created_at': time.time(),
            'expires_at': time.time() + ttl
        }

    def _update_response_time(self, start_time: float):
        """Update average response time metric"""
        response_time = time.time() - start_time
        current_avg = self.metrics.average_response_time
        total_requests = self.metrics.total_requests

        # Calculate new average
        self.metrics.average_response_time = (
            (current_avg * (total_requests - 1) + response_time) / total_requests
        )

    async def get(self, key: str, namespace: str = "", default: Any = None) -> Any:
        """
        Get value from multi-layer cache with performance tracking
        """
        start_time = time.time()
        cache_key = self._generate_cache_key(key, namespace) if namespace else key

        try:
            self.metrics.total_requests += 1

            # L1 Cache check (fastest)
            l1_result = self._get_from_l1(cache_key)
            if l1_result is not None:
                self.metrics.hit_count += 1
                self._update_response_time(start_time)
                return l1_result

            # L2 Cache check (Redis)
            if self.redis:
                data = await self.redis.get(cache_key)
                if data is not None:
                    result = self._deserialize_data(data)
                    if result is not None:
                        # Store in L1 for faster future access
                        self._set_to_l1(cache_key, result)
                        self.metrics.hit_count += 1
                        self._update_response_time(start_time)
                        return result

            # Cache miss
            self.metrics.miss_count += 1
            self._update_response_time(start_time)
            return default

        except Exception as e:
            cache_logger.error(f"Cache get failed for key {cache_key}: {e}")
            return default

    async def delete(self, key: str) -> bool:
        """Delete cached value"""
        if not self.redis:
            return False

        try:
            return await self.redis.delete(key) > 0
        except Exception:
            return False

    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all cache entries with specific tag"""
        if not self.redis:
            return 0

        try:
            keys = await self.redis.smembers(f"tag:{tag}")
            if keys:
                deleted = await self.redis.delete(*keys)
                await self.redis.delete(f"tag:{tag}")
                return deleted
            return 0
        except Exception:
            return 0

    async def mget(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple cache values"""
        if not self.redis or not keys:
            return {}

        try:
            values = await self.redis.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = self._deserialize_data(value)
            return result
        except Exception:
            return {}

    async def mset(self, mapping: Dict[str, Any], expire: int = 300) -> bool:
        """Set multiple cache values"""
        if not self.redis or not mapping:
            return False

        try:
            pipe = self.redis.pipeline()
            for key, value in mapping.items():
                serialized = self._serialize_data(value)
                pipe.setex(key, expire, serialized)

            results = await pipe.execute()
            return all(results)
        except Exception:
            return False


# Global cache instance
cache_service = CacheService()


def cache_response(expire: int = 300, key_prefix: str = "api", tags: List[str] = None):
    """Decorator for caching API responses"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function and parameters
            params_hash = hashlib.md5(str(sorted(kwargs.items())).encode()).hexdigest()
            cache_key = f"{key_prefix}:{func.__name__}:{params_hash}"

            # Try cache first
            cached = await cache_service.get(cache_key)
            if cached is not None:
                return cached

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            await cache_service.set(cache_key, result, expire, tags or [])
            return result
        return wrapper
    return decorator


def cache_query(expire: int = 600, key_prefix: str = "query"):
    """Decorator for caching database query results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from query parameters
            query_hash = hashlib.md5(str(args + tuple(sorted(kwargs.items()))).encode()).hexdigest()
            cache_key = f"{key_prefix}:{func.__name__}:{query_hash}"

            # Try cache first
            cached = await cache_service.get(cache_key)
            if cached is not None:
                return cached

            # Execute query
            result = await func(*args, **kwargs)

            # Cache result
            await cache_service.set(cache_key, result, expire)
            return result
        return wrapper
    return decorator


class DocumentCache:
    """Specialized caching for document generation"""

    @staticmethod
    async def cache_template_placeholders(template_id: int, placeholders: List[Dict]) -> bool:
        """Cache template placeholders for faster document generation"""
        cache_key = f"template_placeholders:{template_id}"
        return await cache_service.set(cache_key, placeholders, expire=86400)  # 24 hours

    @staticmethod
    async def get_template_placeholders(template_id: int) -> Optional[List[Dict]]:
        """Get cached template placeholders"""
        cache_key = f"template_placeholders:{template_id}"
        return await cache_service.get(cache_key)

    @staticmethod
    async def cache_generated_document(doc_hash: str, document_data: Dict, expire: int = 3600) -> bool:
        """Cache generated document"""
        cache_key = f"generated_doc:{doc_hash}"
        tags = ["documents", f"user:{document_data.get('user_id')}"]
        return await cache_service.set(cache_key, document_data, expire, tags)

    @staticmethod
    async def get_generated_document(doc_hash: str) -> Optional[Dict]:
        """Get cached generated document"""
        cache_key = f"generated_doc:{doc_hash}"
        return await cache_service.get(cache_key)

    @staticmethod
    async def invalidate_user_documents(user_id: int) -> int:
        """Invalidate all cached documents for a user"""
        return await cache_service.invalidate_by_tag(f"user:{user_id}")


class UserCache:
    """User-specific caching utilities"""

    @staticmethod
    async def cache_user_profile(user_id: int, profile_data: Dict, expire: int = 1800) -> bool:
        """Cache user profile data"""
        cache_key = f"user_profile:{user_id}"
        return await cache_service.set(cache_key, profile_data, expire)

    @staticmethod
    async def get_user_profile(user_id: int) -> Optional[Dict]:
        """Get cached user profile"""
        cache_key = f"user_profile:{user_id}"
        return await cache_service.get(cache_key)

    @staticmethod
    async def cache_user_permissions(user_id: int, permissions: List[str], expire: int = 3600) -> bool:
        """Cache user permissions for faster authorization"""
        cache_key = f"user_permissions:{user_id}"
        return await cache_service.set(cache_key, permissions, expire)

    @staticmethod
    async def get_user_permissions(user_id: int) -> Optional[List[str]]:
        """Get cached user permissions"""
        cache_key = f"user_permissions:{user_id}"
        return await cache_service.get(cache_key)

    @staticmethod
    async def invalidate_user_cache(user_id: int) -> int:
        """Invalidate all user-related cache"""
        keys_to_delete = [
            f"user_profile:{user_id}",
            f"user_permissions:{user_id}",
            f"user_settings:{user_id}"
        ]
        deleted = 0
        for key in keys_to_delete:
            if await cache_service.delete(key):
                deleted += 1
        return deleted
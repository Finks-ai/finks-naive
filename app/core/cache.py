"""
Multi-level caching system for query optimization.
"""

import hashlib
import json
import asyncio
import yaml
import os
from typing import Dict, Any, Optional, Callable, TypeVar, List, Tuple
from functools import lru_cache, wraps
from datetime import datetime, timedelta
from loguru import logger
from app.core.config import get_settings
from app.core.database import get_db_service

T = TypeVar('T')

class CacheLevel:
    """Cache level enumeration."""
    MEMORY = "memory"
    MONGODB = "mongodb"


class QueryPatternCache:
    """Multi-level cache for query patterns and results."""
    
    def __init__(self):
        self.settings = get_settings()
        self._memory_cache = {}
        self._db_service = None
        self._cache_collection = None
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "memory_hits": 0,
            "mongodb_hits": 0
        }
        self._normalization_rules = self._load_normalization_rules()
    
    def _load_normalization_rules(self) -> Dict[str, List]:
        """Load query normalization rules from YAML file."""
        try:
            config_path = os.path.join(
                os.path.dirname(__file__), 
                "query_normalization.yaml"
            )
            with open(config_path, 'r') as f:
                rules = yaml.safe_load(f)
                logger.info(f"Loaded query normalization rules from {config_path}")
                return rules
        except Exception as e:
            logger.warning(f"Failed to load normalization rules: {e}. Using defaults.")
            # Fallback to minimal defaults
            return {
                "plurals": [["companies", "company"], ["stocks", "stock"]],
                "remove_phrases": ["show me", "find", "list", "get"],
                "synonyms": [],
                "abbreviations": []
            }
    
    @property
    def cache_collection(self):
        """Lazy MongoDB cache collection initialization."""
        if self._cache_collection is None:
            try:
                if not self._db_service:
                    self._db_service = get_db_service()
                self._cache_collection = self._db_service.get_collection("query_cache")
                # Create TTL index for automatic expiration
                self._cache_collection.create_index(
                    "expires_at", 
                    expireAfterSeconds=0,
                    background=True
                )
                logger.info("MongoDB cache collection initialized")
            except Exception as e:
                logger.warning(f"MongoDB cache initialization failed: {e}")
        return self._cache_collection
    
    def get_query_fingerprint(self, query: str, context: Optional[Dict] = None) -> str:
        """
        Generate a normalized fingerprint for query patterns.
        This allows caching of similar queries.
        """
        # Normalize query
        normalized = query.lower().strip()
        
        # Apply plurals normalization
        for old, new in self._normalization_rules.get("plurals", []):
            normalized = normalized.replace(old, new)
        
        # Remove filler phrases
        for phrase in self._normalization_rules.get("remove_phrases", []):
            normalized = normalized.replace(phrase, "")
        
        # Apply synonyms
        for old, new in self._normalization_rules.get("synonyms", []):
            normalized = normalized.replace(old, new)
        
        # Apply abbreviations
        for old, new in self._normalization_rules.get("abbreviations", []):
            normalized = normalized.replace(old, new)
        
        # Remove extra spaces
        normalized = " ".join(normalized.split())
        
        # Add context if provided
        cache_key_data = {"query": normalized}
        if context:
            cache_key_data["context"] = str(sorted(context.items()))
        
        # Generate hash
        return hashlib.md5(
            json.dumps(cache_key_data, sort_keys=True).encode()
        ).hexdigest()
    
    async def get_cached_result(
        self, 
        cache_key: str, 
        cache_levels: list = None
    ) -> Optional[Dict[str, Any]]:
        """Get cached result from available cache levels."""
        if cache_levels is None:
            cache_levels = [CacheLevel.MEMORY, CacheLevel.MONGODB]
        
        # L1: Memory cache
        if CacheLevel.MEMORY in cache_levels:
            result = self._get_from_memory(cache_key)
            if result:
                self._cache_stats["memory_hits"] += 1
                self._cache_stats["hits"] += 1
                logger.debug(f"Cache hit (memory): {cache_key}")
                return result
        
        # L2: MongoDB cache
        if CacheLevel.MONGODB in cache_levels and self.cache_collection is not None:
            result = await self._get_from_mongodb(cache_key)
            if result:
                self._cache_stats["mongodb_hits"] += 1
                self._cache_stats["hits"] += 1
                logger.debug(f"Cache hit (mongodb): {cache_key}")
                # Promote to memory cache
                self._set_in_memory(cache_key, result, ttl_seconds=300)
                return result
        
        self._cache_stats["misses"] += 1
        return None
    
    async def set_cached_result(
        self,
        cache_key: str,
        result: Dict[str, Any],
        ttl_seconds: int = 3600,
        cache_levels: list = None
    ):
        """Set result in multiple cache levels."""
        if cache_levels is None:
            cache_levels = [CacheLevel.MEMORY, CacheLevel.MONGODB]
        
        # L1: Memory cache
        if CacheLevel.MEMORY in cache_levels:
            self._set_in_memory(cache_key, result, ttl_seconds=min(ttl_seconds, 300))
        
        # L2: MongoDB cache
        if CacheLevel.MONGODB in cache_levels and self.cache_collection is not None:
            await self._set_in_mongodb(cache_key, result, ttl_seconds)
    
    def _get_from_memory(self, key: str) -> Optional[Dict[str, Any]]:
        """Get from memory cache with TTL check."""
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if datetime.now() < entry["expires"]:
                return entry["data"]
            else:
                del self._memory_cache[key]
        return None
    
    def _set_in_memory(self, key: str, data: Dict[str, Any], ttl_seconds: int):
        """Set in memory cache with TTL."""
        self._memory_cache[key] = {
            "data": data,
            "expires": datetime.now() + timedelta(seconds=ttl_seconds)
        }
        
        # Cleanup old entries if cache is too large
        if len(self._memory_cache) > 1000:
            self._cleanup_memory_cache()
    
    def _cleanup_memory_cache(self):
        """Remove expired entries from memory cache."""
        now = datetime.now()
        expired_keys = [
            k for k, v in self._memory_cache.items()
            if now >= v["expires"]
        ]
        for key in expired_keys:
            del self._memory_cache[key]
    
    async def _get_from_mongodb(self, key: str) -> Optional[Dict[str, Any]]:
        """Get from MongoDB cache."""
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            doc = await loop.run_in_executor(
                None, 
                lambda: self.cache_collection.find_one(
                    {"_id": key, "expires_at": {"$gt": datetime.utcnow()}}
                )
            )
            if doc:
                return doc.get("data")
        except Exception as e:
            logger.error(f"MongoDB cache get error: {e}")
        return None
    
    async def _set_in_mongodb(self, key: str, data: Dict[str, Any], ttl_seconds: int):
        """Set in MongoDB cache with TTL."""
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.cache_collection.replace_one(
                    {"_id": key},
                    {
                        "_id": key,
                        "data": data,
                        "expires_at": expires_at,
                        "created_at": datetime.utcnow()
                    },
                    upsert=True
                )
            )
        except Exception as e:
            logger.error(f"MongoDB cache set error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._cache_stats["hits"] + self._cache_stats["misses"]
        hit_rate = self._cache_stats["hits"] / total if total > 0 else 0
        
        return {
            **self._cache_stats,
            "hit_rate": f"{hit_rate:.2%}",
            "memory_size": len(self._memory_cache)
        }


# Global cache instance
_query_cache: Optional[QueryPatternCache] = None


def get_query_cache() -> QueryPatternCache:
    """Get global query cache instance."""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryPatternCache()
    return _query_cache


def cached_query(ttl_seconds: int = 3600):
    """Decorator for caching query results."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args
            request = args[1] if len(args) > 1 else kwargs.get('request')
            if not request or not hasattr(request, 'query'):
                return await func(*args, **kwargs)
            
            # Get cache instance
            cache = get_query_cache()
            
            # Generate cache key
            cache_key = cache.get_query_fingerprint(
                request.query,
                {"max_results": getattr(request, 'max_results', 10)}
            )
            
            # Check cache
            cached_result = await cache.get_cached_result(cache_key)
            if cached_result:
                logger.info(f"Returning cached result for query: {request.query}")
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            if result and hasattr(result, 'dict'):
                await cache.set_cached_result(
                    cache_key,
                    result.dict(),
                    ttl_seconds=ttl_seconds
                )
            
            return result
        
        return wrapper
    return decorator


def cache_field_extraction(ttl_seconds: int = 7200):
    """Decorator specifically for caching field extraction results."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract query
            query = args[1] if len(args) > 1 else kwargs.get('query')
            if not query:
                return await func(*args, **kwargs)
            
            # Simplified cache key for field extraction
            cache = get_query_cache()
            cache_key = f"fields:{cache.get_query_fingerprint(query)}"
            
            # Check cache
            cached_fields = await cache.get_cached_result(cache_key)
            if cached_fields:
                logger.debug(f"Using cached field extraction for: {query}")
                return cached_fields
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            if result:
                await cache.set_cached_result(
                    cache_key,
                    result if isinstance(result, dict) else result.dict(),
                    ttl_seconds=ttl_seconds
                )
            
            return result
        
        return wrapper
    return decorator
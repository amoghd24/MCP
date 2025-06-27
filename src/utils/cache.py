"""
Caching utilities for MCP server
"""

import json
import time
from typing import Optional, Any, Dict
from functools import wraps
import hashlib


class SimpleCache:
    """Simple in-memory cache implementation"""
    
    def __init__(self, ttl_seconds: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self.cache:
            item = self.cache[key]
            if time.time() < item["expires_at"]:
                return item["value"]
            else:
                # Remove expired item
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with expiration"""
        ttl = ttl or self.ttl_seconds
        self.cache[key] = {
            "value": value,
            "expires_at": time.time() + ttl
        }
    
    def delete(self, key: str) -> None:
        """Delete key from cache"""
        if key in self.cache:
            del self.cache[key]
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self.cache.clear()
    
    def make_key(self, *args, **kwargs) -> str:
        """Create a cache key from arguments"""
        key_data = {
            "args": args,
            "kwargs": kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()


# Global cache instance
cache = SimpleCache()


def cached(ttl: Optional[int] = None):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{cache.make_key(*args, **kwargs)}"
            
            # Check cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Call function and cache result
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{cache.make_key(*args, **kwargs)}"
            
            # Check cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator 
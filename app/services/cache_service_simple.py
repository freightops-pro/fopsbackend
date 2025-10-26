"""
Simple Cache Service without Redis dependencies for development
"""
import logging
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SimpleCacheService:
    """
    Simple in-memory cache service for development (without Redis)
    """
    
    def __init__(self):
        self.cache = {}
        logger.info("Simple in-memory cache service initialized")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            cached_data = self.cache.get(key)
            if cached_data and cached_data['expires_at'] > datetime.utcnow():
                return cached_data['value']
            else:
                # Remove expired entry
                self.cache.pop(key, None)
                return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache"""
        try:
            self.cache[key] = {
                'value': value,
                'expires_at': datetime.utcnow() + timedelta(seconds=ttl)
            }
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            self.cache.pop(key, None)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def get_or_set(self, key: str, fetch_func, ttl: int = 300) -> Any:
        """Get from cache or fetch and cache the result"""
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value
        
        # Fetch fresh data
        fresh_value = await fetch_func()
        await self.set(key, fresh_value, ttl)
        return fresh_value
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern"""
        try:
            matching_keys = [k for k in self.cache.keys() if pattern.replace('*', '') in k]
            for key in matching_keys:
                del self.cache[key]
            return len(matching_keys)
        except Exception as e:
            logger.error(f"Cache pattern invalidation error for pattern {pattern}: {e}")
            return 0
    
    # Rate limiting methods
    async def get_rate_limit(self, key: str) -> Optional[int]:
        """Get current rate limit count"""
        count = await self.get(key)
        return int(count) if count is not None else 0
    
    async def increment_rate_limit(self, key: str, ttl: int = 60) -> int:
        """Increment rate limit counter"""
        try:
            current = await self.get_rate_limit(key)
            new_count = current + 1
            await self.set(key, new_count, ttl)
            return new_count
        except Exception as e:
            logger.error(f"Rate limit increment error for key {key}: {e}")
            return 0
    
    # Cache statistics
    async def get_stats(self) -> Dict:
        """Get cache statistics"""
        try:
            return {
                "connected_clients": 1,
                "used_memory": f"{len(str(self.cache))}B",
                "keyspace_hits": 0,
                "keyspace_misses": 0,
                "total_commands_processed": len(self.cache)
            }
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {}

# Global cache service instance
cache_service = SimpleCacheService()


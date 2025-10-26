"""
Redis Caching Service for High-Performance Data Access
"""
import redis
import json
import logging
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta
from app.config.settings import settings
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class CacheService:
    """
    High-performance Redis caching service with automatic serialization
    """
    
    def __init__(self):
        self.redis_client = None
        self.fallback_cache = {}  # In-memory fallback
        
        if settings.REDIS_URL:
            try:
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Redis connection established successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed, using fallback cache: {e}")
                self.redis_client = None
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache with automatic deserialization"""
        try:
            if self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    return json.loads(value)
            else:
                # Fallback to in-memory cache
                cached_data = self.fallback_cache.get(key)
                if cached_data and cached_data['expires_at'] > datetime.utcnow():
                    return cached_data['value']
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with automatic serialization"""
        try:
            serialized_value = json.dumps(value, default=str)
            
            if self.redis_client:
                return self.redis_client.setex(key, ttl, serialized_value)
            else:
                # Fallback to in-memory cache
                self.fallback_cache[key] = {
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
            if self.redis_client:
                return bool(self.redis_client.delete(key))
            else:
                self.fallback_cache.pop(key, None)
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
            if self.redis_client:
                keys = self.redis_client.keys(pattern)
                if keys:
                    return self.redis_client.delete(*keys)
            else:
                # Fallback: remove matching keys from in-memory cache
                matching_keys = [k for k in self.fallback_cache.keys() if pattern.replace('*', '') in k]
                for key in matching_keys:
                    del self.fallback_cache[key]
                return len(matching_keys)
        except Exception as e:
            logger.error(f"Cache pattern invalidation error for pattern {pattern}: {e}")
            return 0
    
    # Company-specific caching methods
    async def get_company_data(self, company_id: str) -> Optional[Dict]:
        """Get cached company data"""
        return await self.get(f"company:{company_id}")
    
    async def set_company_data(self, company_id: str, data: Dict, ttl: int = 3600) -> bool:
        """Cache company data"""
        return await self.set(f"company:{company_id}", data, ttl)
    
    async def invalidate_company_cache(self, company_id: str) -> int:
        """Invalidate all cache entries for a company"""
        return await self.invalidate_pattern(f"company:{company_id}:*")
    
    # User-specific caching methods
    async def get_user_data(self, user_id: str) -> Optional[Dict]:
        """Get cached user data"""
        return await self.get(f"user:{user_id}")
    
    async def set_user_data(self, user_id: str, data: Dict, ttl: int = 1800) -> bool:
        """Cache user data"""
        return await self.set(f"user:{user_id}", data, ttl)
    
    # Load data caching
    async def get_loads_for_company(self, company_id: str, filters: Dict = None) -> Optional[List]:
        """Get cached loads for company"""
        cache_key = f"loads:{company_id}:{hash(str(sorted(filters.items())) if filters else 'all')}"
        return await self.get(cache_key)
    
    async def set_loads_for_company(self, company_id: str, loads: List, filters: Dict = None, ttl: int = 300) -> bool:
        """Cache loads for company"""
        cache_key = f"loads:{company_id}:{hash(str(sorted(filters.items())) if filters else 'all')}"
        return await self.set(cache_key, loads, ttl)
    
    # Fleet data caching
    async def get_fleet_data(self, company_id: str) -> Optional[Dict]:
        """Get cached fleet data (vehicles, drivers, equipment)"""
        return await self.get(f"fleet:{company_id}")
    
    async def set_fleet_data(self, company_id: str, data: Dict, ttl: int = 600) -> bool:
        """Cache fleet data"""
        return await self.set(f"fleet:{company_id}", data, ttl)
    
    # Financial data caching
    async def get_financial_summary(self, company_id: str, period: str = "current") -> Optional[Dict]:
        """Get cached financial summary"""
        return await self.get(f"financial:{company_id}:{period}")
    
    async def set_financial_summary(self, company_id: str, data: Dict, period: str = "current", ttl: int = 900) -> bool:
        """Cache financial summary"""
        return await self.set(f"financial:{company_id}:{period}", data, ttl)
    
    # Dashboard data caching
    async def get_dashboard_data(self, company_id: str, user_id: str = None) -> Optional[Dict]:
        """Get cached dashboard data"""
        cache_key = f"dashboard:{company_id}:{user_id or 'default'}"
        return await self.get(cache_key)
    
    async def set_dashboard_data(self, company_id: str, data: Dict, user_id: str = None, ttl: int = 300) -> bool:
        """Cache dashboard data"""
        cache_key = f"dashboard:{company_id}:{user_id or 'default'}"
        return await self.set(cache_key, data, ttl)
    
    # API response caching
    async def cache_api_response(self, endpoint: str, params: Dict, response: Any, ttl: int = 300) -> bool:
        """Cache API response"""
        cache_key = f"api:{endpoint}:{hash(str(sorted(params.items())))}"
        return await self.set(cache_key, response, ttl)
    
    async def get_cached_api_response(self, endpoint: str, params: Dict) -> Optional[Any]:
        """Get cached API response"""
        cache_key = f"api:{endpoint}:{hash(str(sorted(params.items())))}"
        return await self.get(cache_key)
    
    # Session caching
    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Get cached session data"""
        return await self.get(f"session:{session_id}")
    
    async def set_session(self, session_id: str, data: Dict, ttl: int = 3600) -> bool:
        """Cache session data"""
        return await self.set(f"session:{session_id}", data, ttl)
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session from cache"""
        return await self.delete(f"session:{session_id}")
    
    # Rate limiting cache
    async def get_rate_limit(self, key: str) -> Optional[int]:
        """Get current rate limit count"""
        count = await self.get(f"rate_limit:{key}")
        return int(count) if count is not None else 0
    
    async def increment_rate_limit(self, key: str, ttl: int = 60) -> int:
        """Increment rate limit counter"""
        try:
            if self.redis_client:
                pipe = self.redis_client.pipeline()
                pipe.incr(f"rate_limit:{key}")
                pipe.expire(f"rate_limit:{key}", ttl)
                results = pipe.execute()
                return results[0]
            else:
                # Fallback implementation
                current = await self.get_rate_limit(key)
                new_count = current + 1
                await self.set(f"rate_limit:{key}", new_count, ttl)
                return new_count
        except Exception as e:
            logger.error(f"Rate limit increment error for key {key}: {e}")
            return 0
    
    # Cache statistics
    async def get_stats(self) -> Dict:
        """Get cache statistics"""
        try:
            if self.redis_client:
                info = self.redis_client.info()
                return {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": info.get("used_memory_human", "0B"),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0),
                    "total_commands_processed": info.get("total_commands_processed", 0)
                }
            else:
                return {
                    "connected_clients": 1,
                    "used_memory": f"{len(str(self.fallback_cache))}B",
                    "keyspace_hits": 0,
                    "keyspace_misses": 0,
                    "total_commands_processed": len(self.fallback_cache)
                }
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {}

# Global cache service instance
cache_service = CacheService()


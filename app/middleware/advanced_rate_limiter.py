"""
Advanced Rate Limiting Middleware for High-Scale Operations (5000+ Users)
"""
import time
import json
import logging
from typing import Dict, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from fastapi import HTTPException, status
from app.services.cache_service_simple import cache_service
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class AdvancedRateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Advanced rate limiting middleware optimized for 5000+ concurrent users
    """
    
    def __init__(self, app):
        super().__init__(app)
        
        # Rate limits by endpoint type (requests per minute)
        self.rate_limits = {
            # Authentication endpoints - strict limits
            '/api/auth/login': {'limit': 10, 'window': 60},
            '/api/auth/register': {'limit': 5, 'window': 60},
            '/api/auth/forgot-password': {'limit': 3, 'window': 60},
            '/api/auth/reset-password': {'limit': 5, 'window': 60},
            
            # Data endpoints - moderate limits
            '/api/loads': {'limit': 200, 'window': 60},
            '/api/fleet': {'limit': 150, 'window': 60},
            '/api/drivers': {'limit': 150, 'window': 60},
            '/api/vehicles': {'limit': 150, 'window': 60},
            '/api/equipment': {'limit': 150, 'window': 60},
            
            # Dashboard endpoints - higher limits
            '/api/dashboard': {'limit': 300, 'window': 60},
            '/api/metrics': {'limit': 100, 'window': 60},
            
            # Accounting endpoints - moderate limits
            '/api/accounting': {'limit': 100, 'window': 60},
            '/api/invoices': {'limit': 100, 'window': 60},
            '/api/settlements': {'limit': 100, 'window': 60},
            
            # API key endpoints - strict limits
            '/api/api-keys': {'limit': 50, 'window': 60},
            
            # Default limit for unknown endpoints
            'default': {'limit': 100, 'window': 60}
        }
        
        # IP-based rate limiting (additional layer)
        self.ip_limits = {
            'default': {'limit': 1000, 'window': 60},  # 1000 requests per minute per IP
            'strict': {'limit': 500, 'window': 60}     # For suspicious IPs
        }
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            # Get client IP
            client_ip = self._get_client_ip(request)
            
            # Check IP-based rate limiting first
            ip_allowed = await self._check_ip_rate_limit(client_ip, request)
            if not ip_allowed:
                return self._rate_limit_response("IP rate limit exceeded")
            
            # Check endpoint-specific rate limiting
            endpoint_allowed = await self._check_endpoint_rate_limit(client_ip, request)
            if not endpoint_allowed:
                return self._rate_limit_response("Endpoint rate limit exceeded")
            
            # Process request
            response = await call_next(request)
            
            # Log request metrics
            duration = time.time() - start_time
            await self._log_request_metrics(request, response, duration, client_ip)
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}", exc_info=True)
            # Don't block requests if rate limiter fails
            return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request headers"""
        # Check for forwarded IP first (for load balancers)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        # Check for real IP header
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # Fallback to direct connection IP
        if request.client:
            return request.client.host
        
        return 'unknown'
    
    async def _check_ip_rate_limit(self, client_ip: str, request: Request) -> bool:
        """Check IP-based rate limiting"""
        try:
            # Determine IP limit category
            ip_limit = self.ip_limits['default']
            
            # Check if IP is in suspicious list (could be enhanced with ML)
            if await self._is_suspicious_ip(client_ip):
                ip_limit = self.ip_limits['strict']
            
            # Create IP rate limit key
            ip_key = f"ip_rate_limit:{client_ip}:{int(time.time() // ip_limit['window'])}"
            
            # Check current count
            current_count = await cache_service.get_rate_limit(ip_key)
            
            if current_count >= ip_limit['limit']:
                logger.warning(f"IP rate limit exceeded for {client_ip}: {current_count}/{ip_limit['limit']}")
                return False
            
            # Increment counter
            await cache_service.increment_rate_limit(ip_key, ttl=ip_limit['window'])
            
            return True
            
        except Exception as e:
            logger.error(f"IP rate limit check error: {e}")
            return True  # Allow request if check fails
    
    async def _check_endpoint_rate_limit(self, client_ip: str, request: Request) -> bool:
        """Check endpoint-specific rate limiting"""
        try:
            # Get endpoint path
            path = request.url.path
            
            # Find matching rate limit
            rate_limit = self._get_rate_limit_for_path(path)
            
            # Create endpoint rate limit key
            endpoint_key = f"endpoint_rate_limit:{client_ip}:{path}:{int(time.time() // rate_limit['window'])}"
            
            # Check current count
            current_count = await cache_service.get_rate_limit(endpoint_key)
            
            if current_count >= rate_limit['limit']:
                logger.warning(f"Endpoint rate limit exceeded for {client_ip} on {path}: {current_count}/{rate_limit['limit']}")
                return False
            
            # Increment counter
            await cache_service.increment_rate_limit(endpoint_key, ttl=rate_limit['window'])
            
            return True
            
        except Exception as e:
            logger.error(f"Endpoint rate limit check error: {e}")
            return True  # Allow request if check fails
    
    def _get_rate_limit_for_path(self, path: str) -> Dict:
        """Get rate limit configuration for a given path"""
        # Exact match first
        if path in self.rate_limits:
            return self.rate_limits[path]
        
        # Check for partial matches (e.g., /api/loads/123 matches /api/loads)
        for endpoint, limit in self.rate_limits.items():
            if endpoint != 'default' and path.startswith(endpoint):
                return limit
        
        # Return default limit
        return self.rate_limits['default']
    
    async def _is_suspicious_ip(self, client_ip: str) -> bool:
        """Check if IP is suspicious (could be enhanced with ML/blacklists)"""
        try:
            # Check if IP is in suspicious list (stored in cache)
            suspicious_key = f"suspicious_ip:{client_ip}"
            is_suspicious = await cache_service.get(suspicious_key)
            
            if is_suspicious:
                return True
            
            # Simple heuristic: if IP has made many requests to auth endpoints
            auth_key = f"auth_attempts:{client_ip}:{int(time.time() // 300)}"  # 5-minute window
            auth_attempts = await cache_service.get_rate_limit(auth_key)
            
            if auth_attempts > 20:  # More than 20 auth attempts in 5 minutes
                # Mark as suspicious for 1 hour
                await cache_service.set(suspicious_key, True, ttl=3600)
                logger.warning(f"Marked IP {client_ip} as suspicious due to high auth attempts")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Suspicious IP check error: {e}")
            return False
    
    async def _log_request_metrics(self, request: Request, response: Response, duration: float, client_ip: str):
        """Log request metrics for monitoring"""
        try:
            metrics = {
                'timestamp': time.time(),
                'method': request.method,
                'path': request.url.path,
                'status_code': response.status_code,
                'duration_ms': duration * 1000,
                'client_ip': client_ip,
                'user_agent': request.headers.get('user-agent', '')[:100]  # Truncate for storage
            }
            
            # Store metrics in cache for aggregation
            metrics_key = f"request_metrics:{int(time.time() // 60)}"  # 1-minute buckets
            await cache_service.set(metrics_key, metrics, ttl=3600)  # Keep for 1 hour
            
            # Log slow requests
            if duration > 1.0:  # Requests taking more than 1 second
                logger.warning(f"Slow request: {request.method} {request.url.path} took {duration:.2f}s")
            
            # Log error responses
            if response.status_code >= 400:
                logger.warning(f"Error response: {request.method} {request.url.path} returned {response.status_code}")
                
        except Exception as e:
            logger.error(f"Request metrics logging error: {e}")
    
    def _rate_limit_response(self, message: str) -> JSONResponse:
        """Create rate limit exceeded response"""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "message": message,
                "retry_after": 60  # Retry after 60 seconds
            },
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 60)
            }
        )

# Rate limiting decorators for specific endpoints
def rate_limit(limit: int, window: int = 60):
    """
    Decorator for endpoint-specific rate limiting
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would be implemented at the route level
            # For now, the middleware handles all rate limiting
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# IP whitelist for trusted sources (load balancers, monitoring, etc.)
TRUSTED_IPS = [
    '127.0.0.1',
    '::1',
    # Add Railway/Vercel IP ranges here if needed
]

def is_trusted_ip(ip: str) -> bool:
    """Check if IP is in trusted list"""
    return ip in TRUSTED_IPS

# Rate limit statistics endpoint
async def get_rate_limit_stats() -> Dict:
    """Get current rate limiting statistics"""
    try:
        stats = {
            'active_rate_limits': len(AdvancedRateLimiterMiddleware.rate_limits),
            'ip_limits': AdvancedRateLimiterMiddleware.ip_limits,
            'endpoint_limits': AdvancedRateLimiterMiddleware.rate_limits,
            'trusted_ips': TRUSTED_IPS
        }
        return stats
    except Exception as e:
        logger.error(f"Rate limit stats error: {e}")
        return {'error': str(e)}
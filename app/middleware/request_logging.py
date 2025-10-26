"""
Request/Response Logging Middleware
"""
import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log HTTP requests and responses
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Start timing
        start_time = time.time()
        
        # Extract request information
        request_data = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "content_type": request.headers.get("content-type"),
            "content_length": request.headers.get("content-length"),
            "referer": request.headers.get("referer"),
            "host": request.headers.get("host")
        }
        
        # Try to extract user information from headers or auth
        try:
            # Check for authorization header
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                request_data["has_auth_token"] = True
            
            # You can add more user extraction logic here
            # For example, from JWT token or session
            
        except Exception as e:
            logger.warning(f"Could not extract user info: {e}")
        
        # Log the incoming request
        logger.info("Incoming request", extra={
            "extra_fields": {
                "type": "request",
                **request_data
            }
        })
        
        # Process the request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Extract response information
            response_data = {
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type"),
                "content_length": response.headers.get("content-length"),
                "process_time_ms": round(process_time * 1000, 2)
            }
            
            # Log the response
            log_level = logging.INFO
            if response.status_code >= 400:
                log_level = logging.WARNING
            if response.status_code >= 500:
                log_level = logging.ERROR
            
            logger.log(log_level, "Request completed", extra={
                "extra_fields": {
                    "type": "response",
                    "method": request.method,
                    "path": request.url.path,
                    **response_data
                }
            })
            
            # Add performance headers
            response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
            
            return response
            
        except Exception as e:
            # Calculate processing time for failed requests
            process_time = time.time() - start_time
            
            # Log the error
            logger.error("Request failed", extra={
                "extra_fields": {
                    "type": "error",
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "process_time_ms": round(process_time * 1000, 2)
                }
            }, exc_info=True)
            
            # Re-raise the exception
            raise

class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track performance metrics
    """
    
    def __init__(self, app, slow_request_threshold: float = 1.0):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        # Log slow requests
        if process_time > self.slow_request_threshold:
            logger.warning("Slow request detected", extra={
                "extra_fields": {
                    "type": "slow_request",
                    "method": request.method,
                    "path": request.url.path,
                    "process_time_ms": round(process_time * 1000, 2),
                    "threshold_ms": self.slow_request_threshold * 1000
                }
            })
        
        # Add performance headers
        response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
        
        return response


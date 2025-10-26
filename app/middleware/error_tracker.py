"""
Error Tracking Middleware
"""
import logging
import traceback
from typing import Callable, Optional
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.config.logging_config import get_logger
from app.config.settings import settings

logger = get_logger(__name__)

class ErrorTracker:
    """
    Centralized error tracking and alerting system
    """
    
    def __init__(self):
        self.critical_errors = [
            "DatabaseConnectionError",
            "AuthenticationError", 
            "PaymentProcessingError",
            "ExternalServiceError"
        ]
    
    def is_critical(self, error: Exception) -> bool:
        """Check if an error is critical and should trigger alerts"""
        error_type = type(error).__name__
        return error_type in self.critical_errors
    
    async def track_error(self, error: Exception, context: dict = None):
        """Track an error with context"""
        error_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {},
            "is_critical": self.is_critical(error)
        }
        
        # Log the error
        if self.is_critical(error):
            logger.error(f"Critical error: {error_data['error_message']}", 
                        extra={"extra_fields": error_data}, exc_info=True)
            
            # Send alert for critical errors
            await self.send_critical_alert(error_data)
        else:
            logger.error(f"Error: {error_data['error_message']}", 
                        extra={"extra_fields": error_data}, exc_info=True)
    
    async def send_critical_alert(self, error_data: dict):
        """Send alert for critical errors (can be extended with Slack/Discord)"""
        try:
            # In production, this would send to Slack/Discord
            if settings.ENVIRONMENT == "production":
                logger.critical(f"CRITICAL ERROR ALERT: {error_data['error_type']} - {error_data['error_message']}")
                
                # TODO: Implement actual alerting
                # await self.send_slack_alert(error_data)
                # await self.send_discord_alert(error_data)
            
        except Exception as e:
            logger.error(f"Failed to send critical alert: {e}")

# Global error tracker instance
error_tracker = ErrorTracker()

class ErrorTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to catch and track all unhandled errors
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
            
        except StarletteHTTPException as e:
            # Handle HTTP exceptions
            await error_tracker.track_error(e, {
                "type": "http_exception",
                "method": request.method,
                "path": request.url.path,
                "status_code": e.status_code
            })
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": e.detail,
                    "status_code": e.status_code,
                    "path": request.url.path
                }
            )
            
        except HTTPException as e:
            # Handle FastAPI HTTP exceptions
            await error_tracker.track_error(e, {
                "type": "fastapi_http_exception",
                "method": request.method,
                "path": request.url.path,
                "status_code": e.status_code
            })
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": e.detail,
                    "status_code": e.status_code,
                    "path": request.url.path
                }
            )
            
        except Exception as e:
            # Handle all other exceptions
            await error_tracker.track_error(e, {
                "type": "unhandled_exception",
                "method": request.method,
                "path": request.url.path,
                "user_agent": request.headers.get("user-agent"),
                "client_ip": request.client.host if request.client else None
            })
            
            # Return a generic error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "status_code": 500,
                    "path": request.url.path
                }
            )

class DatabaseErrorMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle database-specific errors
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
            
        except Exception as e:
            error_type = type(e).__name__
            
            # Check if it's a database-related error
            if any(db_error in error_type for db_error in [
                "OperationalError", "IntegrityError", "ProgrammingError", 
                "DatabaseError", "ConnectionError", "TimeoutError"
            ]):
                await error_tracker.track_error(e, {
                    "type": "database_error",
                    "error_category": "database",
                    "method": request.method,
                    "path": request.url.path
                })
                
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "Database service temporarily unavailable",
                        "status_code": 503,
                        "path": request.url.path
                    }
                )
            
            # Re-raise if not a database error
            raise

class RateLimitErrorMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle rate limiting errors
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
            
        except Exception as e:
            error_type = type(e).__name__
            
            # Check if it's a rate limiting error
            if "RateLimit" in error_type or "TooManyRequests" in error_type:
                await error_tracker.track_error(e, {
                    "type": "rate_limit_error",
                    "error_category": "rate_limiting",
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": request.client.host if request.client else None
                })
                
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "status_code": 429,
                        "path": request.url.path,
                        "retry_after": 60
                    }
                )
            
            # Re-raise if not a rate limiting error
            raise


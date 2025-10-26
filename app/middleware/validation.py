"""
Input Validation Middleware for Request Sanitization
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from fastapi import HTTPException, status
import re
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class InputValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for input validation and sanitization
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
        # Patterns for malicious input detection
        self.sql_injection_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)",
            r"(--|;|\/\*|\*\/|xp_|sp_)",
            r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
            r"(\b(OR|AND)\s+[\'\"].*[\'\"]\s*=\s*[\'\"].*[\'\"])",
        ]
        
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
        ]
        
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e%5c",
        ]
    
    async def dispatch(self, request: Request, call_next):
        try:
            # Validate request path
            if not self._validate_path(request.url.path):
                logger.warning(f"Suspicious path detected: {request.url.path}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request path"
                )
            
            # Validate query parameters
            if not self._validate_query_params(request.url.query):
                logger.warning(f"Suspicious query parameters detected: {request.url.query}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid query parameters"
                )
            
            # Validate headers
            if not self._validate_headers(request.headers):
                logger.warning("Suspicious headers detected")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid headers"
                )
            
            # Process request
            response = await call_next(request)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Input validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal validation error"
            )
    
    def _validate_path(self, path: str) -> bool:
        """Validate request path for path traversal attempts"""
        if not path or len(path) > 1000:  # Reasonable path length limit
            return False
        
        # Check for path traversal patterns
        for pattern in self.path_traversal_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                return False
        
        # Check for suspicious file extensions
        suspicious_extensions = ['.exe', '.bat', '.cmd', '.com', '.pif', '.scr']
        if any(path.lower().endswith(ext) for ext in suspicious_extensions):
            return False
        
        return True
    
    def _validate_query_params(self, query_string: str) -> bool:
        """Validate query parameters for malicious content"""
        if not query_string:
            return True
        
        if len(query_string) > 2000:  # Reasonable query string length limit
            return False
        
        # Check for SQL injection patterns
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, query_string, re.IGNORECASE):
                return False
        
        # Check for XSS patterns
        for pattern in self.xss_patterns:
            if re.search(pattern, query_string, re.IGNORECASE):
                return False
        
        return True
    
    def _validate_headers(self, headers) -> bool:
        """Validate request headers"""
        # Check for suspicious header values
        suspicious_headers = ['user-agent', 'referer', 'origin']
        
        for header_name in suspicious_headers:
            if header_name in headers:
                header_value = headers[header_name]
                
                # Check for XSS in headers
                for pattern in self.xss_patterns:
                    if re.search(pattern, header_value, re.IGNORECASE):
                        return False
                
                # Check header length
                if len(header_value) > 1000:
                    return False
        
        return True


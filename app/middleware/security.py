"""
Security Middleware for Banking-Grade Protection.

Implements:
- Rate limiting with slowapi
- Account lockout after failed attempts
- Security headers (OWASP recommended)
- Request/response audit logging
- Auto error reporting
"""

import os
import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional
from collections import defaultdict

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


# =============================================================================
# RATE LIMITING
# =============================================================================

def get_client_ip(request: Request) -> str:
    """Get client IP, accounting for proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return get_remote_address(request)


def get_storage_uri() -> str:
    """Get rate limiter storage URI with fallback to memory."""
    redis_url = os.getenv("REDIS_URL", "")
    # Check if it's a valid URL (not a template variable like ${SOMETHING})
    if redis_url and redis_url.startswith(("redis://", "rediss://", "memory://")):
        return redis_url
    # Fallback to in-memory storage
    return "memory://"


limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["200/minute"],
    storage_uri=get_storage_uri(),
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded."""
    logger.warning(f"Rate limit exceeded: IP={get_client_ip(request)}, path={request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"error": "rate_limit_exceeded", "message": "Too many requests. Please try again later.", "retry_after": 60},
        headers={"Retry-After": "60"},
    )


# =============================================================================
# ACCOUNT LOCKOUT
# =============================================================================

class AccountLockoutManager:
    """Manages account lockout after failed login attempts."""

    _failed_attempts: dict = defaultdict(list)
    _lockouts: dict = {}

    MAX_ATTEMPTS_TIER1 = 5
    MAX_ATTEMPTS_TIER2 = 10
    MAX_ATTEMPTS_TIER3 = 15

    LOCKOUT_TIER1 = timedelta(minutes=15)
    LOCKOUT_TIER2 = timedelta(hours=1)
    LOCKOUT_TIER3 = timedelta(hours=24)
    ATTEMPT_WINDOW = timedelta(hours=1)

    @classmethod
    def record_failed_attempt(cls, identifier: str) -> tuple[bool, Optional[int]]:
        """Record a failed login attempt. Returns (is_locked, lockout_seconds)."""
        now = datetime.utcnow()
        cls._failed_attempts[identifier] = [
            a for a in cls._failed_attempts[identifier] if a > now - cls.ATTEMPT_WINDOW
        ]
        cls._failed_attempts[identifier].append(now)
        attempts = len(cls._failed_attempts[identifier])

        logger.warning(f"Failed login attempt #{attempts} for {identifier}")

        if attempts >= cls.MAX_ATTEMPTS_TIER3:
            lockout_duration = cls.LOCKOUT_TIER3
        elif attempts >= cls.MAX_ATTEMPTS_TIER2:
            lockout_duration = cls.LOCKOUT_TIER2
        elif attempts >= cls.MAX_ATTEMPTS_TIER1:
            lockout_duration = cls.LOCKOUT_TIER1
        else:
            return False, None

        cls._lockouts[identifier] = now + lockout_duration
        logger.warning(f"Account locked: {identifier}, attempts={attempts}")
        return True, int(lockout_duration.total_seconds())

    @classmethod
    def is_locked(cls, identifier: str) -> tuple[bool, Optional[int]]:
        """Check if account is locked. Returns (is_locked, remaining_seconds)."""
        lockout_until = cls._lockouts.get(identifier)
        if not lockout_until:
            return False, None
        now = datetime.utcnow()
        if now >= lockout_until:
            del cls._lockouts[identifier]
            return False, None
        return True, int((lockout_until - now).total_seconds())

    @classmethod
    def clear_attempts(cls, identifier: str) -> None:
        """Clear failed attempts after successful login."""
        cls._failed_attempts.pop(identifier, None)
        cls._lockouts.pop(identifier, None)

    @classmethod
    def get_remaining_attempts(cls, identifier: str) -> int:
        """Get remaining attempts before first lockout."""
        attempts = len(cls._failed_attempts.get(identifier, []))
        return max(0, cls.MAX_ATTEMPTS_TIER1 - attempts)


# =============================================================================
# SECURITY HEADERS MIDDLEWARE
# =============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds OWASP-recommended security headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        if os.getenv("ENVIRONMENT") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
            "connect-src 'self' https:; frame-ancestors 'none';"
        )
        return response


# =============================================================================
# AUDIT LOGGING MIDDLEWARE
# =============================================================================

class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Logs all requests for security auditing."""

    SECURITY_PATHS = {"/auth/", "/hq/auth/", "/banking/", "/payroll/"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        request.state.request_id = request_id
        client_ip = get_client_ip(request)
        path = request.url.path

        try:
            response = await call_next(request)
            duration_ms = int((time.time() - start_time) * 1000)

            if response.status_code >= 500:
                logger.error(f"[{request_id}] {request.method} {path} -> {response.status_code} ({duration_ms}ms) IP={client_ip}")
            elif response.status_code >= 400 or any(path.startswith(sp) for sp in self.SECURITY_PATHS):
                logger.warning(f"[{request_id}] {request.method} {path} -> {response.status_code} ({duration_ms}ms) IP={client_ip}")

            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            logger.error(f"[{request_id}] {request.method} {path} -> ERROR IP={client_ip} error={str(e)}")
            raise


# =============================================================================
# ERROR REPORTING SERVICE
# =============================================================================

class ErrorReporter:
    """Auto-reports errors to monitoring systems (Sentry, etc.)."""

    _sentry_initialized = False

    @classmethod
    def initialize(cls):
        """Initialize Sentry if configured."""
        sentry_dsn = os.getenv("SENTRY_DSN")
        if sentry_dsn and not cls._sentry_initialized:
            try:
                import sentry_sdk
                from sentry_sdk.integrations.fastapi import FastApiIntegration
                sentry_sdk.init(dsn=sentry_dsn, integrations=[FastApiIntegration()], traces_sample_rate=0.1, environment=os.getenv("ENVIRONMENT", "development"))
                cls._sentry_initialized = True
                logger.info("Sentry error reporting initialized")
            except ImportError:
                logger.warning("sentry-sdk not installed")

    @classmethod
    def report_error(cls, error: Exception, context: Optional[dict] = None, user_id: Optional[str] = None, company_id: Optional[str] = None) -> str:
        """Report error and return reference ID."""
        error_id = str(uuid.uuid4())[:8]
        logger.error(f"[ERROR:{error_id}] {type(error).__name__}: {str(error)} user={user_id} company={company_id}")

        if cls._sentry_initialized:
            try:
                import sentry_sdk
                with sentry_sdk.push_scope() as scope:
                    if user_id:
                        scope.set_user({"id": user_id})
                    if company_id:
                        scope.set_tag("company_id", company_id)
                    scope.set_tag("error_id", error_id)
                    sentry_sdk.capture_exception(error)
            except Exception:
                pass
        return error_id

    @classmethod
    def report_security_event(cls, event_type: str, description: str, user_id: Optional[str] = None, ip_address: Optional[str] = None) -> None:
        """Report security event (login_failure, account_locked, etc.)."""
        logger.warning(f"[SECURITY:{event_type}] {description} user={user_id} ip={ip_address}")


# =============================================================================
# SETUP FUNCTION
# =============================================================================

def setup_security_middleware(app: FastAPI) -> None:
    """Configure all security middleware."""
    ErrorReporter.initialize()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AuditLoggingMiddleware)
    logger.info("Security middleware configured")

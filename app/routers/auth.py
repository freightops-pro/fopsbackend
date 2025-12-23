from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.api import deps
from app.core.db import get_db
from app.core.config import get_settings
from app.schemas.auth import AuthSessionResponse, ChangePasswordRequest, UserCreate, UserLogin, UserResponse
from app.services.auth import AuthService, DEFAULT_TOKEN_EXPIRY_MINUTES, REMEMBER_ME_TOKEN_EXPIRY_MINUTES
from app.middleware.security import limiter

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

AUTH_COOKIE_NAME = "freightops_token"


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def set_auth_cookie(response: Response, token: str, remember_me: bool = False) -> None:
    """Set auth cookie with appropriate expiry based on remember_me."""
    max_age = (
        REMEMBER_ME_TOKEN_EXPIRY_MINUTES * 60 if remember_me
        else DEFAULT_TOKEN_EXPIRY_MINUTES * 60
    )
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.environment != "development",
        samesite="lax",
        max_age=max_age,
        path="/",
        domain=None,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")


@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register_user(
    request: Request,
    payload: UserCreate,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> AuthSessionResponse:
    """
    Register a new user and company.

    Rate limited to 5 requests per minute to prevent abuse.
    """
    service = AuthService(db)
    try:
        user, token = await service.register(payload)
        set_auth_cookie(response, token)
        session = await service.build_session(user, token=token)
        return session
    except ValueError as exc:
        logger.warning(f"Registration validation error: {str(exc)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"Registration error: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during registration. Please try again."
        )


@router.post("/login", response_model=AuthSessionResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> AuthSessionResponse:
    """
    Authenticate user and return session.

    Rate limited to 10 requests per minute to prevent brute force attacks.
    Account is locked after 5 failed attempts.
    """
    logger.info(f"[LOGIN] Request received for email: {payload.email}")
    service = AuthService(db)
    ip_address = get_client_ip(request)

    try:
        logger.info(f"[LOGIN] Starting authentication for email: {payload.email}")
        user, token = await service.authenticate(
            payload,
            ip_address=ip_address,
            remember_me=payload.remember_me
        )
        logger.info(f"[LOGIN] Authentication successful for user: {user.id}")

        set_auth_cookie(response, token, remember_me=payload.remember_me)
        session = await service.build_session(user, token=token)

        # Ensure token is in response
        if not session.access_token:
            session.access_token = token

        return session
    except ValueError as exc:
        logger.warning(f"Login failed for email {payload.email}: {str(exc)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except Exception as exc:
        logger.error(f"Login error for email {payload.email}: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login. Please try again."
        )


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user=Depends(deps.get_current_user)) -> UserResponse:
    return deps.build_user_response(current_user)


@router.get("/session", response_model=AuthSessionResponse)
async def read_session(
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
) -> AuthSessionResponse:
    service = AuthService(db)
    return await service.build_session(current_user)


@router.post("/change-password", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Change user password and clear must_change_password flag.

    Rate limited to 3 requests per minute.
    """
    service = AuthService(db)
    try:
        await service.change_password(current_user, payload.current_password, payload.new_password)
        return {"message": "Password changed successfully"}
    except ValueError as exc:
        logger.warning(f"Password change failed for user {current_user.id}: {str(exc)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(f"Password change error for user {current_user.id}: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while changing password. Please try again."
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    clear_auth_cookie(response)


@router.get("/verify-email/{token}")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Verify user email with token from email link.
    """
    service = AuthService(db)
    try:
        user = await service.verify_email(token)
        return {
            "message": "Email verified successfully",
            "email": user.email
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/resend-verification")
@limiter.limit("3/hour")
async def resend_verification(
    request: Request,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Resend email verification link.

    Rate limited to 3 requests per hour.
    """
    service = AuthService(db)
    try:
        await service.resend_verification_email(current_user)
        return {"message": "Verification email sent"}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/forgot-password")
@limiter.limit("3/hour")
async def forgot_password(
    request: Request,
    email: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Request password reset email.

    Rate limited to 3 requests per hour.
    Always returns success to prevent email enumeration.
    """
    service = AuthService(db)
    await service.request_password_reset(email)
    return {"message": "If an account exists with this email, a password reset link has been sent."}

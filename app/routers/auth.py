from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.api import deps
from app.core.db import get_db
from app.core.config import get_settings
from app.schemas.auth import AuthSessionResponse, ChangePasswordRequest, UserCreate, UserLogin, UserResponse
from app.services.auth import AuthService

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

AUTH_COOKIE_NAME = "freightops_token"


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,  # Must be False for http://127.0.0.1 in development
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
        domain=None,  # Let browser set domain automatically
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")


@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate, response: Response, db: AsyncSession = Depends(get_db)) -> AuthSessionResponse:
    service = AuthService(db)
    try:
        user, token = await service.register(payload)
        set_auth_cookie(response, token)
        # Token is already passed to build_session, which includes it in the response
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
async def login(payload: UserLogin, response: Response, db: AsyncSession = Depends(get_db)) -> AuthSessionResponse:
    logger.info(f"[LOGIN] Request received for email: {payload.email}")
    service = AuthService(db)
    try:
        logger.info(f"[LOGIN] Starting authentication for email: {payload.email}")
        user, token = await service.authenticate(payload)
        logger.info(f"[LOGIN] Authentication successful, token generated: {token[:20] if token else 'None'}... (length: {len(token) if token else 0})")
        set_auth_cookie(response, token)
        logger.info(f"[LOGIN] Building session for user: {user.id}")
        # Token is already passed to build_session, which includes it in the response
        session = await service.build_session(user, token=token)
        logger.info(f"[LOGIN] Session built successfully for user: {user.id} (email: {user.email})")
        logger.info(f"[LOGIN] Session response - has access_token: {session.access_token is not None}, token length: {len(session.access_token) if session.access_token else 0}")
        # Ensure token is in response - explicitly set it
        if not session.access_token:
            logger.warning(f"[LOGIN] WARNING: access_token is None in session response! Setting it from token variable.")
            session.access_token = token
        logger.info(f"[LOGIN] Final session - access_token present: {session.access_token is not None}, length: {len(session.access_token) if session.access_token else 0}")
        logger.info(f"[LOGIN] Returning session response")
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
    # No token in response - using HTTP-only cookies for security
    return await service.build_session(current_user)


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    payload: ChangePasswordRequest,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Change user password and clear must_change_password flag."""
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


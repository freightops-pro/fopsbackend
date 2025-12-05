import logging
from typing import Annotated

from fastapi import Depends, HTTPException, WebSocket, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.schemas.auth import UserResponse

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    cookie_token = request.cookies.get("freightops_token")
    credentials_token = cookie_token or token
    if not credentials_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")

    payload = decode_access_token(credentials_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    result = await db.get(User, user_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not result.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")
    return result


def build_user_response(user: User) -> UserResponse:
    return UserResponse.model_validate(
        {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "company_id": user.company_id,
            "created_at": user.created_at,
        }
    )


async def get_current_user_websocket(websocket: WebSocket, db: AsyncSession) -> User:
    """
    Authenticate WebSocket connections.

    This function does NOT close the websocket on failure - it returns None
    and logs the error. The caller should handle the None case.
    """
    # Try to get token from Authorization header first
    token_header = websocket.headers.get("Authorization")
    token = None

    if token_header and token_header.startswith("Bearer "):
        token = token_header.split(" ", 1)[1]
    else:
        # Fallback to query parameter for clients that don't support custom headers
        token = websocket.query_params.get("token")

    if not token:
        logger.warning("[WebSocket Auth] No token provided")
        return None

    payload = decode_access_token(token)
    if not payload:
        logger.warning(f"[WebSocket Auth] Token decode failed for token: {token[:50]}...")
        return None

    user_id = payload.get("sub")
    if not user_id:
        logger.warning(f"[WebSocket Auth] No 'sub' in payload: {payload}")
        return None

    user = await db.get(User, user_id)
    if not user:
        logger.warning(f"[WebSocket Auth] User not found for id: {user_id}")
        return None

    logger.info(f"[WebSocket Auth] Authenticated user: {user.email}")
    return user


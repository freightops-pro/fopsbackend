import logging
from typing import Annotated, Callable, List, Optional

from fastapi import Depends, HTTPException, WebSocket, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.rbac import Action, Resource
from app.core.security import decode_access_token
from app.models.user import User
from app.schemas.auth import UserResponse
from app.services.permission import PermissionService

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


async def get_current_company(
    current_user: User = Depends(get_current_user),
) -> str:
    """
    FastAPI dependency that extracts company_id from the current user.
    
    This ensures all endpoints using this dependency have access to the
    authenticated user's company_id for proper tenant isolation.
    
    Usage:
        @router.get("/items")
        async def list_items(company_id: str = Depends(get_current_company)):
            # company_id is guaranteed to be from authenticated user
            ...
    """
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company"
        )
    return current_user.company_id


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


# =============================================================================
# Permission-based dependencies
# =============================================================================


def require_permission(resource: Resource | str, action: Action | str):
    """
    FastAPI dependency that requires a specific permission.

    Usage:
        @router.get("/banking/balance")
        async def get_balance(user = Depends(require_permission(Resource.BANKING, Action.VIEW))):
            ...
    """
    async def dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        permission_service = PermissionService(db)
        has_perm = await permission_service.has_permission(
            current_user.id, resource, action
        )

        if not has_perm:
            resource_str = resource.value if isinstance(resource, Resource) else resource
            action_str = action.value if isinstance(action, Action) else action
            logger.warning(
                f"Permission denied: user={current_user.email}, "
                f"permission={resource_str}:{action_str}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource_str}:{action_str}",
            )

        return current_user

    return dependency


def require_any_permission(permissions: List[tuple]):
    """
    FastAPI dependency that requires at least one of the specified permissions.

    Usage:
        @router.get("/reports")
        async def get_reports(
            user = Depends(require_any_permission([
                (Resource.REPORTS, Action.VIEW),
                (Resource.ACCOUNTING, Action.VIEW),
            ]))
        ):
            ...
    """
    async def dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        permission_service = PermissionService(db)
        has_any = await permission_service.has_any_permission(current_user.id, permissions)

        if not has_any:
            perm_strs = [
                f"{r.value if isinstance(r, Resource) else r}:{a.value if isinstance(a, Action) else a}"
                for r, a in permissions
            ]
            logger.warning(
                f"Permission denied: user={current_user.email}, "
                f"required_any={perm_strs}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied: insufficient permissions",
            )

        return current_user

    return dependency


def require_role(role: str):
    """
    FastAPI dependency that requires a specific role.

    Usage:
        @router.get("/admin/settings")
        async def admin_settings(user = Depends(require_role("TENANT_ADMIN"))):
            ...
    """
    async def dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        permission_service = PermissionService(db)
        has_role = await permission_service.has_role(current_user.id, role)

        if not has_role:
            logger.warning(
                f"Role required: user={current_user.email}, required_role={role}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role required: {role}",
            )

        return current_user

    return dependency


def require_any_role(roles: List[str]):
    """
    FastAPI dependency that requires at least one of the specified roles.

    Usage:
        @router.get("/accounting")
        async def accounting_page(
            user = Depends(require_any_role(["TENANT_ADMIN", "ACCOUNTANT"]))
        ):
            ...
    """
    async def dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        permission_service = PermissionService(db)
        has_any = await permission_service.has_any_role(current_user.id, roles)

        if not has_any:
            logger.warning(
                f"Role required: user={current_user.email}, required_any={roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of these roles required: {', '.join(roles)}",
            )

        return current_user

    return dependency


async def get_permission_service(
    db: AsyncSession = Depends(get_db),
) -> PermissionService:
    """Get a PermissionService instance for manual permission checks."""
    return PermissionService(db)


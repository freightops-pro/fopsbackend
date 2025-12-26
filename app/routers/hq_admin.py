"""
HQ Admin Router - Platform-level admin endpoints.

Provides endpoints for HQ_ADMIN users to:
- View and manage all tenants
- Access platform-wide audit logs
- Get platform statistics
- Suspend/activate tenants
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.models.user import User
from app.services.tenant_service import TenantService
from app.services.audit_log_service import AuditLogService
from app.schemas.tenant import (
    TenantResponse,
    TenantDetailResponse,
    TenantListResponse,
    TenantFilter,
    TenantStatusUpdate,
    TenantUsersListResponse,
    PlatformStats,
)
from app.schemas.audit_log import (
    AuditLogFilter,
    AuditLogListResponse,
    AuditLogSummary,
)

router = APIRouter()


async def _tenant_service(db: AsyncSession = Depends(get_db)) -> TenantService:
    return TenantService(db)


async def _audit_service(db: AsyncSession = Depends(get_db)) -> AuditLogService:
    return AuditLogService(db)


# ============ TENANT MANAGEMENT ============

@router.get("/tenants", response_model=TenantListResponse)
async def list_tenants(
    service: TenantService = Depends(_tenant_service),
    search: Optional[str] = Query(None, description="Search by name, email, DOT, or MC"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    subscription_plan: Optional[str] = Query(None, description="Filter by subscription"),
    state: Optional[str] = Query(None, description="Filter by state"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _current_user: User = Depends(deps.require_role("HQ_ADMIN")),
) -> TenantListResponse:
    """
    List all tenants on the platform.

    Requires HQ_ADMIN role.
    """
    filters = TenantFilter(
        search=search,
        is_active=is_active,
        subscription_plan=subscription_plan,
        state=state,
    )
    return await service.list_tenants(filters=filters, page=page, page_size=page_size)


@router.get("/tenants/stats", response_model=PlatformStats)
async def get_platform_stats(
    service: TenantService = Depends(_tenant_service),
    _current_user: User = Depends(deps.require_role("HQ_ADMIN")),
) -> PlatformStats:
    """
    Get platform-wide statistics.

    Requires HQ_ADMIN role.
    """
    return await service.get_platform_stats()


@router.get("/tenants/{tenant_id}", response_model=TenantDetailResponse)
async def get_tenant(
    tenant_id: str,
    service: TenantService = Depends(_tenant_service),
    _current_user: User = Depends(deps.require_role("HQ_ADMIN")),
) -> TenantDetailResponse:
    """
    Get detailed information about a specific tenant.

    Requires HQ_ADMIN role.
    """
    tenant = await service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return tenant


@router.get("/tenants/{tenant_id}/users", response_model=TenantUsersListResponse)
async def get_tenant_users(
    tenant_id: str,
    service: TenantService = Depends(_tenant_service),
    _current_user: User = Depends(deps.require_role("HQ_ADMIN")),
) -> TenantUsersListResponse:
    """
    Get all users for a specific tenant.

    Requires HQ_ADMIN role.
    """
    return await service.get_tenant_users(tenant_id)


@router.post("/tenants/{tenant_id}/suspend", response_model=TenantDetailResponse)
async def suspend_tenant(
    tenant_id: str,
    data: TenantStatusUpdate,
    service: TenantService = Depends(_tenant_service),
    current_user: User = Depends(deps.require_role("HQ_ADMIN")),
) -> TenantDetailResponse:
    """
    Suspend a tenant.

    Requires HQ_ADMIN role. Prevents all users from accessing the platform.
    """
    if data.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /activate endpoint to activate a tenant",
        )

    result = await service.update_tenant_status(
        tenant_id=tenant_id,
        is_active=False,
        reason=data.reason,
        admin_user_id=current_user.id,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return result


@router.post("/tenants/{tenant_id}/activate", response_model=TenantDetailResponse)
async def activate_tenant(
    tenant_id: str,
    service: TenantService = Depends(_tenant_service),
    current_user: User = Depends(deps.require_role("HQ_ADMIN")),
) -> TenantDetailResponse:
    """
    Activate a suspended tenant.

    Requires HQ_ADMIN role.
    """
    result = await service.update_tenant_status(
        tenant_id=tenant_id,
        is_active=True,
        admin_user_id=current_user.id,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return result


# ============ PLATFORM AUDIT LOGS ============

@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_all_audit_logs(
    service: AuditLogService = Depends(_audit_service),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    event_type: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None, description="Filter by specific tenant"),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    _current_user: User = Depends(deps.require_role("HQ_ADMIN")),
) -> AuditLogListResponse:
    """
    List audit logs across all tenants.

    Requires HQ_ADMIN role. Can filter by specific tenant using company_id.
    """
    filters = AuditLogFilter(
        event_type=event_type,
        user_email=user_email,
        status=status_filter,
        search=search,
    )

    # Pass company_id as None to see all tenants, or specific ID to filter
    return await service.list_audit_logs(
        company_id=company_id,  # None = all tenants
        filters=filters,
        page=page,
        page_size=page_size,
    )


@router.get("/audit-logs/summary", response_model=AuditLogSummary)
async def get_platform_audit_summary(
    service: AuditLogService = Depends(_audit_service),
    days: int = Query(30, ge=1, le=365),
    company_id: Optional[str] = Query(None, description="Filter by specific tenant"),
    _current_user: User = Depends(deps.require_role("HQ_ADMIN")),
) -> AuditLogSummary:
    """
    Get audit log summary for the platform.

    Requires HQ_ADMIN role.
    """
    return await service.get_audit_log_summary(
        company_id=company_id,  # None = all tenants
        days=days,
    )

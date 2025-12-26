"""
Audit Logs Router - API endpoints for security audit logs.

Provides endpoints for:
- Listing audit logs (tenant-scoped)
- Exporting audit logs
- Getting summary statistics
- HQ admin cross-tenant access
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.models.user import User
from app.services.audit_log_service import AuditLogService
from app.schemas.audit_log import (
    AuditLogFilter,
    AuditLogListResponse,
    AuditLogSummary,
    LoginAttemptListResponse,
    EVENT_TYPES,
)

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> AuditLogService:
    return AuditLogService(db)


async def _company_id(current_user: User = Depends(deps.get_current_user)) -> str:
    return current_user.company_id


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    company_id: str = Depends(_company_id),
    service: AuditLogService = Depends(_service),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    status: Optional[str] = Query(None, description="Filter by status (success/failure/blocked)"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    search: Optional[str] = Query(None, description="Search in action/email"),
    _current_user: User = Depends(deps.get_current_user),
) -> AuditLogListResponse:
    """
    List audit logs for the current company.

    Requires authentication. Returns paginated audit logs filtered by company.
    """
    filters = AuditLogFilter(
        event_type=event_type,
        user_id=user_id,
        user_email=user_email,
        status=status,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )

    return await service.list_audit_logs(
        company_id=company_id,
        filters=filters,
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=AuditLogSummary)
async def get_audit_log_summary(
    company_id: str = Depends(_company_id),
    service: AuditLogService = Depends(_service),
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    _current_user: User = Depends(deps.get_current_user),
) -> AuditLogSummary:
    """
    Get summary statistics for audit logs.

    Returns counts and trends for the specified time period.
    """
    return await service.get_audit_log_summary(
        company_id=company_id,
        days=days,
    )


@router.get("/export")
async def export_audit_logs(
    company_id: str = Depends(_company_id),
    service: AuditLogService = Depends(_service),
    format: str = Query("json", description="Export format (json or csv)"),
    event_type: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _current_user: User = Depends(deps.get_current_user),
) -> Response:
    """
    Export audit logs as JSON or CSV.

    Returns downloadable file with audit log data.
    """
    filters = AuditLogFilter(
        event_type=event_type,
        start_date=start_date,
        end_date=end_date,
    )

    data, filename = await service.export_audit_logs(
        company_id=company_id,
        filters=filters,
        format=format,
    )

    if format == "csv":
        # Convert to CSV format
        import csv
        import io
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        csv_content = output.getvalue()

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        return JSONResponse(
            content={"logs": data, "count": len(data)},
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


@router.get("/event-types")
async def get_event_types(
    _current_user: User = Depends(deps.get_current_user),
) -> dict:
    """
    Get list of available event types for filtering.
    """
    return {"event_types": EVENT_TYPES}


@router.get("/login-attempts", response_model=LoginAttemptListResponse)
async def get_login_attempts(
    service: AuditLogService = Depends(_service),
    identifier: Optional[str] = Query(None, description="Filter by email or IP"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _current_user: User = Depends(deps.require_role("TENANT_ADMIN")),
) -> LoginAttemptListResponse:
    """
    Get login attempts. Requires TENANT_ADMIN role.

    Used for security monitoring and account lockout management.
    """
    return await service.get_login_attempts(
        identifier=identifier,
        page=page,
        page_size=page_size,
    )

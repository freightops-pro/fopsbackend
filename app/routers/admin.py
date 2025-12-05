"""HQ Admin routes for platform-level monitoring and management."""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api import deps
from app.core.db import get_db
from app.models.company import Company
from app.models.integration import CompanyIntegration, Integration
from app.schemas.integration import (
    FailedSyncListResponse,
    HQIntegrationHealthResponse,
    IntegrationHealthItem,
    IntegrationTypeHealth,
)

router = APIRouter()


def _calculate_health_status(ci: CompanyIntegration) -> str:
    """Calculate health status based on consecutive failures and last error."""
    if ci.status == "error" or ci.consecutive_failures >= 5:
        return "critical"
    if ci.consecutive_failures >= 2:
        return "warning"
    if ci.last_error_at and ci.last_success_at:
        if ci.last_error_at > ci.last_success_at:
            return "warning"
    return "healthy"


def _to_health_item(ci: CompanyIntegration, company_name: Optional[str] = None) -> IntegrationHealthItem:
    """Convert CompanyIntegration to IntegrationHealthItem."""
    return IntegrationHealthItem(
        id=ci.id,
        company_id=ci.company_id,
        company_name=company_name or (ci.company.name if ci.company else None),
        integration_key=ci.integration.integration_key if ci.integration else "",
        integration_name=ci.integration.display_name if ci.integration else "",
        integration_type=ci.integration.integration_type if ci.integration else "",
        status=ci.status,
        last_sync_at=ci.last_sync_at,
        last_success_at=ci.last_success_at,
        last_error_at=ci.last_error_at,
        last_error_message=ci.last_error_message,
        consecutive_failures=ci.consecutive_failures,
        health_status=_calculate_health_status(ci),
    )


@router.get("/integrations/health", response_model=HQIntegrationHealthResponse)
async def get_integration_health_dashboard(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(deps.get_current_user),  # TODO: Add HQ admin role check
) -> HQIntegrationHealthResponse:
    """
    Get HQ-level integration health dashboard.
    Shows overall health status across all companies and integrations.
    """
    # Get all company integrations with their integration info and company info
    result = await db.execute(
        select(CompanyIntegration)
        .options(joinedload(CompanyIntegration.integration), joinedload(CompanyIntegration.company))
        .where(CompanyIntegration.status != "not-activated")
    )
    all_connections = result.scalars().unique().all()

    # Count unique companies
    company_ids = set(ci.company_id for ci in all_connections)
    total_companies = len(company_ids)

    # Calculate overall metrics
    total_connections = len(all_connections)
    active_connections = sum(1 for ci in all_connections if ci.status == "active")
    error_connections = sum(1 for ci in all_connections if ci.status == "error")

    # Calculate health status counts
    health_counts = {"healthy": 0, "warning": 0, "critical": 0}
    for ci in all_connections:
        health_status = _calculate_health_status(ci)
        health_counts[health_status] += 1

    # Group by integration type for breakdown
    type_groups: dict = {}
    for ci in all_connections:
        if not ci.integration:
            continue
        key = ci.integration.integration_key
        if key not in type_groups:
            type_groups[key] = {
                "integration_type": ci.integration.integration_type,
                "integration_key": key,
                "integration_name": ci.integration.display_name,
                "connections": [],
            }
        type_groups[key]["connections"].append(ci)

    # Build type health summaries
    by_type: List[IntegrationTypeHealth] = []
    for key, group in type_groups.items():
        connections = group["connections"]
        type_health = IntegrationTypeHealth(
            integration_type=group["integration_type"],
            integration_key=group["integration_key"],
            integration_name=group["integration_name"],
            total_connections=len(connections),
            active_connections=sum(1 for c in connections if c.status == "active"),
            error_connections=sum(1 for c in connections if c.status == "error"),
            healthy_connections=sum(1 for c in connections if _calculate_health_status(c) == "healthy"),
            warning_connections=sum(1 for c in connections if _calculate_health_status(c) == "warning"),
            critical_connections=sum(1 for c in connections if _calculate_health_status(c) == "critical"),
            last_sync_overall=max((c.last_sync_at for c in connections if c.last_sync_at), default=None),
        )
        by_type.append(type_health)

    # Get recent errors (last 24 hours or with consecutive failures)
    recent_errors: List[IntegrationHealthItem] = []
    cutoff = datetime.utcnow() - timedelta(hours=24)
    for ci in all_connections:
        if ci.consecutive_failures > 0 or (ci.last_error_at and ci.last_error_at > cutoff):
            recent_errors.append(_to_health_item(ci))

    # Sort by consecutive failures descending, then by last error time
    recent_errors.sort(key=lambda x: (-(x.consecutive_failures or 0), x.last_error_at or datetime.min), reverse=True)
    recent_errors = recent_errors[:20]  # Limit to 20 most recent/critical

    return HQIntegrationHealthResponse(
        total_companies=total_companies,
        total_connections=total_connections,
        active_connections=active_connections,
        error_connections=error_connections,
        healthy_connections=health_counts["healthy"],
        warning_connections=health_counts["warning"],
        critical_connections=health_counts["critical"],
        by_type=by_type,
        recent_errors=recent_errors,
    )


@router.get("/integrations/failed-syncs", response_model=FailedSyncListResponse)
async def get_failed_syncs(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(deps.get_current_user),  # TODO: Add HQ admin role check
    integration_type: Optional[str] = Query(None, description="Filter by integration type"),
    min_failures: int = Query(1, ge=1, description="Minimum consecutive failures"),
    limit: int = Query(50, ge=1, le=200, description="Maximum items to return"),
) -> FailedSyncListResponse:
    """
    Get list of integrations with failed syncs for HQ monitoring.
    Sorted by consecutive failures descending.
    """
    query = (
        select(CompanyIntegration)
        .options(joinedload(CompanyIntegration.integration), joinedload(CompanyIntegration.company))
        .where(CompanyIntegration.consecutive_failures >= min_failures)
    )

    if integration_type:
        query = query.join(Integration).where(Integration.integration_type == integration_type)

    query = query.order_by(CompanyIntegration.consecutive_failures.desc())
    query = query.limit(limit)

    result = await db.execute(query)
    failed_connections = result.scalars().unique().all()

    items = [_to_health_item(ci) for ci in failed_connections]

    # Get total count
    count_query = select(func.count(CompanyIntegration.id)).where(
        CompanyIntegration.consecutive_failures >= min_failures
    )
    if integration_type:
        count_query = count_query.join(Integration).where(Integration.integration_type == integration_type)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return FailedSyncListResponse(items=items, total=total)


@router.get("/integrations/by-company/{company_id}", response_model=List[IntegrationHealthItem])
async def get_company_integration_health(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(deps.get_current_user),  # TODO: Add HQ admin role check
) -> List[IntegrationHealthItem]:
    """
    Get integration health for a specific company (HQ view).
    """
    result = await db.execute(
        select(CompanyIntegration)
        .options(joinedload(CompanyIntegration.integration), joinedload(CompanyIntegration.company))
        .where(CompanyIntegration.company_id == company_id)
    )
    connections = result.scalars().unique().all()

    return [_to_health_item(ci) for ci in connections]


@router.post("/integrations/{connection_id}/reset-failures")
async def reset_integration_failures(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(deps.get_current_user),  # TODO: Add HQ admin role check
) -> dict:
    """
    Reset consecutive failure count for an integration (HQ admin action).
    Used after manual investigation/fix.
    """
    result = await db.execute(
        select(CompanyIntegration).where(CompanyIntegration.id == connection_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        return {"success": False, "message": "Integration connection not found"}

    connection.consecutive_failures = 0
    connection.last_error_message = None
    if connection.status == "error":
        connection.status = "active"

    await db.commit()

    return {"success": True, "message": "Failure count reset successfully"}

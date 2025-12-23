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
from app.schemas import billing as billing_schemas
from app.services.billing import BillingService

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
    _current_user=Depends(deps.require_role("HQ_ADMIN")),
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
    _current_user=Depends(deps.require_role("HQ_ADMIN")),
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
    _current_user=Depends(deps.require_role("HQ_ADMIN")),
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
    _current_user=Depends(deps.require_role("HQ_ADMIN")),
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


# ==================== HQ Billing Management ====================


@router.get("/billing/all-subscriptions")
async def get_all_subscriptions(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(deps.require_role("HQ_ADMIN")),
    status: Optional[str] = Query(None, description="Filter by subscription status"),
    subscription_type: Optional[str] = Query(None, description="Filter by type (self_serve or contract)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """
    HQ Admin: Get all tenant subscriptions with billing data
    """
    from app.models.billing import Subscription

    query = select(Subscription).options(joinedload(Subscription.company), joinedload(Subscription.add_ons))

    if status:
        query = query.where(Subscription.status == status)
    if subscription_type:
        query = query.where(Subscription.subscription_type == subscription_type)

    query = query.order_by(Subscription.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    subscriptions = result.scalars().unique().all()

    # Get total count
    count_query = select(func.count(Subscription.id))
    if status:
        count_query = count_query.where(Subscription.status == status)
    if subscription_type:
        count_query = count_query.where(Subscription.subscription_type == subscription_type)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Calculate revenue metrics
    total_mrr = sum(float(sub.total_monthly_cost) for sub in subscriptions if sub.status == "active")
    trialing_count = sum(1 for sub in subscriptions if sub.status == "trialing")
    active_count = sum(1 for sub in subscriptions if sub.status == "active")
    unpaid_count = sum(1 for sub in subscriptions if sub.status == "unpaid")

    return {
        "subscriptions": [
            {
                "id": sub.id,
                "company_id": sub.company_id,
                "company_name": sub.company.name if sub.company else None,
                "status": sub.status,
                "subscription_type": sub.subscription_type,
                "billing_cycle": sub.billing_cycle,
                "truck_count": sub.truck_count,
                "total_monthly_cost": float(sub.total_monthly_cost),
                "trial_ends_at": sub.trial_ends_at,
                "trial_days_remaining": sub.trial_days_remaining,
                "active_addons": [
                    {"service": addon.service, "name": addon.name, "cost": float(addon.monthly_cost)}
                    for addon in sub.add_ons
                    if addon.status == "active"
                ],
                "stripe_customer_id": sub.stripe_customer_id,
                "created_at": sub.created_at,
            }
            for sub in subscriptions
        ],
        "total": total,
        "metrics": {
            "total_mrr": total_mrr,
            "trialing_count": trialing_count,
            "active_count": active_count,
            "unpaid_count": unpaid_count,
        },
    }


@router.get("/billing/company/{company_id}", response_model=billing_schemas.BillingData)
async def get_company_billing(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(deps.require_role("HQ_ADMIN")),
) -> billing_schemas.BillingData:
    """
    HQ Admin: Get billing data for a specific company
    """
    service = BillingService(db)
    return await service.get_billing_data(company_id)


@router.patch("/billing/company/{company_id}/subscription-type")
async def update_company_subscription_type(
    company_id: str,
    subscription_type: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(deps.require_role("HQ_ADMIN")),
) -> dict:
    """
    HQ Admin: Change subscription type between self_serve and contract
    """
    from app.models.billing import Subscription

    result = await db.execute(select(Subscription).where(Subscription.company_id == company_id))
    subscription = result.scalar_one_or_none()

    if not subscription:
        return {"success": False, "message": "Subscription not found"}

    if subscription_type not in ["self_serve", "contract"]:
        return {"success": False, "message": "Invalid subscription type"}

    subscription.subscription_type = subscription_type
    subscription.updated_at = datetime.utcnow()

    await db.commit()

    return {
        "success": True,
        "message": f"Subscription type updated to {subscription_type}",
        "subscription": {
            "id": subscription.id,
            "company_id": subscription.company_id,
            "subscription_type": subscription.subscription_type,
        },
    }


@router.post("/billing/company/{company_id}/pause")
async def pause_company_subscription(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(deps.require_role("HQ_ADMIN")),
) -> dict:
    """
    HQ Admin: Pause a company's subscription (for non-payment, abuse, etc.)
    """
    from app.models.billing import Subscription

    result = await db.execute(select(Subscription).where(Subscription.company_id == company_id))
    subscription = result.scalar_one_or_none()

    if not subscription:
        return {"success": False, "message": "Subscription not found"}

    subscription.status = "paused"
    subscription.updated_at = datetime.utcnow()

    await db.commit()

    return {
        "success": True,
        "message": "Subscription paused successfully",
        "subscription_id": subscription.id,
    }


@router.post("/billing/company/{company_id}/unpause")
async def unpause_company_subscription(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(deps.require_role("HQ_ADMIN")),
) -> dict:
    """
    HQ Admin: Unpause a company's subscription
    """
    from app.models.billing import Subscription

    result = await db.execute(select(Subscription).where(Subscription.company_id == company_id))
    subscription = result.scalar_one_or_none()

    if not subscription:
        return {"success": False, "message": "Subscription not found"}

    subscription.status = "active"
    subscription.updated_at = datetime.utcnow()

    await db.commit()

    return {
        "success": True,
        "message": "Subscription unpaused successfully",
        "subscription_id": subscription.id,
    }

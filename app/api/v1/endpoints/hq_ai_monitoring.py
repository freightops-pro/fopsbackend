"""
HQ AI Monitoring Endpoints

Master Spec Module 5: AI usage tracking and anomaly detection
- GET /ai-usage/stats - Get AI usage statistics
- GET /ai-usage/logs - List AI usage logs
- POST /ai-usage/log - Create AI usage log
- GET /ai-anomalies - List anomaly alerts
- POST /ai-anomalies/{id}/resolve - Resolve anomaly alert
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_hq_user
from app.models.hq_user import HQUser
from app.models.hq_ai_anomaly_alert import AnomalyType, AlertSeverity
from app.services import hq_ai_monitoring
from app.schemas.hq_ai_monitoring import (
    AIUsageLogCreate,
    AIUsageLogResponse,
    AIUsageStatsResponse,
    AIAnomalyAlertResponse,
    ResolveAnomalyRequest,
)

router = APIRouter()


@router.get("/ai-usage/stats", response_model=AIUsageStatsResponse)
async def get_ai_usage_stats(
    tenant_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: HQUser = Depends(get_current_hq_user),
):
    """
    Get AI usage statistics.

    Query params:
    - tenant_id: Filter by tenant (optional, admins only)
    - start_date: Filter logs after this date
    - end_date: Filter logs before this date
    """
    # Non-admin users can only see their own tenant stats
    if not current_user.is_superuser and tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Only superusers can view other tenant statistics",
        )

    stats = await hq_ai_monitoring.get_usage_stats(
        db=db,
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
    )

    return stats


@router.get("/ai-usage/logs", response_model=list[AIUsageLogResponse])
async def get_ai_usage_logs(
    tenant_id: Optional[str] = Query(None),
    operation: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: HQUser = Depends(get_current_hq_user),
):
    """
    Get AI usage logs with filters.

    Query params:
    - tenant_id: Filter by tenant (optional, admins only)
    - operation: Filter by operation type
    - model: Filter by AI model
    - start_date: Filter logs after this date
    - end_date: Filter logs before this date
    - limit: Max results (default 100, max 500)
    - offset: Pagination offset
    """
    # Non-admin users can only see their own tenant logs
    if not current_user.is_superuser and tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Only superusers can view other tenant logs",
        )

    logs = await hq_ai_monitoring.get_usage_logs(
        db=db,
        tenant_id=tenant_id,
        operation=operation,
        model=model,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    return logs


@router.post("/ai-usage/log", response_model=AIUsageLogResponse)
async def create_ai_usage_log(
    log_data: AIUsageLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: HQUser = Depends(get_current_hq_user),
):
    """
    Create an AI usage log entry.

    This endpoint should be called by backend services after AI API calls.
    """
    log = await hq_ai_monitoring.log_ai_usage(
        db=db,
        tenant_id=log_data.tenant_id,
        operation=log_data.operation,
        model=log_data.model,
        prompt_tokens=log_data.prompt_tokens,
        completion_tokens=log_data.completion_tokens,
        total_cost=log_data.total_cost,
        latency_ms=log_data.latency_ms,
        user_id=log_data.user_id,
        metadata=log_data.metadata,
    )

    return log


@router.get("/ai-anomalies", response_model=list[AIAnomalyAlertResponse])
async def get_ai_anomalies(
    tenant_id: Optional[str] = Query(None),
    anomaly_type: Optional[AnomalyType] = Query(None),
    severity: Optional[AlertSeverity] = Query(None),
    resolved: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: HQUser = Depends(get_current_hq_user),
):
    """
    Get AI anomaly alerts with filters.

    Query params:
    - tenant_id: Filter by tenant (optional, admins only)
    - anomaly_type: Filter by anomaly type
    - severity: Filter by severity level
    - resolved: Filter by resolution status
    - limit: Max results (default 50, max 200)
    - offset: Pagination offset
    """
    # Non-admin users can only see their own tenant anomalies
    if not current_user.is_superuser and tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Only superusers can view other tenant anomalies",
        )

    anomalies = await hq_ai_monitoring.get_anomalies(
        db=db,
        tenant_id=tenant_id,
        anomaly_type=anomaly_type,
        severity=severity,
        resolved=resolved,
        limit=limit,
        offset=offset,
    )

    return anomalies


@router.post("/ai-anomalies/{anomaly_id}/resolve", response_model=AIAnomalyAlertResponse)
async def resolve_ai_anomaly(
    anomaly_id: str,
    request: ResolveAnomalyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: HQUser = Depends(get_current_hq_user),
):
    """
    Mark an anomaly alert as resolved.

    Args:
        anomaly_id: ID of the anomaly to resolve
        request: Resolution details
    """
    try:
        anomaly = await hq_ai_monitoring.resolve_anomaly(
            db=db,
            anomaly_id=anomaly_id,
            resolved_by=current_user.id,
            resolution_notes=request.resolution_notes,
        )
        return anomaly
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

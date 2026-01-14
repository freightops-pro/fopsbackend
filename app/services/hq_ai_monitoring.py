"""
HQ AI Monitoring Service

Master Spec Module 5: AI usage tracking and anomaly detection
- Logs AI API usage (tokens, cost, latency)
- Detects anomalies in usage patterns
- Provides cost analytics and alerts
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from app.models.hq_ai_usage_log import HQAIUsageLog
from app.models.hq_ai_anomaly_alert import HQAIAnomalyAlert, AnomalyType, AlertSeverity


async def log_ai_usage(
    db: AsyncSession,
    tenant_id: str,
    operation: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_cost: float,
    latency_ms: int,
    user_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> HQAIUsageLog:
    """
    Log an AI API usage event.

    Args:
        db: Database session
        tenant_id: Tenant ID
        operation: Operation type (e.g., "load_matching", "document_parsing")
        model: AI model used (e.g., "gpt-4", "claude-sonnet-4")
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        total_cost: Total cost in USD
        latency_ms: Latency in milliseconds
        user_id: Optional user ID who triggered the operation
        metadata: Optional additional metadata
    """
    log = HQAIUsageLog(
        tenant_id=tenant_id,
        user_id=user_id,
        operation=operation,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        total_cost=total_cost,
        latency_ms=latency_ms,
        metadata=metadata or {},
    )

    db.add(log)
    await db.commit()
    await db.refresh(log)

    # Check for anomalies after logging
    await _check_for_anomalies(db, tenant_id, log)

    return log


async def get_usage_stats(
    db: AsyncSession,
    tenant_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """
    Get AI usage statistics.

    Returns:
        dict: Usage statistics including total tokens, cost, latency, etc.
    """
    query = select(HQAIUsageLog)

    conditions = []
    if tenant_id:
        conditions.append(HQAIUsageLog.tenant_id == tenant_id)
    if start_date:
        conditions.append(HQAIUsageLog.created_at >= start_date)
    if end_date:
        conditions.append(HQAIUsageLog.created_at <= end_date)

    if conditions:
        query = query.where(and_(*conditions))

    result = await db.execute(query)
    logs = result.scalars().all()

    if not logs:
        return {
            "total_requests": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "avg_latency_ms": 0,
            "by_operation": {},
            "by_model": {},
        }

    # Calculate aggregations
    total_requests = len(logs)
    total_tokens = sum(log.total_tokens for log in logs)
    total_cost = sum(log.total_cost for log in logs)
    avg_latency = sum(log.latency_ms for log in logs) / total_requests if total_requests > 0 else 0

    # Group by operation
    by_operation = {}
    for log in logs:
        if log.operation not in by_operation:
            by_operation[log.operation] = {
                "count": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
            }
        by_operation[log.operation]["count"] += 1
        by_operation[log.operation]["total_tokens"] += log.total_tokens
        by_operation[log.operation]["total_cost"] += log.total_cost

    # Group by model
    by_model = {}
    for log in logs:
        if log.model not in by_model:
            by_model[log.model] = {
                "count": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
            }
        by_model[log.model]["count"] += 1
        by_model[log.model]["total_tokens"] += log.total_tokens
        by_model[log.model]["total_cost"] += log.total_cost

    return {
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 2),
        "avg_latency_ms": round(avg_latency, 0),
        "by_operation": by_operation,
        "by_model": by_model,
    }


async def get_usage_logs(
    db: AsyncSession,
    tenant_id: Optional[str] = None,
    operation: Optional[str] = None,
    model: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[HQAIUsageLog]:
    """
    Get AI usage logs with filters.
    """
    query = select(HQAIUsageLog)

    conditions = []
    if tenant_id:
        conditions.append(HQAIUsageLog.tenant_id == tenant_id)
    if operation:
        conditions.append(HQAIUsageLog.operation == operation)
    if model:
        conditions.append(HQAIUsageLog.model == model)
    if start_date:
        conditions.append(HQAIUsageLog.created_at >= start_date)
    if end_date:
        conditions.append(HQAIUsageLog.created_at <= end_date)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(desc(HQAIUsageLog.created_at)).limit(limit).offset(offset)

    result = await db.execute(query)
    return result.scalars().all()


async def get_anomalies(
    db: AsyncSession,
    tenant_id: Optional[str] = None,
    anomaly_type: Optional[AnomalyType] = None,
    severity: Optional[AlertSeverity] = None,
    resolved: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[HQAIAnomalyAlert]:
    """
    Get AI anomaly alerts with filters.
    """
    query = select(HQAIAnomalyAlert)

    conditions = []
    if tenant_id:
        conditions.append(HQAIAnomalyAlert.tenant_id == tenant_id)
    if anomaly_type:
        conditions.append(HQAIAnomalyAlert.anomaly_type == anomaly_type)
    if severity:
        conditions.append(HQAIAnomalyAlert.severity == severity)
    if resolved is not None:
        conditions.append(HQAIAnomalyAlert.is_resolved == resolved)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(desc(HQAIAnomalyAlert.created_at)).limit(limit).offset(offset)

    result = await db.execute(query)
    return result.scalars().all()


async def resolve_anomaly(
    db: AsyncSession,
    anomaly_id: str,
    resolved_by: str,
    resolution_notes: Optional[str] = None,
) -> HQAIAnomalyAlert:
    """
    Mark an anomaly alert as resolved.
    """
    result = await db.execute(
        select(HQAIAnomalyAlert).where(HQAIAnomalyAlert.id == anomaly_id)
    )
    anomaly = result.scalar_one_or_none()

    if not anomaly:
        raise ValueError(f"Anomaly {anomaly_id} not found")

    anomaly.is_resolved = True
    anomaly.resolved_at = datetime.utcnow()
    anomaly.resolved_by = resolved_by
    if resolution_notes:
        anomaly.metadata = anomaly.metadata or {}
        anomaly.metadata["resolution_notes"] = resolution_notes

    await db.commit()
    await db.refresh(anomaly)

    return anomaly


async def _check_for_anomalies(
    db: AsyncSession,
    tenant_id: str,
    current_log: HQAIUsageLog,
) -> None:
    """
    Check for anomalies based on current usage log.

    Detects:
    - High cost (single request > $5)
    - High latency (> 30 seconds)
    - Unusual spike (5x average in last hour)
    """
    # High cost detection
    if current_log.total_cost > 5.0:
        await _create_anomaly_alert(
            db=db,
            tenant_id=tenant_id,
            anomaly_type=AnomalyType.HIGH_COST,
            severity=AlertSeverity.HIGH if current_log.total_cost > 10.0 else AlertSeverity.MEDIUM,
            message=f"High cost detected: ${current_log.total_cost:.2f} for operation {current_log.operation}",
            metadata={
                "log_id": current_log.id,
                "operation": current_log.operation,
                "cost": current_log.total_cost,
                "model": current_log.model,
            },
        )

    # High latency detection
    if current_log.latency_ms > 30000:
        await _create_anomaly_alert(
            db=db,
            tenant_id=tenant_id,
            anomaly_type=AnomalyType.HIGH_LATENCY,
            severity=AlertSeverity.MEDIUM,
            message=f"High latency detected: {current_log.latency_ms}ms for operation {current_log.operation}",
            metadata={
                "log_id": current_log.id,
                "operation": current_log.operation,
                "latency_ms": current_log.latency_ms,
                "model": current_log.model,
            },
        )

    # Unusual spike detection - check last hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    result = await db.execute(
        select(func.avg(HQAIUsageLog.total_tokens))
        .where(
            and_(
                HQAIUsageLog.tenant_id == tenant_id,
                HQAIUsageLog.operation == current_log.operation,
                HQAIUsageLog.created_at >= one_hour_ago,
                HQAIUsageLog.id != current_log.id,  # Exclude current log
            )
        )
    )
    avg_tokens = result.scalar() or 0

    if avg_tokens > 0 and current_log.total_tokens > (avg_tokens * 5):
        await _create_anomaly_alert(
            db=db,
            tenant_id=tenant_id,
            anomaly_type=AnomalyType.UNUSUAL_SPIKE,
            severity=AlertSeverity.MEDIUM,
            message=f"Unusual spike detected: {current_log.total_tokens} tokens (5x average of {int(avg_tokens)})",
            metadata={
                "log_id": current_log.id,
                "operation": current_log.operation,
                "current_tokens": current_log.total_tokens,
                "avg_tokens": int(avg_tokens),
                "spike_factor": round(current_log.total_tokens / avg_tokens, 1),
            },
        )


async def _create_anomaly_alert(
    db: AsyncSession,
    tenant_id: str,
    anomaly_type: AnomalyType,
    severity: AlertSeverity,
    message: str,
    metadata: dict,
) -> HQAIAnomalyAlert:
    """
    Create an anomaly alert.
    """
    # Check if similar alert exists in last hour (avoid spam)
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    result = await db.execute(
        select(HQAIAnomalyAlert)
        .where(
            and_(
                HQAIAnomalyAlert.tenant_id == tenant_id,
                HQAIAnomalyAlert.anomaly_type == anomaly_type,
                HQAIAnomalyAlert.created_at >= one_hour_ago,
                HQAIAnomalyAlert.is_resolved == False,
            )
        )
        .limit(1)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing alert with new occurrence
        existing.metadata = existing.metadata or {}
        existing.metadata["occurrences"] = existing.metadata.get("occurrences", 1) + 1
        existing.metadata["last_occurrence"] = metadata
        await db.commit()
        return existing

    # Create new alert
    alert = HQAIAnomalyAlert(
        tenant_id=tenant_id,
        anomaly_type=anomaly_type,
        severity=severity,
        message=message,
        metadata=metadata,
    )

    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    return alert

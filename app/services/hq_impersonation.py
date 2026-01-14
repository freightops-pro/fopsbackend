"""
HQ Impersonation Service

Master Spec Module 2: Tenant impersonation for support
- Start impersonation session
- End impersonation session
- Get active sessions
- Get impersonation logs
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from app.models.hq_impersonation import HQImpersonationLog


async def start_impersonation(
    db: AsyncSession,
    admin_id: str,
    tenant_id: str,
    reason: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    duration_hours: int = 1,
) -> HQImpersonationLog:
    """
    Start an impersonation session.

    Args:
        db: Database session
        admin_id: HQ admin employee ID
        tenant_id: Tenant to impersonate
        reason: Reason for impersonation (required for audit)
        ip_address: Client IP address
        user_agent: Client user agent
        duration_hours: Session duration in hours (default 1, max 8)

    Returns:
        HQImpersonationLog: Impersonation session record
    """
    # Limit duration to 8 hours max
    duration_hours = min(duration_hours, 8)

    # Generate secure session token
    session_token = secrets.token_urlsafe(32)

    # Create log entry
    log = HQImpersonationLog(
        admin_id=admin_id,
        tenant_id=tenant_id,
        session_token=session_token,
        expires_at=datetime.utcnow() + timedelta(hours=duration_hours),
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(log)
    await db.commit()
    await db.refresh(log)

    return log


async def end_impersonation(
    db: AsyncSession,
    session_token: str,
) -> Optional[HQImpersonationLog]:
    """
    End an impersonation session.

    Args:
        db: Database session
        session_token: Session token to end

    Returns:
        HQImpersonationLog if found, None otherwise
    """
    result = await db.execute(
        select(HQImpersonationLog).where(
            and_(
                HQImpersonationLog.session_token == session_token,
                HQImpersonationLog.ended_at.is_(None),
            )
        )
    )
    log = result.scalar_one_or_none()

    if log:
        log.ended_at = datetime.utcnow()
        await db.commit()
        await db.refresh(log)

    return log


async def get_active_sessions(
    db: AsyncSession,
    admin_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> list[HQImpersonationLog]:
    """
    Get active impersonation sessions.

    Args:
        db: Database session
        admin_id: Filter by admin (optional)
        tenant_id: Filter by tenant (optional)

    Returns:
        List of active impersonation sessions
    """
    query = select(HQImpersonationLog).where(
        and_(
            HQImpersonationLog.ended_at.is_(None),
            HQImpersonationLog.expires_at > datetime.utcnow(),
        )
    )

    conditions = []
    if admin_id:
        conditions.append(HQImpersonationLog.admin_id == admin_id)
    if tenant_id:
        conditions.append(HQImpersonationLog.tenant_id == tenant_id)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(desc(HQImpersonationLog.started_at))

    result = await db.execute(query)
    return result.scalars().all()


async def get_impersonation_logs(
    db: AsyncSession,
    admin_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[HQImpersonationLog]:
    """
    Get impersonation logs with filters.

    Args:
        db: Database session
        admin_id: Filter by admin (optional)
        tenant_id: Filter by tenant (optional)
        start_date: Filter logs after this date
        end_date: Filter logs before this date
        limit: Max results
        offset: Pagination offset

    Returns:
        List of impersonation logs
    """
    query = select(HQImpersonationLog)

    conditions = []
    if admin_id:
        conditions.append(HQImpersonationLog.admin_id == admin_id)
    if tenant_id:
        conditions.append(HQImpersonationLog.tenant_id == tenant_id)
    if start_date:
        conditions.append(HQImpersonationLog.started_at >= start_date)
    if end_date:
        conditions.append(HQImpersonationLog.started_at <= end_date)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(desc(HQImpersonationLog.started_at)).limit(limit).offset(offset)

    result = await db.execute(query)
    return result.scalars().all()


async def validate_session_token(
    db: AsyncSession,
    session_token: str,
) -> Optional[HQImpersonationLog]:
    """
    Validate an impersonation session token.

    Args:
        db: Database session
        session_token: Token to validate

    Returns:
        HQImpersonationLog if valid and active, None otherwise
    """
    result = await db.execute(
        select(HQImpersonationLog).where(
            and_(
                HQImpersonationLog.session_token == session_token,
                HQImpersonationLog.ended_at.is_(None),
                HQImpersonationLog.expires_at > datetime.utcnow(),
            )
        )
    )
    return result.scalar_one_or_none()

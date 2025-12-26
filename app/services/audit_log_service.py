"""
Audit Log Service for querying and managing audit logs.

Provides methods for:
- Listing audit logs with filtering and pagination
- Exporting audit logs
- Getting summary statistics
- HQ-level cross-tenant audit queries
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from uuid import uuid4

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, LoginAttempt
from app.schemas.audit_log import (
    AuditLogResponse,
    AuditLogFilter,
    AuditLogListResponse,
    AuditLogSummary,
    LoginAttemptResponse,
    LoginAttemptListResponse,
)

logger = logging.getLogger(__name__)


class AuditLogService:
    """Service for managing audit logs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_audit_logs(
        self,
        company_id: Optional[str] = None,
        filters: Optional[AuditLogFilter] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> AuditLogListResponse:
        """
        List audit logs with filtering and pagination.

        Args:
            company_id: Filter by company (None for HQ admin to see all)
            filters: Additional filter criteria
            page: Page number (1-indexed)
            page_size: Number of items per page
        """
        query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))

        # Base company filter (for tenant users)
        if company_id:
            query = query.where(AuditLog.company_id == company_id)
            count_query = count_query.where(AuditLog.company_id == company_id)

        # Apply additional filters
        if filters:
            if filters.event_type:
                query = query.where(AuditLog.event_type == filters.event_type)
                count_query = count_query.where(AuditLog.event_type == filters.event_type)

            if filters.user_id:
                query = query.where(AuditLog.user_id == filters.user_id)
                count_query = count_query.where(AuditLog.user_id == filters.user_id)

            if filters.user_email:
                query = query.where(AuditLog.user_email.ilike(f"%{filters.user_email}%"))
                count_query = count_query.where(AuditLog.user_email.ilike(f"%{filters.user_email}%"))

            if filters.status:
                query = query.where(AuditLog.status == filters.status)
                count_query = count_query.where(AuditLog.status == filters.status)

            if filters.resource_type:
                query = query.where(AuditLog.resource_type == filters.resource_type)
                count_query = count_query.where(AuditLog.resource_type == filters.resource_type)

            if filters.start_date:
                query = query.where(AuditLog.timestamp >= filters.start_date)
                count_query = count_query.where(AuditLog.timestamp >= filters.start_date)

            if filters.end_date:
                query = query.where(AuditLog.timestamp <= filters.end_date)
                count_query = count_query.where(AuditLog.timestamp <= filters.end_date)

            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.where(
                    or_(
                        AuditLog.action.ilike(search_term),
                        AuditLog.user_email.ilike(search_term),
                    )
                )
                count_query = count_query.where(
                    or_(
                        AuditLog.action.ilike(search_term),
                        AuditLog.user_email.ilike(search_term),
                    )
                )

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        query = query.order_by(desc(AuditLog.timestamp)).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        logs = result.scalars().all()

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return AuditLogListResponse(
            items=[AuditLogResponse.model_validate(log) for log in logs],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_audit_log_summary(
        self,
        company_id: Optional[str] = None,
        days: int = 30,
    ) -> AuditLogSummary:
        """
        Get summary statistics for audit logs.

        Args:
            company_id: Filter by company (None for HQ admin)
            days: Number of days to include in summary
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        # Base conditions
        base_condition = AuditLog.timestamp >= cutoff_date
        if company_id:
            base_condition = and_(base_condition, AuditLog.company_id == company_id)

        # Total events
        total_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(base_condition)
        )
        total_events = total_result.scalar() or 0

        # Status counts
        status_counts = await self.db.execute(
            select(AuditLog.status, func.count(AuditLog.id))
            .where(base_condition)
            .group_by(AuditLog.status)
        )
        status_map = {row[0]: row[1] for row in status_counts.fetchall()}

        # Login counts
        login_success = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                and_(base_condition, AuditLog.event_type == "auth.login_success")
            )
        )
        login_failure = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                and_(base_condition, AuditLog.event_type == "auth.login_failure")
            )
        )

        # Recent security events (last 24 hours)
        recent_condition = AuditLog.timestamp >= recent_cutoff
        if company_id:
            recent_condition = and_(recent_condition, AuditLog.company_id == company_id)

        security_events = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                and_(
                    recent_condition,
                    or_(
                        AuditLog.status == "failure",
                        AuditLog.status == "blocked",
                        AuditLog.event_type.like("security.%"),
                    )
                )
            )
        )

        # Top event types
        top_events = await self.db.execute(
            select(AuditLog.event_type, func.count(AuditLog.id).label("count"))
            .where(base_condition)
            .group_by(AuditLog.event_type)
            .order_by(desc("count"))
            .limit(10)
        )

        return AuditLogSummary(
            total_events=total_events,
            success_count=status_map.get("success", 0),
            failure_count=status_map.get("failure", 0),
            blocked_count=status_map.get("blocked", 0),
            login_success_count=login_success.scalar() or 0,
            login_failure_count=login_failure.scalar() or 0,
            recent_security_events=security_events.scalar() or 0,
            top_event_types=[
                {"event_type": row[0], "count": row[1]}
                for row in top_events.fetchall()
            ],
        )

    async def get_login_attempts(
        self,
        identifier: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> LoginAttemptListResponse:
        """Get login attempts, optionally filtered by identifier."""
        query = select(LoginAttempt)
        count_query = select(func.count(LoginAttempt.id))

        if identifier:
            query = query.where(LoginAttempt.identifier == identifier)
            count_query = count_query.where(LoginAttempt.identifier == identifier)

        # Get total
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order_by(desc(LoginAttempt.timestamp)).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        attempts = result.scalars().all()

        return LoginAttemptListResponse(
            items=[LoginAttemptResponse.model_validate(a) for a in attempts],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_audit_log(
        self,
        event_type: str,
        action: str,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        company_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        metadata: Optional[dict] = None,
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """Create a new audit log entry."""
        log = AuditLog(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            user_email=user_email,
            company_id=company_id,
            event_type=event_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            extra_data=metadata,
            error_message=error_message,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def export_audit_logs(
        self,
        company_id: Optional[str] = None,
        filters: Optional[AuditLogFilter] = None,
        format: str = "json",
    ) -> Tuple[List[dict], str]:
        """
        Export audit logs for download.

        Returns tuple of (data, filename).
        """
        # Get all matching logs (no pagination for export)
        query = select(AuditLog)

        if company_id:
            query = query.where(AuditLog.company_id == company_id)

        if filters:
            if filters.start_date:
                query = query.where(AuditLog.timestamp >= filters.start_date)
            if filters.end_date:
                query = query.where(AuditLog.timestamp <= filters.end_date)
            if filters.event_type:
                query = query.where(AuditLog.event_type == filters.event_type)

        query = query.order_by(desc(AuditLog.timestamp)).limit(10000)  # Safety limit

        result = await self.db.execute(query)
        logs = result.scalars().all()

        # Convert to dict format
        data = []
        for log in logs:
            data.append({
                "timestamp": log.timestamp.isoformat(),
                "user_email": log.user_email,
                "event_type": log.event_type,
                "action": log.action,
                "status": log.status,
                "ip_address": log.ip_address,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
            })

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"audit_logs_{timestamp}.{format}"

        return data, filename

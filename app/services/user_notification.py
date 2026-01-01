import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_notification import UserNotification
from app.models.user import User
from app.schemas.user_notification import NotificationCreate, BroadcastNotificationRequest
from app.services.event_dispatcher import emit_event, EventType


class UserNotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_notification(
        self,
        company_id: str,
        payload: NotificationCreate,
    ) -> UserNotification:
        """Create a notification for a specific user or all users in company."""
        notification = UserNotification(
            id=str(uuid.uuid4()),
            company_id=company_id,
            user_id=payload.user_id,
            type=payload.type,
            title=payload.title,
            message=payload.message,
            link=payload.link,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            priority=payload.priority,
            target_roles=payload.target_roles,
            expires_at=payload.expires_at,
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        # Emit WebSocket event for real-time push
        await emit_event(
            EventType.NOTIFICATION_CREATED,
            {
                "id": notification.id,
                "notification_type": notification.type,
                "title": notification.title,
                "message": notification.message,
                "link": notification.link,
                "priority": notification.priority,
                "created_at": notification.created_at.isoformat() if notification.created_at else None,
                "user_id": notification.user_id,
            },
            company_id=company_id,
            target_user_id=payload.user_id,
        )

        return notification

    async def broadcast_notification(
        self,
        company_id: str,
        payload: BroadcastNotificationRequest,
    ) -> UserNotification:
        """Broadcast a notification to all users in a company (optionally filtered by role)."""
        notification = UserNotification(
            id=str(uuid.uuid4()),
            company_id=company_id,
            user_id=None,  # NULL means broadcast
            type=payload.type,
            title=payload.title,
            message=payload.message,
            link=payload.link,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            priority=payload.priority,
            target_roles=payload.target_roles,
            expires_at=payload.expires_at,
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        # Emit WebSocket event for real-time broadcast
        await emit_event(
            EventType.NOTIFICATION_BROADCAST,
            {
                "id": notification.id,
                "notification_type": notification.type,
                "title": notification.title,
                "message": notification.message,
                "link": notification.link,
                "priority": notification.priority,
                "created_at": notification.created_at.isoformat() if notification.created_at else None,
            },
            company_id=company_id,
        )

        return notification

    async def list_notifications(
        self,
        company_id: str,
        user_id: str,
        user_roles: list[str],
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
    ) -> tuple[list[UserNotification], int, int]:
        """
        List notifications for a user.
        Returns: (notifications, total_count, unread_count)
        """
        now = datetime.utcnow()

        # Build filter: notifications for this user OR broadcasts to company
        # Also filter by role if target_roles is set
        base_filter = and_(
            UserNotification.company_id == company_id,
            or_(
                UserNotification.user_id == user_id,
                UserNotification.user_id.is_(None),  # Broadcasts
            ),
            or_(
                UserNotification.expires_at.is_(None),
                UserNotification.expires_at > now,
            ),
        )

        # For role-based filtering, we need to check if any of the user's roles
        # are in the target_roles comma-separated string
        # This is a simplification - in production you might want a separate table
        role_conditions = [UserNotification.target_roles.is_(None)]  # NULL = all roles
        for role in user_roles:
            role_conditions.append(UserNotification.target_roles.contains(role))

        full_filter = and_(base_filter, or_(*role_conditions))

        # Get total count
        count_query = select(func.count()).select_from(UserNotification).where(full_filter)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get unread count
        unread_filter = and_(full_filter, UserNotification.read == False)
        unread_query = select(func.count()).select_from(UserNotification).where(unread_filter)
        unread_result = await self.db.execute(unread_query)
        unread_count = unread_result.scalar() or 0

        # Apply unread_only filter if requested
        query_filter = unread_filter if unread_only else full_filter

        # Get notifications
        query = (
            select(UserNotification)
            .where(query_filter)
            .order_by(UserNotification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(query)
        notifications = list(result.scalars().all())

        return notifications, total, unread_count

    async def get_unread_count(
        self,
        company_id: str,
        user_id: str,
        user_roles: list[str],
    ) -> int:
        """Get just the unread count for a user."""
        now = datetime.utcnow()

        base_filter = and_(
            UserNotification.company_id == company_id,
            or_(
                UserNotification.user_id == user_id,
                UserNotification.user_id.is_(None),
            ),
            or_(
                UserNotification.expires_at.is_(None),
                UserNotification.expires_at > now,
            ),
            UserNotification.read == False,
        )

        role_conditions = [UserNotification.target_roles.is_(None)]
        for role in user_roles:
            role_conditions.append(UserNotification.target_roles.contains(role))

        full_filter = and_(base_filter, or_(*role_conditions))

        query = select(func.count()).select_from(UserNotification).where(full_filter)
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def mark_as_read(
        self,
        company_id: str,
        user_id: str,
        notification_ids: list[str],
    ) -> int:
        """Mark specific notifications as read. Returns count of updated rows."""
        now = datetime.utcnow()

        # Only allow marking notifications the user can see
        stmt = (
            update(UserNotification)
            .where(
                and_(
                    UserNotification.id.in_(notification_ids),
                    UserNotification.company_id == company_id,
                    or_(
                        UserNotification.user_id == user_id,
                        UserNotification.user_id.is_(None),
                    ),
                    UserNotification.read == False,
                )
            )
            .values(read=True, read_at=now)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def mark_all_as_read(
        self,
        company_id: str,
        user_id: str,
    ) -> int:
        """Mark all notifications for a user as read."""
        now = datetime.utcnow()

        stmt = (
            update(UserNotification)
            .where(
                and_(
                    UserNotification.company_id == company_id,
                    or_(
                        UserNotification.user_id == user_id,
                        UserNotification.user_id.is_(None),
                    ),
                    UserNotification.read == False,
                )
            )
            .values(read=True, read_at=now)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def delete_notification(
        self,
        company_id: str,
        notification_id: str,
    ) -> bool:
        """Delete a notification (admin only)."""
        query = select(UserNotification).where(
            and_(
                UserNotification.id == notification_id,
                UserNotification.company_id == company_id,
            )
        )
        result = await self.db.execute(query)
        notification = result.scalar_one_or_none()

        if not notification:
            return False

        await self.db.delete(notification)
        await self.db.commit()
        return True


# Helper functions for creating common notification types

async def create_compliance_alert(
    db: AsyncSession,
    company_id: str,
    title: str,
    message: str,
    entity_type: str,
    entity_id: str,
    link: Optional[str] = None,
    user_id: Optional[str] = None,
) -> UserNotification:
    """Create a compliance-related notification."""
    service = UserNotificationService(db)
    return await service.create_notification(
        company_id=company_id,
        payload=NotificationCreate(
            type="compliance",
            title=title,
            message=message,
            link=link or "/fleet/compliance",
            entity_type=entity_type,
            entity_id=entity_id,
            priority="high",
            user_id=user_id,
        ),
    )


async def create_load_notification(
    db: AsyncSession,
    company_id: str,
    title: str,
    message: str,
    load_id: str,
    link: Optional[str] = None,
    user_id: Optional[str] = None,
    priority: str = "normal",
) -> UserNotification:
    """Create a load-related notification."""
    service = UserNotificationService(db)
    return await service.create_notification(
        company_id=company_id,
        payload=NotificationCreate(
            type="load",
            title=title,
            message=message,
            link=link or "/dispatch/load-manager",
            entity_type="load",
            entity_id=load_id,
            priority=priority,
            user_id=user_id,
        ),
    )


async def create_system_notification(
    db: AsyncSession,
    company_id: str,
    title: str,
    message: str,
    link: Optional[str] = None,
) -> UserNotification:
    """Create a system-wide notification for all users in a company."""
    service = UserNotificationService(db)
    return await service.broadcast_notification(
        company_id=company_id,
        payload=BroadcastNotificationRequest(
            type="system",
            title=title,
            message=message,
            link=link,
            priority="normal",
        ),
    )

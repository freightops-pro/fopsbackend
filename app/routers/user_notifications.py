from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.user_notification import (
    NotificationCreate,
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationResponse,
    NotificationUnreadCount,
    BroadcastNotificationRequest,
)
from app.services.user_notification import UserNotificationService

router = APIRouter()


def _service(db: AsyncSession = Depends(get_db)) -> UserNotificationService:
    return UserNotificationService(db)


def _get_user_roles(user: User) -> list[str]:
    """Extract roles from user. In production, this would query the RBAC system."""
    roles = ["user"]
    if hasattr(user, "is_admin") and user.is_admin:
        roles.append("admin")
    if hasattr(user, "role") and user.role:
        roles.append(user.role)
    return roles


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
    user: User = Depends(get_current_user),
    service: UserNotificationService = Depends(_service),
) -> NotificationListResponse:
    """List notifications for the current user."""
    user_roles = _get_user_roles(user)

    notifications, total, unread_count = await service.list_notifications(
        company_id=user.company_id,
        user_id=user.id,
        user_roles=user_roles,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )

    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=NotificationUnreadCount)
async def get_unread_count(
    user: User = Depends(get_current_user),
    service: UserNotificationService = Depends(_service),
) -> NotificationUnreadCount:
    """Get just the unread notification count (for badge display)."""
    user_roles = _get_user_roles(user)

    count = await service.get_unread_count(
        company_id=user.company_id,
        user_id=user.id,
        user_roles=user_roles,
    )

    return NotificationUnreadCount(unread_count=count)


@router.post("/mark-read")
async def mark_notifications_read(
    payload: NotificationMarkReadRequest,
    user: User = Depends(get_current_user),
    service: UserNotificationService = Depends(_service),
) -> dict:
    """Mark specific notifications as read."""
    updated = await service.mark_as_read(
        company_id=user.company_id,
        user_id=user.id,
        notification_ids=payload.notification_ids,
    )

    return {"updated": updated}


@router.post("/mark-all-read")
async def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    service: UserNotificationService = Depends(_service),
) -> dict:
    """Mark all notifications as read for the current user."""
    updated = await service.mark_all_as_read(
        company_id=user.company_id,
        user_id=user.id,
    )

    return {"updated": updated}


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    payload: NotificationCreate,
    user: User = Depends(get_current_user),
    service: UserNotificationService = Depends(_service),
) -> NotificationResponse:
    """Create a notification (for internal use or admin)."""
    notification = await service.create_notification(
        company_id=user.company_id,
        payload=payload,
    )

    return NotificationResponse.model_validate(notification)


@router.post("/broadcast", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def broadcast_notification(
    payload: BroadcastNotificationRequest,
    user: User = Depends(get_current_user),
    service: UserNotificationService = Depends(_service),
) -> NotificationResponse:
    """Broadcast a notification to all users in the company."""
    notification = await service.broadcast_notification(
        company_id=user.company_id,
        payload=payload,
    )

    return NotificationResponse.model_validate(notification)


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    user: User = Depends(get_current_user),
    service: UserNotificationService = Depends(_service),
) -> dict:
    """Delete a notification (admin only)."""
    deleted = await service.delete_notification(
        company_id=user.company_id,
        notification_id=notification_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return {"deleted": True}

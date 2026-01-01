from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


NotificationType = Literal["load", "compliance", "alert", "system", "dispatch", "billing"]
NotificationPriority = Literal["low", "normal", "high", "urgent"]


class NotificationBase(BaseModel):
    type: NotificationType
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)
    link: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    priority: NotificationPriority = "normal"
    target_roles: Optional[str] = None  # Comma-separated roles
    expires_at: Optional[datetime] = None


class NotificationCreate(NotificationBase):
    """Create a notification for a user or all users in a company."""
    user_id: Optional[str] = None  # NULL = broadcast to all users in company


class NotificationResponse(NotificationBase):
    """Notification response returned from API."""
    id: str
    company_id: str
    user_id: Optional[str]
    read: bool
    read_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Paginated list of notifications."""
    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class NotificationMarkReadRequest(BaseModel):
    """Request to mark notifications as read."""
    notification_ids: list[str]


class NotificationUnreadCount(BaseModel):
    """Just the unread count."""
    unread_count: int


class BroadcastNotificationRequest(NotificationBase):
    """Broadcast a notification to all users (or by role) in a company."""
    pass

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class UserNotification(Base):
    """User-facing notifications for alerts, system events, and updates."""

    __tablename__ = "user_notification"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("user.id"), nullable=True, index=True)  # NULL = all users in company

    # Notification content
    type = Column(String, nullable=False, index=True)  # load, compliance, alert, system, dispatch, billing
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)

    # Optional link to navigate to
    link = Column(String, nullable=True)

    # Related entity (for context)
    entity_type = Column(String, nullable=True)  # load, driver, equipment, invoice, etc.
    entity_id = Column(String, nullable=True)

    # Status
    read = Column(Boolean, nullable=False, default=False)
    read_at = Column(DateTime, nullable=True)

    # Priority/severity
    priority = Column(String, nullable=False, default="normal")  # low, normal, high, urgent

    # Role-based targeting (comma-separated roles, NULL = all roles)
    target_roles = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)  # Auto-dismiss after this time

    # Relationships
    company = relationship("Company")
    user = relationship("User")

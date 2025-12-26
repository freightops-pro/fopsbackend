"""HQ Employee Presence Model.

Tracks online/away/offline status for HQ portal employees
with support for away messages and automatic status detection.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class HQPresence(Base):
    """HQ employee presence status.

    Unlike tenant presence which is channel-scoped, HQ presence is global
    per employee across all channels.
    """
    __tablename__ = "hq_presence"

    id = Column(String, primary_key=True)
    employee_id = Column(
        String,
        ForeignKey("hq_employee.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    status = Column(String, nullable=False, default="offline")  # online, away, offline
    away_message = Column(Text, nullable=True)  # Custom away message
    status_set_manually = Column(Boolean, nullable=False, default=False)  # If true, don't auto-away
    last_activity_at = Column(DateTime, nullable=True)  # Last user activity for idle detection
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationship to employee
    employee = relationship("HQEmployee", backref="presence")

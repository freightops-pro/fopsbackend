"""HQ Lead Activity model for tracking notes, emails, and follow-ups."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Column, String, Text, DateTime, Enum, ForeignKey, Boolean, JSON
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class ActivityType(str, PyEnum):
    """Types of lead activities."""
    NOTE = "note"  # Manual note added by sales rep
    EMAIL_SENT = "email_sent"  # Email sent to lead
    EMAIL_RECEIVED = "email_received"  # Email received from lead
    CALL = "call"  # Phone call logged
    MEETING = "meeting"  # Meeting scheduled/completed
    FOLLOW_UP = "follow_up"  # Follow-up reminder
    STATUS_CHANGE = "status_change"  # Lead status was changed
    AI_ACTION = "ai_action"  # AI performed an action


class FollowUpStatus(str, PyEnum):
    """Status of follow-up reminders."""
    PENDING = "pending"  # Not yet due
    DUE = "due"  # Currently due
    COMPLETED = "completed"  # Follow-up was completed
    SNOOZED = "snoozed"  # Postponed
    CANCELLED = "cancelled"  # No longer needed


class HQLeadActivity(Base):
    """
    Activity log for a lead - tracks all interactions, notes, and follow-ups.

    This is the main timeline/history for a lead, showing all touchpoints.
    """
    __tablename__ = "hq_lead_activities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Which lead this activity belongs to
    lead_id = Column(String(36), ForeignKey("hq_leads.id"), nullable=False, index=True)

    # Activity type
    activity_type = Column(Enum(ActivityType), nullable=False)

    # Activity content
    subject = Column(String(500), nullable=True)  # Email subject or activity title
    content = Column(Text, nullable=True)  # Note content, email body, call notes

    # Email-specific fields
    email_from = Column(String(255), nullable=True)
    email_to = Column(String(255), nullable=True)
    email_cc = Column(Text, nullable=True)  # Comma-separated
    email_message_id = Column(String(255), nullable=True)  # For threading replies
    email_thread_id = Column(String(255), nullable=True)  # Group related emails
    email_status = Column(String(50), nullable=True)  # sent, delivered, opened, bounced

    # Follow-up specific fields
    follow_up_date = Column(DateTime, nullable=True)
    follow_up_status = Column(Enum(FollowUpStatus), nullable=True)
    follow_up_completed_at = Column(DateTime, nullable=True)

    # Call specific fields
    call_duration_seconds = Column(String(50), nullable=True)
    call_outcome = Column(String(100), nullable=True)  # connected, voicemail, no_answer

    # Metadata
    metadata = Column(JSON, nullable=True)  # Additional context (AI analysis, etc.)

    # Who created this activity
    created_by_id = Column(String(36), ForeignKey("hq_employees.id"), nullable=True)

    # Is this pinned/important?
    is_pinned = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lead = relationship("HQLead", back_populates="activities")
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<HQLeadActivity {self.id} - {self.activity_type.value} for lead {self.lead_id}>"


class HQEmailTemplate(Base):
    """
    Reusable email templates for sales outreach.
    """
    __tablename__ = "hq_email_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Template details
    name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)

    # Template type/category
    category = Column(String(100), nullable=True)  # introduction, follow_up, proposal, etc.

    # Who can use this template
    is_global = Column(Boolean, default=True)  # Available to all sales reps
    created_by_id = Column(String(36), ForeignKey("hq_employees.id"), nullable=True)

    # Template variables (placeholders)
    # e.g., ["company_name", "contact_name", "fleet_size"]
    variables = Column(JSON, nullable=True)

    # Usage tracking
    times_used = Column(String(50), default="0")

    # Is active
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<HQEmailTemplate {self.name}>"


class HQEmailConfig(Base):
    """
    Email configuration for sending emails from the CRM.

    Stores SMTP settings or API keys for email providers.
    """
    __tablename__ = "hq_email_config"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Config name
    name = Column(String(255), nullable=False)

    # Provider type
    provider = Column(String(50), nullable=False)  # smtp, sendgrid, mailgun, ses

    # Configuration (encrypted in production)
    config = Column(JSON, nullable=False)
    # For SMTP: {"host": "", "port": 587, "username": "", "password": "", "use_tls": true}
    # For SendGrid: {"api_key": "..."}

    # Sending identity
    from_email = Column(String(255), nullable=False)
    from_name = Column(String(255), nullable=True)
    reply_to = Column(String(255), nullable=True)

    # Is this the default config?
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<HQEmailConfig {self.name} - {self.provider}>"

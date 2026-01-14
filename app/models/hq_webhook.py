"""HQ Webhook Log model for tracking external service webhooks."""

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text, func
import enum

from app.models.base import Base


class WebhookProvider(str, enum.Enum):
    """Master Spec: Webhook source provider."""
    SYNCTERA = "SYNCTERA"
    CHECKHQ = "CHECKHQ"
    STRIPE = "STRIPE"
    PLAID = "PLAID"
    OTHER = "OTHER"


class WebhookStatus(str, enum.Enum):
    """Master Spec: Webhook processing status."""
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    IGNORED = "IGNORED"


class HQWebhookLog(Base):
    """Master Spec Module 3: Webhook event logging for embedded finance providers."""

    __tablename__ = "hq_webhook_log"

    id = Column(String, primary_key=True)

    # Provider identification
    provider = Column(
        Enum(WebhookProvider, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        index=True
    )
    event_id = Column(String, nullable=True, index=True, comment="Provider's unique event ID")
    event_type = Column(String, nullable=False, index=True, comment="e.g., account.created, transaction.posted")

    # Request details
    raw_payload = Column(Text, nullable=False, comment="Full JSON payload received")
    headers = Column(Text, nullable=True, comment="JSON of relevant HTTP headers")
    source_ip = Column(String, nullable=True)

    # Processing status
    status = Column(
        Enum(WebhookStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=WebhookStatus.RECEIVED,
        index=True
    )
    processing_attempts = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    # Verification
    signature_verified = Column(Boolean, nullable=False, default=False)
    verification_method = Column(String, nullable=True, comment="e.g., HMAC-SHA256")

    # Idempotency
    is_duplicate = Column(Boolean, nullable=False, default=False)
    original_webhook_id = Column(String, nullable=True, comment="If duplicate, ID of original webhook")

    # Timestamps
    received_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

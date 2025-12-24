"""HQ Banking Admin models for Synctera fraud alerts and audit logging."""

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Text, JSON, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class FraudAlertSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FraudAlertStatus(str, enum.Enum):
    PENDING = "pending"
    INVESTIGATING = "investigating"
    APPROVED = "approved"
    BLOCKED = "blocked"
    RESOLVED = "resolved"


class HQFraudAlert(Base):
    """
    Fraud alerts from Synctera for HQ admin review.
    These are system-detected alerts, not user-reported fraud.
    """

    __tablename__ = "hq_fraud_alert"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Synctera identifiers
    synctera_alert_id = Column(String, nullable=True, unique=True, index=True)
    transaction_id = Column(String, nullable=True, index=True)
    card_id = Column(String, nullable=True, index=True)
    account_id = Column(String, nullable=True, index=True)

    # Alert details
    alert_type = Column(String, nullable=False)  # large_transaction, velocity, suspicious_activity, etc.
    amount = Column(Numeric(14, 2), nullable=False, default=0)
    description = Column(Text, nullable=True)
    severity = Column(
        String,
        nullable=False,
        default=FraudAlertSeverity.MEDIUM.value
    )

    # Status tracking
    status = Column(
        String,
        nullable=False,
        default=FraudAlertStatus.PENDING.value
    )

    # Resolution
    resolved_by = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company")
    resolver = relationship("HQEmployee", foreign_keys=[resolved_by])


class BankingAuditAction(str, enum.Enum):
    ACCOUNT_FROZEN = "account_frozen"
    ACCOUNT_UNFROZEN = "account_unfrozen"
    KYB_APPROVED = "kyb_approved"
    KYB_REJECTED = "kyb_rejected"
    FRAUD_APPROVED = "fraud_approved"
    FRAUD_BLOCKED = "fraud_blocked"
    CARD_SUSPENDED = "card_suspended"
    CARD_TERMINATED = "card_terminated"
    PAYOUT_INITIATED = "payout_initiated"
    TRANSFER_APPROVED = "transfer_approved"


class HQBankingAuditLog(Base):
    """
    Audit log for all HQ banking admin actions.
    Tracks freeze/unfreeze, fraud review, KYB decisions, etc.
    """

    __tablename__ = "hq_banking_audit_log"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=True, index=True)

    # Action details
    action = Column(String, nullable=False)
    description = Column(Text, nullable=False)

    # Who performed it
    performed_by = Column(String, ForeignKey("hq_employee.id"), nullable=False, index=True)

    # Request context
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    # Additional action data
    action_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    company = relationship("Company")
    performer = relationship("HQEmployee", foreign_keys=[performed_by])

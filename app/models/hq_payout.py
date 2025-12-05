"""HQ Payout model for Stripe Connect payouts to tenants."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class PayoutStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HQPayout(Base):
    """Payouts to tenant Stripe Connect accounts."""

    __tablename__ = "hq_payout"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("hq_tenant.id"), nullable=False, index=True)
    status = Column(
        Enum(PayoutStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=PayoutStatus.PENDING
    )

    # Amount
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String, nullable=False, default="USD")

    # Stripe
    stripe_payout_id = Column(String, nullable=True, unique=True)
    stripe_transfer_id = Column(String, nullable=True)
    stripe_destination_account = Column(String, nullable=True)

    # Details
    description = Column(Text, nullable=True)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)

    # Tracking
    initiated_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    initiated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("HQTenant", back_populates="payouts")
    initiated_by = relationship("HQEmployee", foreign_keys=[initiated_by_id])

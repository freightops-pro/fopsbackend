"""HQ Commission Payout model for affiliate and sales tracking."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class PayoutStatus(str, enum.Enum):
    """Master Spec: Commission payout status."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PAID = "PAID"
    REJECTED = "REJECTED"


class CommissionType(str, enum.Enum):
    """Master Spec: Type of commission."""
    MRR = "MRR"
    SETUP_FEE = "SETUP_FEE"
    FINTECH_REVENUE = "FINTECH_REVENUE"
    REFERRAL_BONUS = "REFERRAL_BONUS"


class HQCommissionPayout(Base):
    """Master Spec Module 4: Commission payouts for agents/affiliates."""

    __tablename__ = "hq_commission_payout"

    id = Column(String, primary_key=True)

    # Agent/Affiliate
    agent_id = Column(String, ForeignKey("hq_employee.id"), nullable=False, index=True)

    # Related entities
    tenant_id = Column(String, ForeignKey("hq_tenant.id"), nullable=True, index=True)
    deal_id = Column(String, ForeignKey("hq_deal.id"), nullable=True, index=True)

    # Commission details
    commission_type = Column(
        Enum(CommissionType, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False
    )
    commission_rate = Column(Numeric(5, 4), nullable=False, comment="Rate applied (e.g., 0.1000 = 10%)")
    base_amount = Column(Numeric(12, 2), nullable=False, comment="Amount commission is calculated on")
    commission_amount = Column(Numeric(12, 2), nullable=False, comment="Final commission amount")

    # Period tracking
    period_start = Column(DateTime, nullable=True, comment="Start of period for MRR/recurring commissions")
    period_end = Column(DateTime, nullable=True, comment="End of period for MRR/recurring commissions")

    # Status tracking
    status = Column(
        Enum(PayoutStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=PayoutStatus.PENDING
    )
    approved_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Payment tracking
    payment_method = Column(String, nullable=True, comment="e.g., ACH, Check, Stripe")
    payment_reference = Column(String, nullable=True, comment="Payment confirmation number")

    # Notes
    notes = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    agent = relationship("HQEmployee", foreign_keys=[agent_id])
    tenant = relationship("HQTenant")
    deal = relationship("HQDeal")
    approved_by = relationship("HQEmployee", foreign_keys=[approved_by_id])

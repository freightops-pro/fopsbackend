"""HQ Commission Record model for tracking commission per deal."""

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class CommissionRecordStatus(str, enum.Enum):
    PENDING = "pending"      # Within 30-day waiting period
    ELIGIBLE = "eligible"    # Past 30 days, eligible for payment
    ACTIVE = "active"        # Actively receiving payments
    CANCELLED = "cancelled"  # Deal cancelled or rep inactive


class HQCommissionRecord(Base):
    """
    Commission earned per deal/contract.
    One record per sales rep per contract.
    Tracks lifetime commission for a subscription.
    """

    __tablename__ = "hq_commission_record"

    id = Column(String, primary_key=True)

    # Links
    sales_rep_id = Column(String, ForeignKey("hq_employee.id"), nullable=False, index=True)
    contract_id = Column(String, ForeignKey("hq_contract.id"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("hq_tenant.id"), nullable=False, index=True)

    # Commission rate snapshot at time of deal
    commission_rate = Column(Numeric(5, 2), nullable=False)

    # MRR at time of deal (base for commission calculation)
    base_mrr = Column(Numeric(10, 2), nullable=False)

    # Status
    status = Column(
        Enum(CommissionRecordStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=CommissionRecordStatus.PENDING
    )

    # Deal timeline
    deal_closed_at = Column(DateTime, nullable=False)  # When contract became active
    eligible_at = Column(DateTime, nullable=False)     # deal_closed_at + 30 days

    # Running totals
    total_paid_amount = Column(Numeric(12, 2), nullable=False, default=0)
    payment_count = Column(String, nullable=False, default="0")

    # Active flag - set to false when rep becomes inactive
    is_active = Column(Boolean, nullable=False, default=True)
    deactivated_at = Column(DateTime, nullable=True)
    deactivated_reason = Column(String, nullable=True)

    # Tracking
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    sales_rep = relationship("HQEmployee", foreign_keys=[sales_rep_id])
    contract = relationship("HQContract", foreign_keys=[contract_id])
    tenant = relationship("HQTenant", foreign_keys=[tenant_id])
    payments = relationship("HQCommissionPayment", back_populates="commission_record", cascade="all, delete-orphan")

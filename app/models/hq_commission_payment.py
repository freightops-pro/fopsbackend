"""HQ Commission Payment model for actual commission payments."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class CommissionPaymentStatus(str, enum.Enum):
    PENDING = "pending"      # Calculated but not yet approved
    APPROVED = "approved"    # Approved for payment
    PAID = "paid"            # Payment completed
    CANCELLED = "cancelled"  # Payment cancelled


class HQCommissionPayment(Base):
    """
    Actual commission payments to sales reps.
    One payment per billing period per commission record.
    """

    __tablename__ = "hq_commission_payment"

    id = Column(String, primary_key=True)

    # Links
    commission_record_id = Column(String, ForeignKey("hq_commission_record.id"), nullable=False, index=True)
    sales_rep_id = Column(String, ForeignKey("hq_employee.id"), nullable=False, index=True)

    # Billing period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Amounts
    mrr_amount = Column(Numeric(10, 2), nullable=False)  # MRR for this period
    commission_rate = Column(Numeric(5, 2), nullable=False)  # Rate at time of payment
    commission_amount = Column(Numeric(10, 2), nullable=False)  # mrr * rate

    # Status
    status = Column(
        Enum(CommissionPaymentStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=CommissionPaymentStatus.PENDING
    )

    # Payment info
    payment_date = Column(DateTime, nullable=True)
    payment_reference = Column(String, nullable=True)  # Check number, transfer ID, etc.
    payment_method = Column(String, nullable=True)  # payroll, direct_deposit, check

    # Approval
    approved_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Tracking
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    commission_record = relationship("HQCommissionRecord", back_populates="payments")
    sales_rep = relationship("HQEmployee", foreign_keys=[sales_rep_id])
    approved_by = relationship("HQEmployee", foreign_keys=[approved_by_id])

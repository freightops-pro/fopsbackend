"""HQ Credit model for credit management with approval workflow."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class CreditType(str, enum.Enum):
    PROMOTIONAL = "promotional"
    SERVICE_ISSUE = "service_issue"
    BILLING_ADJUSTMENT = "billing_adjustment"
    GOODWILL = "goodwill"
    REFERRAL = "referral"


class CreditStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    EXPIRED = "expired"


class HQCredit(Base):
    """Credits issued to tenants with approval workflow."""

    __tablename__ = "hq_credit"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("hq_tenant.id"), nullable=False, index=True)
    credit_type = Column(
        Enum(CreditType, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False
    )
    status = Column(
        Enum(CreditStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=CreditStatus.PENDING
    )

    # Amount
    amount = Column(Numeric(10, 2), nullable=False)
    remaining_amount = Column(Numeric(10, 2), nullable=False)

    # Details
    reason = Column(Text, nullable=False)
    internal_notes = Column(Text, nullable=True)

    # Validity
    expires_at = Column(DateTime, nullable=True)

    # Approval workflow
    requested_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=False)
    approved_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Application
    applied_at = Column(DateTime, nullable=True)
    applied_to_invoice_id = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("HQTenant", back_populates="credits")
    requested_by = relationship("HQEmployee", foreign_keys=[requested_by_id])
    approved_by = relationship("HQEmployee", foreign_keys=[approved_by_id])
    rejected_by = relationship("HQEmployee", foreign_keys=[rejected_by_id])

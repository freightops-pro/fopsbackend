"""HQ Contractor Settlement model for 1099 contractor payments."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class SettlementStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HQContractorSettlement(Base):
    """
    Settlement for 1099 contractors (sales reps).
    Aggregates commission payments, bonuses, reimbursements, and deductions
    into a single payable settlement.
    """

    __tablename__ = "hq_contractor_settlement"

    id = Column(String, primary_key=True)

    # Contractor (sales rep)
    contractor_id = Column(String, ForeignKey("hq_employee.id"), nullable=False, index=True)

    # Settlement period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    payment_date = Column(DateTime, nullable=False)

    # Settlement number (e.g., SET-2024-001)
    settlement_number = Column(String, nullable=False, unique=True)

    # Status
    status = Column(
        Enum(SettlementStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=SettlementStatus.DRAFT
    )

    # Line items stored as JSON
    # Format: [{"type": "commission", "description": "...", "amount": 100.00, ...}, ...]
    items = Column(JSON, nullable=False, default=list)

    # Commission payment IDs included in this settlement
    commission_payment_ids = Column(JSON, nullable=False, default=list)

    # Totals (calculated from items)
    total_commission = Column(Numeric(12, 2), nullable=False, default=0)
    total_bonus = Column(Numeric(12, 2), nullable=False, default=0)
    total_reimbursements = Column(Numeric(12, 2), nullable=False, default=0)
    total_deductions = Column(Numeric(12, 2), nullable=False, default=0)
    net_payment = Column(Numeric(12, 2), nullable=False, default=0)

    # Notes
    notes = Column(Text, nullable=True)

    # Approval
    approved_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Payment
    paid_at = Column(DateTime, nullable=True)
    payment_reference = Column(String, nullable=True)
    payment_method = Column(String, nullable=True)  # check, direct_deposit, wire

    # Tracking
    created_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    contractor = relationship("HQEmployee", foreign_keys=[contractor_id])
    approved_by = relationship("HQEmployee", foreign_keys=[approved_by_id])
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])

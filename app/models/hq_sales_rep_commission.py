"""HQ Sales Rep Commission configuration model."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class CommissionTier(str, enum.Enum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    ENTERPRISE = "enterprise"


class HQSalesRepCommission(Base):
    """Commission rate configuration per sales rep."""

    __tablename__ = "hq_sales_rep_commission"

    id = Column(String, primary_key=True)

    # Sales rep
    sales_rep_id = Column(String, ForeignKey("hq_employee.id"), nullable=False, unique=True, index=True)

    # Commission rate (percentage, e.g., 10.00 for 10%)
    commission_rate = Column(Numeric(5, 2), nullable=False, default=5.00)

    # Tier level
    tier_level = Column(
        Enum(CommissionTier, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=CommissionTier.JUNIOR
    )

    # Validity period
    effective_from = Column(DateTime, nullable=False, server_default=func.now())
    effective_until = Column(DateTime, nullable=True)  # null = indefinite

    # Notes
    notes = Column(Text, nullable=True)

    # Tracking
    created_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    updated_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    sales_rep = relationship("HQEmployee", foreign_keys=[sales_rep_id], backref="commission_config")
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])
    updated_by = relationship("HQEmployee", foreign_keys=[updated_by_id])

"""HQ Contract model for sales/contract management."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class ContractStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    RENEWED = "renewed"


class ContractType(str, enum.Enum):
    STANDARD = "standard"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"
    PILOT = "pilot"


class HQContract(Base):
    """Sales contract management."""

    __tablename__ = "hq_contract"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("hq_tenant.id"), nullable=False, index=True)
    contract_number = Column(String, unique=True, nullable=False)
    contract_type = Column(
        Enum(ContractType, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=ContractType.STANDARD
    )
    status = Column(
        Enum(ContractStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=ContractStatus.DRAFT
    )
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Pricing
    monthly_value = Column(Numeric(10, 2), nullable=False)
    annual_value = Column(Numeric(12, 2), nullable=True)
    setup_fee = Column(Numeric(10, 2), nullable=True, default=0)

    # Terms
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    auto_renew = Column(String, nullable=True, default="false")
    notice_period_days = Column(String, nullable=True, default="30")

    # Custom terms for enterprise
    custom_terms = Column(Text, nullable=True)

    # Tracking
    signed_by_customer = Column(String, nullable=True)
    signed_by_hq = Column(String, nullable=True)
    signed_at = Column(DateTime, nullable=True)

    created_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    approved_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    assigned_sales_rep_id = Column(String, ForeignKey("hq_employee.id"), nullable=True, index=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("HQTenant", back_populates="contracts")
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])
    approved_by = relationship("HQEmployee", foreign_keys=[approved_by_id])
    assigned_sales_rep = relationship("HQEmployee", foreign_keys=[assigned_sales_rep_id])

"""HQ Quote model for sales quote management."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class QuoteStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class HQQuote(Base):
    """Sales quote for enterprise customers."""

    __tablename__ = "hq_quote"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("hq_tenant.id"), nullable=True, index=True)
    quote_number = Column(String, unique=True, nullable=False)
    status = Column(
        Enum(QuoteStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=QuoteStatus.DRAFT
    )

    # Contact info (for prospects not yet tenants)
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_company = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)

    # Quote details
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    tier = Column(String, nullable=False, default="professional")

    # Pricing
    base_monthly_rate = Column(Numeric(10, 2), nullable=False)
    discount_percent = Column(Numeric(5, 2), nullable=True, default=0)
    discount_amount = Column(Numeric(10, 2), nullable=True, default=0)
    final_monthly_rate = Column(Numeric(10, 2), nullable=False)
    setup_fee = Column(Numeric(10, 2), nullable=True, default=0)

    # Add-ons (JSON stored as text for simplicity)
    addons = Column(Text, nullable=True)

    # Validity
    valid_until = Column(DateTime, nullable=True)

    # Tracking
    sent_at = Column(DateTime, nullable=True)
    viewed_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    created_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("HQTenant", back_populates="quotes")
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])

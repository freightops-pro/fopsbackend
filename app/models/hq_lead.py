"""HQ Lead model for sales lead management."""

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class LeadStatus(str, enum.Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    CONVERTED = "converted"


class LeadSource(str, enum.Enum):
    REFERRAL = "referral"
    WEBSITE = "website"
    COLD_CALL = "cold_call"
    PARTNER = "partner"
    TRADE_SHOW = "trade_show"
    LINKEDIN = "linkedin"
    FMCSA = "fmcsa"  # FMCSA Motor Carrier Census import
    OTHER = "other"


class HQLead(Base):
    """Sales lead tracking for enterprise CRM."""

    __tablename__ = "hq_lead"

    id = Column(String, primary_key=True)
    lead_number = Column(String, unique=True, nullable=False, index=True)

    # Company/Contact info
    company_name = Column(String, nullable=False)
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True, index=True)
    contact_phone = Column(String, nullable=True)
    contact_title = Column(String, nullable=True)

    # FMCSA data
    state = Column(String(2), nullable=True, index=True)  # Two-letter state code
    dot_number = Column(String, nullable=True, index=True)  # DOT number
    mc_number = Column(String, nullable=True, index=True)  # MC number
    carrier_type = Column(String, nullable=True)  # Type of carrier operation
    cargo_types = Column(String, nullable=True)  # Types of cargo hauled

    # Lead details
    source = Column(
        Enum(LeadSource, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=LeadSource.OTHER
    )
    status = Column(
        Enum(LeadStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=LeadStatus.NEW
    )

    # Estimated value
    estimated_mrr = Column(Numeric(10, 2), nullable=True)
    estimated_trucks = Column(String, nullable=True)  # e.g., "10-25"
    estimated_drivers = Column(String, nullable=True)

    # Assignment
    assigned_sales_rep_id = Column(String, ForeignKey("hq_employee.id"), nullable=True, index=True)

    # Follow-up
    next_follow_up_date = Column(DateTime, nullable=True)
    last_contacted_at = Column(DateTime, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Conversion tracking
    converted_to_opportunity_id = Column(String, ForeignKey("hq_opportunity.id"), nullable=True)
    converted_at = Column(DateTime, nullable=True)

    # Tracking
    created_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    assigned_sales_rep = relationship("HQEmployee", foreign_keys=[assigned_sales_rep_id])
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])
    converted_to_opportunity = relationship("HQOpportunity", foreign_keys=[converted_to_opportunity_id])
    activities = relationship("HQLeadActivity", back_populates="lead", order_by="HQLeadActivity.created_at.desc()")

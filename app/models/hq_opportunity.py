"""HQ Opportunity model for sales opportunity management."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class OpportunityStage(str, enum.Enum):
    DISCOVERY = "discovery"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class HQOpportunity(Base):
    """Sales opportunity for pipeline management."""

    __tablename__ = "hq_opportunity"

    id = Column(String, primary_key=True)
    opportunity_number = Column(String, unique=True, nullable=False, index=True)

    # Source - from lead or existing tenant
    lead_id = Column(String, ForeignKey("hq_lead.id"), nullable=True, index=True)
    tenant_id = Column(String, ForeignKey("hq_tenant.id"), nullable=True, index=True)

    # Company/Contact info (copied from lead or entered directly)
    company_name = Column(String, nullable=False)
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)

    # Opportunity details
    title = Column(String, nullable=False)  # e.g., "Enterprise Fleet Management"
    description = Column(Text, nullable=True)

    # Stage and probability
    stage = Column(
        Enum(OpportunityStage, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=OpportunityStage.DISCOVERY
    )
    probability = Column(Numeric(5, 2), nullable=True, default=20)  # 0-100%

    # Value
    estimated_mrr = Column(Numeric(10, 2), nullable=False)
    estimated_setup_fee = Column(Numeric(10, 2), nullable=True, default=0)
    estimated_trucks = Column(String, nullable=True)

    # Timeline
    estimated_close_date = Column(DateTime, nullable=True)
    actual_close_date = Column(DateTime, nullable=True)

    # Assignment
    assigned_sales_rep_id = Column(String, ForeignKey("hq_employee.id"), nullable=True, index=True)

    # Conversion tracking
    converted_to_quote_id = Column(String, ForeignKey("hq_quote.id"), nullable=True)
    converted_at = Column(DateTime, nullable=True)

    # Lost deal tracking
    lost_reason = Column(String, nullable=True)
    competitor = Column(String, nullable=True)  # If lost to competitor

    # Notes
    notes = Column(Text, nullable=True)

    # Tracking
    created_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    lead = relationship("HQLead", foreign_keys=[lead_id], backref="opportunities")
    tenant = relationship("HQTenant", foreign_keys=[tenant_id])
    assigned_sales_rep = relationship("HQEmployee", foreign_keys=[assigned_sales_rep_id])
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])
    converted_to_quote = relationship("HQQuote", foreign_keys=[converted_to_quote_id])

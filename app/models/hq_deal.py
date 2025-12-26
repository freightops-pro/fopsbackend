"""HQ Deal model for unified sales pipeline management."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class DealStage(str, enum.Enum):
    """Unified deal pipeline stages."""
    LEAD = "lead"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    DEMO = "demo"
    CLOSING = "closing"
    WON = "won"
    LOST = "lost"


class DealSource(str, enum.Enum):
    """Source of the deal."""
    REFERRAL = "referral"
    WEBSITE = "website"
    COLD_CALL = "cold_call"
    PARTNER = "partner"
    TRADE_SHOW = "trade_show"
    LINKEDIN = "linkedin"
    FMCSA = "fmcsa"
    OTHER = "other"


class HQDeal(Base):
    """Unified deal entity for the sales pipeline.

    Replaces the separate Lead -> Opportunity workflow with a single
    entity that moves through stages from Lead to Won/Lost.
    """

    __tablename__ = "hq_deal"

    id = Column(String, primary_key=True)
    deal_number = Column(String, unique=True, nullable=False, index=True)

    # Company/Contact info
    company_name = Column(String, nullable=False, index=True)
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True, index=True)
    contact_phone = Column(String, nullable=True)
    contact_title = Column(String, nullable=True)

    # Stage and probability
    stage = Column(
        Enum(DealStage, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=DealStage.LEAD,
        index=True
    )
    probability = Column(Numeric(5, 2), nullable=False, default=10)  # 0-100%

    # Value estimates
    estimated_mrr = Column(Numeric(10, 2), nullable=True)
    estimated_setup_fee = Column(Numeric(10, 2), nullable=True, default=0)
    estimated_trucks = Column(String, nullable=True)  # e.g., "10-25"

    # Timeline
    estimated_close_date = Column(DateTime, nullable=True)

    # Source tracking
    source = Column(
        Enum(DealSource, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=DealSource.OTHER
    )

    # Assignment
    assigned_sales_rep_id = Column(String, ForeignKey("hq_employee.id"), nullable=True, index=True)

    # Follow-up tracking
    next_follow_up_date = Column(DateTime, nullable=True)
    last_contacted_at = Column(DateTime, nullable=True)

    # FMCSA/Company data
    dot_number = Column(String, nullable=True, index=True)
    mc_number = Column(String, nullable=True, index=True)
    state = Column(String(2), nullable=True, index=True)
    carrier_type = Column(String, nullable=True)

    # Outcome tracking
    lost_reason = Column(String, nullable=True)
    competitor = Column(String, nullable=True)  # If lost to competitor
    won_at = Column(DateTime, nullable=True)
    lost_at = Column(DateTime, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Audit trail
    created_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    assigned_sales_rep = relationship("HQEmployee", foreign_keys=[assigned_sales_rep_id])
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])
    subscription = relationship("HQSubscription", back_populates="deal", uselist=False)
    activities = relationship("HQDealActivity", back_populates="deal", cascade="all, delete-orphan")


class HQDealActivity(Base):
    """Activity log for deals (calls, emails, meetings, notes)."""

    __tablename__ = "hq_deal_activity"

    id = Column(String, primary_key=True)
    deal_id = Column(String, ForeignKey("hq_deal.id"), nullable=False, index=True)

    activity_type = Column(String, nullable=False)  # call, email, meeting, note, stage_change
    description = Column(Text, nullable=False)

    # For stage changes
    from_stage = Column(String, nullable=True)
    to_stage = Column(String, nullable=True)

    # Audit
    created_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    deal = relationship("HQDeal", back_populates="activities")
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])

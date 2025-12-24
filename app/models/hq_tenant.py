"""HQ Tenant model for managing customer companies."""

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIAL = "trial"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class SubscriptionTier(str, enum.Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class HQTenant(Base):
    """
    HQ-level tenant management.
    Links to Company model for tenant-specific data.
    """

    __tablename__ = "hq_tenant"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), unique=True, nullable=False, index=True)
    status = Column(
        Enum(TenantStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=TenantStatus.TRIAL
    )
    subscription_tier = Column(
        Enum(SubscriptionTier, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=SubscriptionTier.STARTER
    )
    monthly_rate = Column(Numeric(10, 2), nullable=True)
    billing_email = Column(String, nullable=True)
    stripe_customer_id = Column(String, nullable=True, unique=True)
    stripe_subscription_id = Column(String, nullable=True, unique=True)
    trial_ends_at = Column(DateTime, nullable=True)
    subscription_started_at = Column(DateTime, nullable=True)
    current_period_ends_at = Column(DateTime, nullable=True)
    assigned_sales_rep_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company", backref="hq_tenant")
    assigned_sales_rep = relationship("HQEmployee", foreign_keys=[assigned_sales_rep_id])
    contracts = relationship("HQContract", back_populates="tenant", cascade="all, delete-orphan")
    quotes = relationship("HQQuote", back_populates="tenant", cascade="all, delete-orphan")
    credits = relationship("HQCredit", back_populates="tenant", cascade="all, delete-orphan")
    payouts = relationship("HQPayout", back_populates="tenant", cascade="all, delete-orphan")
    customer = relationship("HQCustomer", back_populates="tenant", uselist=False)

"""HQ Subscription model for managing tenant subscriptions."""

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class HQSubscriptionStatus(str, enum.Enum):
    """HQ Subscription status values."""
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"


class HQBillingInterval(str, enum.Enum):
    """HQ Billing interval options."""
    MONTHLY = "monthly"
    ANNUAL = "annual"


class HQSubscription(Base):
    """Subscription record for tenant billing management.

    Created when a deal is won, tracks the ongoing subscription
    relationship with the tenant.
    """

    __tablename__ = "hq_subscription"

    id = Column(String, primary_key=True)
    subscription_number = Column(String, unique=True, nullable=False, index=True)

    # Tenant relationship
    tenant_id = Column(String, ForeignKey("hq_tenant.id"), nullable=False, index=True)

    # Source deal (optional - could be created without a deal)
    deal_id = Column(String, ForeignKey("hq_deal.id"), nullable=True, index=True)

    # Status
    status = Column(
        Enum(HQSubscriptionStatus, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=HQSubscriptionStatus.ACTIVE,
        index=True
    )

    # Billing configuration
    billing_interval = Column(
        Enum(HQBillingInterval, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        default=HQBillingInterval.MONTHLY
    )

    # Pricing
    monthly_rate = Column(Numeric(10, 2), nullable=False)
    annual_rate = Column(Numeric(10, 2), nullable=True)  # Discounted annual rate
    current_mrr = Column(Numeric(10, 2), nullable=False)  # Current monthly recurring revenue

    # Setup fee
    setup_fee = Column(Numeric(10, 2), nullable=True, default=0)
    setup_fee_paid = Column(Boolean, nullable=False, default=False)

    # Trial
    trial_ends_at = Column(DateTime, nullable=True)

    # Lifecycle dates
    started_at = Column(DateTime, nullable=False)
    paused_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(String, nullable=True)
    next_billing_date = Column(DateTime, nullable=True)

    # Usage limits from plan
    truck_limit = Column(String, nullable=True)  # e.g., "1-10", "11-25", "unlimited"
    user_limit = Column(String, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Audit trail
    created_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant = relationship("HQTenant", back_populates="subscription")
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])
    deal = relationship("HQDeal", foreign_keys=[deal_id], back_populates="subscription")
    rate_changes = relationship("HQSubscriptionRateChange", back_populates="subscription", cascade="all, delete-orphan")


class HQSubscriptionRateChange(Base):
    """Track rate changes for a subscription."""

    __tablename__ = "hq_subscription_rate_change"

    id = Column(String, primary_key=True)
    subscription_id = Column(String, ForeignKey("hq_subscription.id"), nullable=False, index=True)

    # Change details
    previous_mrr = Column(Numeric(10, 2), nullable=False)
    new_mrr = Column(Numeric(10, 2), nullable=False)
    reason = Column(String, nullable=True)

    # When the change takes effect
    effective_date = Column(DateTime, nullable=False)

    # Audit
    changed_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    subscription = relationship("HQSubscription", back_populates="rate_changes")
    changed_by = relationship("HQEmployee", foreign_keys=[changed_by_id])

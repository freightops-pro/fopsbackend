"""
Billing and subscription database models for Stripe integration
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class Subscription(Base):
    """
    Tenant subscription to FreightOps
    Synced with Stripe subscription
    """
    __tablename__ = "billing_subscription"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, unique=True, index=True)

    # Subscription details
    status = Column(String, nullable=False, default="trialing")  # trialing, active, past_due, canceled, unpaid, paused
    subscription_type = Column(String, nullable=False, default="self_serve")  # self_serve, contract
    billing_cycle = Column(String, nullable=False, default="monthly")  # monthly, annual

    # Pricing
    truck_count = Column(Integer, nullable=False, default=1)
    base_price_per_truck = Column(Numeric(10, 2), nullable=False, default=49.00)
    total_monthly_cost = Column(Numeric(10, 2), nullable=False, default=0.00)

    # Trial period
    trial_ends_at = Column(DateTime, nullable=True)
    trial_days_remaining = Column(Integer, nullable=True)

    # Billing period
    current_period_start = Column(DateTime, nullable=False, server_default=func.now())
    current_period_end = Column(DateTime, nullable=False, server_default=func.now())

    # Cancellation
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    canceled_at = Column(DateTime, nullable=True)

    # Stripe IDs
    stripe_subscription_id = Column(String, nullable=True, unique=True, index=True)
    stripe_customer_id = Column(String, nullable=True, index=True)

    # Metadata
    metadata_json = Column("metadata", JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company", back_populates="subscription")
    add_ons = relationship("SubscriptionAddOn", back_populates="subscription", cascade="all, delete-orphan")


class SubscriptionAddOn(Base):
    """
    Add-on services for subscriptions (Port Integration, Check Payroll)
    Billed immediately without trial period
    """
    __tablename__ = "billing_subscription_addon"

    id = Column(String, primary_key=True)
    subscription_id = Column(String, ForeignKey("billing_subscription.id"), nullable=False, index=True)

    # Add-on details
    service = Column(String, nullable=False)  # port_integration, check_payroll
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")  # active, inactive, pending

    # Pricing
    monthly_cost = Column(Numeric(10, 2), nullable=False)
    employee_count = Column(Integer, nullable=True)  # For Check Payroll
    per_employee_cost = Column(Numeric(10, 2), nullable=True)  # For Check Payroll

    # No trial for add-ons
    has_trial = Column(Boolean, nullable=False, default=False)

    # Activation
    activated_at = Column(DateTime, nullable=True)

    # Stripe ID
    stripe_subscription_id = Column(String, nullable=True, index=True)

    # Metadata
    metadata_json = Column("metadata", JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    subscription = relationship("Subscription", back_populates="add_ons")


class PaymentMethod(Base):
    """
    Customer payment methods from Stripe
    """
    __tablename__ = "billing_payment_method"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Payment method details
    payment_type = Column(String, nullable=False, default="card")  # card, bank_account

    # Card details (JSON to store brand, last4, exp_month, exp_year)
    card_details = Column(JSON, nullable=True)

    # Default payment method
    is_default = Column(Boolean, nullable=False, default=False)

    # Stripe ID
    stripe_payment_method_id = Column(String, nullable=False, unique=True, index=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company")


class StripeInvoice(Base):
    """
    Invoice records synced from Stripe
    """
    __tablename__ = "billing_stripe_invoice"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Invoice details
    invoice_number = Column(String, nullable=True)
    amount_due = Column(Numeric(10, 2), nullable=False)
    amount_paid = Column(Numeric(10, 2), nullable=False, default=0.00)
    status = Column(String, nullable=False)  # draft, open, paid, void, uncollectible

    # Dates
    invoice_created_at = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)

    # PDF URL
    invoice_pdf = Column(String, nullable=True)

    # Stripe ID
    stripe_invoice_id = Column(String, nullable=False, unique=True, index=True)

    # Line items
    line_items = Column(JSON, nullable=True)

    # Metadata
    metadata_json = Column("metadata", JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company")


class StripeWebhookEvent(Base):
    """
    Log of Stripe webhook events received
    """
    __tablename__ = "billing_stripe_webhook_event"

    id = Column(String, primary_key=True)

    # Event details
    stripe_event_id = Column(String, nullable=False, unique=True, index=True)
    event_type = Column(String, nullable=False, index=True)

    # Payload
    payload = Column(JSON, nullable=False)

    # Processing
    processed = Column(Boolean, nullable=False, default=False)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)

    # Timestamp
    created_at = Column(DateTime, nullable=False, server_default=func.now())

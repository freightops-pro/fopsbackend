"""
Stripe Subscription Models
"""
from sqlalchemy import Column, String, DateTime, Boolean, Text, Numeric, Integer, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.config.db import Base


class StripeCustomer(Base):
    """Stripe customer information linked to companies"""
    __tablename__ = "stripe_customers"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, unique=True)
    stripe_customer_id = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=False)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address_line1 = Column(String, nullable=True)
    address_line2 = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    country = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("Companies", back_populates="stripe_customer")


class SubscriptionPlan(Base):
    """Available subscription plans"""
    __tablename__ = "subscription_plans"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)  # e.g., "Starter", "Professional", "Enterprise"
    stripe_price_id = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    price_monthly = Column(Numeric(10, 2), nullable=False)
    price_yearly = Column(Numeric(10, 2), nullable=True)
    interval = Column(String, nullable=False)  # "month" or "year"
    features = Column(Text, nullable=True)  # JSON string of features
    max_users = Column(Integer, nullable=True)
    max_vehicles = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    is_popular = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CompanySubscription(Base):
    """Company subscription information"""
    __tablename__ = "company_subscriptions"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, unique=True)
    stripe_customer_id = Column(String, nullable=False, index=True)
    stripe_subscription_id = Column(String, nullable=False, unique=True, index=True)
    plan_id = Column(String, ForeignKey("subscription_plans.id"), nullable=False)
    
    status = Column(String, nullable=False)  # active, past_due, canceled, incomplete, etc.
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    canceled_at = Column(DateTime, nullable=True)
    
    # Pricing information
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, nullable=False, default="usd")
    interval = Column(String, nullable=False)  # "month" or "year"
    
    # Trial information
    trial_start = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("Companies", back_populates="subscription")
    plan = relationship("SubscriptionPlan")


class StripeWebhookEvent(Base):
    """Store Stripe webhook events for audit and debugging"""
    __tablename__ = "stripe_webhook_events"

    id = Column(String, primary_key=True, index=True)
    stripe_event_id = Column(String, nullable=False, unique=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    processed = Column(Boolean, default=False)
    processing_error = Column(Text, nullable=True)
    event_data = Column(Text, nullable=True)  # JSON string of the event data
    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)


class PaymentMethod(Base):
    """Company payment methods"""
    __tablename__ = "payment_methods"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    stripe_payment_method_id = Column(String, nullable=False, unique=True, index=True)
    type = Column(String, nullable=False)  # "card", "bank_account", etc.
    is_default = Column(Boolean, default=False)
    
    # Card information (if type is "card")
    card_brand = Column(String, nullable=True)
    card_last4 = Column(String, nullable=True)
    card_exp_month = Column(Integer, nullable=True)
    card_exp_year = Column(Integer, nullable=True)
    
    # Bank account information (if type is "bank_account")
    bank_name = Column(String, nullable=True)
    bank_account_last4 = Column(String, nullable=True)
    bank_account_type = Column(String, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("Companies")


class StripeInvoice(Base):
    """Stripe invoices"""
    __tablename__ = "stripe_invoices"

    id = Column(String, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    stripe_invoice_id = Column(String, nullable=False, unique=True, index=True)
    stripe_subscription_id = Column(String, nullable=True, index=True)
    
    amount_due = Column(Numeric(10, 2), nullable=False)
    amount_paid = Column(Numeric(10, 2), nullable=True)
    amount_remaining = Column(Numeric(10, 2), nullable=True)
    currency = Column(String, nullable=False, default="usd")
    
    status = Column(String, nullable=False)  # draft, open, paid, void, uncollectible
    paid = Column(Boolean, default=False)
    paid_at = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    
    invoice_pdf = Column(String, nullable=True)  # URL to PDF
    hosted_invoice_url = Column(String, nullable=True)  # URL to hosted invoice
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("Companies")

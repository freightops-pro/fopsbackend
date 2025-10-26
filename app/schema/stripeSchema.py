"""
Stripe Subscription Schemas
"""
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List, Dict, Any
from decimal import Decimal


class SubscriptionPlanCreate(BaseModel):
    name: str
    stripe_price_id: str
    description: Optional[str] = None
    price_monthly: Decimal
    price_yearly: Optional[Decimal] = None
    interval: str = "month"
    features: Optional[List[str]] = None
    max_users: Optional[int] = None
    max_vehicles: Optional[int] = None
    is_popular: bool = False
    sort_order: int = 0


class SubscriptionPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_monthly: Optional[Decimal] = None
    price_yearly: Optional[Decimal] = None
    features: Optional[List[str]] = None
    max_users: Optional[int] = None
    max_vehicles: Optional[int] = None
    is_active: Optional[bool] = None
    is_popular: Optional[bool] = None
    sort_order: Optional[int] = None


class SubscriptionPlanResponse(BaseModel):
    id: str
    name: str
    stripe_price_id: str
    description: Optional[str]
    price_monthly: Decimal
    price_yearly: Optional[Decimal]
    interval: str
    features: Optional[List[str]]
    max_users: Optional[int]
    max_vehicles: Optional[int]
    is_active: bool
    is_popular: bool
    sort_order: int
    created_at: datetime

    class Config:
        from_attributes = True


class StripeCustomerCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class StripeCustomerUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class StripeCustomerResponse(BaseModel):
    id: str
    company_id: str
    stripe_customer_id: str
    email: str
    name: Optional[str]
    phone: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]
    country: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CreateSubscriptionRequest(BaseModel):
    plan_id: str
    payment_method_id: Optional[str] = None
    trial_period_days: Optional[int] = None


class UpdateSubscriptionRequest(BaseModel):
    plan_id: Optional[str] = None
    payment_method_id: Optional[str] = None
    cancel_at_period_end: Optional[bool] = None


class CompanySubscriptionResponse(BaseModel):
    id: str
    company_id: str
    stripe_subscription_id: str
    plan_id: str
    status: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool
    canceled_at: Optional[datetime]
    amount: Decimal
    currency: str
    interval: str
    trial_start: Optional[datetime]
    trial_end: Optional[datetime]
    created_at: datetime
    plan: Optional[SubscriptionPlanResponse] = None

    class Config:
        from_attributes = True


class PaymentMethodResponse(BaseModel):
    id: str
    company_id: str
    stripe_payment_method_id: str
    type: str
    is_default: bool
    card_brand: Optional[str]
    card_last4: Optional[str]
    card_exp_month: Optional[int]
    card_exp_year: Optional[int]
    bank_name: Optional[str]
    bank_account_last4: Optional[str]
    bank_account_type: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    id: str
    company_id: str
    stripe_invoice_id: str
    stripe_subscription_id: Optional[str]
    amount_due: Decimal
    amount_paid: Optional[Decimal]
    amount_remaining: Optional[Decimal]
    currency: str
    status: str
    paid: bool
    paid_at: Optional[datetime]
    due_date: Optional[datetime]
    invoice_pdf: Optional[str]
    hosted_invoice_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class StripeSetupIntentResponse(BaseModel):
    client_secret: str
    setup_intent_id: str


class StripeCheckoutSessionResponse(BaseModel):
    session_id: str
    session_url: str


class WebhookEventResponse(BaseModel):
    id: str
    stripe_event_id: str
    event_type: str
    processed: bool
    processing_error: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]

    class Config:
        from_attributes = True


class SubscriptionUsageResponse(BaseModel):
    company_id: str
    current_users: int
    max_users: Optional[int]
    current_vehicles: int
    max_vehicles: Optional[int]
    usage_percentage_users: Optional[float]
    usage_percentage_vehicles: Optional[float]
    plan_name: str
    status: str

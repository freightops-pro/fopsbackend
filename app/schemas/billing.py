"""
Billing and subscription Pydantic schemas
Matches frontend TypeScript types in src/types/billing.ts
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# Subscription status and types
SubscriptionStatus = Literal["trialing", "active", "past_due", "canceled", "unpaid", "paused"]
SubscriptionType = Literal["self_serve", "contract"]
BillingCycle = Literal["monthly", "annual"]
AddOnService = Literal["port_integration", "check_payroll"]


class SubscriptionResponse(BaseModel):
    """Core subscription data"""
    id: str
    status: SubscriptionStatus
    subscription_type: SubscriptionType = Field(alias="type")
    billing_cycle: BillingCycle
    truck_count: int
    base_price_per_truck: float
    total_monthly_cost: float
    trial_ends_at: Optional[datetime] = None
    trial_days_remaining: Optional[int] = None
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    canceled_at: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class AddOnResponse(BaseModel):
    """Add-on subscription"""
    id: str
    service: AddOnService
    name: str
    description: Optional[str] = None
    status: Literal["active", "inactive", "pending"]
    monthly_cost: float
    employee_count: Optional[int] = None
    per_employee_cost: Optional[float] = None
    has_trial: bool
    activated_at: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = None

    model_config = {"from_attributes": True}


class CardDetails(BaseModel):
    """Card payment method details"""
    brand: str
    last4: str
    exp_month: int
    exp_year: int


class PaymentMethodResponse(BaseModel):
    """Payment method"""
    id: str
    payment_type: Literal["card"] = Field(alias="type")
    card: Optional[CardDetails] = None
    is_default: bool
    stripe_payment_method_id: str

    model_config = {"from_attributes": True, "populate_by_name": True}


class InvoiceLineItemResponse(BaseModel):
    """Invoice line item"""
    id: str
    description: str
    amount: float
    quantity: float
    unit_amount: float


class InvoiceResponse(BaseModel):
    """Stripe invoice"""
    id: str
    invoice_number: Optional[str] = Field(alias="number", default=None)
    amount_due: float
    amount_paid: float
    status: Literal["draft", "open", "paid", "void", "uncollectible"]
    invoice_created_at: datetime = Field(alias="created_at")
    due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    invoice_pdf: Optional[str] = None
    stripe_invoice_id: str
    line_items: List[InvoiceLineItemResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True, "populate_by_name": True}


class BillingData(BaseModel):
    """Complete billing data response"""
    subscription: SubscriptionResponse
    add_ons: List[AddOnResponse] = Field(default_factory=list)
    payment_method: Optional[PaymentMethodResponse] = None
    recent_invoices: List[InvoiceResponse] = Field(default_factory=list)
    upcoming_invoice: Optional[InvoiceResponse] = None


# Request schemas
class UpdateSubscriptionRequest(BaseModel):
    """Update subscription request"""
    truck_count: Optional[int] = None
    billing_cycle: Optional[BillingCycle] = None


class ActivateAddOnRequest(BaseModel):
    """Activate add-on request"""
    service: AddOnService
    employee_count: Optional[int] = None  # Required for Check Payroll


class DeactivateAddOnRequest(BaseModel):
    """Deactivate add-on request"""
    cancel_immediately: bool = False


class AddPaymentMethodRequest(BaseModel):
    """Add payment method request"""
    stripe_payment_method_id: str
    set_as_default: bool = False


class CancelSubscriptionRequest(BaseModel):
    """Cancel subscription request"""
    cancel_immediately: bool = False


class CreateCheckoutSessionRequest(BaseModel):
    """Create Stripe Checkout session request"""
    return_url: str
    cancel_url: str


class CreatePortalSessionRequest(BaseModel):
    """Create Stripe Customer Portal session request"""
    return_url: str


class CustomerPortalSession(BaseModel):
    """Stripe Customer Portal session"""
    url: str


class CheckoutSession(BaseModel):
    """Stripe Checkout session"""
    url: str

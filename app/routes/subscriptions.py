"""
Subscription Management Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import stripe

from app.config.db import get_db
from app.config.settings import settings
from app.services.stripe_service import StripeService
from app.schema.stripeSchema import (
    SubscriptionPlanCreate, SubscriptionPlanUpdate, SubscriptionPlanResponse,
    StripeCustomerCreate, StripeCustomerUpdate, StripeCustomerResponse,
    CreateSubscriptionRequest, UpdateSubscriptionRequest, CompanySubscriptionResponse,
    StripeSetupIntentResponse, StripeCheckoutSessionResponse, SubscriptionUsageResponse,
    InvoiceResponse, PaymentMethodResponse
)
from app.models.stripeModels import SubscriptionPlan, StripeCustomer, StripeInvoice, PaymentMethod
from app.models.userModels import Companies
from app.routes.user import get_current_user, verify_token

router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions"])


def get_current_company_id(current_user: dict = Depends(get_current_user)) -> str:
    """Get current user's company ID"""
    if not current_user.get("companyId"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be associated with a company"
        )
    return current_user["companyId"]


# Subscription Plans Management (Admin only)
@router.get("/plans", response_model=List[SubscriptionPlanResponse])
def get_subscription_plans(db: Session = Depends(get_db)):
    """Get all available subscription plans"""
    plans = db.query(SubscriptionPlan).filter(SubscriptionPlan.is_active == True).order_by(SubscriptionPlan.sort_order).all()
    return plans


@router.post("/plans", response_model=SubscriptionPlanResponse)
def create_subscription_plan(
    plan_data: SubscriptionPlanCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new subscription plan (Admin only)"""
    # Check if user is admin (you might want to implement proper admin check)
    if current_user.get("role") not in ["admin", "platform_owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create subscription plans"
        )
    
    # Check if plan with same price ID already exists
    existing_plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.stripe_price_id == plan_data.stripe_price_id
    ).first()
    if existing_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan with this Stripe price ID already exists"
        )
    
    plan = SubscriptionPlan(
        id=f"plan_{plan_data.name.lower().replace(' ', '_')}",
        name=plan_data.name,
        stripe_price_id=plan_data.stripe_price_id,
        description=plan_data.description,
        price_monthly=plan_data.price_monthly,
        price_yearly=plan_data.price_yearly,
        interval=plan_data.interval,
        features=plan_data.features,
        max_users=plan_data.max_users,
        max_vehicles=plan_data.max_vehicles,
        is_popular=plan_data.is_popular,
        sort_order=plan_data.sort_order
    )
    
    db.add(plan)
    db.commit()
    db.refresh(plan)
    
    return plan


@router.put("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
def update_subscription_plan(
    plan_id: str,
    plan_data: SubscriptionPlanUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a subscription plan (Admin only)"""
    if current_user.get("role") not in ["admin", "platform_owner"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update subscription plans"
        )
    
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found"
        )
    
    # Update fields
    for field, value in plan_data.dict(exclude_unset=True).items():
        setattr(plan, field, value)
    
    db.commit()
    db.refresh(plan)
    
    return plan


# Customer Management
@router.post("/customer", response_model=StripeCustomerResponse)
def create_customer(
    customer_data: StripeCustomerCreate,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Create Stripe customer for company"""
    # Check if customer already exists
    existing_customer = db.query(StripeCustomer).filter(
        StripeCustomer.company_id == company_id
    ).first()
    
    if existing_customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stripe customer already exists for this company"
        )
    
    stripe_service = StripeService(db)
    customer = stripe_service.create_customer(company_id, customer_data)
    
    return customer


@router.get("/customer", response_model=StripeCustomerResponse)
def get_customer(
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get company's Stripe customer"""
    stripe_service = StripeService(db)
    customer = stripe_service.get_customer(company_id)
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stripe customer not found"
        )
    
    return customer


@router.put("/customer", response_model=StripeCustomerResponse)
def update_customer(
    customer_data: StripeCustomerUpdate,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Update company's Stripe customer"""
    stripe_service = StripeService(db)
    customer = stripe_service.get_customer(company_id)
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stripe customer not found"
        )
    
    # Update customer in Stripe
    stripe_customer_data = {}
    for field, value in customer_data.dict(exclude_unset=True).items():
        if value is not None:
            stripe_customer_data[field] = value
            setattr(customer, field, value)
    
    if stripe_customer_data:
        stripe.Customer.modify(
            customer.stripe_customer_id,
            **stripe_customer_data
        )
    
    db.commit()
    db.refresh(customer)
    
    return customer


# Subscription Management
@router.post("/subscribe", response_model=CompanySubscriptionResponse)
def create_subscription(
    subscription_data: CreateSubscriptionRequest,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Create subscription for company"""
    stripe_service = StripeService(db)
    subscription = stripe_service.create_subscription(company_id, subscription_data)
    
    return subscription


@router.get("/subscription", response_model=CompanySubscriptionResponse)
def get_subscription(
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get company's current subscription"""
    stripe_service = StripeService(db)
    subscription = stripe_service.get_subscription(company_id)
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found for this company"
        )
    
    return subscription


@router.put("/subscription", response_model=CompanySubscriptionResponse)
def update_subscription(
    update_data: UpdateSubscriptionRequest,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Update company's subscription"""
    stripe_service = StripeService(db)
    subscription = stripe_service.update_subscription(company_id, update_data)
    
    return subscription


@router.post("/cancel")
def cancel_subscription(
    immediate: bool = False,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Cancel company's subscription"""
    stripe_service = StripeService(db)
    subscription = stripe_service.cancel_subscription(company_id, immediate)
    
    return {
        "message": "Subscription canceled successfully",
        "canceled_immediately": immediate,
        "subscription": subscription
    }


# Payment Methods
@router.post("/setup-intent", response_model=StripeSetupIntentResponse)
def create_setup_intent(
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Create setup intent for saving payment methods"""
    stripe_service = StripeService(db)
    setup_intent = stripe_service.create_setup_intent(company_id)
    
    return setup_intent


@router.get("/payment-methods", response_model=List[PaymentMethodResponse])
def get_payment_methods(
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get company's payment methods"""
    payment_methods = db.query(PaymentMethod).filter(
        PaymentMethod.company_id == company_id
    ).all()
    
    return payment_methods


# Checkout Sessions
@router.post("/checkout", response_model=StripeCheckoutSessionResponse)
def create_checkout_session(
    plan_id: str,
    success_url: str,
    cancel_url: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Create Stripe checkout session"""
    stripe_service = StripeService(db)
    checkout_session = stripe_service.create_checkout_session(
        company_id, plan_id, success_url, cancel_url
    )
    
    return checkout_session


# Usage and Analytics
@router.get("/usage", response_model=SubscriptionUsageResponse)
def get_usage_stats(
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get current usage statistics"""
    stripe_service = StripeService(db)
    usage_stats = stripe_service.get_usage_stats(company_id)
    
    if "error" in usage_stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=usage_stats["error"]
        )
    
    return usage_stats


# Invoices
@router.get("/invoices", response_model=List[InvoiceResponse])
def get_invoices(
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get company's invoices"""
    invoices = db.query(StripeInvoice).filter(
        StripeInvoice.company_id == company_id
    ).order_by(StripeInvoice.created_at.desc()).offset(offset).limit(limit).all()
    
    return invoices


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    company_id: str = Depends(get_current_company_id)
):
    """Get specific invoice"""
    invoice = db.query(StripeInvoice).filter(
        StripeInvoice.id == invoice_id,
        StripeInvoice.company_id == company_id
    ).first()
    
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found"
        )
    
    return invoice


# Webhook endpoint
@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )
    
    # Process the event
    stripe_service = StripeService(db)
    success = stripe_service.handle_webhook_event(event)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook event"
        )
    
    return {"status": "success"}

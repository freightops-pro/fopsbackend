from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import stripe
import logging

from app.config.db import get_db
from app.models.userModels import Companies
from app.config.settings import settings
from app.routes.user import verify_token

# Configure Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/api/subscription", tags=["subscription"])
logger = logging.getLogger(__name__)

# Pydantic models
class CreateCheckoutSessionRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str

class CreatePortalSessionRequest(BaseModel):
    return_url: str

class SubscriptionPlan(BaseModel):
    id: str
    name: str
    description: str
    price: int  # in cents
    currency: str
    interval: str  # 'month' or 'year'
    features: list[str]

# Subscription plans configuration
SUBSCRIPTION_PLANS = [
    SubscriptionPlan(
        id="price_starter_monthly",
        name="Starter",
        description="Perfect for small trucking operations",
        price=9900,  # $99/month
        currency="usd",
        interval="month",
        features=[
            "Up to 5 drivers",
            "Up to 10 vehicles",
            "Basic dispatch",
            "Load management",
            "Basic reporting"
        ]
    ),
    SubscriptionPlan(
        id="price_professional_monthly", 
        name="Professional",
        description="Ideal for growing fleets",
        price=19900,  # $199/month
        currency="usd",
        interval="month",
        features=[
            "Up to 25 drivers",
            "Up to 50 vehicles", 
            "Advanced dispatch",
            "Route optimization",
            "Compliance tracking",
            "Advanced reporting",
            "API access",
            "Real-time collaboration",
            "Advanced annotations & comments"
        ]
    ),
    SubscriptionPlan(
        id="price_enterprise_monthly",
        name="Enterprise", 
        description="For large fleet operations",
        price=39900,  # $399/month
        currency="usd",
        interval="month",
        features=[
            "Unlimited drivers",
            "Unlimited vehicles",
            "Full platform access",
            "Custom integrations",
            "Priority support",
            "Custom reporting",
            "Dedicated account manager",
            "Real-time collaboration",
            "Advanced annotations & comments",
            "Internal team messaging",
            "Team chat rooms",
            "Group collaboration tools"
        ]
    )
]

@router.get("/config")
def get_subscription_config():
    """Get Stripe configuration for frontend"""
    return {
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "stripe_enabled": bool(settings.STRIPE_SECRET_KEY)
    }

@router.get("/plans")
def get_subscription_plans():
    """Get available subscription plans"""
    return {"plans": SUBSCRIPTION_PLANS}

@router.get("/current")
def get_current_subscription(
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Get current subscription status for the company"""
    company_id = token.get("companyId") or token.get("companyid")
    if not company_id:
        raise HTTPException(status_code=400, detail="Missing company context")
    
    company = db.query(Companies).filter(Companies.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    subscription_info = {
        "status": company.subscriptionStatus,
        "plan": company.subscriptionPlan,
        "stripe_customer_id": company.stripeCustomerId,
        "has_active_subscription": company.subscriptionStatus == "active"
    }
    
    # If company has Stripe customer ID, get subscription details from Stripe
    if company.stripeCustomerId and settings.STRIPE_SECRET_KEY:
        try:
            # Get customer from Stripe
            customer = stripe.Customer.retrieve(company.stripeCustomerId)
            
            # Get active subscriptions
            subscriptions = stripe.Subscription.list(
                customer=company.stripeCustomerId,
                status="active",
                limit=1
            )
            
            if subscriptions.data:
                subscription = subscriptions.data[0]
                subscription_info.update({
                    "stripe_subscription_id": subscription.id,
                    "current_period_start": subscription.current_period_start,
                    "current_period_end": subscription.current_period_end,
                    "cancel_at_period_end": subscription.cancel_at_period_end,
                    "price_id": subscription.items.data[0].price.id if subscription.items.data else None
                })
        except stripe.StripeError as e:
            logger.error(f"Stripe error getting subscription: {e}")
    
    return subscription_info

@router.post("/create-checkout-session")
def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Create a Stripe checkout session for subscription"""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    company_id = token.get("companyId") or token.get("companyid")
    if not company_id:
        raise HTTPException(status_code=400, detail="Missing company context")
    
    company = db.query(Companies).filter(Companies.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    try:
        # Create or get Stripe customer
        if company.stripeCustomerId:
            customer_id = company.stripeCustomerId
        else:
            customer = stripe.Customer.create(
                email=company.email,
                name=company.name,
                metadata={
                    "company_id": company_id
                }
            )
            customer_id = customer.id
            
            # Update company with Stripe customer ID
            company.stripeCustomerId = customer_id
            db.commit()
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': request.price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                'company_id': company_id
            }
        )
        
        return {"checkout_url": checkout_session.url}
        
    except stripe.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

@router.post("/create-portal-session")
def create_portal_session(
    request: CreatePortalSessionRequest,
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Create a Stripe customer portal session for subscription management"""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    company_id = token.get("companyId") or token.get("companyid")
    if not company_id:
        raise HTTPException(status_code=400, detail="Missing company context")
    
    company = db.query(Companies).filter(Companies.id == company_id).first()
    if not company or not company.stripeCustomerId:
        raise HTTPException(status_code=404, detail="No active subscription found")
    
    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=company.stripeCustomerId,
            return_url=request.return_url,
        )
        
        return {"portal_url": portal_session.url}
        
    except stripe.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create portal session")

@router.post("/webhook")
def stripe_webhook(
    request: Dict[Any, Any],
    db: Session = Depends(get_db)
):
    """Handle Stripe webhook events"""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    try:
        event = request
        
        # Handle the event
        if event['type'] == 'customer.subscription.created':
            subscription = event['data']['object']
            handle_subscription_created(subscription, db)
            
        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            handle_subscription_updated(subscription, db)
            
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            handle_subscription_deleted(subscription, db)
            
        elif event['type'] == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            handle_payment_succeeded(invoice, db)
            
        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            handle_payment_failed(invoice, db)
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

def handle_subscription_created(subscription: Dict[str, Any], db: Session):
    """Handle subscription created event"""
    customer_id = subscription['customer']
    
    # Find company by Stripe customer ID
    company = db.query(Companies).filter(Companies.stripeCustomerId == customer_id).first()
    if company:
        company.subscriptionStatus = "active"
        # Map Stripe price ID to plan name
        price_id = subscription['items']['data'][0]['price']['id']
        for plan in SUBSCRIPTION_PLANS:
            if plan.id == price_id:
                company.subscriptionPlan = plan.name.lower()
                break
        db.commit()

def handle_subscription_updated(subscription: Dict[str, Any], db: Session):
    """Handle subscription updated event"""
    customer_id = subscription['customer']
    status = subscription['status']
    
    company = db.query(Companies).filter(Companies.stripeCustomerId == customer_id).first()
    if company:
        if status == 'active':
            company.subscriptionStatus = "active"
        elif status in ['past_due', 'unpaid']:
            company.subscriptionStatus = "past_due"
        elif status in ['canceled', 'incomplete_expired']:
            company.subscriptionStatus = "canceled"
        
        db.commit()

def handle_subscription_deleted(subscription: Dict[str, Any], db: Session):
    """Handle subscription deleted event"""
    customer_id = subscription['customer']
    
    company = db.query(Companies).filter(Companies.stripeCustomerId == customer_id).first()
    if company:
        company.subscriptionStatus = "canceled"
        db.commit()

def handle_payment_succeeded(invoice: Dict[str, Any], db: Session):
    """Handle successful payment event"""
    customer_id = invoice['customer']
    
    company = db.query(Companies).filter(Companies.stripeCustomerId == customer_id).first()
    if company:
        company.subscriptionStatus = "active"
        db.commit()

def handle_payment_failed(invoice: Dict[str, Any], db: Session):
    """Handle failed payment event"""
    customer_id = invoice['customer']
    
    company = db.query(Companies).filter(Companies.stripeCustomerId == customer_id).first()
    if company:
        company.subscriptionStatus = "past_due"
        db.commit()

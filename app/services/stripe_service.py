"""
Stripe Service for Subscription Management
"""
import stripe
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from decimal import Decimal

from app.config.settings import settings
from app.models.stripeModels import (
    StripeCustomer, SubscriptionPlan, CompanySubscription, 
    PaymentMethod, StripeInvoice, StripeWebhookEvent
)
from app.models.userModels import Companies, Users, Equipment
from app.schema.stripeSchema import (
    StripeCustomerCreate, CreateSubscriptionRequest, 
    UpdateSubscriptionRequest
)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Service for managing Stripe subscriptions and payments"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_customer(self, company_id: str, customer_data: StripeCustomerCreate) -> StripeCustomer:
        """Create a Stripe customer for a company"""
        try:
            # Create customer in Stripe
            stripe_customer = stripe.Customer.create(
                email=customer_data.email,
                name=customer_data.name,
                phone=customer_data.phone,
                address={
                    "line1": customer_data.address_line1,
                    "line2": customer_data.address_line2,
                    "city": customer_data.city,
                    "state": customer_data.state,
                    "postal_code": customer_data.postal_code,
                    "country": customer_data.country,
                } if customer_data.address_line1 else None,
                metadata={
                    "company_id": company_id,
                    "source": "freightops"
                }
            )
            
            # Create customer record in database
            db_customer = StripeCustomer(
                id=f"cus_{company_id}",
                company_id=company_id,
                stripe_customer_id=stripe_customer.id,
                email=customer_data.email,
                name=customer_data.name,
                phone=customer_data.phone,
                address_line1=customer_data.address_line1,
                address_line2=customer_data.address_line2,
                city=customer_data.city,
                state=customer_data.state,
                postal_code=customer_data.postal_code,
                country=customer_data.country,
            )
            
            self.db.add(db_customer)
            self.db.commit()
            self.db.refresh(db_customer)
            
            return db_customer
            
        except stripe.error.StripeError as e:
            self.db.rollback()
            raise Exception(f"Stripe error: {str(e)}")
    
    def get_customer(self, company_id: str) -> Optional[StripeCustomer]:
        """Get Stripe customer by company ID"""
        return self.db.query(StripeCustomer).filter(
            StripeCustomer.company_id == company_id
        ).first()
    
    def create_subscription(
        self, 
        company_id: str, 
        subscription_data: CreateSubscriptionRequest
    ) -> CompanySubscription:
        """Create a subscription for a company"""
        try:
            # Get customer
            customer = self.get_customer(company_id)
            if not customer:
                raise Exception("Stripe customer not found. Please set up billing first.")
            
            # Get plan
            plan = self.db.query(SubscriptionPlan).filter(
                SubscriptionPlan.id == subscription_data.plan_id
            ).first()
            if not plan:
                raise Exception("Subscription plan not found")
            
            # Create subscription in Stripe
            stripe_subscription_data = {
                "customer": customer.stripe_customer_id,
                "items": [{"price": plan.stripe_price_id}],
                "payment_behavior": "default_incomplete",
                "payment_settings": {"save_default_payment_method": "on_subscription"},
                "expand": ["latest_invoice.payment_intent"],
            }
            
            if subscription_data.payment_method_id:
                stripe_subscription_data["default_payment_method"] = subscription_data.payment_method_id
            
            if subscription_data.trial_period_days:
                stripe_subscription_data["trial_period_days"] = subscription_data.trial_period_days
            
            stripe_subscription = stripe.Subscription.create(**stripe_subscription_data)
            
            # Create subscription record in database
            db_subscription = CompanySubscription(
                id=f"sub_{company_id}",
                company_id=company_id,
                stripe_customer_id=customer.stripe_customer_id,
                stripe_subscription_id=stripe_subscription.id,
                plan_id=plan.id,
                status=stripe_subscription.status,
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
                cancel_at_period_end=stripe_subscription.cancel_at_period_end,
                amount=Decimal(str(stripe_subscription.items.data[0].price.unit_amount / 100)),
                currency=stripe_subscription.currency,
                interval=stripe_subscription.items.data[0].price.recurring.interval,
                trial_start=datetime.fromtimestamp(stripe_subscription.trial_start) if stripe_subscription.trial_start else None,
                trial_end=datetime.fromtimestamp(stripe_subscription.trial_end) if stripe_subscription.trial_end else None,
            )
            
            self.db.add(db_subscription)
            
            # Update company subscription info
            company = self.db.query(Companies).filter(Companies.id == company_id).first()
            if company:
                company.subscriptionStatus = stripe_subscription.status
                company.subscriptionPlan = plan.name
                company.stripeCustomerId = customer.stripe_customer_id
            
            self.db.commit()
            self.db.refresh(db_subscription)
            
            return db_subscription
            
        except stripe.error.StripeError as e:
            self.db.rollback()
            raise Exception(f"Stripe error: {str(e)}")
    
    def update_subscription(
        self, 
        company_id: str, 
        update_data: UpdateSubscriptionRequest
    ) -> CompanySubscription:
        """Update a company's subscription"""
        try:
            # Get current subscription
            subscription = self.db.query(CompanySubscription).filter(
                CompanySubscription.company_id == company_id
            ).first()
            if not subscription:
                raise Exception("Subscription not found")
            
            # Update subscription in Stripe
            stripe_update_data = {}
            
            if update_data.plan_id:
                # Get new plan
                new_plan = self.db.query(SubscriptionPlan).filter(
                    SubscriptionPlan.id == update_data.plan_id
                ).first()
                if not new_plan:
                    raise Exception("New subscription plan not found")
                
                # Update subscription items
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    items=[{
                        "id": stripe.Subscription.retrieve(subscription.stripe_subscription_id).items.data[0].id,
                        "price": new_plan.stripe_price_id,
                    }],
                    proration_behavior="create_prorations"
                )
                
                # Update plan in database
                subscription.plan_id = new_plan.id
                
                # Update company subscription plan
                company = self.db.query(Companies).filter(Companies.id == company_id).first()
                if company:
                    company.subscriptionPlan = new_plan.name
            
            if update_data.payment_method_id:
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    default_payment_method=update_data.payment_method_id
                )
            
            if update_data.cancel_at_period_end is not None:
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=update_data.cancel_at_period_end
                )
                subscription.cancel_at_period_end = update_data.cancel_at_period_end
                
                if update_data.cancel_at_period_end:
                    subscription.canceled_at = datetime.utcnow()
            
            # Refresh subscription data from Stripe
            stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            
            subscription.status = stripe_subscription.status
            subscription.current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start)
            subscription.current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end)
            subscription.amount = Decimal(str(stripe_subscription.items.data[0].price.unit_amount / 100))
            subscription.interval = stripe_subscription.items.data[0].price.recurring.interval
            
            self.db.commit()
            self.db.refresh(subscription)
            
            return subscription
            
        except stripe.error.StripeError as e:
            self.db.rollback()
            raise Exception(f"Stripe error: {str(e)}")
    
    def cancel_subscription(self, company_id: str, immediate: bool = False) -> CompanySubscription:
        """Cancel a company's subscription"""
        try:
            subscription = self.db.query(CompanySubscription).filter(
                CompanySubscription.company_id == company_id
            ).first()
            if not subscription:
                raise Exception("Subscription not found")
            
            if immediate:
                # Cancel immediately
                stripe.Subscription.delete(subscription.stripe_subscription_id)
                subscription.status = "canceled"
                subscription.canceled_at = datetime.utcnow()
            else:
                # Cancel at period end
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                subscription.cancel_at_period_end = True
            
            # Update company status
            company = self.db.query(Companies).filter(Companies.id == company_id).first()
            if company:
                company.subscriptionStatus = "canceled" if immediate else "active"
            
            self.db.commit()
            self.db.refresh(subscription)
            
            return subscription
            
        except stripe.error.StripeError as e:
            self.db.rollback()
            raise Exception(f"Stripe error: {str(e)}")
    
    def get_subscription(self, company_id: str) -> Optional[CompanySubscription]:
        """Get company subscription"""
        return self.db.query(CompanySubscription).filter(
            CompanySubscription.company_id == company_id
        ).first()
    
    def create_setup_intent(self, company_id: str) -> Dict[str, str]:
        """Create a setup intent for saving payment methods"""
        try:
            customer = self.get_customer(company_id)
            if not customer:
                raise Exception("Stripe customer not found")
            
            setup_intent = stripe.SetupIntent.create(
                customer=customer.stripe_customer_id,
                payment_method_types=["card"],
                usage="off_session"
            )
            
            return {
                "client_secret": setup_intent.client_secret,
                "setup_intent_id": setup_intent.id
            }
            
        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")
    
    def create_checkout_session(
        self, 
        company_id: str, 
        plan_id: str, 
        success_url: str, 
        cancel_url: str
    ) -> Dict[str, str]:
        """Create a Stripe checkout session"""
        try:
            customer = self.get_customer(company_id)
            plan = self.db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
            
            if not plan:
                raise Exception("Subscription plan not found")
            
            checkout_session = stripe.checkout.Session.create(
                customer=customer.stripe_customer_id if customer else None,
                customer_email=None if customer else None,  # Will be collected in checkout
                payment_method_types=["card"],
                line_items=[{
                    "price": plan.stripe_price_id,
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "company_id": company_id,
                    "plan_id": plan_id
                },
                subscription_data={
                    "metadata": {
                        "company_id": company_id,
                        "plan_id": plan_id
                    }
                }
            )
            
            return {
                "session_id": checkout_session.id,
                "session_url": checkout_session.url
            }
            
        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")
    
    def get_usage_stats(self, company_id: str) -> Dict[str, Any]:
        """Get current usage statistics for a company"""
        # Get current subscription
        subscription = self.get_subscription(company_id)
        if not subscription:
            return {"error": "No active subscription found"}
        
        # Get current usage
        current_users = self.db.query(Users).filter(
            Users.companyid == company_id,
            Users.isactive == True
        ).count()
        
        current_vehicles = self.db.query(Equipment).filter(
            Equipment.companyid == company_id
        ).count()
        
        # Calculate usage percentages
        usage_percentage_users = None
        usage_percentage_vehicles = None
        
        if subscription.plan.max_users:
            usage_percentage_users = (current_users / subscription.plan.max_users) * 100
        
        if subscription.plan.max_vehicles:
            usage_percentage_vehicles = (current_vehicles / subscription.plan.max_vehicles) * 100
        
        return {
            "company_id": company_id,
            "current_users": current_users,
            "max_users": subscription.plan.max_users,
            "current_vehicles": current_vehicles,
            "max_vehicles": subscription.plan.max_vehicles,
            "usage_percentage_users": usage_percentage_users,
            "usage_percentage_vehicles": usage_percentage_vehicles,
            "plan_name": subscription.plan.name,
            "status": subscription.status
        }
    
    def handle_webhook_event(self, event_data: Dict[str, Any]) -> bool:
        """Handle Stripe webhook events"""
        try:
            event_type = event_data.get("type")
            event_id = event_data.get("id")
            
            # Check if we've already processed this event
            existing_event = self.db.query(StripeWebhookEvent).filter(
                StripeWebhookEvent.stripe_event_id == event_id
            ).first()
            
            if existing_event:
                return True  # Already processed
            
            # Store the event
            webhook_event = StripeWebhookEvent(
                id=f"evt_{event_id}",
                stripe_event_id=event_id,
                event_type=event_type,
                event_data=json.dumps(event_data),
                processed=False
            )
            self.db.add(webhook_event)
            
            # Process the event
            success = self._process_webhook_event(event_data)
            
            # Update event status
            webhook_event.processed = success
            webhook_event.processed_at = datetime.utcnow() if success else None
            
            self.db.commit()
            return success
            
        except Exception as e:
            self.db.rollback()
            # Store the error
            if 'webhook_event' in locals():
                webhook_event.processing_error = str(e)
                webhook_event.processed = False
                self.db.commit()
            return False
    
    def _process_webhook_event(self, event_data: Dict[str, Any]) -> bool:
        """Process specific webhook events"""
        event_type = event_data.get("type")
        data = event_data.get("data", {}).get("object", {})
        
        try:
            if event_type == "customer.subscription.created":
                return self._handle_subscription_created(data)
            elif event_type == "customer.subscription.updated":
                return self._handle_subscription_updated(data)
            elif event_type == "customer.subscription.deleted":
                return self._handle_subscription_deleted(data)
            elif event_type == "invoice.payment_succeeded":
                return self._handle_payment_succeeded(data)
            elif event_type == "invoice.payment_failed":
                return self._handle_payment_failed(data)
            elif event_type == "invoice.created":
                return self._handle_invoice_created(data)
            else:
                # Log unhandled event types
                print(f"Unhandled webhook event type: {event_type}")
                return True
                
        except Exception as e:
            print(f"Error processing webhook event {event_type}: {str(e)}")
            return False
    
    def _handle_subscription_created(self, subscription_data: Dict[str, Any]) -> bool:
        """Handle subscription.created webhook"""
        # This should already be handled by our API, but we can sync data here
        return True
    
    def _handle_subscription_updated(self, subscription_data: Dict[str, Any]) -> bool:
        """Handle subscription.updated webhook"""
        stripe_subscription_id = subscription_data.get("id")
        subscription = self.db.query(CompanySubscription).filter(
            CompanySubscription.stripe_subscription_id == stripe_subscription_id
        ).first()
        
        if subscription:
            subscription.status = subscription_data.get("status")
            subscription.current_period_start = datetime.fromtimestamp(subscription_data.get("current_period_start", 0))
            subscription.current_period_end = datetime.fromtimestamp(subscription_data.get("current_period_end", 0))
            subscription.cancel_at_period_end = subscription_data.get("cancel_at_period_end", False)
            
            # Update company status
            company = self.db.query(Companies).filter(Companies.id == subscription.company_id).first()
            if company:
                company.subscriptionStatus = subscription.status
            
            self.db.commit()
        
        return True
    
    def _handle_subscription_deleted(self, subscription_data: Dict[str, Any]) -> bool:
        """Handle subscription.deleted webhook"""
        stripe_subscription_id = subscription_data.get("id")
        subscription = self.db.query(CompanySubscription).filter(
            CompanySubscription.stripe_subscription_id == stripe_subscription_id
        ).first()
        
        if subscription:
            subscription.status = "canceled"
            subscription.canceled_at = datetime.utcnow()
            
            # Update company status
            company = self.db.query(Companies).filter(Companies.id == subscription.company_id).first()
            if company:
                company.subscriptionStatus = "canceled"
            
            self.db.commit()
        
        return True
    
    def _handle_payment_succeeded(self, invoice_data: Dict[str, Any]) -> bool:
        """Handle invoice.payment_succeeded webhook"""
        # Update invoice status and create invoice record
        stripe_invoice_id = invoice_data.get("id")
        stripe_subscription_id = invoice_data.get("subscription")
        
        subscription = self.db.query(CompanySubscription).filter(
            CompanySubscription.stripe_subscription_id == stripe_subscription_id
        ).first()
        
        if subscription:
            # Create or update invoice record
            invoice = self.db.query(StripeInvoice).filter(
                StripeInvoice.stripe_invoice_id == stripe_invoice_id
            ).first()
            
            if not invoice:
                invoice = StripeInvoice(
                    id=f"inv_{stripe_invoice_id}",
                    company_id=subscription.company_id,
                    stripe_invoice_id=stripe_invoice_id,
                    stripe_subscription_id=stripe_subscription_id,
                    amount_due=Decimal(str(invoice_data.get("amount_due", 0) / 100)),
                    amount_paid=Decimal(str(invoice_data.get("amount_paid", 0) / 100)),
                    amount_remaining=Decimal(str(invoice_data.get("amount_remaining", 0) / 100)),
                    currency=invoice_data.get("currency", "usd"),
                    status=invoice_data.get("status"),
                    paid=invoice_data.get("paid", False),
                    paid_at=datetime.fromtimestamp(invoice_data.get("status_transitions", {}).get("paid_at", 0)) if invoice_data.get("paid") else None,
                    due_date=datetime.fromtimestamp(invoice_data.get("due_date", 0)) if invoice_data.get("due_date") else None,
                    invoice_pdf=invoice_data.get("invoice_pdf"),
                    hosted_invoice_url=invoice_data.get("hosted_invoice_url")
                )
                self.db.add(invoice)
            else:
                invoice.status = invoice_data.get("status")
                invoice.paid = invoice_data.get("paid", False)
                invoice.amount_paid = Decimal(str(invoice_data.get("amount_paid", 0) / 100))
                invoice.amount_remaining = Decimal(str(invoice_data.get("amount_remaining", 0) / 100))
            
            self.db.commit()
        
        return True
    
    def _handle_payment_failed(self, invoice_data: Dict[str, Any]) -> bool:
        """Handle invoice.payment_failed webhook"""
        # Handle failed payment - could send notifications, update status, etc.
        return True
    
    def _handle_invoice_created(self, invoice_data: Dict[str, Any]) -> bool:
        """Handle invoice.created webhook"""
        # Create invoice record when invoice is created
        stripe_invoice_id = invoice_data.get("id")
        stripe_subscription_id = invoice_data.get("subscription")
        
        subscription = self.db.query(CompanySubscription).filter(
            CompanySubscription.stripe_subscription_id == stripe_subscription_id
        ).first()
        
        if subscription:
            invoice = StripeInvoice(
                id=f"inv_{stripe_invoice_id}",
                company_id=subscription.company_id,
                stripe_invoice_id=stripe_invoice_id,
                stripe_subscription_id=stripe_subscription_id,
                amount_due=Decimal(str(invoice_data.get("amount_due", 0) / 100)),
                currency=invoice_data.get("currency", "usd"),
                status=invoice_data.get("status"),
                paid=invoice_data.get("paid", False),
                due_date=datetime.fromtimestamp(invoice_data.get("due_date", 0)) if invoice_data.get("due_date") else None,
                invoice_pdf=invoice_data.get("invoice_pdf"),
                hosted_invoice_url=invoice_data.get("hosted_invoice_url")
            )
            self.db.add(invoice)
            self.db.commit()
        
        return True

"""
Billing service for Stripe integration
Handles subscriptions, add-ons, payment methods, and invoices
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.billing import (
    PaymentMethod,
    StripeInvoice,
    Subscription,
    SubscriptionAddOn,
)
from app.schemas import billing as schemas

settings = get_settings()
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.stripe_secret_key


class BillingService:
    """Service for managing billing and Stripe integration"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_billing_data(self, company_id: str) -> schemas.BillingData:
        """Get complete billing data for a company"""
        # Get subscription with add-ons
        subscription = await self._get_or_create_subscription(company_id)

        # Get payment method
        payment_method = await self._get_default_payment_method(company_id)

        # Get recent invoices (last 12 months)
        recent_invoices = await self._get_recent_invoices(company_id, limit=12)

        # Get upcoming invoice (if exists)
        upcoming_invoice = None
        if subscription.stripe_customer_id:
            try:
                upcoming = stripe.Invoice.upcoming(customer=subscription.stripe_customer_id)
                upcoming_invoice = self._stripe_invoice_to_schema(upcoming)
            except stripe.error.StripeError as e:
                logger.warning(f"No upcoming invoice for company {company_id}: {e}")

        return schemas.BillingData(
            subscription=self._subscription_to_schema(subscription),
            add_ons=[self._addon_to_schema(addon) for addon in subscription.add_ons],
            payment_method=self._payment_method_to_schema(payment_method) if payment_method else None,
            recent_invoices=[self._invoice_to_schema(inv) for inv in recent_invoices],
            upcoming_invoice=upcoming_invoice,
        )

    async def update_subscription(
        self,
        company_id: str,
        request: schemas.UpdateSubscriptionRequest,
    ) -> schemas.BillingData:
        """Update subscription (truck count or billing cycle)"""
        subscription = await self._get_subscription(company_id)

        if subscription.subscription_type == "contract":
            raise ValueError("Contract subscriptions cannot be modified via API")

        # Update truck count
        if request.truck_count is not None:
            if request.truck_count < 1:
                raise ValueError("Truck count must be at least 1")
            subscription.truck_count = request.truck_count

        # Update billing cycle
        if request.billing_cycle is not None:
            subscription.billing_cycle = request.billing_cycle
            # Update price per truck based on billing cycle
            subscription.base_price_per_truck = 39.00 if request.billing_cycle == "annual" else 49.00

        # Recalculate total monthly cost
        subscription.total_monthly_cost = self._calculate_total_cost(subscription)

        # Update Stripe subscription if exists
        if subscription.stripe_subscription_id:
            try:
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    items=[
                        {
                            "price_data": {
                                "currency": "usd",
                                "product": settings.stripe_product_id,
                                "recurring": {
                                    "interval": "month" if subscription.billing_cycle == "monthly" else "year"
                                },
                                "unit_amount": int(subscription.base_price_per_truck * 100),
                            },
                            "quantity": subscription.truck_count,
                        }
                    ],
                )
            except stripe.error.StripeError as e:
                logger.error(f"Failed to update Stripe subscription: {e}")
                raise

        subscription.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(subscription)

        return await self.get_billing_data(company_id)

    async def activate_addon(
        self,
        company_id: str,
        request: schemas.ActivateAddOnRequest,
    ) -> schemas.BillingData:
        """
        Activate an add-on service
        Important: Add-ons are charged immediately without trial period
        """
        subscription = await self._get_subscription(company_id)

        if subscription.subscription_type == "contract":
            raise ValueError("Contract subscriptions cannot modify add-ons via API")

        # Check if add-on already exists
        existing = next((a for a in subscription.add_ons if a.service == request.service), None)
        if existing and existing.status == "active":
            raise ValueError(f"Add-on {request.service} is already active")

        # Validate employee count for Check Payroll
        if request.service == "check_payroll" and request.employee_count is None:
            raise ValueError("employee_count is required for Check Payroll add-on")

        # Calculate cost
        monthly_cost = 0.0
        employee_count = None
        per_employee_cost = None

        if request.service == "port_integration":
            monthly_cost = 99.00
            name = "Port Integration"
            description = "Container tracking and port terminal access"
        elif request.service == "check_payroll":
            employee_count = request.employee_count or 0
            per_employee_cost = 6.00
            monthly_cost = 39.00 + (employee_count * per_employee_cost)
            name = "Check Payroll Service"
            description = f"Full-service payroll processing for {employee_count} employees"

        # Create or update add-on
        if existing:
            addon = existing
            addon.status = "active"
            addon.monthly_cost = monthly_cost
            addon.employee_count = employee_count
            addon.per_employee_cost = per_employee_cost
            addon.activated_at = datetime.utcnow()
        else:
            addon = SubscriptionAddOn(
                id=str(uuid.uuid4()),
                subscription_id=subscription.id,
                service=request.service,
                name=name,
                description=description,
                status="active",
                monthly_cost=monthly_cost,
                employee_count=employee_count,
                per_employee_cost=per_employee_cost,
                has_trial=False,
                activated_at=datetime.utcnow(),
            )
            self.db.add(addon)

        # Create Stripe subscription for add-on (billed immediately)
        if subscription.stripe_customer_id:
            try:
                stripe_addon_sub = stripe.Subscription.create(
                    customer=subscription.stripe_customer_id,
                    items=[
                        {
                            "price_data": {
                                "currency": "usd",
                                "product": settings.stripe_addon_products.get(request.service),
                                "recurring": {"interval": "month"},
                                "unit_amount": int(monthly_cost * 100),
                            },
                            "quantity": 1,
                        }
                    ],
                    proration_behavior="create_prorations",  # Prorate for remainder of billing cycle
                    billing_cycle_anchor_config={
                        "month": subscription.current_period_end.month,
                        "day": subscription.current_period_end.day,
                    },
                )
                addon.stripe_subscription_id = stripe_addon_sub.id
            except stripe.error.StripeError as e:
                logger.error(f"Failed to create Stripe add-on subscription: {e}")
                raise

        # Recalculate total cost
        subscription.total_monthly_cost = self._calculate_total_cost(subscription)
        subscription.updated_at = datetime.utcnow()

        await self.db.commit()
        return await self.get_billing_data(company_id)

    async def deactivate_addon(
        self,
        company_id: str,
        service: str,
        cancel_immediately: bool = False,
    ) -> schemas.BillingData:
        """Deactivate an add-on service"""
        subscription = await self._get_subscription(company_id)

        addon = next((a for a in subscription.add_ons if a.service == service), None)
        if not addon:
            raise ValueError(f"Add-on {service} not found")

        if addon.status != "active":
            raise ValueError(f"Add-on {service} is not active")

        # Cancel Stripe subscription
        if addon.stripe_subscription_id:
            try:
                stripe.Subscription.delete(
                    addon.stripe_subscription_id,
                    prorate=True,
                    invoice_now=cancel_immediately,
                )
            except stripe.error.StripeError as e:
                logger.error(f"Failed to cancel Stripe add-on subscription: {e}")
                raise

        # Update add-on status
        addon.status = "inactive"
        addon.updated_at = datetime.utcnow()

        # Recalculate total cost
        subscription.total_monthly_cost = self._calculate_total_cost(subscription)
        subscription.updated_at = datetime.utcnow()

        await self.db.commit()
        return await self.get_billing_data(company_id)

    async def create_customer_portal_session(
        self,
        company_id: str,
        return_url: str,
    ) -> schemas.CustomerPortalSession:
        """Create Stripe Customer Portal session for payment method management"""
        subscription = await self._get_subscription(company_id)

        if not subscription.stripe_customer_id:
            raise ValueError("No Stripe customer found")

        try:
            session = stripe.billing_portal.Session.create(
                customer=subscription.stripe_customer_id,
                return_url=return_url,
            )
            return schemas.CustomerPortalSession(url=session.url)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create customer portal session: {e}")
            raise

    async def create_checkout_session(
        self,
        company_id: str,
        return_url: str,
        cancel_url: str,
    ) -> schemas.CheckoutSession:
        """Create Stripe Checkout session for adding payment method after trial"""
        subscription = await self._get_subscription(company_id)

        if subscription.subscription_type == "contract":
            raise ValueError("Contract subscriptions do not use Checkout")

        if not subscription.stripe_customer_id:
            # Create Stripe customer if doesn't exist
            customer = stripe.Customer.create(metadata={"company_id": company_id})
            subscription.stripe_customer_id = customer.id
            await self.db.commit()

        try:
            session = stripe.checkout.Session.create(
                customer=subscription.stripe_customer_id,
                mode="setup",
                payment_method_types=["card"],
                success_url=return_url,
                cancel_url=cancel_url,
            )
            return schemas.CheckoutSession(url=session.url)
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise

    async def cancel_subscription(
        self,
        company_id: str,
        cancel_immediately: bool = False,
    ) -> schemas.BillingData:
        """Cancel subscription (self-serve only)"""
        subscription = await self._get_subscription(company_id)

        if subscription.subscription_type == "contract":
            raise ValueError("Contract subscriptions cannot be canceled via API")

        if subscription.stripe_subscription_id:
            try:
                if cancel_immediately:
                    stripe.Subscription.delete(subscription.stripe_subscription_id)
                    subscription.status = "canceled"
                    subscription.canceled_at = datetime.utcnow()
                else:
                    stripe.Subscription.modify(
                        subscription.stripe_subscription_id,
                        cancel_at_period_end=True,
                    )
                    subscription.cancel_at_period_end = True
            except stripe.error.StripeError as e:
                logger.error(f"Failed to cancel Stripe subscription: {e}")
                raise

        subscription.updated_at = datetime.utcnow()
        await self.db.commit()
        return await self.get_billing_data(company_id)

    async def reactivate_subscription(self, company_id: str) -> schemas.BillingData:
        """Reactivate a canceled subscription"""
        subscription = await self._get_subscription(company_id)

        if subscription.stripe_subscription_id:
            try:
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=False,
                )
                subscription.cancel_at_period_end = False
                subscription.status = "active"
            except stripe.error.StripeError as e:
                logger.error(f"Failed to reactivate Stripe subscription: {e}")
                raise

        subscription.updated_at = datetime.utcnow()
        await self.db.commit()
        return await self.get_billing_data(company_id)

    # Helper methods
    async def _get_subscription(self, company_id: str) -> Subscription:
        """Get subscription with add-ons"""
        result = await self.db.execute(
            select(Subscription)
            .options(selectinload(Subscription.add_ons))
            .where(Subscription.company_id == company_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            raise ValueError(f"Subscription not found for company {company_id}")
        return subscription

    async def _get_or_create_subscription(self, company_id: str) -> Subscription:
        """Get existing subscription or create trial subscription"""
        subscription = await self.db.execute(
            select(Subscription)
            .options(selectinload(Subscription.add_ons))
            .where(Subscription.company_id == company_id)
        )
        sub = subscription.scalar_one_or_none()

        if not sub:
            # Create new trial subscription
            trial_ends_at = datetime.utcnow() + timedelta(days=14)
            sub = Subscription(
                id=str(uuid.uuid4()),
                company_id=company_id,
                status="trialing",
                subscription_type="self_serve",
                billing_cycle="monthly",
                truck_count=1,
                base_price_per_truck=49.00,
                total_monthly_cost=0.00,  # Free during trial
                trial_ends_at=trial_ends_at,
                trial_days_remaining=14,
                current_period_start=datetime.utcnow(),
                current_period_end=trial_ends_at,
            )
            self.db.add(sub)
            await self.db.commit()
            await self.db.refresh(sub)

        # Update trial days remaining
        if sub.trial_ends_at and sub.status == "trialing":
            days_remaining = (sub.trial_ends_at - datetime.utcnow()).days
            sub.trial_days_remaining = max(0, days_remaining)

        return sub

    async def _get_default_payment_method(self, company_id: str) -> Optional[PaymentMethod]:
        """Get default payment method for company"""
        result = await self.db.execute(
            select(PaymentMethod)
            .where(PaymentMethod.company_id == company_id)
            .where(PaymentMethod.is_default == True)
        )
        return result.scalar_one_or_none()

    async def _get_recent_invoices(self, company_id: str, limit: int = 12) -> List[StripeInvoice]:
        """Get recent invoices for company"""
        result = await self.db.execute(
            select(StripeInvoice)
            .where(StripeInvoice.company_id == company_id)
            .order_by(StripeInvoice.invoice_created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    def _calculate_total_cost(self, subscription: Subscription) -> float:
        """Calculate total monthly cost including add-ons"""
        if subscription.truck_count == 1:
            # Free tier
            base_cost = 0.0
        else:
            base_cost = subscription.truck_count * float(subscription.base_price_per_truck)

        # Add active add-ons
        addon_cost = sum(
            float(addon.monthly_cost) for addon in subscription.add_ons if addon.status == "active"
        )

        return base_cost + addon_cost

    def _subscription_to_schema(self, sub: Subscription) -> schemas.SubscriptionResponse:
        """Convert Subscription model to schema"""
        return schemas.SubscriptionResponse(
            id=sub.id,
            status=sub.status,
            type=sub.subscription_type,
            billing_cycle=sub.billing_cycle,
            truck_count=sub.truck_count,
            base_price_per_truck=float(sub.base_price_per_truck),
            total_monthly_cost=float(sub.total_monthly_cost),
            trial_ends_at=sub.trial_ends_at,
            trial_days_remaining=sub.trial_days_remaining,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            cancel_at_period_end=sub.cancel_at_period_end,
            canceled_at=sub.canceled_at,
            stripe_subscription_id=sub.stripe_subscription_id,
            stripe_customer_id=sub.stripe_customer_id,
        )

    def _addon_to_schema(self, addon: SubscriptionAddOn) -> schemas.AddOnResponse:
        """Convert SubscriptionAddOn model to schema"""
        return schemas.AddOnResponse(
            id=addon.id,
            service=addon.service,
            name=addon.name,
            description=addon.description,
            status=addon.status,
            monthly_cost=float(addon.monthly_cost),
            employee_count=addon.employee_count,
            per_employee_cost=float(addon.per_employee_cost) if addon.per_employee_cost else None,
            has_trial=addon.has_trial,
            activated_at=addon.activated_at,
            stripe_subscription_id=addon.stripe_subscription_id,
        )

    def _payment_method_to_schema(self, pm: PaymentMethod) -> schemas.PaymentMethodResponse:
        """Convert PaymentMethod model to schema"""
        card_details = None
        if pm.card_details:
            card_details = schemas.CardDetails(**pm.card_details)

        return schemas.PaymentMethodResponse(
            id=pm.id,
            type=pm.payment_type,
            card=card_details,
            is_default=pm.is_default,
            stripe_payment_method_id=pm.stripe_payment_method_id,
        )

    def _invoice_to_schema(self, invoice: StripeInvoice) -> schemas.InvoiceResponse:
        """Convert StripeInvoice model to schema"""
        line_items = []
        if invoice.line_items:
            line_items = [schemas.InvoiceLineItemResponse(**item) for item in invoice.line_items]

        return schemas.InvoiceResponse(
            id=invoice.id,
            number=invoice.invoice_number,
            amount_due=float(invoice.amount_due),
            amount_paid=float(invoice.amount_paid),
            status=invoice.status,
            created_at=invoice.invoice_created_at,
            due_date=invoice.due_date,
            paid_at=invoice.paid_at,
            invoice_pdf=invoice.invoice_pdf,
            stripe_invoice_id=invoice.stripe_invoice_id,
            line_items=line_items,
        )

    def _stripe_invoice_to_schema(self, stripe_invoice) -> schemas.InvoiceResponse:
        """Convert Stripe Invoice object to schema"""
        line_items = []
        for line in stripe_invoice.lines.data:
            line_items.append(
                schemas.InvoiceLineItemResponse(
                    id=line.id,
                    description=line.description or "",
                    amount=line.amount / 100,
                    quantity=line.quantity,
                    unit_amount=line.price.unit_amount / 100 if line.price else 0,
                )
            )

        return schemas.InvoiceResponse(
            id=stripe_invoice.id,
            number=stripe_invoice.number,
            amount_due=stripe_invoice.amount_due / 100,
            amount_paid=stripe_invoice.amount_paid / 100,
            status=stripe_invoice.status,
            created_at=datetime.fromtimestamp(stripe_invoice.created),
            due_date=datetime.fromtimestamp(stripe_invoice.due_date) if stripe_invoice.due_date else None,
            paid_at=datetime.fromtimestamp(stripe_invoice.status_transitions.paid_at)
            if stripe_invoice.status_transitions.paid_at
            else None,
            invoice_pdf=stripe_invoice.invoice_pdf,
            stripe_invoice_id=stripe_invoice.id,
            line_items=line_items,
        )

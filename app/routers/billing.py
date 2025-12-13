"""
Billing router for tenant subscription management
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import stripe

from app.api import deps
from app.core.config import get_settings
from app.core.db import get_db
from app.schemas import billing as schemas
from app.services.billing import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])
logger = logging.getLogger(__name__)
settings = get_settings()


@router.get("", response_model=schemas.BillingData)
async def get_billing_data(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> schemas.BillingData:
    """
    Get complete billing data for current tenant
    Includes subscription, add-ons, payment method, and invoices
    """
    try:
        service = BillingService(db)
        return await service.get_billing_data(current_user.company_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get billing data: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get billing data")


@router.patch("/subscription", response_model=schemas.BillingData)
async def update_subscription(
    request: schemas.UpdateSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> schemas.BillingData:
    """
    Update subscription (truck count or billing cycle)
    Only for self-serve subscriptions
    """
    try:
        service = BillingService(db)
        return await service.update_subscription(current_user.company_id, request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update subscription: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update subscription")


@router.post("/preview", response_model=schemas.SubscriptionPreviewResponse)
async def preview_subscription_changes(
    request: schemas.SubscriptionPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> schemas.SubscriptionPreviewResponse:
    """
    Preview subscription cost changes before committing
    Shows current cost, new cost, and immediate prorated charge
    """
    try:
        service = BillingService(db)
        return await service.preview_subscription_changes(current_user.company_id, request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to preview subscription: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to preview subscription")


@router.post("/update-subscription", response_model=schemas.BillingData)
async def bulk_update_subscription(
    request: schemas.BulkSubscriptionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> schemas.BillingData:
    """
    Update subscription with multiple changes at once
    Supports: truck count, billing cycle, add-ons, and payment method in a single transaction
    User will be charged immediately for prorated amounts
    """
    try:
        service = BillingService(db)
        return await service.bulk_update_subscription(current_user.company_id, request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update subscription: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update subscription")


@router.post("/add-ons", response_model=schemas.BillingData)
async def activate_addon(
    request: schemas.ActivateAddOnRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> schemas.BillingData:
    """
    Activate an add-on service
    IMPORTANT: Add-ons are charged immediately without trial period
    """
    try:
        service = BillingService(db)
        return await service.activate_addon(current_user.company_id, request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to activate add-on: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to activate add-on")


@router.delete("/add-ons/{service}", response_model=schemas.BillingData)
async def deactivate_addon(
    service: str,
    request: schemas.DeactivateAddOnRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> schemas.BillingData:
    """
    Deactivate an add-on service
    Can optionally cancel immediately or at period end
    """
    try:
        billing_service = BillingService(db)
        return await billing_service.deactivate_addon(
            current_user.company_id,
            service,
            request.cancel_immediately,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to deactivate add-on: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to deactivate add-on")


@router.post("/portal-session", response_model=schemas.CustomerPortalSession)
async def create_customer_portal_session(
    request: schemas.CreatePortalSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> schemas.CustomerPortalSession:
    """
    Create Stripe Customer Portal session for payment method management
    User will be redirected to Stripe-hosted portal
    """
    try:
        service = BillingService(db)
        return await service.create_customer_portal_session(
            current_user.company_id,
            request.return_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create portal session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session",
        )


@router.post("/checkout-session", response_model=schemas.CheckoutSession)
async def create_checkout_session(
    request: schemas.CreateCheckoutSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> schemas.CheckoutSession:
    """
    Create Stripe Checkout session for adding payment method after trial
    User will be redirected to Stripe Checkout
    """
    try:
        service = BillingService(db)
        return await service.create_checkout_session(
            current_user.company_id,
            request.return_url,
            request.cancel_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        )


@router.post("/subscription/cancel", response_model=schemas.BillingData)
async def cancel_subscription(
    request: schemas.CancelSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> schemas.BillingData:
    """
    Cancel subscription
    Only for self-serve subscriptions
    """
    try:
        service = BillingService(db)
        return await service.cancel_subscription(
            current_user.company_id,
            request.cancel_immediately,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription",
        )


@router.post("/subscription/reactivate", response_model=schemas.BillingData)
async def reactivate_subscription(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
) -> schemas.BillingData:
    """
    Reactivate a canceled subscription
    Only for self-serve subscriptions
    """
    try:
        service = BillingService(db)
        return await service.reactivate_subscription(current_user.company_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reactivate subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate subscription",
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Stripe webhook endpoint for handling subscription lifecycle events
    This endpoint is called by Stripe when subscription events occur
    """
    from app.models.billing import StripeWebhookEvent

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        logger.error("Missing Stripe signature header")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing signature")

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.get_stripe_webhook_secret()
        )
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    # Log webhook event
    webhook_event = StripeWebhookEvent(
        id=str(event.id),
        event_type=event.type,
        event_data=event.data.object,
        processed_at=None,
    )
    db.add(webhook_event)

    try:
        # Handle different event types
        if event.type == "customer.subscription.updated":
            await _handle_subscription_updated(db, event.data.object)
        elif event.type == "customer.subscription.deleted":
            await _handle_subscription_deleted(db, event.data.object)
        elif event.type == "invoice.payment_succeeded":
            await _handle_payment_succeeded(db, event.data.object)
        elif event.type == "invoice.payment_failed":
            await _handle_payment_failed(db, event.data.object)
        elif event.type == "customer.subscription.trial_will_end":
            await _handle_trial_will_end(db, event.data.object)

        # Mark webhook as processed
        webhook_event.processed_at = datetime.utcnow()
        await db.commit()

        return {"status": "success", "event_type": event.type}

    except Exception as e:
        logger.error(f"Error processing webhook {event.type}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        )


# Webhook event handlers
async def _handle_subscription_updated(db: AsyncSession, subscription_data: dict):
    """Handle subscription.updated webhook"""
    from app.models.billing import Subscription
    from sqlalchemy import select

    stripe_sub_id = subscription_data.get("id")
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        logger.warning(f"Subscription not found for Stripe ID: {stripe_sub_id}")
        return

    # Update subscription status
    status_mapping = {
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "unpaid",
        "trialing": "trialing",
    }
    subscription.status = status_mapping.get(subscription_data.get("status"), "active")
    subscription.cancel_at_period_end = subscription_data.get("cancel_at_period_end", False)

    if subscription_data.get("canceled_at"):
        subscription.canceled_at = datetime.fromtimestamp(subscription_data["canceled_at"])

    await db.commit()
    logger.info(f"Updated subscription {subscription.id} from Stripe webhook")


async def _handle_subscription_deleted(db: AsyncSession, subscription_data: dict):
    """Handle subscription.deleted webhook"""
    from app.models.billing import Subscription
    from sqlalchemy import select

    stripe_sub_id = subscription_data.get("id")
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.status = "canceled"
        subscription.canceled_at = datetime.utcnow()
        await db.commit()
        logger.info(f"Canceled subscription {subscription.id} from Stripe webhook")


async def _handle_payment_succeeded(db: AsyncSession, invoice_data: dict):
    """Handle invoice.payment_succeeded webhook"""
    from app.models.billing import StripeInvoice
    from sqlalchemy import select
    import uuid

    stripe_invoice_id = invoice_data.get("id")

    # Check if invoice already exists
    result = await db.execute(
        select(StripeInvoice).where(StripeInvoice.stripe_invoice_id == stripe_invoice_id)
    )
    existing_invoice = result.scalar_one_or_none()

    if existing_invoice:
        existing_invoice.status = "paid"
        existing_invoice.paid_at = datetime.fromtimestamp(invoice_data.get("status_transitions", {}).get("paid_at"))
    else:
        # Create new invoice record
        invoice = StripeInvoice(
            id=str(uuid.uuid4()),
            company_id=None,  # Would need to look up from customer_id
            stripe_invoice_id=stripe_invoice_id,
            amount_due=invoice_data.get("amount_due", 0) / 100,
            amount_paid=invoice_data.get("amount_paid", 0) / 100,
            status="paid",
            created_at=datetime.fromtimestamp(invoice_data.get("created")),
            paid_at=datetime.fromtimestamp(invoice_data.get("status_transitions", {}).get("paid_at")),
        )
        db.add(invoice)

    await db.commit()
    logger.info(f"Recorded successful payment for invoice {stripe_invoice_id}")


async def _handle_payment_failed(db: AsyncSession, invoice_data: dict):
    """Handle invoice.payment_failed webhook"""
    from app.models.billing import Subscription
    from sqlalchemy import select

    # Get subscription from invoice
    stripe_sub_id = invoice_data.get("subscription")
    if not stripe_sub_id:
        return

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.status = "past_due"
        await db.commit()
        logger.warning(f"Payment failed for subscription {subscription.id}")
        # TODO: Send notification to customer


async def _handle_trial_will_end(db: AsyncSession, subscription_data: dict):
    """Handle subscription.trial_will_end webhook (3 days before trial ends)"""
    from app.models.billing import Subscription
    from sqlalchemy import select

    stripe_sub_id = subscription_data.get("id")
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        logger.info(f"Trial ending soon for subscription {subscription.id}")
        # TODO: Send notification to customer about trial ending

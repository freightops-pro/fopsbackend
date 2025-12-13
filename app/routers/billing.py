"""
Billing router for tenant subscription management
"""
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

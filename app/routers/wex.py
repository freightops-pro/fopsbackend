"""
WEX EnCompass API Router - Fuel card payments and virtual card management.

Endpoints for:
- Virtual fuel card creation and management
- Fuel vendor (merchant) management
- Transaction reconciliation with IFTA
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.wex import (
    CreateFuelCardRequest,
    CreateFuelVendorRequest,
    FuelCardResponse,
    FuelCardStatusResponse,
    FuelCardSummaryResponse,
    FuelVendorResponse,
    CancelFuelCardResponse,
    SyncTransactionsRequest,
    TransactionSyncResult,
    WEXAuthorizationPushPayload,
    WEXWebhookResponse,
)
from app.services.wex.wex_service import WEXService

logger = logging.getLogger(__name__)

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> WEXService:
    return WEXService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


# ==================== FUEL CARD ENDPOINTS ====================


@router.post("/fuel-cards", response_model=FuelCardResponse, status_code=status.HTTP_201_CREATED)
async def create_fuel_card(
    payload: CreateFuelCardRequest,
    company_id: str = Depends(_company_id),
    service: WEXService = Depends(_service),
) -> FuelCardResponse:
    """
    Create a virtual fuel card for a driver.

    This generates a single-use virtual card that can be used at the specified
    fuel vendor. The card details (number, CVV, expiration) are returned.

    The card is valid for the specified number of days and limited to the
    maximum amount specified.
    """
    try:
        result = await service.create_fuel_card(
            company_id=company_id,
            merchant_id=payload.merchant_id,
            amount=payload.amount,
            driver_id=payload.driver_id,
            truck_id=payload.truck_id,
            load_id=payload.load_id,
            fuel_stop_location=payload.fuel_stop_location,
            jurisdiction=payload.jurisdiction,
            valid_days=payload.valid_days,
        )
        return FuelCardResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create fuel card: {str(exc)}"
        )


@router.get("/fuel-cards/{merchant_log_id}", response_model=FuelCardStatusResponse)
async def get_fuel_card_status(
    merchant_log_id: str,
    company_id: str = Depends(_company_id),
    service: WEXService = Depends(_service),
) -> FuelCardStatusResponse:
    """
    Get the current status of a fuel card.

    Returns card details, authorization history, and posted transactions.
    """
    try:
        result = await service.get_fuel_card_status(
            company_id=company_id,
            merchant_log_id=merchant_log_id,
        )
        return FuelCardStatusResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get fuel card status: {str(exc)}"
        )


@router.delete("/fuel-cards/{merchant_log_id}", response_model=CancelFuelCardResponse)
async def cancel_fuel_card(
    merchant_log_id: str,
    company_id: str = Depends(_company_id),
    service: WEXService = Depends(_service),
) -> CancelFuelCardResponse:
    """
    Cancel a fuel card.

    Voids the virtual card and prevents further use.
    """
    try:
        result = await service.cancel_fuel_card(
            company_id=company_id,
            merchant_log_id=merchant_log_id,
        )
        return CancelFuelCardResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel fuel card: {str(exc)}"
        )


# ==================== VENDOR ENDPOINTS ====================


@router.post("/vendors", response_model=FuelVendorResponse, status_code=status.HTTP_201_CREATED)
async def create_fuel_vendor(
    payload: CreateFuelVendorRequest,
    company_id: str = Depends(_company_id),
    service: WEXService = Depends(_service),
) -> FuelVendorResponse:
    """
    Create a new fuel vendor in WEX.

    Fuel vendors must be created before fuel cards can be issued for them.
    """
    try:
        result = await service.create_fuel_vendor(
            company_id=company_id,
            name=payload.name,
            address=payload.address,
            contact=payload.contact,
            tax_id=payload.tax_id,
        )
        return FuelVendorResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create fuel vendor: {str(exc)}"
        )


@router.get("/vendors/{merchant_id}", response_model=FuelVendorResponse)
async def get_fuel_vendor(
    merchant_id: str,
    company_id: str = Depends(_company_id),
    service: WEXService = Depends(_service),
) -> FuelVendorResponse:
    """Get fuel vendor details."""
    try:
        result = await service.get_fuel_vendor(
            company_id=company_id,
            merchant_id=merchant_id,
        )
        return FuelVendorResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get fuel vendor: {str(exc)}"
        )


# ==================== TRANSACTION SYNC ENDPOINTS ====================


@router.post("/transactions/sync", response_model=TransactionSyncResult)
async def sync_transactions(
    payload: SyncTransactionsRequest,
    company_id: str = Depends(_company_id),
    service: WEXService = Depends(_service),
) -> TransactionSyncResult:
    """
    Sync WEX transactions to FreightOps for IFTA reconciliation.

    This fetches posted transactions from WEX and creates/updates
    fuel transaction records in FreightOps for IFTA reporting.
    """
    try:
        result = await service.sync_transactions(
            company_id=company_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        return TransactionSyncResult(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync transactions: {str(exc)}"
        )


@router.get("/summary", response_model=FuelCardSummaryResponse)
async def get_fuel_card_summary(
    start_date: str,
    end_date: str,
    company_id: str = Depends(_company_id),
    service: WEXService = Depends(_service),
) -> FuelCardSummaryResponse:
    """
    Get a summary of fuel card usage for a period.

    Returns totals and breakdowns by jurisdiction for IFTA reporting.
    """
    try:
        result = await service.get_fuel_card_summary(
            company_id=company_id,
            start_date=start_date,
            end_date=end_date,
        )
        return FuelCardSummaryResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get fuel card summary: {str(exc)}"
        )


# ==================== WEBHOOK ENDPOINTS ====================


@router.post("/webhooks/authorization-push", response_model=WEXWebhookResponse)
async def handle_authorization_push(
    payload: WEXAuthorizationPushPayload,
    db: AsyncSession = Depends(get_db),
) -> WEXWebhookResponse:
    """
    WEX Authorization Push Webhook endpoint.

    Receives real-time authorization notifications from WEX when cards are used.
    This enables:
    - Real-time transaction monitoring
    - Fraud detection alerts
    - Immediate fuel purchase tracking for IFTA

    Note: This endpoint does NOT require authentication as it receives
    callbacks directly from WEX servers. Authorization is handled by WEX
    using the registered endpoint URL.
    """
    try:
        logger.info(
            f"WEX Authorization Push received: AuthID={payload.AuthorizationId}, "
            f"Amount=${payload.Amount}, Response={payload.Response}, "
            f"Merchant={payload.MerchantName}"
        )

        # Process based on authorization response
        if payload.Response == "Approval":
            # Log successful authorization
            logger.info(
                f"Card authorized: ${payload.Amount} at {payload.MerchantName} "
                f"({payload.MerchantCity}, {payload.MerchantStateProvince})"
            )

            # Store authorization in database for reconciliation
            # The UniqueId links to the MerchantLog we created
            if payload.UniqueId:
                from app.models.fuel import FuelTransaction
                from sqlalchemy import select

                # Find pending fuel transaction by external_id (MerchantLog ID)
                result = await db.execute(
                    select(FuelTransaction).where(
                        FuelTransaction.external_id == payload.UniqueId,
                        FuelTransaction.status == "pending",
                    )
                )
                txn = result.scalar_one_or_none()

                if txn:
                    # Update with authorization details
                    txn.cost = payload.Amount
                    txn.location = payload.MerchantName
                    if payload.MerchantStateProvince:
                        txn.jurisdiction = payload.MerchantStateProvince
                    txn.status = "authorized"
                    await db.commit()
                    logger.info(f"Updated fuel transaction {txn.id} with authorization")

        elif payload.Response == "Decline":
            # Log declined authorization for alerting
            logger.warning(
                f"Card DECLINED: ${payload.Amount} at {payload.MerchantName} - "
                f"Reason: {payload.DeclineReasonMessage} ({payload.DeclineReasonCode})"
            )

            # TODO: Trigger alert notification to dispatcher/admin
            # This could integrate with the notification service

        return WEXWebhookResponse(
            ResponseCode=0,
            ResponseDescription="Authorization received successfully"
        )

    except Exception as exc:
        logger.error(f"Failed to process WEX authorization push: {exc}")
        # Return success anyway to prevent WEX from retrying indefinitely
        # Log the error for investigation
        return WEXWebhookResponse(
            ResponseCode=0,
            ResponseDescription=f"Processed with warning: {str(exc)}"
        )

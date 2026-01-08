"""Factoring API endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.factoring import (
    BatchSendToFactoringRequest,
    FactoringProviderCreate,
    FactoringProviderResponse,
    FactoringProviderUpdate,
    FactoringSummary,
    FactoringTransactionResponse,
    FactoringWebhookPayload,
    SendToFactoringRequest,
)
from app.services.factoring import FactoringService

router = APIRouter(prefix="/factoring", tags=["factoring"])


def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    """Extract company ID from current user."""
    if not current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to a company",
        )
    return current_user.company_id


def _service(db: AsyncSession = Depends(get_db)) -> FactoringService:
    """Get factoring service instance."""
    return FactoringService(db)


# ========== Provider Management ==========


@router.post("/providers", response_model=FactoringProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    provider_data: FactoringProviderCreate,
    company_id: str = Depends(_company_id),
    service: FactoringService = Depends(_service),
    current_user=Depends(deps.get_current_user),
):
    """
    Create a new factoring provider configuration.
    Requires admin or accountant role.
    """
    if current_user.role not in ["ADMIN", "ACCOUNTANT"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and accountants can configure factoring providers",
        )

    provider = await service.create_provider(company_id, provider_data)
    return FactoringProviderResponse.model_validate(provider)


@router.get("/providers", response_model=List[FactoringProviderResponse])
async def list_providers(
    company_id: str = Depends(_company_id),
    service: FactoringService = Depends(_service),
):
    """List all factoring providers for the company."""
    providers = await service.list_providers(company_id)
    return [FactoringProviderResponse.model_validate(p) for p in providers]


@router.get("/providers/{provider_id}", response_model=FactoringProviderResponse)
async def get_provider(
    provider_id: str,
    company_id: str = Depends(_company_id),
    service: FactoringService = Depends(_service),
):
    """Get a specific factoring provider."""
    provider = await service.get_provider(company_id, provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factoring provider not found",
        )
    return FactoringProviderResponse.model_validate(provider)


@router.get("/providers/active/current", response_model=FactoringProviderResponse)
async def get_active_provider(
    company_id: str = Depends(_company_id),
    service: FactoringService = Depends(_service),
):
    """Get the currently active factoring provider."""
    provider = await service.get_active_provider(company_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active factoring provider configured",
        )
    return FactoringProviderResponse.model_validate(provider)


@router.put("/providers/{provider_id}", response_model=FactoringProviderResponse)
async def update_provider(
    provider_id: str,
    provider_data: FactoringProviderUpdate,
    company_id: str = Depends(_company_id),
    service: FactoringService = Depends(_service),
    current_user=Depends(deps.get_current_user),
):
    """
    Update a factoring provider configuration.
    Requires admin or accountant role.
    """
    if current_user.role not in ["ADMIN", "ACCOUNTANT"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and accountants can update factoring providers",
        )

    provider = await service.update_provider(company_id, provider_id, provider_data)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factoring provider not found",
        )
    return FactoringProviderResponse.model_validate(provider)


# ========== Transaction Management ==========


@router.post("/send", response_model=FactoringTransactionResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_to_factoring(
    request: SendToFactoringRequest,
    company_id: str = Depends(_company_id),
    service: FactoringService = Depends(_service),
    current_user=Depends(deps.get_current_user),
):
    """
    Send a single load/invoice to factoring.
    Returns 202 Accepted as this is an async operation.
    """
    if current_user.role not in ["ADMIN", "ACCOUNTANT", "DISPATCHER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to send loads to factoring",
        )

    try:
        transaction = await service.send_to_factoring(company_id, request)
        return FactoringTransactionResponse.model_validate(transaction)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/batch-send", response_model=List[FactoringTransactionResponse], status_code=status.HTTP_202_ACCEPTED)
async def batch_send_to_factoring(
    request: BatchSendToFactoringRequest,
    company_id: str = Depends(_company_id),
    service: FactoringService = Depends(_service),
    current_user=Depends(deps.get_current_user),
):
    """
    Send multiple loads to factoring in a batch.
    Returns 202 Accepted as this is an async operation.
    """
    if current_user.role not in ["ADMIN", "ACCOUNTANT", "DISPATCHER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to send loads to factoring",
        )

    try:
        transactions = await service.batch_send_to_factoring(company_id, request)
        return [FactoringTransactionResponse.model_validate(t) for t in transactions]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/transactions", response_model=List[FactoringTransactionResponse])
async def list_transactions(
    status_filter: Optional[str] = None,
    company_id: str = Depends(_company_id),
    service: FactoringService = Depends(_service),
):
    """List factoring transactions, optionally filtered by status."""
    transactions = await service.list_transactions(company_id, status=status_filter)
    return [FactoringTransactionResponse.model_validate(t) for t in transactions]


@router.get("/transactions/{transaction_id}", response_model=FactoringTransactionResponse)
async def get_transaction(
    transaction_id: str,
    company_id: str = Depends(_company_id),
    service: FactoringService = Depends(_service),
):
    """Get a specific factoring transaction."""
    transaction = await service.get_transaction(company_id, transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    return FactoringTransactionResponse.model_validate(transaction)


@router.get("/summary", response_model=FactoringSummary)
async def get_factoring_summary(
    company_id: str = Depends(_company_id),
    service: FactoringService = Depends(_service),
):
    """Get summary of factoring activity."""
    summary = await service.get_factoring_summary(company_id)
    return FactoringSummary(**summary)


# ========== Webhooks ==========


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def factoring_webhook(
    payload: FactoringWebhookPayload,
    x_webhook_signature: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Receive webhook notifications from factoring provider.
    This endpoint is called by the factoring company's system.

    Note: In production, validate the webhook signature using the provider's webhook secret.
    """
    # TODO: Validate webhook signature
    # if not _validate_webhook_signature(payload, x_webhook_signature):
    #     raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Extract company_id from transaction lookup
    # For now, we'll need to find the transaction first to get company_id
    service = FactoringService(db)

    # Try to find transaction across all companies (webhook comes from external source)
    # In production, we'd need a more sophisticated lookup mechanism
    try:
        # This is simplified - in production we'd have a better way to route webhooks
        # Perhaps by including company_id in the webhook URL or having a webhook secret per company
        transaction = await service.process_webhook(
            company_id="",  # Will be filled by service lookup
            payload=payload,
        )

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found",
            )

        return {
            "status": "success",
            "transaction_id": transaction.id,
            "message": f"Webhook processed: {payload.status}",
        }
    except Exception as e:
        # Log the error but return 200 to prevent webhook retries for invalid data
        print(f"Webhook processing error: {e}")
        return {
            "status": "error",
            "message": str(e),
        }

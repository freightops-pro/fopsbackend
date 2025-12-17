"""
Banking Plaid Integration API Endpoints

Handles connecting external bank accounts via Plaid.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.services.plaid_service import PlaidService


router = APIRouter(prefix="/banking/plaid", tags=["Banking Plaid"])


# === Request/Response Schemas ===

class CreateLinkTokenRequest(BaseModel):
    """Request to create a Plaid Link token."""
    redirect_uri: Optional[str] = None


class CreateLinkTokenResponse(BaseModel):
    """Plaid Link token response."""
    link_token: str
    expiration: str


class ExchangePublicTokenRequest(BaseModel):
    """Request to exchange public token for access token."""
    public_token: str
    institution_id: Optional[str] = None
    institution_name: Optional[str] = None


class ExchangePublicTokenResponse(BaseModel):
    """Token exchange response."""
    plaid_item_id: str
    accounts_synced: int


class SyncAccountsResponse(BaseModel):
    """Account sync response."""
    accounts_synced: List[str]


class SyncTransactionsResponse(BaseModel):
    """Transaction sync response."""
    added: int
    modified: int
    removed: int
    has_more: bool


class ConnectedBankResponse(BaseModel):
    """Connected bank info."""
    id: str
    institution_name: str
    status: str
    last_synced_at: Optional[str]
    accounts_count: int


# === Endpoints ===

@router.post("/link-token", response_model=CreateLinkTokenResponse)
async def create_link_token(
    request: CreateLinkTokenRequest,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a Plaid Link token to initiate bank connection flow.

    This token is used by the frontend Plaid Link component to start
    the OAuth-style bank connection process.

    Returns a link_token that expires in 30 minutes.
    """
    service = PlaidService()

    try:
        result = await service.create_link_token(
            db=db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            redirect_uri=request.redirect_uri
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create link token: {str(e)}"
        )


@router.post("/exchange-token", response_model=ExchangePublicTokenResponse)
async def exchange_public_token(
    request: ExchangePublicTokenRequest,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Exchange Plaid public token for permanent access token.

    Called after user successfully connects their bank via Plaid Link.
    The public token is temporary and must be exchanged immediately.

    This will:
    1. Exchange the token
    2. Store encrypted access token
    3. Fetch and store all accounts
    4. Fetch initial transactions
    """
    service = PlaidService()

    try:
        plaid_item_id = await service.exchange_public_token(
            db=db,
            company_id=current_user.company_id,
            public_token=request.public_token,
            institution_id=request.institution_id,
            institution_name=request.institution_name
        )

        # Count accounts synced
        result = await db.execute(
            "SELECT COUNT(*) FROM plaid_account WHERE item_id = :item_id",
            {"item_id": plaid_item_id}
        )
        accounts_count = result.scalar()

        return ExchangePublicTokenResponse(
            plaid_item_id=plaid_item_id,
            accounts_synced=accounts_count
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exchange token: {str(e)}"
        )


@router.post("/{plaid_item_id}/sync-accounts", response_model=SyncAccountsResponse)
async def sync_accounts(
    plaid_item_id: str,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync accounts from Plaid for a connected bank.

    Fetches latest account balances and creates/updates account records.
    """
    service = PlaidService()

    try:
        account_ids = await service.sync_accounts(db, plaid_item_id)

        return SyncAccountsResponse(accounts_synced=account_ids)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync accounts: {str(e)}"
        )


@router.post("/{plaid_item_id}/sync-transactions", response_model=SyncTransactionsResponse)
async def sync_transactions(
    plaid_item_id: str,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync transactions from Plaid using incremental sync.

    Only fetches new/modified transactions since last sync (efficient).
    """
    service = PlaidService()

    try:
        result = await service.sync_transactions(db, plaid_item_id)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync transactions: {str(e)}"
        )


@router.get("/connected-banks", response_model=List[ConnectedBankResponse])
async def get_connected_banks(
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all connected banks for the company.

    Returns list of Plaid items with account counts and sync status.
    """
    service = PlaidService()

    try:
        banks = await service.get_connected_banks(db, current_user.company_id)

        return banks

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch connected banks: {str(e)}"
        )


@router.delete("/{plaid_item_id}")
async def disconnect_bank(
    plaid_item_id: str,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnect a bank (soft delete).

    Marks the Plaid item as disconnected and stops syncing.
    Historical transactions are preserved.
    """
    service = PlaidService()

    try:
        await service.disconnect_bank(db, plaid_item_id)

        return {"status": "disconnected"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect bank: {str(e)}"
        )

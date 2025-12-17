"""
Banking Reconciliation API Endpoints

Auto-matches bank transactions with ledger entries.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.services.reconciliation_service import ReconciliationService


router = APIRouter(prefix="/banking/reconciliation", tags=["Banking Reconciliation"])


# === Request/Response Schemas ===

class ReconcileAccountRequest(BaseModel):
    """Request to reconcile an account."""
    account_id: str
    account_type: str  # 'plaid' or 'synctera'
    start_date: datetime
    end_date: datetime
    auto_approve_threshold: float = 0.95  # Confidence threshold for auto-matching


class ReconcileAccountResponse(BaseModel):
    """Reconciliation result."""
    matched: int
    unmatched_bank: int
    unmatched_ledger: int
    confidence_scores: dict


class ManualMatchRequest(BaseModel):
    """Request to manually match a transaction."""
    account_type: str
    bank_transaction_id: str
    ledger_entry_id: str


class UnmatchRequest(BaseModel):
    """Request to undo a reconciliation match."""
    account_type: str
    bank_transaction_id: str


class ReconciliationSummaryResponse(BaseModel):
    """Reconciliation summary for a company."""
    total_bank_transactions: int
    total_ledger_entries: int
    matched: int
    unmatched_bank: int
    unmatched_ledger: int
    match_rate: float


# === Endpoints ===

@router.post("/auto-match", response_model=ReconcileAccountResponse)
async def auto_match_transactions(
    request: ReconcileAccountRequest,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Auto-match bank transactions with ledger entries.

    Matching algorithm:
    - 40% weight: Exact amount match
    - 30% weight: Date within ±2 days
    - 30% weight: Description similarity (fuzzy matching)

    Auto-approves matches with confidence >= threshold (default 95%).
    Lower confidence matches are flagged for manual review.
    """
    service = ReconciliationService(db)

    try:
        result = await service.reconcile_account(
            account_id=request.account_id,
            account_type=request.account_type,
            start_date=request.start_date,
            end_date=request.end_date,
            auto_approve_threshold=request.auto_approve_threshold
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation failed: {str(e)}"
        )


@router.post("/manual-match")
async def manual_match(
    request: ManualMatchRequest,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually match a bank transaction to a ledger entry.

    Use this when auto-matching fails or confidence is too low.
    """
    service = ReconciliationService(db)

    try:
        await service.manual_match(
            account_type=request.account_type,
            bank_transaction_id=request.bank_transaction_id,
            ledger_entry_id=request.ledger_entry_id,
            user_id=current_user.id
        )

        return {"status": "matched"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual match failed: {str(e)}"
        )


@router.post("/unmatch")
async def unmatch_transaction(
    request: UnmatchRequest,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Undo a reconciliation match.

    Use this when a match was incorrect.
    """
    service = ReconciliationService(db)

    try:
        await service.unmatch(
            account_type=request.account_type,
            bank_transaction_id=request.bank_transaction_id
        )

        return {"status": "unmatched"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unmatch failed: {str(e)}"
        )


@router.get("/summary", response_model=ReconciliationSummaryResponse)
async def get_reconciliation_summary(
    days: int = 30,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get reconciliation summary for the company.

    Shows overall match rate and statistics for the last N days (default 30).
    """
    service = ReconciliationService(db)

    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        summary = await service.get_reconciliation_summary(
            company_id=current_user.company_id,
            start_date=start_date,
            end_date=end_date
        )

        return summary

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get summary: {str(e)}"
        )

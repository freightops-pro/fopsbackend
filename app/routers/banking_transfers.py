"""
Banking Transfer API Endpoints

Handles internal transfers, ACH transfers, and wire transfers.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.services.transfer_service import TransferService, TransferType, TransferStatus


router = APIRouter(prefix="/banking/transfers", tags=["Banking Transfers"])


# === Request/Response Schemas ===

class InternalTransferRequest(BaseModel):
    """Request for internal transfer between company accounts."""
    from_account_id: str = Field(..., description="Source Synctera account ID")
    to_account_id: str = Field(..., description="Destination Synctera account ID")
    amount: float = Field(..., gt=0, description="Transfer amount (USD)")
    description: str = Field(..., max_length=255, description="Transfer description/memo")
    scheduled_date: Optional[datetime] = Field(None, description="Optional future date to execute")


class ACHTransferRequest(BaseModel):
    """Request for ACH transfer to external bank."""
    from_account_id: str
    recipient_id: Optional[str] = Field(None, description="Saved recipient ID (if reusing)")
    recipient_name: Optional[str] = Field(None, description="Recipient name (if new)")
    recipient_routing_number: Optional[str] = Field(None, description="9-digit routing number")
    recipient_account_number: Optional[str] = Field(None, description="Account number")
    recipient_account_type: Optional[str] = Field(None, description="checking or savings")
    amount: float = Field(..., gt=0)
    description: str = Field(..., max_length=255)
    save_recipient: bool = Field(False, description="Save recipient for future use")


class WireTransferRequest(BaseModel):
    """Request for wire transfer (domestic or international)."""
    from_account_id: str
    recipient_name: str
    recipient_routing_number: str
    recipient_account_number: str
    recipient_bank_name: str
    amount: float = Field(..., gt=0)
    description: str
    wire_type: str = Field("domestic", description="domestic or international")
    recipient_swift_code: Optional[str] = None
    recipient_address: Optional[dict] = None


class TransferResponse(BaseModel):
    """Transfer response."""
    transfer_id: str
    transfer_type: str
    status: str
    amount: float
    fee_amount: Optional[float] = None
    scheduled_date: Optional[datetime] = None
    estimated_completion: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime


class TransferHistoryResponse(BaseModel):
    """Transfer history item."""
    id: str
    type: str
    status: str
    amount: float
    fee: float
    description: str
    recipient: Optional[str]
    created_at: str
    processed_at: Optional[str]


# === Endpoints ===

@router.post("/internal", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
async def create_internal_transfer(
    request: InternalTransferRequest,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create an internal transfer between two Synctera accounts.

    Internal transfers are:
    - Instant (processed immediately if not scheduled)
    - Free (no fees)
    - Between accounts owned by the same company

    Requires:
    - Both accounts must belong to the authenticated user's company
    - Source account must have sufficient available balance
    """
    service = TransferService(db)

    try:
        result = await service.create_internal_transfer(
            company_id=current_user.company_id,
            from_account_id=request.from_account_id,
            to_account_id=request.to_account_id,
            amount=request.amount,
            description=request.description,
            user_id=current_user.id,
            scheduled_date=request.scheduled_date
        )

        return TransferResponse(
            transfer_id=result["transfer_id"],
            transfer_type="internal",
            status=result["status"],
            amount=request.amount,
            fee_amount=0.0,
            scheduled_date=result.get("scheduled_date"),
            processed_at=result.get("processed_at") and datetime.fromisoformat(result["processed_at"]),
            created_at=datetime.utcnow()
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Transfer failed: {str(e)}")


@router.post("/ach", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
async def create_ach_transfer(
    request: ACHTransferRequest,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create an ACH transfer to an external bank account.

    ACH transfers:
    - Take 1-3 business days
    - Subject to daily limit ($25,000/day per account)
    - May have small fees ($0-3)

    You can either:
    - Use a saved recipient (provide recipient_id)
    - Enter new recipient details (all recipient_* fields required)
    """
    # Validate: either recipient_id OR all recipient details
    if not request.recipient_id:
        if not all([
            request.recipient_name,
            request.recipient_routing_number,
            request.recipient_account_number,
            request.recipient_account_type
        ]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either recipient_id or all recipient details (name, routing, account number, type) required"
            )

    service = TransferService(db)

    try:
        result = await service.create_ach_transfer(
            company_id=current_user.company_id,
            from_account_id=request.from_account_id,
            recipient_name=request.recipient_name or "",
            recipient_routing_number=request.recipient_routing_number or "",
            recipient_account_number=request.recipient_account_number or "",
            recipient_account_type=request.recipient_account_type or "checking",
            amount=request.amount,
            description=request.description,
            user_id=current_user.id,
            save_recipient=request.save_recipient,
            recipient_id=request.recipient_id
        )

        return TransferResponse(
            transfer_id=result["transfer_id"],
            transfer_type="ach",
            status=result["status"],
            amount=request.amount,
            fee_amount=0.0,  # TODO: Add ACH fee if applicable
            estimated_completion=result.get("estimated_completion"),
            created_at=datetime.utcnow()
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"ACH transfer failed: {str(e)}")


@router.post("/wire", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
async def create_wire_transfer(
    request: WireTransferRequest,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a wire transfer (domestic or international).

    Wire transfers:
    - Same day (domestic) or 1-2 days (international)
    - Higher fees: $25 domestic, $45 international
    - Require additional verification for large amounts

    For international wires, provide:
    - recipient_swift_code (required)
    - recipient_address (required)
    """
    if request.wire_type == "international":
        if not request.recipient_swift_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SWIFT code required for international wires"
            )
        if not request.recipient_address:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recipient address required for international wires"
            )

    service = TransferService(db)

    try:
        result = await service.create_wire_transfer(
            company_id=current_user.company_id,
            from_account_id=request.from_account_id,
            recipient_name=request.recipient_name,
            recipient_routing_number=request.recipient_routing_number,
            recipient_account_number=request.recipient_account_number,
            recipient_bank_name=request.recipient_bank_name,
            amount=request.amount,
            description=request.description,
            user_id=current_user.id,
            wire_type=request.wire_type,
            recipient_swift_code=request.recipient_swift_code,
            recipient_address=request.recipient_address
        )

        fee = 25.00 if request.wire_type == "domestic" else 45.00

        return TransferResponse(
            transfer_id=result["transfer_id"],
            transfer_type="wire",
            status=result["status"],
            amount=request.amount,
            fee_amount=result.get("fee_amount", fee),
            created_at=datetime.utcnow()
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Wire transfer failed: {str(e)}")


@router.get("/history", response_model=List[TransferHistoryResponse])
async def get_transfer_history(
    limit: int = 50,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get recent transfer history for the company.

    Returns up to `limit` most recent transfers (default 50, max 200).
    """
    if limit > 200:
        limit = 200

    service = TransferService(db)

    try:
        transfers = await service.get_transfer_history(
            company_id=current_user.company_id,
            limit=limit
        )

        return transfers

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{transfer_id}", response_model=TransferResponse)
async def get_transfer_status(
    transfer_id: str,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get status of a specific transfer.

    Use this to check if an ACH transfer has completed or if a wire has been processed.
    """
    # TODO: Implement get_transfer_by_id in TransferService
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Coming soon")

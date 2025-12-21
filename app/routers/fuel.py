import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.models.fuel import FuelCard
from app.schemas.fuel import (
    FuelCardCreate,
    FuelCardListResponse,
    FuelCardResponse,
    FuelCardUpdate,
    FuelImportRequest,
    FuelSummaryResponse,
    FuelUploadResponse,
    JurisdictionSummaryResponse,
)
from app.services.fuel import FuelService

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> FuelService:
    return FuelService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


# ==================== FUEL CARD MANAGEMENT ====================


@router.get("/cards", response_model=FuelCardListResponse)
async def list_fuel_cards(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    card_type: Optional[str] = Query(None, description="Filter by card type (physical, virtual)"),
    card_provider: Optional[str] = Query(None, description="Filter by provider"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    driver_id: Optional[str] = Query(None, description="Filter by assigned driver"),
) -> FuelCardListResponse:
    """List all fuel cards for the company."""
    query = select(FuelCard).where(FuelCard.company_id == company_id)

    if card_type:
        query = query.where(FuelCard.card_type == card_type)
    if card_provider:
        query = query.where(FuelCard.card_provider == card_provider)
    if status_filter:
        query = query.where(FuelCard.status == status_filter)
    if driver_id:
        query = query.where(FuelCard.driver_id == driver_id)

    query = query.order_by(FuelCard.created_at.desc())

    result = await db.execute(query)
    cards = result.scalars().all()

    return FuelCardListResponse(
        cards=[_card_to_response(card) for card in cards],
        total=len(cards),
    )


@router.post("/cards", response_model=FuelCardResponse, status_code=status.HTTP_201_CREATED)
async def create_fuel_card(
    payload: FuelCardCreate,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> FuelCardResponse:
    """Create a new fuel card."""
    # Mask the card number - only store last 4 digits
    masked_number = payload.card_number[-4:] if len(payload.card_number) > 4 else payload.card_number

    card = FuelCard(
        id=str(uuid.uuid4()),
        company_id=company_id,
        card_number=f"****{masked_number}",
        card_provider=payload.card_provider,
        card_type=payload.card_type,
        card_nickname=payload.card_nickname,
        driver_id=payload.driver_id,
        truck_id=payload.truck_id,
        status="active",
        expiration_date=payload.expiration_date,
        daily_limit=payload.daily_limit,
        transaction_limit=payload.transaction_limit,
        notes=payload.notes,
    )

    db.add(card)
    await db.commit()
    await db.refresh(card)

    return _card_to_response(card)


@router.get("/cards/{card_id}", response_model=FuelCardResponse)
async def get_fuel_card(
    card_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> FuelCardResponse:
    """Get a fuel card by ID."""
    result = await db.execute(
        select(FuelCard).where(
            FuelCard.id == card_id,
            FuelCard.company_id == company_id,
        )
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fuel card not found")

    return _card_to_response(card)


@router.patch("/cards/{card_id}", response_model=FuelCardResponse)
async def update_fuel_card(
    card_id: str,
    payload: FuelCardUpdate,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> FuelCardResponse:
    """Update a fuel card."""
    result = await db.execute(
        select(FuelCard).where(
            FuelCard.id == card_id,
            FuelCard.company_id == company_id,
        )
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fuel card not found")

    # Update fields if provided
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(card, field, value)

    await db.commit()
    await db.refresh(card)

    return _card_to_response(card)


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_fuel_card(
    card_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a fuel card."""
    result = await db.execute(
        select(FuelCard).where(
            FuelCard.id == card_id,
            FuelCard.company_id == company_id,
        )
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fuel card not found")

    await db.delete(card)
    await db.commit()


def _card_to_response(card: FuelCard) -> FuelCardResponse:
    """Convert FuelCard model to response schema."""
    return FuelCardResponse(
        id=card.id,
        card_number=card.card_number,
        card_provider=card.card_provider,
        card_type=card.card_type,
        card_nickname=card.card_nickname,
        driver_id=card.driver_id,
        driver_name=None,  # TODO: Join with driver table if needed
        truck_id=card.truck_id,
        status=card.status,
        expiration_date=card.expiration_date,
        daily_limit=float(card.daily_limit) if card.daily_limit else None,
        transaction_limit=float(card.transaction_limit) if card.transaction_limit else None,
        notes=card.notes,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


# ==================== FUEL SUMMARY & IMPORT ====================


@router.get("/summary", response_model=FuelSummaryResponse)
async def get_fuel_summary(
    company_id: str = Depends(_company_id),
    service: FuelService = Depends(_service),
) -> FuelSummaryResponse:
    return await service.summary(company_id)


@router.get("/jurisdictions", response_model=List[JurisdictionSummaryResponse])
async def get_jurisdiction_rollup(
    company_id: str = Depends(_company_id),
    service: FuelService = Depends(_service),
) -> List[JurisdictionSummaryResponse]:
    return await service.jurisdictions(company_id)


@router.post("/import", response_model=FuelUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_fuel_statement(
    payload: FuelImportRequest,
    company_id: str = Depends(_company_id),
    service: FuelService = Depends(_service),
) -> FuelUploadResponse:
    try:
        await service.import_statement(company_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return FuelUploadResponse(success=True, message="Fuel statement accepted for processing")

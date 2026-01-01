from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.location import LocationCreate, LocationResponse, LocationUpdate
from app.services.location import LocationService

router = APIRouter()


async def _location_service(db: AsyncSession = Depends(get_db)) -> LocationService:
    return LocationService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


@router.get("", response_model=List[LocationResponse])
async def list_locations(
    location_type: Optional[str] = None,
    company_id: str = Depends(_company_id),
    location_service: LocationService = Depends(_location_service),
) -> List[LocationResponse]:
    """List all locations in the address book for the company, optionally filtered by type."""
    locations = await location_service.list_locations(company_id, location_type)
    return [LocationResponse.model_validate(location) for location in locations]


@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: str,
    company_id: str = Depends(_company_id),
    location_service: LocationService = Depends(_location_service),
) -> LocationResponse:
    """Get a single location by ID."""
    try:
        location = await location_service.get_location(company_id, location_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return LocationResponse.model_validate(location)


@router.post("", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    payload: LocationCreate,
    company_id: str = Depends(_company_id),
    location_service: LocationService = Depends(_location_service),
) -> LocationResponse:
    """Create a new location in the address book."""
    location = await location_service.create_location(company_id, payload)
    return LocationResponse.model_validate(location)


@router.patch("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: str,
    payload: LocationUpdate,
    company_id: str = Depends(_company_id),
    location_service: LocationService = Depends(_location_service),
) -> LocationResponse:
    """Update an existing location."""
    try:
        location = await location_service.update_location(company_id, location_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return LocationResponse.model_validate(location)


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: str,
    company_id: str = Depends(_company_id),
    location_service: LocationService = Depends(_location_service),
) -> None:
    """Delete a location from the address book."""
    try:
        await location_service.delete_location(company_id, location_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

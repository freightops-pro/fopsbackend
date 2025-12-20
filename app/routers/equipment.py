from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.equipment import (
    BulkLocationUpdate,
    EquipmentCreate,
    EquipmentLocationUpdate,
    EquipmentMaintenanceCreate,
    EquipmentMaintenanceEventResponse,
    EquipmentMaintenanceForecastResponse,
    EquipmentResponse,
    EquipmentUsageEventCreate,
    EquipmentUsageEventResponse,
    LocationUpdate,
)
from app.services.equipment import EquipmentService

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> EquipmentService:
    return EquipmentService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


@router.get("/equipment", response_model=List[EquipmentResponse])
async def list_equipment(
    company_id: str = Depends(_company_id),
    service: EquipmentService = Depends(_service),
) -> List[EquipmentResponse]:
    equipment_with_expenses = await service.list_equipment_with_expenses(company_id)
    return [EquipmentResponse.model_validate(e) for e in equipment_with_expenses]


@router.post("/equipment", response_model=EquipmentResponse, status_code=status.HTTP_201_CREATED)
async def create_equipment(
    payload: EquipmentCreate,
    company_id: str = Depends(_company_id),
    service: EquipmentService = Depends(_service),
) -> EquipmentResponse:
    try:
        return await service.create_equipment(company_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/equipment/{equipment_id}/usage",
    response_model=EquipmentUsageEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def log_usage_event(
    equipment_id: str,
    payload: EquipmentUsageEventCreate,
    company_id: str = Depends(_company_id),
    service: EquipmentService = Depends(_service),
) -> EquipmentUsageEventResponse:
    try:
        return await service.log_usage(company_id, equipment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/equipment/{equipment_id}/maintenance",
    response_model=EquipmentMaintenanceEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def log_maintenance_event(
    equipment_id: str,
    payload: EquipmentMaintenanceCreate,
    company_id: str = Depends(_company_id),
    service: EquipmentService = Depends(_service),
) -> EquipmentMaintenanceEventResponse:
    try:
        return await service.log_maintenance(company_id, equipment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/equipment/{equipment_id}/forecasts/refresh",
    response_model=List[EquipmentMaintenanceForecastResponse],
)
async def refresh_forecasts(
    equipment_id: str,
    company_id: str = Depends(_company_id),
    service: EquipmentService = Depends(_service),
) -> List[EquipmentMaintenanceForecastResponse]:
    try:
        return await service.refresh_forecasts(company_id, equipment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ============ Location Tracking Endpoints ============
# These endpoints receive live location data from ELD/GPS telemetry providers
# (Samsara, Motive, driver apps, etc.)


@router.post(
    "/equipment/{equipment_id}/location",
    response_model=EquipmentResponse,
    summary="Update equipment location",
    description="Update the live location of a specific equipment unit from ELD/GPS/driver app.",
)
async def update_equipment_location(
    equipment_id: str,
    payload: LocationUpdate,
    company_id: str = Depends(_company_id),
    service: EquipmentService = Depends(_service),
) -> EquipmentResponse:
    """
    Update the live location of a specific equipment unit.
    Called by ELD integrations, GPS telemetry, or driver mobile apps.
    """
    try:
        return await service.update_location(company_id, equipment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/equipment/locations/bulk",
    response_model=dict,
    summary="Bulk update equipment locations",
    description="Bulk update locations for multiple equipment units. Used by telemetry webhooks.",
)
async def bulk_update_locations(
    payload: BulkLocationUpdate,
    company_id: str = Depends(_company_id),
    service: EquipmentService = Depends(_service),
) -> dict:
    """
    Bulk update locations for multiple equipment units.
    Called by telemetry provider webhooks (Samsara, Motive, etc.)
    """
    results = await service.bulk_update_locations(company_id, payload.updates)
    return {
        "updated": results["updated"],
        "failed": results["failed"],
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get(
    "/equipment/locations",
    response_model=List[EquipmentResponse],
    summary="Get equipment with live locations",
    description="Get all equipment that has live location data available.",
)
async def get_equipment_with_locations(
    company_id: str = Depends(_company_id),
    service: EquipmentService = Depends(_service),
) -> List[EquipmentResponse]:
    """
    Get all equipment that has live location data.
    Useful for populating the fleet tracking map.
    """
    return await service.get_equipment_with_locations(company_id)


from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.equipment import (
    EquipmentCreate,
    EquipmentMaintenanceCreate,
    EquipmentMaintenanceEventResponse,
    EquipmentMaintenanceForecastResponse,
    EquipmentResponse,
    EquipmentUsageEventCreate,
    EquipmentUsageEventResponse,
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
    return await service.list_equipment(company_id)


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


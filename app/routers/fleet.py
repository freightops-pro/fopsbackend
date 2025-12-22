from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.driver import (
    AssignEquipmentRequest,
    AvailableEquipmentResponse,
    DriverComplianceProfileResponse,
    DriverComplianceUpdateRequest,
    DriverCreate,
    DriverCreateResponse,
    DriverEquipmentInfo,
    DriverProfileUpdate,
    GeneratePasswordResponse,
    UserAccessActionResponse,
    UserAccessInfo,
)
from app.schemas.fuel import FuelSummaryResponse, JurisdictionSummaryResponse
from app.services.driver import DriverService
from app.services.fuel import FuelService

router = APIRouter()


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


async def _fuel_service(db: AsyncSession = Depends(get_db)) -> FuelService:
    return FuelService(db)


async def _driver_service(db: AsyncSession = Depends(get_db)) -> DriverService:
    return DriverService(db)


@router.get("/fuel/summary", response_model=FuelSummaryResponse)
async def get_fleet_fuel_summary(
    company_id: str = Depends(_company_id),
    service: FuelService = Depends(_fuel_service),
) -> FuelSummaryResponse:
    return await service.summary(company_id)


@router.get("/fuel/jurisdictions", response_model=List[JurisdictionSummaryResponse])
async def get_fleet_jurisdictions(
    company_id: str = Depends(_company_id),
    service: FuelService = Depends(_fuel_service),
) -> List[JurisdictionSummaryResponse]:
    return await service.jurisdictions(company_id)


@router.get("/drivers", response_model=List[DriverComplianceProfileResponse])
async def list_fleet_drivers(
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> List[DriverComplianceProfileResponse]:
    return await service.list_profiles(company_id)


@router.post("/drivers", response_model=DriverCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_fleet_driver(
    payload: DriverCreate,
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> DriverCreateResponse:
    try:
        return await service.create_driver(company_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.patch(
    "/drivers/{driver_id}/compliance",
    response_model=DriverComplianceProfileResponse,
)
async def update_driver_compliance(
    driver_id: str,
    payload: DriverComplianceUpdateRequest,
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> DriverComplianceProfileResponse:
    try:
        return await service.update_compliance(company_id, driver_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch(
    "/drivers/{driver_id}",
    response_model=DriverComplianceProfileResponse,
)
async def update_driver_profile(
    driver_id: str,
    payload: DriverProfileUpdate,
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> DriverComplianceProfileResponse:
    """Update driver profile information."""
    try:
        return await service.update_driver_profile(company_id, driver_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/drivers/{driver_id}/user-access",
    response_model=UserAccessInfo,
)
async def get_driver_user_access(
    driver_id: str,
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> UserAccessInfo:
    """Get user access information for a driver."""
    try:
        return await service.get_user_access(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/drivers/{driver_id}/user-access/suspend",
    response_model=UserAccessActionResponse,
)
async def suspend_driver_user_access(
    driver_id: str,
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> UserAccessActionResponse:
    """Suspend user access for a driver."""
    try:
        return await service.suspend_user_access(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/drivers/{driver_id}/user-access/activate",
    response_model=UserAccessActionResponse,
)
async def activate_driver_user_access(
    driver_id: str,
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> UserAccessActionResponse:
    """Activate user access for a driver."""
    try:
        return await service.activate_user_access(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/drivers/{driver_id}/user-access/reset-password",
    response_model=UserAccessActionResponse,
)
async def send_driver_password_reset(
    driver_id: str,
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> UserAccessActionResponse:
    """Send password reset email to driver."""
    try:
        return await service.send_password_reset_email(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/drivers/{driver_id}/user-access/generate-password",
    response_model=GeneratePasswordResponse,
)
async def generate_driver_password(
    driver_id: str,
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> GeneratePasswordResponse:
    """Generate a new temporary password for a driver."""
    try:
        return await service.generate_new_password(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/drivers/{driver_id}/app-access",
    response_model=GeneratePasswordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_driver_app_access(
    driver_id: str,
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> GeneratePasswordResponse:
    """Create app access (user account) for a driver who doesn't have one yet."""
    try:
        return await service.create_user_account(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/drivers/{driver_id}/equipment",
    response_model=DriverEquipmentInfo,
)
async def get_driver_equipment(
    driver_id: str,
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> DriverEquipmentInfo:
    """Get equipment assigned to a driver."""
    try:
        return await service.get_driver_equipment(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/equipment/available",
    response_model=AvailableEquipmentResponse,
)
async def get_available_equipment(
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> AvailableEquipmentResponse:
    """Get available equipment for assignment."""
    return await service.get_available_equipment(company_id)


@router.put(
    "/drivers/{driver_id}/equipment/{equipment_type}",
    response_model=UserAccessActionResponse,
)
async def assign_driver_equipment(
    driver_id: str,
    equipment_type: str,
    payload: AssignEquipmentRequest,
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> UserAccessActionResponse:
    """Assign equipment to a driver."""
    try:
        return await service.assign_equipment(
            company_id, driver_id, equipment_type, payload.equipment_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/drivers/{driver_id}/equipment/{equipment_type}",
    response_model=UserAccessActionResponse,
)
async def unassign_driver_equipment(
    driver_id: str,
    equipment_type: str,
    company_id: str = Depends(_company_id),
    service: DriverService = Depends(_driver_service),
) -> UserAccessActionResponse:
    """Unassign equipment from a driver."""
    try:
        return await service.unassign_equipment(company_id, driver_id, equipment_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


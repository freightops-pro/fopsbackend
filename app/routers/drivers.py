from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.routers import websocket
from app.schemas.driver import (
    AssignEquipmentRequest,
    AvailableEquipmentResponse,
    DriverComplianceProfileResponse,
    DriverComplianceResponse,
    DriverComplianceUpdateRequest,
    DriverDocumentResponse,
    DriverEquipmentInfo,
    DriverIncidentCreate,
    DriverIncidentResponse,
    DriverProfileUpdate,
    DriverTrainingCreate,
    DriverTrainingResponse,
    GeneratePasswordResponse,
    LocationUpdate,
    UserAccessActionResponse,
    UserAccessInfo,
)
from app.services.driver import DriverService
from app.services.storage import StorageService

router = APIRouter()


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


@router.get("/compliance", response_model=List[DriverComplianceResponse])
async def list_driver_compliance(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> List[DriverComplianceResponse]:
    service = DriverService(db)
    return await service.list_compliance(company_id)


@router.get("/{driver_id}/profile")
async def get_driver_profile(
    driver_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
):
    """Get driver profile with equipment and stats for mobile app."""
    service = DriverService(db)
    try:
        return await service.get_driver_profile(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/{driver_id}/incidents",
    response_model=DriverIncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_driver_incident(
    driver_id: str,
    payload: DriverIncidentCreate,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> DriverIncidentResponse:
    service = DriverService(db)
    try:
        return await service.log_incident(company_id, driver_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/{driver_id}/documents",
    response_model=DriverDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_driver_document(
    driver_id: str,
    document_type: str,
    file: UploadFile,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> DriverDocumentResponse:
    """Upload a driver document to Cloudflare R2 storage."""
    service = DriverService(db)
    storage_service = StorageService()
    
    try:
        # Read file contents
        contents = await file.read()
        
        # Upload to R2 with company and driver prefix for organization
        storage_key = await storage_service.upload_file(
            file_content=contents,
            filename=file.filename or "document",
            prefix=f"drivers/{company_id}/{driver_id}",
            content_type=file.content_type,
        )
        
        # Store the R2 key in the database
        return await service.upload_document(company_id, driver_id, document_type, storage_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(exc)}",
        )


@router.get("/documents/{document_id}/download-url")
async def get_document_download_url(
    document_id: str,
    expires_in: int = Query(default=3600, ge=60, le=86400, description="URL expiration in seconds (60-86400)"),
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Generate a presigned URL for downloading a driver document.
    
    The URL will be valid for the specified expiration time (default: 1 hour).
    """
    from sqlalchemy import select
    from app.models.driver import DriverDocument, Driver
    
    storage_service = StorageService()
    
    try:
        # Get document with driver relationship
        result = await db.execute(
            select(DriverDocument, Driver)
            .join(Driver, DriverDocument.driver_id == Driver.id)
            .where(DriverDocument.id == document_id)
        )
        row = result.first()
        
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        
        document, driver = row
        
        # Verify driver belongs to company
        if driver.company_id != company_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
        # Generate presigned URL
        presigned_url = storage_service.get_file_url(document.file_url, expires_in=expires_in)
        
        return {
            "document_id": document_id,
            "url": presigned_url,
            "expires_in": expires_in,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(exc)}",
        )


@router.post(
    "/{driver_id}/training",
    response_model=DriverTrainingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_driver_training(
    driver_id: str,
    payload: DriverTrainingCreate,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> DriverTrainingResponse:
    service = DriverService(db)
    try:
        return await service.log_training(company_id, driver_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{driver_id}", response_model=DriverComplianceProfileResponse)
async def update_driver_profile(
    driver_id: str,
    payload: DriverProfileUpdate,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> DriverComplianceProfileResponse:
    """Update driver profile information."""
    service = DriverService(db)
    try:
        return await service.update_driver_profile(company_id, driver_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{driver_id}/compliance", response_model=DriverComplianceProfileResponse)
async def update_driver_compliance(
    driver_id: str,
    payload: DriverComplianceUpdateRequest,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> DriverComplianceProfileResponse:
    """Update driver compliance information."""
    service = DriverService(db)
    try:
        return await service.update_compliance(company_id, driver_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/users/{user_id}/profile", response_model=DriverComplianceProfileResponse)
async def update_driver_profile_by_user_id(
    user_id: str,
    payload: DriverProfileUpdate,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> DriverComplianceProfileResponse:
    """Update driver profile information by user_id, creating Driver record if needed."""
    service = DriverService(db)
    try:
        return await service.update_driver_profile_by_user_id(company_id, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{driver_id}/user-access", response_model=UserAccessInfo)
async def get_driver_user_access(
    driver_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> UserAccessInfo:
    """Get user access information for a driver."""
    service = DriverService(db)
    try:
        return await service.get_user_access(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{driver_id}/user-access/suspend", response_model=UserAccessActionResponse)
async def suspend_driver_user_access(
    driver_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> UserAccessActionResponse:
    """Suspend user access for a driver."""
    service = DriverService(db)
    try:
        return await service.suspend_user_access(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{driver_id}/user-access/activate", response_model=UserAccessActionResponse)
async def activate_driver_user_access(
    driver_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> UserAccessActionResponse:
    """Activate user access for a driver."""
    service = DriverService(db)
    try:
        return await service.activate_user_access(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/users/{user_id}/activate-access", response_model=UserAccessActionResponse)
async def activate_user_access_by_user_id(
    user_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> UserAccessActionResponse:
    """Activate user access for a user, creating a Driver record if needed."""
    service = DriverService(db)
    try:
        return await service.activate_user_access_by_user_id(company_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{driver_id}/user-access/reset-password", response_model=UserAccessActionResponse)
async def send_driver_password_reset(
    driver_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> UserAccessActionResponse:
    """Send password reset email to a driver."""
    service = DriverService(db)
    try:
        return await service.send_password_reset_email(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{driver_id}/user-access/generate-password", response_model=GeneratePasswordResponse)
async def generate_driver_password(
    driver_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> GeneratePasswordResponse:
    """Generate a new temporary password for a driver."""
    service = DriverService(db)
    try:
        return await service.generate_new_password(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{driver_id}/equipment", response_model=DriverEquipmentInfo)
async def get_driver_equipment(
    driver_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> DriverEquipmentInfo:
    """Get equipment assigned to a driver."""
    service = DriverService(db)
    try:
        return await service.get_driver_equipment(company_id, driver_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/equipment/available", response_model=AvailableEquipmentResponse)
async def get_available_equipment(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> AvailableEquipmentResponse:
    """Get available equipment that can be assigned to drivers."""
    service = DriverService(db)
    return await service.get_available_equipment(company_id)


@router.put("/{driver_id}/equipment/{equipment_type}", response_model=UserAccessActionResponse)
async def assign_driver_equipment(
    driver_id: str,
    equipment_type: str,
    payload: AssignEquipmentRequest,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> UserAccessActionResponse:
    """Assign equipment (truck, trailer, or fuel_card) to a driver."""
    service = DriverService(db)
    try:
        return await service.assign_equipment(company_id, driver_id, equipment_type, payload.equipment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{driver_id}/equipment/{equipment_type}", response_model=UserAccessActionResponse)
async def unassign_driver_equipment(
    driver_id: str,
    equipment_type: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> UserAccessActionResponse:
    """Unassign equipment (truck, trailer, or fuel_card) from a driver."""
    service = DriverService(db)
    try:
        return await service.unassign_equipment(company_id, driver_id, equipment_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{driver_id}/location", status_code=status.HTTP_204_NO_CONTENT)
async def update_driver_location(
    driver_id: str,
    location: LocationUpdate,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Update driver's real-time location.

    This endpoint receives location updates from the driver's mobile app
    and broadcasts them to company users via WebSocket for real-time tracking.
    """
    from datetime import datetime

    # Verify driver exists and belongs to user's company
    service = DriverService(db)
    try:
        # Verify driver belongs to user's company
        await service._get_driver(current_user.company_id, driver_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")

    # Broadcast location update via WebSocket
    await websocket.broadcast_location_update(
        driver_id=driver_id,
        company_id=current_user.company_id,
        location_data={
            "latitude": location.latitude,
            "longitude": location.longitude,
            "speed": location.speed,
            "heading": location.heading,
            "accuracy": location.accuracy,
            "altitude": location.altitude,
            "timestamp": (location.timestamp or datetime.utcnow()).isoformat(),
            "load_id": location.load_id,
        }
    )

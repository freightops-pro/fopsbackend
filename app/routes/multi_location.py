from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.config.db import get_db
from app.routes.user import get_current_user
from app.models.userModels import Users
from app.schema.multi_location import (
    LocationCreate, LocationUpdate, LocationResponse,
    LocationUserCreate, LocationUserResponse,
    LocationEquipmentCreate, LocationEquipmentResponse,
    InterLocationTransferCreate, InterLocationTransferResponse,
    LocationFinancialsResponse
)
from app.services.multi_location_service import MultiLocationService

router = APIRouter(prefix="/api/locations", tags=["multi-location"])

def get_current_company_id(current_user: Users = Depends(get_current_user)) -> int:
    """Get current user's company ID"""
    return current_user.company_id

@router.get("/", response_model=List[LocationResponse])
async def get_locations(
    include_inactive: bool = False,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all locations for the company"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    service = MultiLocationService(db)
    locations = await service.get_locations(company_id, include_inactive)
    
    return locations

@router.post("/", response_model=LocationResponse)
async def create_location(
    location_data: LocationCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create a new location"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    # Check if user has permission to create locations
    if current_user.role not in ['admin', 'manager']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create locations"
        )
    
    service = MultiLocationService(db)
    location = await service.create_location(company_id, location_data)
    
    return location

@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get a specific location"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    service = MultiLocationService(db)
    location = await service.get_location(location_id, company_id)
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    return location

@router.put("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: int,
    location_data: LocationUpdate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Update a location"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    # Check if user has permission to update locations
    if current_user.role not in ['admin', 'manager']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update locations"
        )
    
    service = MultiLocationService(db)
    
    try:
        location = await service.update_location(location_id, company_id, location_data)
        return location
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.delete("/{location_id}")
async def delete_location(
    location_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Delete a location"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    # Check if user has permission to delete locations
    if current_user.role not in ['admin', 'manager']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete locations"
        )
    
    service = MultiLocationService(db)
    
    try:
        success = await service.delete_location(location_id, company_id)
        if success:
            return {"message": "Location deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete location"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Location User Management Endpoints

@router.post("/{location_id}/users", response_model=LocationUserResponse)
async def assign_user_to_location(
    location_id: int,
    user_data: LocationUserCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Assign a user to a location"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    # Check if user has permission to assign users
    if current_user.role not in ['admin', 'manager']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to assign users to locations"
        )
    
    service = MultiLocationService(db)
    
    try:
        location_user = await service.assign_user_to_location(
            location_id=location_id,
            user_id=user_data.user_id,
            company_id=company_id,
            permissions=user_data
        )
        return location_user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/users/{user_id}", response_model=List[LocationUserResponse])
async def get_user_locations(
    user_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all locations accessible by a user"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    # Users can only view their own locations unless they're admin/manager
    if current_user.id != user_id and current_user.role not in ['admin', 'manager']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view other users' locations"
        )
    
    service = MultiLocationService(db)
    locations = await service.get_user_locations(user_id, company_id)
    
    return locations

@router.delete("/{location_id}/users/{user_id}")
async def remove_user_from_location(
    location_id: int,
    user_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Remove user access to a location"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    # Check if user has permission to remove users
    if current_user.role not in ['admin', 'manager']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to remove users from locations"
        )
    
    service = MultiLocationService(db)
    
    success = await service.remove_user_from_location(location_id, user_id, company_id)
    
    if success:
        return {"message": "User removed from location successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in location"
        )

# Location Equipment Management Endpoints

@router.post("/{location_id}/equipment", response_model=LocationEquipmentResponse)
async def assign_equipment_to_location(
    location_id: int,
    equipment_data: LocationEquipmentCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Assign equipment to a location"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    # Check if user has permission to assign equipment
    if current_user.role not in ['admin', 'manager', 'dispatcher']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to assign equipment"
        )
    
    service = MultiLocationService(db)
    
    try:
        equipment = await service.assign_equipment_to_location(
            location_id=location_id,
            vehicle_id=equipment_data.vehicle_id,
            company_id=company_id,
            assignment_data=equipment_data
        )
        return equipment
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{location_id}/equipment", response_model=List[LocationEquipmentResponse])
async def get_location_equipment(
    location_id: int,
    include_inactive: bool = False,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all equipment assigned to a location"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    service = MultiLocationService(db)
    equipment = await service.get_location_equipment(location_id, company_id, include_inactive)
    
    return equipment

@router.delete("/{location_id}/equipment/{vehicle_id}")
async def remove_equipment_from_location(
    location_id: int,
    vehicle_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Remove equipment from location"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    # Check if user has permission to remove equipment
    if current_user.role not in ['admin', 'manager', 'dispatcher']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to remove equipment"
        )
    
    service = MultiLocationService(db)
    
    success = await service.remove_equipment_from_location(location_id, vehicle_id, company_id)
    
    if success:
        return {"message": "Equipment removed from location successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found in location"
        )

# Inter-Location Transfer Endpoints

@router.post("/transfers", response_model=InterLocationTransferResponse)
async def create_transfer(
    transfer_data: InterLocationTransferCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create an inter-location equipment transfer"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    # Check if user has permission to create transfers
    if current_user.role not in ['admin', 'manager', 'dispatcher']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create transfers"
        )
    
    service = MultiLocationService(db)
    
    try:
        transfer = await service.create_transfer(company_id, transfer_data)
        return transfer
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/transfers", response_model=List[InterLocationTransferResponse])
async def get_transfers(
    location_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get transfers for the company"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    service = MultiLocationService(db)
    transfers = await service.get_transfers(company_id, location_id, status)
    
    return transfers

@router.put("/transfers/{transfer_id}")
async def update_transfer_status(
    transfer_id: int,
    status: str,
    completed_date: Optional[str] = None,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Update transfer status"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    # Check if user has permission to update transfers
    if current_user.role not in ['admin', 'manager', 'dispatcher']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to update transfers"
        )
    
    service = MultiLocationService(db)
    
    try:
        from datetime import datetime
        completed_datetime = None
        if completed_date:
            completed_datetime = datetime.fromisoformat(completed_date.replace('Z', '+00:00'))
        
        transfer = await service.update_transfer_status(
            transfer_id=transfer_id,
            company_id=company_id,
            status=status,
            completed_date=completed_datetime
        )
        return transfer
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

# Analytics Endpoints

@router.get("/analytics")
async def get_location_analytics(
    period_days: int = 30,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get analytics across all locations"""
    
    # Check if user has Professional or Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-location management requires Professional or Enterprise subscription"
        )
    
    service = MultiLocationService(db)
    analytics = await service.get_location_analytics(company_id, period_days)
    
    return analytics

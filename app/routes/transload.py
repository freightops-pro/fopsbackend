from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.config.db import get_db
from app.routes.user import get_current_user
from app.models.userModels import Users
from app.schema.transload import (
    TransloadFacilityCreate,
    TransloadFacilityUpdate,
    TransloadFacilityResponse,
    TransloadOperationCreate,
    TransloadOperationUpdate,
    TransloadOperationResponse
)

router = APIRouter(prefix="/api/transload", tags=["transload"])
logger = logging.getLogger(__name__)

def get_current_company_id(current_user: Users = Depends(get_current_user)) -> int:
    """Get current user's company ID"""
    return current_user.company_id

@router.get("/facilities")
async def get_transload_facilities(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all transload facilities for a company"""
    if current_user.subscription_tier not in ["professional", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professional or Enterprise subscription required"
        )
    
    # Return empty array for now - facilities will be implemented later
    return []

@router.get("/operations")
async def get_transload_operations(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all transload operations for a company"""
    if current_user.subscription_tier not in ["professional", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professional or Enterprise subscription required"
        )
    
    # Return empty array for now - operations will be implemented later
    return []

@router.post("/operations")
async def create_transload_operation(
    operation_data: TransloadOperationCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create a new transload operation"""
    if current_user.subscription_tier not in ["professional", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professional or Enterprise subscription required"
        )
    
    # Return success for now - operation creation will be implemented later
    return {
        "id": 1,
        "facility_id": operation_data.facility_id,
        "facility_name": "Sample Facility",
        "inbound_load_id": operation_data.inbound_load_id,
        "start_time": operation_data.start_time,
        "status": operation_data.status
    }

@router.post("/facilities")
async def create_transload_facility(
    facility_data: TransloadFacilityCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create a new transload facility"""
    if current_user.subscription_tier not in ["professional", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professional or Enterprise subscription required"
        )
    
    # Return success for now - facility creation will be implemented later
    return {
        "id": 1,
        "name": facility_data.name,
        "location": facility_data.location,
        "capacity": facility_data.capacity
    }

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.config.db import get_db
from app.routes.user import get_current_user
from app.models.load_leg import LoadLeg, TransloadOperation, TransloadFacility
from app.models.simple_load import SimpleLoad
from app.models.userModels import Users
from app.schema.multi_leg import (
    LoadLegCreate,
    LoadLegResponse,
    LoadLegUpdate,
    TransloadOperationCreate,
    TransloadOperationResponse,
    TransloadFacilityCreate,
    TransloadFacilityResponse,
    MultiLegLoadCreate,
    MultiLegLoadResponse
)
from app.services.leg_coordination import LegCoordinationService

router = APIRouter(prefix="/api/multi-leg", tags=["multi-leg"])

def get_current_company_id(current_user: Users = Depends(get_current_user)) -> int:
    """Get current user's company ID"""
    return current_user.company_id

@router.post("/loads", response_model=MultiLegLoadResponse)
async def create_multi_leg_load(
    load_data: MultiLegLoadCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create a new multi-leg load with multiple legs"""
    
    # Verify user has Pro/Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-leg dispatch is only available for Professional and Enterprise subscribers"
        )
    
    try:
        # Create the main load
        main_load = SimpleLoad(
            company_id=company_id,
            customer_name=load_data.customer_name,
            reference_number=load_data.reference_number,
            pickup_location=load_data.legs[0].origin if load_data.legs else "",
            delivery_location=load_data.legs[-1].destination if load_data.legs else "",
            pickup_date=load_data.legs[0].pickup_time if load_data.legs else None,
            delivery_date=load_data.legs[-1].delivery_time if load_data.legs else None,
            rate=load_data.total_rate,
            is_multi_leg=True,
            status="planning"
        )
        
        db.add(main_load)
        db.commit()
        db.refresh(main_load)
        
        # Create individual legs
        legs = []
        for i, leg_data in enumerate(load_data.legs):
            leg = LoadLeg(
                company_id=company_id,
                load_id=main_load.id,
                leg_number=i + 1,
                origin=leg_data.origin,
                destination=leg_data.destination,
                handoff_location=leg_data.handoff_location,
                pickup_time=leg_data.pickup_time,
                delivery_time=leg_data.delivery_time,
                equipment_type=leg_data.equipment_type,
                leg_rate=leg_data.leg_rate,
                driver_pay=leg_data.driver_pay,
                notes=leg_data.notes,
                special_instructions=leg_data.special_instructions
            )
            
            db.add(leg)
            legs.append(leg)
        
        db.commit()
        
        # Initialize leg coordination service
        coordination_service = LegCoordinationService(db)
        
        # Return the created multi-leg load
        return MultiLegLoadResponse(
            id=main_load.id,
            customer_name=main_load.customer_name,
            reference_number=main_load.reference_number,
            total_rate=load_data.total_rate,
            legs=[LoadLegResponse.from_orm(leg) for leg in legs],
            status=main_load.status,
            created_at=main_load.created_at
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create multi-leg load: {str(e)}"
        )

@router.get("/loads/{load_id}/legs", response_model=List[LoadLegResponse])
async def get_load_legs(
    load_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all legs for a specific load"""
    
    # Verify user has Pro/Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-leg dispatch is only available for Professional and Enterprise subscribers"
        )
    
    legs = db.query(LoadLeg).filter(
        LoadLeg.company_id == company_id,
        LoadLeg.load_id == load_id
    ).order_by(LoadLeg.leg_number).all()
    
    return [LoadLegResponse.from_orm(leg) for leg in legs]

@router.put("/legs/{leg_id}/assign-driver")
async def assign_driver_to_leg(
    leg_id: int,
    driver_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Assign a driver to a specific leg"""
    
    # Verify user has Pro/Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-leg dispatch is only available for Professional and Enterprise subscribers"
        )
    
    # Get the leg
    leg = db.query(LoadLeg).filter(
        LoadLeg.id == leg_id,
        LoadLeg.company_id == company_id
    ).first()
    
    if not leg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Load leg not found"
        )
    
    # Verify driver exists and belongs to company
    driver = db.query(User).filter(
        User.id == driver_id,
        User.company_id == company_id,
        User.role == "driver"
    ).first()
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Update the leg
    leg.driver_id = driver_id
    leg.status = "assigned"
    leg.assigned_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": f"Driver {driver.first_name} {driver.last_name} assigned to leg {leg.leg_number}",
        "leg_id": leg_id,
        "driver_id": driver_id,
        "assigned_at": leg.assigned_at
    }

@router.put("/legs/{leg_id}/update-status")
async def update_leg_status(
    leg_id: int,
    status: str,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Update the status of a specific leg"""
    
    # Verify user has Pro/Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-leg dispatch is only available for Professional and Enterprise subscribers"
        )
    
    valid_statuses = ["pending", "assigned", "in_progress", "completed", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    # Get the leg
    leg = db.query(LoadLeg).filter(
        LoadLeg.id == leg_id,
        LoadLeg.company_id == company_id
    ).first()
    
    if not leg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Load leg not found"
        )
    
    # Update status and timestamps
    leg.status = status
    leg.updated_at = datetime.utcnow()
    
    if status == "in_progress":
        leg.actual_pickup_time = datetime.utcnow()
    elif status == "completed":
        leg.actual_delivery_time = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": f"Leg {leg.leg_number} status updated to {status}",
        "leg_id": leg_id,
        "status": status,
        "updated_at": leg.updated_at
    }

@router.post("/transload-operations", response_model=TransloadOperationResponse)
async def create_transload_operation(
    operation_data: TransloadOperationCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create a new transload operation"""
    
    # Verify user has Pro/Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Transloading operations are only available for Professional and Enterprise subscribers"
        )
    
    try:
        operation = TransloadOperation(
            company_id=company_id,
            load_id=operation_data.load_id,
            facility_id=operation_data.facility_id,
            facility_name=operation_data.facility_name,
            facility_location=operation_data.facility_location,
            operation_type=operation_data.operation_type,
            dock_door=operation_data.dock_door,
            inbound_leg_id=operation_data.inbound_leg_id,
            outbound_leg_id=operation_data.outbound_leg_id,
            scheduled_start=operation_data.scheduled_start,
            scheduled_end=operation_data.scheduled_end,
            labor_assigned=operation_data.labor_assigned,
            equipment_staged=operation_data.equipment_staged,
            handling_cost=operation_data.handling_cost,
            storage_cost=operation_data.storage_cost,
            notes=operation_data.notes
        )
        
        db.add(operation)
        db.commit()
        db.refresh(operation)
        
        return TransloadOperationResponse.from_orm(operation)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create transload operation: {str(e)}"
        )

@router.get("/transload-facilities", response_model=List[TransloadFacilityResponse])
async def get_transload_facilities(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all transload facilities for the company"""
    
    # Verify user has Pro/Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Transloading operations are only available for Professional and Enterprise subscribers"
        )
    
    facilities = db.query(TransloadFacility).filter(
        TransloadFacility.company_id == company_id,
        TransloadFacility.is_active == True
    ).all()
    
    return [TransloadFacilityResponse.from_orm(facility) for facility in facilities]

@router.post("/transload-facilities", response_model=TransloadFacilityResponse)
async def create_transload_facility(
    facility_data: TransloadFacilityCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create a new transload facility"""
    
    # Verify user has Pro/Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Transloading operations are only available for Professional and Enterprise subscribers"
        )
    
    try:
        facility = TransloadFacility(
            company_id=company_id,
            name=facility_data.name,
            location=facility_data.location,
            address=facility_data.address,
            capacity=facility_data.capacity,
            dock_doors=facility_data.dock_doors,
            contact_name=facility_data.contact_name,
            contact_phone=facility_data.contact_phone,
            contact_email=facility_data.contact_email,
            services=facility_data.services,
            operating_hours=facility_data.operating_hours
        )
        
        db.add(facility)
        db.commit()
        db.refresh(facility)
        
        return TransloadFacilityResponse.from_orm(facility)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create transload facility: {str(e)}"
        )

@router.get("/loads/{load_id}/coordination-status")
async def get_load_coordination_status(
    load_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get coordination status for a multi-leg load"""
    
    # Verify user has Pro/Enterprise access
    if current_user.subscription_tier not in ['professional', 'enterprise']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-leg dispatch is only available for Professional and Enterprise subscribers"
        )
    
    coordination_service = LegCoordinationService(db)
    status = coordination_service.get_load_coordination_status(load_id, company_id)
    
    return status

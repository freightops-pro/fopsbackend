from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.config.db import get_db
from app.models.userModels import Equipment, EquipmentCreate, EquipmentUpdate, EquipmentResponse, Users
from app.config.settings import settings
from app.routes.user import get_current_user
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/equipment", tags=["Equipment"])

# Helper function to get company ID from current user
def get_company_id_from_user(current_user: Users) -> str:
    """Extract company ID from authenticated user"""
    if not current_user.companyid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not associated with a company"
        )
    return current_user.companyid

@router.post("/equipment", response_model=EquipmentResponse, status_code=status.HTTP_201_CREATED)
def create_equipment(
    equipment: EquipmentCreate, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Create new equipment (truck or trailer)
    """
    try:
        # Check if equipment number already exists
        existing_equipment = db.query(Equipment).filter(
            Equipment.equipmentNumber == equipment.equipmentNumber
        ).first()
        
        if existing_equipment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Equipment number already exists"
            )
        
        # Check if VIN already exists
        existing_vin = db.query(Equipment).filter(
            Equipment.vinNumber == equipment.vinNumber
        ).first()
        
        if existing_vin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="VIN number already exists"
            )
        
        # Create new equipment
        company_id = get_company_id_from_user(current_user)
        db_equipment = Equipment(
            id=str(uuid.uuid4()),
            companyId=company_id,
            equipmentNumber=equipment.equipmentNumber,
            equipmentType=equipment.equipmentType,
            make=equipment.make,
            model=equipment.model,
            year=equipment.year,
            vinNumber=equipment.vinNumber,
            plateNumber=equipment.plateNumber,
            currentMileage=equipment.currentMileage,
            engineType=equipment.engineType,
            fuelType=equipment.fuelType,
            eldProvider=equipment.eldProvider,
            eldDeviceId=equipment.eldDeviceId,
            trailerType=equipment.trailerType,
            trailerLength=equipment.trailerLength,
            maxWeight=equipment.maxWeight,
            registrationState=equipment.registrationState,
            registrationExpiry=equipment.registrationExpiry,
            insuranceProvider=equipment.insuranceProvider,
            insurancePolicyNumber=equipment.insurancePolicyNumber,
            insuranceExpiry=equipment.insuranceExpiry,
            dotNumber=equipment.dotNumber,
            mcNumber=equipment.mcNumber,
            purchasePrice=equipment.purchasePrice,
            monthlyPayment=equipment.monthlyPayment,
            assignedDriverId=equipment.assignedDriverId,
            homeTerminal=equipment.homeTerminal,
            operationalStatus=equipment.operationalStatus,
            specialFeatures=equipment.specialFeatures,
            additionalNotes=equipment.additionalNotes,
            status=equipment.status,
            currentLocation=equipment.currentLocation,
            createdAt=datetime.utcnow(),
            updatedAt=datetime.utcnow(),
            isActive=True
        )
        
        db.add(db_equipment)
        db.commit()
        db.refresh(db_equipment)
        
        return db_equipment
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create equipment: {str(e)}"
        )

@router.get("/equipment", response_model=List[EquipmentResponse])
def get_all_equipment(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Get all equipment for the company
    """
    try:
        company_id = get_company_id_from_user(current_user)
        equipment = db.query(Equipment).filter(
            Equipment.companyId == company_id,
            Equipment.isActive == True
        ).all()
        
        return equipment
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch equipment: {str(e)}"
        )

@router.get("/equipment/{equipment_id}", response_model=EquipmentResponse)
def get_equipment(
    equipment_id: str, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Get specific equipment by ID
    """
    try:
        company_id = get_company_id_from_user(current_user)
        equipment = db.query(Equipment).filter(
            Equipment.id == equipment_id,
            Equipment.companyId == company_id,
            Equipment.isActive == True
        ).first()
        
        if not equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipment not found"
            )
        
        return equipment
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch equipment: {str(e)}"
        )

@router.put("/equipment/{equipment_id}", response_model=EquipmentResponse)
def update_equipment(
    equipment_id: str, 
    equipment_update: EquipmentUpdate, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Update equipment information
    """
    try:
        company_id = get_company_id_from_user(current_user)
        db_equipment = db.query(Equipment).filter(
            Equipment.id == equipment_id,
            Equipment.companyId == company_id,
            Equipment.isActive == True
        ).first()
        
        if not db_equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipment not found"
            )
        
        # Update fields if provided
        update_data = equipment_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_equipment, field, value)
        
        db_equipment.updatedAt = datetime.utcnow()
        
        db.commit()
        db.refresh(db_equipment)
        
        return db_equipment
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update equipment: {str(e)}"
        )

@router.delete("/equipment/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_equipment(
    equipment_id: str, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Soft delete equipment (set isActive to False)
    """
    try:
        company_id = get_company_id_from_user(current_user)
        db_equipment = db.query(Equipment).filter(
            Equipment.id == equipment_id,
            Equipment.companyId == company_id,
            Equipment.isActive == True
        ).first()
        
        if not db_equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipment not found"
            )
        
        # Soft delete
        db_equipment.isActive = False
        db_equipment.updatedAt = datetime.utcnow()
        
        db.commit()
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete equipment: {str(e)}"
        )

@router.get("/equipment/type/{equipment_type}", response_model=List[EquipmentResponse])
def get_equipment_by_type(
    equipment_type: str, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Get equipment by type (truck, trailer, etc.)
    """
    try:
        company_id = get_company_id_from_user(current_user)
        equipment = db.query(Equipment).filter(
            Equipment.companyId == company_id,
            Equipment.equipmentType == equipment_type,
            Equipment.isActive == True
        ).all()
        
        return equipment
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch equipment by type: {str(e)}"
        )

@router.get("/equipment/status/{status}", response_model=List[EquipmentResponse])
def get_equipment_by_status(
    status: str, 
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Get equipment by status (available, in_transit, maintenance, out_of_service)
    """
    try:
        company_id = get_company_id_from_user(current_user)
        equipment = db.query(Equipment).filter(
            Equipment.companyId == company_id,
            Equipment.status == status,
            Equipment.isActive == True
        ).all()
        
        return equipment
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch equipment by status: {str(e)}"
        )

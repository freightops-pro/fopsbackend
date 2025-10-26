from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging

from app.models.simple_load import SimpleLoad
from app.schema.truckAssignmentSchema import (
    TruckAssignmentRequest,
    DriverConfirmationRequest,
    TrailerSetupRequest,
    TruckConfirmationRequest,
    AvailableTruck
)

logger = logging.getLogger(__name__)


def get_truck_assignment_status(db: Session, load_id: str, company_id: str) -> Optional[Dict[str, Any]]:
    """
    Get current truck assignment status for a load.
    
    Args:
        db: Database session
        load_id: The load ID
        company_id: Company ID for multi-tenant isolation
        
    Returns:
        Truck assignment status dict or None if not found
    """
    load = db.query(SimpleLoad).filter(
        SimpleLoad.id == load_id,
        SimpleLoad.companyId == company_id
    ).first()
    if not load:
        return None
    
    # Get trailer info from meta
    trailer_number = None
    has_trailer = None
    if load.meta:
        trailer_number = load.meta.get("trailer_number")
        has_trailer = load.meta.get("has_trailer")
    
    return {
        "loadId": load_id,
        "truckAssignmentStatus": load.truckAssignmentStatus,
        "assignedTruckId": load.assignedTruckId,
        "assignedDriverId": load.assignedDriverId,
        "truckAssignmentTime": load.truckAssignmentTime,
        "driverConfirmationTime": load.driverConfirmationTime,
        "trailerSetupTime": load.trailerSetupTime,
        "truckConfirmationTime": load.truckConfirmationTime,
        "trailerNumber": trailer_number,
        "hasTrailer": has_trailer
    }


def get_available_trucks(db: Session, company_id: str) -> List[AvailableTruck]:
    """Get available trucks for a company (real-time)"""
    # This is a placeholder implementation
    # In a real system, you would query the trucks table
    # For now, return mock data
    available_trucks = [
        AvailableTruck(
            id="truck-001",
            truckNumber="TRK-001",
            make="Freightliner",
            model="Cascadia",
            year=2022,
            status="available",
            location="Main Yard"
        ),
        AvailableTruck(
            id="truck-002",
            truckNumber="TRK-002",
            make="Peterbilt",
            model="579",
            year=2021,
            status="available",
            location="Main Yard"
        ),
        AvailableTruck(
            id="truck-003",
            truckNumber="TRK-003",
            make="Volvo",
            model="VNL",
            year=2023,
            status="available",
            location="Main Yard"
        )
    ]
    return available_trucks


def assign_truck(
    db: Session, 
    load_id: str, 
    assignment_data: TruckAssignmentRequest,
    company_id: str
) -> Dict[str, Any]:
    """
    Assign truck to load.
    
    Args:
        db: Database session
        load_id: The load ID
        assignment_data: Truck assignment details
        company_id: Company ID for multi-tenant isolation
        
    Returns:
        Assignment result
        
    Raises:
        ValueError: Load not found or invalid status
    """
    load = db.query(SimpleLoad).filter(
        SimpleLoad.id == load_id,
        SimpleLoad.companyId == company_id
    ).first()
    if not load:
        raise ValueError("Load not found")
    
    if load.truckAssignmentStatus != "truck_assignment_required":
        raise ValueError(f"Cannot assign truck from status: {load.truckAssignmentStatus}")
    
    load.assignedTruckId = assignment_data.truckId
    load.truckAssignmentStatus = "truck_assigned"
    load.truckAssignmentTime = assignment_data.timestamp or datetime.utcnow()
    
    db.commit()
    db.refresh(load)
    
    logger.info(f"Truck {assignment_data.truckId} assigned to load {load_id}")
    
    return {
        "success": True,
        "message": "Truck assigned successfully",
        "newStatus": "truck_assigned",
        "timestamp": load.truckAssignmentTime
    }


def confirm_driver(
    db: Session, 
    load_id: str, 
    confirmation_data: DriverConfirmationRequest,
    company_id: str
) -> Dict[str, Any]:
    """
    Confirm driver is driving the assigned truck.
    
    Args:
        db: Database session
        load_id: The load ID
        confirmation_data: Driver confirmation details
        company_id: Company ID for multi-tenant isolation
        
    Returns:
        Confirmation result
        
    Raises:
        ValueError: Load not found or invalid status
    """
    load = db.query(SimpleLoad).filter(
        SimpleLoad.id == load_id,
        SimpleLoad.companyId == company_id
    ).first()
    if not load:
        raise ValueError("Load not found")
    
    if load.truckAssignmentStatus != "truck_assigned":
        raise ValueError(f"Cannot confirm driver from status: {load.truckAssignmentStatus}")
    
    if not confirmation_data.isDrivingAssignedTruck:
        raise ValueError("Driver must be driving the assigned truck to proceed")
    
    load.truckAssignmentStatus = "driver_confirmed"
    load.driverConfirmationTime = confirmation_data.timestamp or datetime.utcnow()
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Driver confirmation successful",
        "newStatus": "driver_confirmed",
        "timestamp": load.driverConfirmationTime
    }


def setup_trailer(
    db: Session, 
    load_id: str, 
    trailer_data: TrailerSetupRequest,
    company_id: str
) -> Dict[str, Any]:
    """
    Set up trailer information.
    
    Args:
        db: Database session
        load_id: The load ID
        trailer_data: Trailer setup details
        company_id: Company ID for multi-tenant isolation
        
    Returns:
        Setup result
        
    Raises:
        ValueError: Load not found or invalid status
    """
    load = db.query(SimpleLoad).filter(
        SimpleLoad.id == load_id,
        SimpleLoad.companyId == company_id
    ).first()
    if not load:
        raise ValueError("Load not found")
    
    if load.truckAssignmentStatus != "driver_confirmed":
        raise ValueError(f"Cannot setup trailer from status: {load.truckAssignmentStatus}")
    
    load.truckAssignmentStatus = "trailer_set"
    load.trailerSetupTime = trailer_data.timestamp or datetime.utcnow()
    
    # Store trailer info in meta
    meta = load.meta or {}
    meta["has_trailer"] = trailer_data.hasTrailer
    if trailer_data.hasTrailer and trailer_data.trailerNumber:
        meta["trailer_number"] = trailer_data.trailerNumber
    load.meta = meta
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Trailer setup completed",
        "newStatus": "trailer_set",
        "timestamp": load.trailerSetupTime
    }


def confirm_truck(
    db: Session, 
    load_id: str, 
    confirmation_data: TruckConfirmationRequest,
    company_id: str
) -> Dict[str, Any]:
    """
    Final truck confirmation.
    
    Args:
        db: Database session
        load_id: The load ID
        confirmation_data: Truck confirmation details
        company_id: Company ID for multi-tenant isolation
        
    Returns:
        Confirmation result
        
    Raises:
        ValueError: Load not found or invalid status
    """
    load = db.query(SimpleLoad).filter(
        SimpleLoad.id == load_id,
        SimpleLoad.companyId == company_id
    ).first()
    if not load:
        raise ValueError("Load not found")
    
    if load.truckAssignmentStatus != "trailer_set":
        raise ValueError(f"Cannot confirm truck from status: {load.truckAssignmentStatus}")
    
    load.truckAssignmentStatus = "truck_confirmed"
    load.truckConfirmationTime = confirmation_data.timestamp or datetime.utcnow()
    
    # Update main status to ready for pickup
    load.status = "ready_for_pickup"
    
    db.commit()
    db.refresh(load)
    
    logger.info(f"Truck confirmed for load {load_id}")
    
    return {
        "success": True,
        "message": "Truck confirmation completed",
        "newStatus": "truck_confirmed",
        "timestamp": load.truckConfirmationTime
    }


def is_truck_assignment_complete(db: Session, load_id: str, company_id: str) -> bool:
    """
    Check if truck assignment is complete and pickup can start.
    
    Args:
        db: Database session
        load_id: The load ID
        company_id: Company ID for multi-tenant isolation
        
    Returns:
        True if truck assignment is complete
    """
    load = db.query(SimpleLoad).filter(
        SimpleLoad.id == load_id,
        SimpleLoad.companyId == company_id
    ).first()
    if not load:
        return False
    
    return load.truckAssignmentStatus == "truck_confirmed"

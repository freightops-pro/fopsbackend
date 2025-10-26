from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any
from app.models.simple_load import SimpleLoad
from app.schema.pickupSchema import (
    PickupNavigationRequest,
    PickupArrivalRequest,
    TrailerConfirmationRequest,
    ContainerConfirmationRequest,
    PickupConfirmationRequest,
    DepartureRequest
)


def get_pickup_status(db: Session, load_id: str) -> Optional[Dict[str, Any]]:
    """Get current pickup status for a load"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        return None
    
    return {
        "loadId": load_id,
        "pickupStatus": load.pickupStatus,
        "navigationStartTime": load.navigationStartTime,
        "pickupArrivalTime": load.pickupArrivalTime,
        "trailerConfirmationTime": load.trailerConfirmationTime,
        "containerConfirmationTime": load.containerConfirmationTime,
        "pickupConfirmationTime": load.pickupConfirmationTime,
        "departureTime": load.departureTime,
        "billOfLadingUrl": load.billOfLadingUrl,
        "pickupNotes": load.pickupNotes,
        "pickupLocation": load.pickupLocation,
        "deliveryLocation": load.deliveryLocation
    }


def start_pickup_navigation(
    db: Session, 
    load_id: str, 
    navigation_data: PickupNavigationRequest
) -> Dict[str, Any]:
    """Start navigation to pickup location"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise ValueError("Load not found")
    
    # Check if truck assignment is complete
    if load.truckAssignmentStatus != "truck_confirmed":
        raise ValueError(f"Cannot start pickup navigation. Truck assignment status: {load.truckAssignmentStatus}")
    
    if load.pickupStatus not in ["pending"]:
        raise ValueError(f"Cannot start navigation from status: {load.pickupStatus}")
    
    load.pickupStatus = "navigation"
    load.navigationStartTime = navigation_data.timestamp or datetime.utcnow()
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Navigation started successfully",
        "newStatus": "navigation",
        "timestamp": load.navigationStartTime
    }


def mark_pickup_arrival(
    db: Session, 
    load_id: str, 
    arrival_data: PickupArrivalRequest
) -> Dict[str, Any]:
    """Mark arrival at pickup location"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise ValueError("Load not found")
    
    if load.pickupStatus not in ["navigation"]:
        raise ValueError(f"Cannot mark arrival from status: {load.pickupStatus}")
    
    load.pickupStatus = "arrived"
    load.pickupArrivalTime = arrival_data.timestamp or datetime.utcnow()
    
    # Store geofence data in meta
    if arrival_data.latitude and arrival_data.longitude:
        meta = load.meta or {}
        meta["pickup_arrival_location"] = {
            "latitude": arrival_data.latitude,
            "longitude": arrival_data.longitude,
            "geofenceStatus": arrival_data.geofenceStatus
        }
        load.meta = meta
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Arrival at pickup location confirmed",
        "newStatus": "arrived",
        "timestamp": load.pickupArrivalTime
    }


def confirm_trailer(
    db: Session, 
    load_id: str, 
    trailer_data: TrailerConfirmationRequest
) -> Dict[str, Any]:
    """Confirm trailer for pickup"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise ValueError("Load not found")
    
    if load.pickupStatus not in ["arrived"]:
        raise ValueError(f"Cannot confirm trailer from status: {load.pickupStatus}")
    
    load.pickupStatus = "trailer_confirmed"
    load.trailerConfirmationTime = trailer_data.timestamp or datetime.utcnow()
    
    if trailer_data.trailerNumber:
        meta = load.meta or {}
        meta["trailer_number"] = trailer_data.trailerNumber
        load.meta = meta
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Trailer confirmed successfully",
        "newStatus": "trailer_confirmed",
        "timestamp": load.trailerConfirmationTime
    }


def confirm_container(
    db: Session, 
    load_id: str, 
    container_data: ContainerConfirmationRequest
) -> Dict[str, Any]:
    """Confirm container for pickup"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise ValueError("Load not found")
    
    if load.pickupStatus not in ["trailer_confirmed"]:
        raise ValueError(f"Cannot confirm container from status: {load.pickupStatus}")
    
    load.pickupStatus = "container_confirmed"
    load.containerConfirmationTime = container_data.timestamp or datetime.utcnow()
    
    if container_data.containerNumber:
        meta = load.meta or {}
        meta["container_number"] = container_data.containerNumber
        load.meta = meta
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Container confirmed successfully",
        "newStatus": "container_confirmed",
        "timestamp": load.containerConfirmationTime
    }


def confirm_pickup(
    db: Session, 
    load_id: str, 
    pickup_data: PickupConfirmationRequest
) -> Dict[str, Any]:
    """Confirm final pickup completion"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise ValueError("Load not found")
    
    if load.pickupStatus not in ["container_confirmed", "trailer_confirmed"]:
        raise ValueError(f"Cannot confirm pickup from status: {load.pickupStatus}")
    
    load.pickupStatus = "pickup_confirmed"
    load.pickupConfirmationTime = pickup_data.timestamp or datetime.utcnow()
    load.pickupNotes = pickup_data.pickupNotes
    load.status = "picked_up"
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Pickup confirmed successfully",
        "newStatus": "pickup_confirmed",
        "timestamp": load.pickupConfirmationTime
    }


def mark_departure(
    db: Session, 
    load_id: str, 
    departure_data: DepartureRequest
) -> Dict[str, Any]:
    """Mark departure from pickup location"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise ValueError("Load not found")
    
    if load.pickupStatus not in ["pickup_confirmed"]:
        raise ValueError(f"Cannot mark departure from status: {load.pickupStatus}")
    
    load.pickupStatus = "departed"
    load.departureTime = departure_data.timestamp or datetime.utcnow()
    load.status = "in_transit"
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Departure confirmed successfully",
        "newStatus": "departed",
        "timestamp": load.departureTime
    }

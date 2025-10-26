from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any
from app.models.simple_load import SimpleLoad
from app.schema.deliverySchema import (
    DeliveryArrivalRequest,
    DeliveryDockingRequest,
    DeliveryUnloadingRequest,
    DeliveryConfirmationRequest
)


def get_delivery_status(db: Session, load_id: str) -> Optional[Dict[str, Any]]:
    """Get current delivery status for a load"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        return None
    
    return {
        "loadId": load_id,
        "deliveryStatus": load.deliveryStatus,
        "arrivalTime": load.arrivalTime,
        "dockingTime": load.dockingTime,
        "unloadingStartTime": load.unloadingStartTime,
        "unloadingEndTime": load.unloadingEndTime,
        "deliveryTime": load.deliveryTime,
        "recipientName": load.recipientName,
        "deliveryNotes": load.deliveryNotes
    }


def update_delivery_arrival(
    db: Session, 
    load_id: str, 
    arrival_data: DeliveryArrivalRequest
) -> Dict[str, Any]:
    """Update delivery status to arrived"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise ValueError("Load not found")
    
    # Validate status transition - allow from in_transit or if status is None
    if load.deliveryStatus not in ["in_transit", None]:
        raise ValueError(f"Cannot mark as arrived from status: {load.deliveryStatus}")
    
    # Update load
    load.deliveryStatus = "arrived"
    load.arrivalTime = arrival_data.timestamp or datetime.utcnow()
    
    # Update meta with geofence data if provided
    if arrival_data.latitude and arrival_data.longitude:
        meta = load.meta or {}
        meta["arrival_location"] = {
            "latitude": arrival_data.latitude,
            "longitude": arrival_data.longitude,
            "geofenceStatus": arrival_data.geofenceStatus
        }
        load.meta = meta
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Arrival confirmed successfully",
        "newStatus": "arrived",
        "timestamp": load.arrivalTime
    }


def update_delivery_docking(
    db: Session, 
    load_id: str, 
    docking_data: DeliveryDockingRequest
) -> Dict[str, Any]:
    """Update delivery status to docked"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise ValueError("Load not found")
    
    # Validate status transition
    if load.deliveryStatus not in ["arrived"]:
        raise ValueError(f"Cannot mark as docked from status: {load.deliveryStatus}")
    
    # Update load
    load.deliveryStatus = "docked"
    load.dockingTime = docking_data.timestamp or datetime.utcnow()
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Docking confirmed successfully",
        "newStatus": "docked",
        "timestamp": load.dockingTime
    }


def update_delivery_unloading_start(
    db: Session, 
    load_id: str, 
    unloading_data: DeliveryUnloadingRequest
) -> Dict[str, Any]:
    """Update delivery status to unloading started"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise ValueError("Load not found")
    
    # Validate status transition - allow from docked or arrived
    if load.deliveryStatus not in ["docked", "arrived"]:
        raise ValueError(f"Cannot start unloading from status: {load.deliveryStatus}")
    
    # Update load
    load.deliveryStatus = "unloading"
    load.unloadingStartTime = unloading_data.timestamp or datetime.utcnow()
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Unloading started successfully",
        "newStatus": "unloading",
        "timestamp": load.unloadingStartTime
    }


def update_delivery_unloading_complete(
    db: Session, 
    load_id: str, 
    unloading_data: DeliveryUnloadingRequest
) -> Dict[str, Any]:
    """Update delivery status to unloading completed"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise ValueError("Load not found")
    
    # Validate status transition
    if load.deliveryStatus not in ["unloading"]:
        raise ValueError(f"Cannot complete unloading from status: {load.deliveryStatus}")
    
    # Update load
    load.deliveryStatus = "unloading_complete"
    load.unloadingEndTime = unloading_data.timestamp or datetime.utcnow()
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Unloading completed successfully",
        "newStatus": "unloading_complete",
        "timestamp": load.unloadingEndTime
    }


def confirm_delivery(
    db: Session, 
    load_id: str, 
    confirmation_data: DeliveryConfirmationRequest
) -> Dict[str, Any]:
    """Confirm final delivery"""
    load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
    if not load:
        raise ValueError("Load not found")
    
    # Validate status transition - allow from unloading_complete, unloading, or arrived
    if load.deliveryStatus not in ["unloading_complete", "unloading", "arrived"]:
        raise ValueError(f"Cannot confirm delivery from status: {load.deliveryStatus}")
    
    # Update load
    load.deliveryStatus = "delivered"
    load.deliveryTime = confirmation_data.deliveryTimestamp or datetime.utcnow()
    load.recipientName = confirmation_data.recipientName
    load.deliveryNotes = confirmation_data.deliveryNotes
    
    # Update main status as well
    load.status = "delivered"
    
    db.commit()
    db.refresh(load)
    
    return {
        "success": True,
        "message": "Delivery confirmed successfully",
        "newStatus": "delivered",
        "timestamp": load.deliveryTime
    }


def validate_delivery_status_transition(current_status: str, new_status: str) -> bool:
    """Validate if a status transition is allowed"""
    valid_transitions = {
        "in_transit": ["arrived"],
        "arrived": ["docked"],
        "docked": ["unloading"],
        "unloading": ["unloading_complete", "delivered"],
        "unloading_complete": ["delivered"]
    }
    
    return new_status in valid_transitions.get(current_status, [])

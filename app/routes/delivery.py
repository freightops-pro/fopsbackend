from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.config.db import get_db
from app.schema.deliverySchema import (
    DeliveryStatusResponse,
    DeliveryUpdateResponse,
    DeliveryArrivalRequest,
    DeliveryDockingRequest,
    DeliveryUnloadingRequest,
    DeliveryConfirmationRequest
)
from app.services.delivery_service import (
    get_delivery_status,
    update_delivery_arrival,
    update_delivery_docking,
    update_delivery_unloading_start,
    update_delivery_unloading_complete,
    confirm_delivery
)

router = APIRouter(prefix="/api/delivery", tags=["Delivery Flow"])

@router.get("/status/{load_id}", response_model=DeliveryStatusResponse)
def get_delivery_status_endpoint(load_id: str, db: Session = Depends(get_db)):
    """
    Get current delivery status for a load.
    Returns the current delivery stage and all timestamps.
    """
    try:
        status_data = get_delivery_status(db, load_id)
        if not status_data:
            raise HTTPException(status_code=404, detail="Load not found")
        
        return DeliveryStatusResponse(**status_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get delivery status: {str(e)}")

@router.post("/{load_id}/arrive", response_model=DeliveryUpdateResponse)
def mark_arrival(
    load_id: str, 
    arrival_data: DeliveryArrivalRequest, 
    db: Session = Depends(get_db)
):
    """
    Mark driver arrival at delivery location.
    Includes geofence simulation with optional coordinates.
    """
    try:
        result = update_delivery_arrival(db, load_id, arrival_data)
        return DeliveryUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark arrival: {str(e)}")

@router.post("/{load_id}/request-docking", response_model=DeliveryUpdateResponse)
def request_docking(
    load_id: str, 
    docking_data: DeliveryDockingRequest, 
    db: Session = Depends(get_db)
):
    """
    Request docking at delivery location.
    """
    try:
        result = update_delivery_docking(db, load_id, docking_data)
        return DeliveryUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to request docking: {str(e)}")

@router.post("/{load_id}/dock", response_model=DeliveryUpdateResponse)
def mark_docking(
    load_id: str, 
    docking_data: DeliveryDockingRequest, 
    db: Session = Depends(get_db)
):
    """
    Mark driver as docked at delivery location.
    """
    try:
        result = update_delivery_docking(db, load_id, docking_data)
        return DeliveryUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark docking: {str(e)}")

@router.post("/{load_id}/start-unloading", response_model=DeliveryUpdateResponse)
def start_unloading(
    load_id: str, 
    unloading_data: DeliveryUnloadingRequest, 
    db: Session = Depends(get_db)
):
    """
    Mark unloading as started.
    """
    try:
        result = update_delivery_unloading_start(db, load_id, unloading_data)
        return DeliveryUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start unloading: {str(e)}")

@router.post("/{load_id}/complete-unloading", response_model=DeliveryUpdateResponse)
def complete_unloading(
    load_id: str, 
    unloading_data: DeliveryUnloadingRequest, 
    db: Session = Depends(get_db)
):
    """
    Mark unloading as completed.
    """
    try:
        result = update_delivery_unloading_complete(db, load_id, unloading_data)
        return DeliveryUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete unloading: {str(e)}")

@router.post("/{load_id}/confirm", response_model=DeliveryUpdateResponse)
def confirm_delivery_endpoint(
    load_id: str, 
    confirmation_data: DeliveryConfirmationRequest, 
    db: Session = Depends(get_db)
):
    """
    Confirm final delivery with recipient details and proof of delivery.
    This marks the load as fully delivered and triggers settlement calculation.
    """
    try:
        result = confirm_delivery(db, load_id, confirmation_data)
        return DeliveryUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm delivery: {str(e)}")


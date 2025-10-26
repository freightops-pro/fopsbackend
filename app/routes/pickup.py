from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.config.db import get_db
from app.schema.pickupSchema import (
    PickupStatusResponse,
    PickupUpdateResponse,
    PickupNavigationRequest,
    PickupArrivalRequest,
    TrailerConfirmationRequest,
    ContainerConfirmationRequest,
    PickupConfirmationRequest,
    DepartureRequest,
    BillOfLadingUploadResponse
)
from app.services.pickup_service import (
    get_pickup_status,
    start_pickup_navigation,
    mark_pickup_arrival,
    confirm_trailer,
    confirm_container,
    confirm_pickup,
    mark_departure
)
from app.services.file_upload_service import upload_bill_of_lading

router = APIRouter(prefix="/api/pickup", tags=["Pickup Flow"])

@router.get("/status/{load_id}", response_model=PickupStatusResponse)
def get_pickup_status_endpoint(load_id: str, db: Session = Depends(get_db)):
    """Get current pickup status for a load"""
    try:
        status_data = get_pickup_status(db, load_id)
        if not status_data:
            raise HTTPException(status_code=404, detail="Load not found")
        
        return PickupStatusResponse(**status_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pickup status: {str(e)}")

@router.post("/{load_id}/start-navigation", response_model=PickupUpdateResponse)
def start_navigation(
    load_id: str, 
    navigation_data: PickupNavigationRequest, 
    db: Session = Depends(get_db)
):
    """Start navigation to pickup location"""
    try:
        result = start_pickup_navigation(db, load_id, navigation_data)
        return PickupUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start navigation: {str(e)}")

@router.post("/{load_id}/arrive", response_model=PickupUpdateResponse)
def mark_arrival(
    load_id: str, 
    arrival_data: PickupArrivalRequest, 
    db: Session = Depends(get_db)
):
    """Mark arrival at pickup location with geofence simulation"""
    try:
        result = mark_pickup_arrival(db, load_id, arrival_data)
        return PickupUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark arrival: {str(e)}")

@router.post("/{load_id}/confirm-trailer", response_model=PickupUpdateResponse)
def confirm_trailer_endpoint(
    load_id: str, 
    trailer_data: TrailerConfirmationRequest, 
    db: Session = Depends(get_db)
):
    """Confirm trailer for pickup"""
    try:
        result = confirm_trailer(db, load_id, trailer_data)
        return PickupUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm trailer: {str(e)}")

@router.post("/{load_id}/confirm-container", response_model=PickupUpdateResponse)
def confirm_container_endpoint(
    load_id: str, 
    container_data: ContainerConfirmationRequest, 
    db: Session = Depends(get_db)
):
    """Confirm container for pickup"""
    try:
        result = confirm_container(db, load_id, container_data)
        return PickupUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm container: {str(e)}")

@router.post("/{load_id}/confirm-pickup", response_model=PickupUpdateResponse)
def confirm_pickup_endpoint(
    load_id: str, 
    pickup_data: PickupConfirmationRequest, 
    db: Session = Depends(get_db)
):
    """Confirm final pickup completion"""
    try:
        result = confirm_pickup(db, load_id, pickup_data)
        return PickupUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm pickup: {str(e)}")

@router.post("/{load_id}/depart", response_model=PickupUpdateResponse)
def mark_departure_endpoint(
    load_id: str, 
    departure_data: DepartureRequest, 
    db: Session = Depends(get_db)
):
    """Mark departure from pickup location"""
    try:
        result = mark_departure(db, load_id, departure_data)
        return PickupUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark departure: {str(e)}")

@router.post("/{load_id}/upload-bol", response_model=BillOfLadingUploadResponse)
async def upload_bill_of_lading_endpoint(
    load_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload bill of lading document"""
    try:
        upload_result = await upload_bill_of_lading(load_id, file)
        
        # Update the load with BOL URL
        from app.models.simple_load import SimpleLoad
        load = db.query(SimpleLoad).filter(SimpleLoad.id == load_id).first()
        if load:
            load.billOfLadingUrl = upload_result["file_url"]
            db.commit()
        
        return BillOfLadingUploadResponse(**upload_result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload bill of lading: {str(e)}")

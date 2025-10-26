from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import logging

from app.config.db import get_db
from app.routes.user import verify_token
from app.utils.tenant_helpers import get_company_id_from_token
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
logger = logging.getLogger(__name__)

@router.get("/status/{load_id}", response_model=PickupStatusResponse)
def get_pickup_status_endpoint(
    load_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """
    Get current pickup status for a load.
    
    Args:
        load_id: The load ID
        
    Returns:
        Current pickup status
        
    Raises:
        404: Load not found or unauthorized
        500: Service error
    """
    try:
        company_id = get_company_id_from_token(token)
        status_data = get_pickup_status(db, load_id, company_id)
        if not status_data:
            raise HTTPException(status_code=404, detail="Load not found")
        
        return PickupStatusResponse(**status_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pickup status for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get pickup status")

@router.post("/{load_id}/start-navigation", response_model=PickupUpdateResponse)
def start_navigation(
    load_id: str, 
    navigation_data: PickupNavigationRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """
    Start navigation to pickup location.
    
    Args:
        load_id: The load ID
        navigation_data: Navigation details
        
    Returns:
        Updated pickup status
        
    Raises:
        400: Invalid data
        500: Service error
    """
    try:
        company_id = get_company_id_from_token(token)
        result = start_pickup_navigation(db, load_id, navigation_data, company_id)
        return PickupUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid navigation start for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start navigation for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start navigation")

@router.post("/{load_id}/arrive", response_model=PickupUpdateResponse)
def mark_arrival(
    load_id: str, 
    arrival_data: PickupArrivalRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Mark arrival at pickup location with geofence simulation."""
    try:
        company_id = get_company_id_from_token(token)
        result = mark_pickup_arrival(db, load_id, arrival_data, company_id)
        return PickupUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid arrival data for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark arrival for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to mark arrival")

@router.post("/{load_id}/confirm-trailer", response_model=PickupUpdateResponse)
def confirm_trailer_endpoint(
    load_id: str, 
    trailer_data: TrailerConfirmationRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Confirm trailer for pickup."""
    try:
        company_id = get_company_id_from_token(token)
        result = confirm_trailer(db, load_id, trailer_data, company_id)
        return PickupUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid trailer confirmation for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to confirm trailer for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to confirm trailer")

@router.post("/{load_id}/confirm-container", response_model=PickupUpdateResponse)
def confirm_container_endpoint(
    load_id: str, 
    container_data: ContainerConfirmationRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Confirm container for pickup."""
    try:
        company_id = get_company_id_from_token(token)
        result = confirm_container(db, load_id, container_data, company_id)
        return PickupUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid container confirmation for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to confirm container for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to confirm container")

@router.post("/{load_id}/confirm-pickup", response_model=PickupUpdateResponse)
def confirm_pickup_endpoint(
    load_id: str, 
    pickup_data: PickupConfirmationRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Confirm final pickup completion."""
    try:
        company_id = get_company_id_from_token(token)
        result = confirm_pickup(db, load_id, pickup_data, company_id)
        return PickupUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid pickup confirmation for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to confirm pickup for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to confirm pickup")

@router.post("/{load_id}/depart", response_model=PickupUpdateResponse)
def mark_departure_endpoint(
    load_id: str, 
    departure_data: DepartureRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Mark departure from pickup location."""
    try:
        company_id = get_company_id_from_token(token)
        result = mark_departure(db, load_id, departure_data, company_id)
        return PickupUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid departure data for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark departure for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to mark departure")

@router.post("/{load_id}/upload-bol", response_model=BillOfLadingUploadResponse)
async def upload_bill_of_lading_endpoint(
    load_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Upload bill of lading document."""
    try:
        company_id = get_company_id_from_token(token)
        
        # Verify load ownership before upload
        from app.models.simple_load import SimpleLoad
        from app.utils.tenant_helpers import verify_resource_ownership
        load = verify_resource_ownership(db, SimpleLoad, load_id, company_id)
        
        upload_result = await upload_bill_of_lading(load_id, file)
        
        # Update the load with BOL URL
        load.billOfLadingUrl = upload_result["file_url"]
        db.commit()
        
        logger.info(f"BOL uploaded for load {load_id} by company {company_id}")
        return BillOfLadingUploadResponse(**upload_result)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to upload BOL for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload bill of lading")

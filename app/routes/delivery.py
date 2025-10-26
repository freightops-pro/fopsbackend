from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from app.config.db import get_db
from app.routes.user import verify_token
from app.utils.tenant_helpers import get_company_id_from_token
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
logger = logging.getLogger(__name__)

@router.get("/status/{load_id}", response_model=DeliveryStatusResponse)
def get_delivery_status_endpoint(
    load_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """
    Get current delivery status for a load.
    Returns the current delivery stage and all timestamps.
    
    Args:
        load_id: The load ID
        
    Returns:
        Delivery status with timestamps
        
    Raises:
        404: Load not found or unauthorized
        500: Service error
    """
    try:
        company_id = get_company_id_from_token(token)
        status_data = get_delivery_status(db, load_id, company_id)
        if not status_data:
            raise HTTPException(status_code=404, detail="Load not found")
        
        return DeliveryStatusResponse(**status_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get delivery status for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get delivery status")

@router.post("/{load_id}/arrive", response_model=DeliveryUpdateResponse)
def mark_arrival(
    load_id: str, 
    arrival_data: DeliveryArrivalRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Mark driver arrival at delivery location. Includes geofence simulation with optional coordinates."""
    try:
        company_id = get_company_id_from_token(token)
        result = update_delivery_arrival(db, load_id, arrival_data, company_id)
        return DeliveryUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid arrival data for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark delivery arrival for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to mark arrival")

@router.post("/{load_id}/request-docking", response_model=DeliveryUpdateResponse)
def request_docking(
    load_id: str, 
    docking_data: DeliveryDockingRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Request docking at delivery location."""
    try:
        company_id = get_company_id_from_token(token)
        result = update_delivery_docking(db, load_id, docking_data, company_id)
        return DeliveryUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid docking request for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to request docking for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to request docking")

@router.post("/{load_id}/dock", response_model=DeliveryUpdateResponse)
def mark_docking(
    load_id: str, 
    docking_data: DeliveryDockingRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Mark driver as docked at delivery location."""
    try:
        company_id = get_company_id_from_token(token)
        result = update_delivery_docking(db, load_id, docking_data, company_id)
        return DeliveryUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid docking data for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark docking for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to mark docking")

@router.post("/{load_id}/start-unloading", response_model=DeliveryUpdateResponse)
def start_unloading(
    load_id: str, 
    unloading_data: DeliveryUnloadingRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Mark unloading as started."""
    try:
        company_id = get_company_id_from_token(token)
        result = update_delivery_unloading_start(db, load_id, unloading_data, company_id)
        return DeliveryUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid unloading start for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start unloading for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start unloading")

@router.post("/{load_id}/complete-unloading", response_model=DeliveryUpdateResponse)
def complete_unloading(
    load_id: str, 
    unloading_data: DeliveryUnloadingRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """Mark unloading as completed."""
    try:
        company_id = get_company_id_from_token(token)
        result = update_delivery_unloading_complete(db, load_id, unloading_data, company_id)
        return DeliveryUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid unloading completion for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete unloading for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to complete unloading")

@router.post("/{load_id}/confirm", response_model=DeliveryUpdateResponse)
def confirm_delivery_endpoint(
    load_id: str, 
    confirmation_data: DeliveryConfirmationRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """
    Confirm final delivery with recipient details and proof of delivery.
    This marks the load as fully delivered and triggers settlement calculation.
    """
    try:
        company_id = get_company_id_from_token(token)
        result = confirm_delivery(db, load_id, confirmation_data, company_id)
        return DeliveryUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid delivery confirmation for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to confirm delivery for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to confirm delivery")


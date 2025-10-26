from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import logging

from app.config.db import get_db
from app.routes.user import verify_token
from app.utils.tenant_helpers import get_company_id_from_token
from app.schema.truckAssignmentSchema import (
    TruckAssignmentStatusResponse,
    TruckAssignmentUpdateResponse,
    AvailableTrucksResponse,
    TruckAssignmentRequest,
    DriverConfirmationRequest,
    TrailerSetupRequest,
    TruckConfirmationRequest
)
from app.services.truck_assignment_service import (
    get_truck_assignment_status,
    get_available_trucks,
    assign_truck,
    confirm_driver,
    setup_trailer,
    confirm_truck
)

router = APIRouter(prefix="/api/truck-assignment", tags=["Truck Assignment"])
logger = logging.getLogger(__name__)

@router.get("/status/{load_id}", response_model=TruckAssignmentStatusResponse)
def get_truck_assignment_status_endpoint(
    load_id: str,
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """
    Get current truck assignment status for a load.
    
    Args:
        load_id: The load ID
        
    Returns:
        Truck assignment status
        
    Raises:
        404: Load not found or unauthorized
        500: Service error
    """
    try:
        company_id = get_company_id_from_token(token)
        status_data = get_truck_assignment_status(db, load_id, company_id)
        if not status_data:
            raise HTTPException(status_code=404, detail="Load not found")
        
        return TruckAssignmentStatusResponse(**status_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get truck assignment status for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get truck assignment status")

@router.get("/available-trucks", response_model=AvailableTrucksResponse)
def get_available_trucks_endpoint(
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """
    Get available trucks for the authenticated company.
    
    Returns:
        List of available trucks
        
    Raises:
        500: Service error
    """
    try:
        company_id = get_company_id_from_token(token)
        trucks = get_available_trucks(db, company_id)
        return AvailableTrucksResponse(trucks=trucks, total=len(trucks))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get available trucks for company {company_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get available trucks")

@router.post("/{load_id}/assign-truck", response_model=TruckAssignmentUpdateResponse)
def assign_truck_endpoint(
    load_id: str, 
    assignment_data: TruckAssignmentRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """
    Assign truck to load.
    
    Args:
        load_id: The load ID
        assignment_data: Truck assignment details
        
    Returns:
        Updated assignment status
        
    Raises:
        400: Invalid assignment data
        404: Load not found or unauthorized
        500: Service error
    """
    try:
        company_id = get_company_id_from_token(token)
        result = assign_truck(db, load_id, assignment_data, company_id)
        return TruckAssignmentUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid truck assignment for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign truck to load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to assign truck")

@router.post("/{load_id}/confirm-driver", response_model=TruckAssignmentUpdateResponse)
def confirm_driver_endpoint(
    load_id: str, 
    confirmation_data: DriverConfirmationRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """
    Confirm driver is driving the assigned truck.
    
    Args:
        load_id: The load ID
        confirmation_data: Driver confirmation details
        
    Returns:
        Updated assignment status
        
    Raises:
        400: Invalid confirmation data
        500: Service error
    """
    try:
        company_id = get_company_id_from_token(token)
        result = confirm_driver(db, load_id, confirmation_data, company_id)
        return TruckAssignmentUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid driver confirmation for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to confirm driver for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to confirm driver")

@router.post("/{load_id}/setup-trailer", response_model=TruckAssignmentUpdateResponse)
def setup_trailer_endpoint(
    load_id: str, 
    trailer_data: TrailerSetupRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """
    Set up trailer information.
    
    Args:
        load_id: The load ID
        trailer_data: Trailer setup details
        
    Returns:
        Updated assignment status
        
    Raises:
        400: Invalid trailer data
        500: Service error
    """
    try:
        company_id = get_company_id_from_token(token)
        result = setup_trailer(db, load_id, trailer_data, company_id)
        return TruckAssignmentUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid trailer setup for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to setup trailer for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to setup trailer")

@router.post("/{load_id}/confirm-truck", response_model=TruckAssignmentUpdateResponse)
def confirm_truck_endpoint(
    load_id: str, 
    confirmation_data: TruckConfirmationRequest, 
    db: Session = Depends(get_db),
    token: dict = Depends(verify_token)
):
    """
    Final truck confirmation.
    
    Args:
        load_id: The load ID
        confirmation_data: Truck confirmation details
        
    Returns:
        Updated assignment status
        
    Raises:
        400: Invalid confirmation data
        500: Service error
    """
    try:
        company_id = get_company_id_from_token(token)
        result = confirm_truck(db, load_id, confirmation_data, company_id)
        return TruckAssignmentUpdateResponse(**result)
    except ValueError as e:
        logger.warning(f"Invalid truck confirmation for load {load_id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to confirm truck for load {load_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to confirm truck")

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.config.db import get_db
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

@router.get("/status/{load_id}", response_model=TruckAssignmentStatusResponse)
def get_truck_assignment_status_endpoint(load_id: str, db: Session = Depends(get_db)):
    """Get current truck assignment status for a load"""
    try:
        status_data = get_truck_assignment_status(db, load_id)
        if not status_data:
            raise HTTPException(status_code=404, detail="Load not found")
        
        return TruckAssignmentStatusResponse(**status_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get truck assignment status: {str(e)}")

@router.get("/available-trucks", response_model=AvailableTrucksResponse)
def get_available_trucks_endpoint(
    company_id: str = Query(..., description="Company ID"),
    db: Session = Depends(get_db)
):
    """Get available trucks for a company (real-time)"""
    try:
        trucks = get_available_trucks(db, company_id)
        return AvailableTrucksResponse(trucks=trucks, total=len(trucks))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get available trucks: {str(e)}")

@router.post("/{load_id}/assign-truck", response_model=TruckAssignmentUpdateResponse)
def assign_truck_endpoint(
    load_id: str, 
    assignment_data: TruckAssignmentRequest, 
    db: Session = Depends(get_db)
):
    """Assign truck to load"""
    try:
        result = assign_truck(db, load_id, assignment_data)
        return TruckAssignmentUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assign truck: {str(e)}")

@router.post("/{load_id}/confirm-driver", response_model=TruckAssignmentUpdateResponse)
def confirm_driver_endpoint(
    load_id: str, 
    confirmation_data: DriverConfirmationRequest, 
    db: Session = Depends(get_db)
):
    """Confirm driver is driving the assigned truck"""
    try:
        result = confirm_driver(db, load_id, confirmation_data)
        return TruckAssignmentUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm driver: {str(e)}")

@router.post("/{load_id}/setup-trailer", response_model=TruckAssignmentUpdateResponse)
def setup_trailer_endpoint(
    load_id: str, 
    trailer_data: TrailerSetupRequest, 
    db: Session = Depends(get_db)
):
    """Set up trailer information"""
    try:
        result = setup_trailer(db, load_id, trailer_data)
        return TruckAssignmentUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to setup trailer: {str(e)}")

@router.post("/{load_id}/confirm-truck", response_model=TruckAssignmentUpdateResponse)
def confirm_truck_endpoint(
    load_id: str, 
    confirmation_data: TruckConfirmationRequest, 
    db: Session = Depends(get_db)
):
    """Final truck confirmation"""
    try:
        result = confirm_truck(db, load_id, confirmation_data)
        return TruckAssignmentUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm truck: {str(e)}")

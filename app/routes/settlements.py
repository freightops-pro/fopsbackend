from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.config.db import get_db
from app.schema.payrollSchema import (
    SettlementRequestResponse, 
    SettlementSubmissionResponse,
    SettlementRequestData
)
from app.services.payroll_service import (
    get_settlement_request_data,
    submit_settlement_request
)

router = APIRouter(prefix="/api/settlements", tags=["Settlements"])

@router.get("/request/{load_id}", response_model=SettlementRequestResponse)
def get_settlement_request(load_id: str, db: Session = Depends(get_db)):
    """
    Get settlement request data for a specific load.
    This endpoint provides all the information needed to calculate and display
    settlement details during delivery completion.
    """
    try:
        settlement_data = get_settlement_request_data(db, load_id)
        if not settlement_data:
            raise HTTPException(status_code=404, detail="Load not found or no driver assigned")
        
        return SettlementRequestResponse(**settlement_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get settlement data: {str(e)}")

@router.post("/request/{load_id}", response_model=SettlementSubmissionResponse)
def submit_settlement_request_endpoint(
    load_id: str, 
    settlement_data: SettlementRequestData, 
    db: Session = Depends(get_db)
):
    """
    Submit settlement request with completed delivery data.
    This endpoint processes the settlement calculation and creates a settlement record.
    """
    try:
        result = submit_settlement_request(db, load_id, settlement_data)
        return SettlementSubmissionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit settlement: {str(e)}")

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
from app.config.db import get_db
from app.models.userModels import Users, Companies
from app.models.broker_commission import BrokerCommission
from app.schema.broker_commission import (
    BrokerCommissionCreate, BrokerCommissionUpdate, 
    BrokerCommissionResponse, BrokerCommissionWithDetails
)
from app.services.commission_service import CommissionService
from app.routes.user import get_current_user

router = APIRouter()

def get_current_company_id(current_user: Users = Depends(get_current_user)) -> str:
    """Get current user's company ID"""
    return current_user.companyid

@router.get("/commissions", response_model=List[BrokerCommissionResponse])
async def get_commissions(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db),
    payment_status: Optional[str] = None
):
    """Get commissions for current user's company"""
    try:
        commission_service = CommissionService(db)
        
        # Determine if user is broker or carrier
        company = db.query(Companies).filter(
            Companies.id == current_user.companyid
        ).first()
        
        if company.businessType == "brokerage":
            commissions = commission_service.get_broker_commissions(
                current_user.companyid, payment_status
            )
        else:
            commissions = commission_service.get_carrier_commissions(
                current_user.companyid, payment_status
            )
        
        return commissions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch commissions: {str(e)}"
        )

@router.post("/commissions", response_model=BrokerCommissionResponse)
async def create_commission(
    commission_data: BrokerCommissionCreate,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new commission record"""
    try:
        # Verify user is a broker
        company = db.query(Companies).filter(
            Companies.id == current_user.companyid,
            Companies.businessType == "brokerage"
        ).first()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only brokerage companies can create commissions"
            )
        
        commission_service = CommissionService(db)
        
        commission = commission_service.create_commission_record(
            load_id=commission_data.load_id,
            broker_company_id=current_user.companyid,
            carrier_company_id=commission_data.carrier_company_id,
            total_load_value=commission_data.total_load_value,
            commission_percentage=commission_data.commission_percentage,
            notes=commission_data.notes
        )
        
        return commission
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create commission: {str(e)}"
        )

@router.put("/commissions/{commission_id}", response_model=BrokerCommissionResponse)
async def update_commission(
    commission_id: str,
    update_data: BrokerCommissionUpdate,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a commission record"""
    try:
        commission_service = CommissionService(db)
        
        # Verify user has access to this commission
        commission = db.query(BrokerCommission).filter(
            BrokerCommission.id == commission_id
        ).first()
        
        if not commission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Commission not found"
            )
        
        # Check if user's company is involved in this commission
        if (commission.broker_company_id != current_user.companyid and 
            commission.carrier_company_id != current_user.companyid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this commission"
            )
        
        # Update payment status
        if update_data.payment_status:
            commission = commission_service.update_commission_payment_status(
                commission_id, update_data.payment_status, update_data.settlement_id
            )
        
        # Update other fields
        if update_data.notes is not None:
            commission.notes = update_data.notes
        
        db.commit()
        db.refresh(commission)
        
        return commission
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update commission: {str(e)}"
        )

@router.get("/commissions/summary")
async def get_commission_summary(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get commission summary for current user's company"""
    try:
        commission_service = CommissionService(db)
        
        # Determine if user is broker or carrier
        company = db.query(Companies).filter(
            Companies.id == current_user.companyid
        ).first()
        
        is_broker = company.businessType == "brokerage"
        
        summary = commission_service.get_commission_summary(
            current_user.companyid, is_broker
        )
        
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch commission summary: {str(e)}"
        )

@router.post("/commissions/process-load/{load_board_id}")
async def process_load_completion_commission(
    load_board_id: str,
    final_load_value: Optional[Decimal] = None,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Process commission when a load is completed"""
    try:
        # Verify user has access to this load
        from app.models.load_board import LoadBoard
        load_board = db.query(LoadBoard).filter(
            LoadBoard.id == load_board_id
        ).first()
        
        if not load_board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Load board entry not found"
            )
        
        # Check if user's company is involved in this load
        if (load_board.broker_company_id != current_user.companyid and 
            load_board.carrier_company_id != current_user.companyid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this load"
            )
        
        commission_service = CommissionService(db)
        
        commission = commission_service.process_load_completion_commission(
            load_board_id, final_load_value
        )
        
        return commission
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process load completion commission: {str(e)}"
        )

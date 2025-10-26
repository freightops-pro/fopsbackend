from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from app.config.db import get_db
from app.routes.user import get_current_user
from app.models.userModels import Users
from app.schema.automated_dispatch import (
    AutomatedDispatchRuleCreate,
    AutomatedDispatchRuleUpdate,
    AutomatedDispatchRuleResponse,
    DriverMatchRequest,
    DriverMatchResponse
)

router = APIRouter(prefix="/api/automated-dispatch", tags=["automated-dispatch"])
logger = logging.getLogger(__name__)

def get_current_company_id(current_user: Users = Depends(get_current_user)) -> int:
    """Get current user's company ID"""
    return current_user.company_id

@router.get("/rules")
async def get_automated_dispatch_rules(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all automated dispatch rules for a company"""
    if current_user.subscription_tier not in ["professional", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professional or Enterprise subscription required"
        )
    
    # Return empty array for now - rules will be implemented later
    return []

@router.post("/match-drivers")
async def match_drivers(
    request: DriverMatchRequest,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Match drivers to a load using automated dispatch rules"""
    if current_user.subscription_tier not in ["professional", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professional or Enterprise subscription required"
        )
    
    # Return empty array for now - driver matching will be implemented later
    return []

@router.post("/rules")
async def create_automated_dispatch_rule(
    rule_data: AutomatedDispatchRuleCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create a new automated dispatch rule"""
    if current_user.subscription_tier not in ["professional", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professional or Enterprise subscription required"
        )
    
    # Return success for now - rule creation will be implemented later
    return {"message": "Rule created successfully", "rule_id": 1}

@router.put("/rules/{rule_id}")
async def update_automated_dispatch_rule(
    rule_id: int,
    rule_data: AutomatedDispatchRuleUpdate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Update an automated dispatch rule"""
    if current_user.subscription_tier not in ["professional", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professional or Enterprise subscription required"
        )
    
    # Return success for now - rule update will be implemented later
    return {"message": "Rule updated successfully"}

@router.delete("/rules/{rule_id}")
async def delete_automated_dispatch_rule(
    rule_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Delete an automated dispatch rule"""
    if current_user.subscription_tier not in ["professional", "enterprise"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Professional or Enterprise subscription required"
        )
    
    # Return success for now - rule deletion will be implemented later
    return {"message": "Rule deleted successfully"}

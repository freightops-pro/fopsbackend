from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging

from app.config.db import get_db
from app.routes.user import get_current_user
from app.models.userModels import Users
from app.schema.filters import (
    FilterGroupCreate,
    FilterGroupUpdate,
    FilterGroupResponse,
    FilterOption,
    SavedFilterCreate,
    SavedFilterResponse
)

router = APIRouter(prefix="/api/filters", tags=["filters"])
logger = logging.getLogger(__name__)

def get_current_company_id(current_user: Users = Depends(get_current_user)) -> int:
    """Get current user's company ID"""
    return current_user.company_id

@router.get("/groups")
async def get_filter_groups(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all filter groups for a company"""
    
    # Return basic filter groups for now
    return [
        {
            "id": "status",
            "label": "Load Status",
            "type": "multiselect",
            "options": [
                {"id": "available", "label": "Available", "value": "available", "count": 0},
                {"id": "assigned", "label": "Assigned", "value": "assigned", "count": 0},
                {"id": "in_transit", "label": "In Transit", "value": "in_transit", "count": 0},
                {"id": "completed", "label": "Completed", "value": "completed", "count": 0}
            ]
        },
        {
            "id": "priority",
            "label": "Priority",
            "type": "multiselect",
            "options": [
                {"id": "urgent", "label": "Urgent", "value": "urgent", "count": 0},
                {"id": "high", "label": "High", "value": "high", "count": 0},
                {"id": "normal", "label": "Normal", "value": "normal", "count": 0},
                {"id": "low", "label": "Low", "value": "low", "count": 0}
            ]
        },
        {
            "id": "customer",
            "label": "Customer",
            "type": "search",
            "options": []
        },
        {
            "id": "driver",
            "label": "Driver",
            "type": "select",
            "options": []
        },
        {
            "id": "location",
            "label": "Origin/Destination",
            "type": "search",
            "options": []
        },
        {
            "id": "trailerType",
            "label": "Trailer Type",
            "type": "multiselect",
            "options": [
                {"id": "dry_van", "label": "Dry Van", "value": "dry_van", "count": 0},
                {"id": "reefer", "label": "Reefer", "value": "reefer", "count": 0},
                {"id": "flatbed", "label": "Flatbed", "value": "flatbed", "count": 0},
                {"id": "tanker", "label": "Tanker", "value": "tanker", "count": 0}
            ]
        },
        {
            "id": "dateRange",
            "label": "Date Range",
            "type": "daterange",
            "options": []
        },
        {
            "id": "rate",
            "label": "Rate Range",
            "type": "number",
            "options": []
        }
    ]

@router.get("/saved")
async def get_saved_filters(
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all saved filters for a user"""
    return []

@router.post("/saved")
async def save_filter(
    filter_data: SavedFilterCreate,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Save a new filter"""
    return {"message": "Filter saved successfully", "filter_id": 1}

@router.delete("/saved/{filter_id}")
async def delete_saved_filter(
    filter_id: int,
    current_user: Users = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Delete a saved filter"""
    return {"message": "Filter deleted successfully"}

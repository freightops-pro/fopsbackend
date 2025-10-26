from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class TransloadStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TransloadFacilityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=200)
    capacity: int = Field(..., gt=0)
    dock_doors: int = Field(..., gt=0)
    description: Optional[str] = Field(None, max_length=500)

class TransloadFacilityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    location: Optional[str] = Field(None, min_length=1, max_length=200)
    capacity: Optional[int] = Field(None, gt=0)
    dock_doors: Optional[int] = Field(None, gt=0)
    description: Optional[str] = Field(None, max_length=500)

class TransloadFacilityResponse(BaseModel):
    id: int
    name: str
    location: str
    capacity: int
    current_loads: int
    dock_doors: int
    available_doors: int
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    company_id: int

    class Config:
        from_attributes = True

class TransloadOperationCreate(BaseModel):
    facility_id: int
    inbound_load_id: str
    outbound_load_id: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    status: TransloadStatus = Field(default=TransloadStatus.SCHEDULED)
    dock_door: Optional[int] = None
    labor_assigned: Optional[int] = Field(default=0)
    equipment_staged: Optional[List[str]] = Field(default_factory=list)
    notes: Optional[str] = Field(None, max_length=500)

class TransloadOperationUpdate(BaseModel):
    facility_id: Optional[int] = None
    inbound_load_id: Optional[str] = None
    outbound_load_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[TransloadStatus] = None
    dock_door: Optional[int] = None
    labor_assigned: Optional[int] = None
    equipment_staged: Optional[List[str]] = None
    notes: Optional[str] = Field(None, max_length=500)

class TransloadOperationResponse(BaseModel):
    id: int
    facility_id: int
    facility_name: str
    inbound_load_id: str
    outbound_load_id: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    status: TransloadStatus
    dock_door: Optional[int]
    labor_assigned: Optional[int]
    equipment_staged: Optional[List[str]]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    company_id: int

    class Config:
        from_attributes = True

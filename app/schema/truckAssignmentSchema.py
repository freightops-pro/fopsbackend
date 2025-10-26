from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

# Request Schemas
class TruckAssignmentRequest(BaseModel):
    truckId: str
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None

class DriverConfirmationRequest(BaseModel):
    isDrivingAssignedTruck: bool
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None

class TrailerSetupRequest(BaseModel):
    trailerNumber: Optional[str] = None  # None means "no trailer"
    hasTrailer: bool
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None

class TruckConfirmationRequest(BaseModel):
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None

# Response Schemas
class AvailableTruck(BaseModel):
    id: str
    truckNumber: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    status: str
    location: Optional[str] = None

class TruckAssignmentStatusResponse(BaseModel):
    loadId: str
    truckAssignmentStatus: str
    assignedTruckId: Optional[str] = None
    assignedDriverId: Optional[str] = None
    truckAssignmentTime: Optional[datetime] = None
    driverConfirmationTime: Optional[datetime] = None
    trailerSetupTime: Optional[datetime] = None
    truckConfirmationTime: Optional[datetime] = None
    trailerNumber: Optional[str] = None
    hasTrailer: Optional[bool] = None

class TruckAssignmentUpdateResponse(BaseModel):
    success: bool
    message: str
    newStatus: str
    timestamp: datetime

class AvailableTrucksResponse(BaseModel):
    trucks: List[AvailableTruck]
    total: int

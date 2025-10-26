from datetime import datetime
from typing import Optional
from pydantic import BaseModel

# Request Schemas
class PickupNavigationRequest(BaseModel):
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None

class PickupArrivalRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: Optional[datetime] = None
    geofenceStatus: str = "entered"
    notes: Optional[str] = None

class TrailerConfirmationRequest(BaseModel):
    timestamp: Optional[datetime] = None
    trailerNumber: Optional[str] = None
    notes: Optional[str] = None

class ContainerConfirmationRequest(BaseModel):
    timestamp: Optional[datetime] = None
    containerNumber: Optional[str] = None
    notes: Optional[str] = None

class PickupConfirmationRequest(BaseModel):
    timestamp: Optional[datetime] = None
    pickupNotes: Optional[str] = None

class DepartureRequest(BaseModel):
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None

# Response Schemas
class PickupStatusResponse(BaseModel):
    loadId: str
    pickupStatus: str
    navigationStartTime: Optional[datetime] = None
    pickupArrivalTime: Optional[datetime] = None
    trailerConfirmationTime: Optional[datetime] = None
    containerConfirmationTime: Optional[datetime] = None
    pickupConfirmationTime: Optional[datetime] = None
    departureTime: Optional[datetime] = None
    billOfLadingUrl: Optional[str] = None
    pickupNotes: Optional[str] = None
    pickupLocation: str
    deliveryLocation: str

class PickupUpdateResponse(BaseModel):
    success: bool
    message: str
    newStatus: str
    timestamp: datetime

class BillOfLadingUploadResponse(BaseModel):
    success: bool
    message: str
    filename: str
    file_url: str
    file_size: int
    content_type: str

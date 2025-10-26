from datetime import datetime
from typing import Optional
from pydantic import BaseModel

# Delivery Status Update Schemas
class DeliveryArrivalRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: Optional[datetime] = None
    geofenceStatus: str = "entered"  # entered, confirmed
    notes: Optional[str] = None

class DeliveryDockingRequest(BaseModel):
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None

class DeliveryUnloadingRequest(BaseModel):
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None

class DeliveryConfirmationRequest(BaseModel):
    deliveryTimestamp: Optional[datetime] = None
    recipientName: str
    deliveryNotes: Optional[str] = None

# Response Schemas
class DeliveryStatusResponse(BaseModel):
    loadId: str
    deliveryStatus: str
    arrivalTime: Optional[datetime] = None
    dockingTime: Optional[datetime] = None
    unloadingStartTime: Optional[datetime] = None
    unloadingEndTime: Optional[datetime] = None
    deliveryTime: Optional[datetime] = None
    recipientName: Optional[str] = None
    deliveryNotes: Optional[str] = None

class DeliveryUpdateResponse(BaseModel):
    success: bool
    message: str
    newStatus: str
    timestamp: datetime


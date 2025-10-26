from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ContainerStatus(str, Enum):
    AT_PORT = "at_port"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    DELIVERED = "delivered"
    CUSTOMS = "customs"
    UNKNOWN = "unknown"

class ContainerLocation(BaseModel):
    port: str
    country: str
    status: ContainerStatus
    timestamp: datetime
    vessel: Optional[str] = None
    terminal: Optional[str] = None
    berth: Optional[str] = None

class ContainerTrackingRequest(BaseModel):
    container_numbers: List[str] = Field(..., min_items=1, max_items=100)

class ContainerTrackingResponse(BaseModel):
    container_number: str
    size: str
    type: str
    current_location: ContainerLocation
    origin: str
    destination: str
    vessel: Optional[str] = None
    voyage: Optional[str] = None
    estimated_arrival: Optional[datetime] = None
    actual_arrival: Optional[datetime] = None
    demurrage_cost: Optional[float] = None
    detention_cost: Optional[float] = None
    status: ContainerStatus
    last_update: datetime
    next_port: Optional[str] = None
    transit_time: Optional[int] = None

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class LoadStopCreate(BaseModel):
    stop_type: str = Field(..., description="Type of stop: pickup, yard, delivery")
    business_name: str = Field(..., description="Business name at stop")
    address: str = Field(..., description="Full address")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State")
    zip: str = Field(..., description="ZIP code")
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")
    appointment_start: Optional[datetime] = Field(None, description="Appointment start time")
    appointment_end: Optional[datetime] = Field(None, description="Appointment end time")
    driver_assist: bool = Field(False, description="Requires driver assistance")
    sequence_number: int = Field(..., description="Sequence order of stops")
    special_instructions: Optional[str] = Field(None, description="Special instructions for this stop")

class LoadStopResponse(BaseModel):
    id: str
    stop_type: str
    business_name: str
    address: str
    city: str
    state: str
    zip: str
    latitude: Optional[float]
    longitude: Optional[float]
    appointment_start: Optional[datetime]
    appointment_end: Optional[datetime]
    driver_assist: bool
    sequence_number: int
    special_instructions: Optional[str]
    created_at: datetime
    updated_at: datetime

class AccessorialCharge(BaseModel):
    type: str = Field(..., description="Type of accessorial: fuel, detention, layover, etc.")
    amount: float = Field(..., description="Amount of charge")
    description: Optional[str] = Field(None, description="Description of the charge")

class LoadLegCreate(BaseModel):
    driver_id: Optional[str] = Field(None, description="Assigned driver ID")
    start_stop_id: Optional[str] = Field(None, description="Start stop ID")
    end_stop_id: Optional[str] = Field(None, description="End stop ID")
    miles: Optional[float] = Field(None, description="Distance in miles")
    driver_pay: Optional[float] = Field(None, description="Driver pay amount")
    origin: str = Field(..., description="Origin address")
    destination: str = Field(..., description="Destination address")
    pickup_time: datetime = Field(..., description="Scheduled pickup time")
    delivery_time: datetime = Field(..., description="Scheduled delivery time")
    notes: Optional[str] = Field(None, description="Leg notes")

class LoadLegResponse(BaseModel):
    id: int
    leg_number: int
    driver_id: Optional[str]
    driver_name: Optional[str]
    start_stop_id: Optional[str]
    end_stop_id: Optional[str]
    miles: Optional[float]
    driver_pay: Optional[float]
    origin: str
    destination: str
    pickup_time: datetime
    delivery_time: datetime
    status: str
    dispatched: bool
    dispatched_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

class LoadCreateWithLegs(BaseModel):
    # Basic load information
    customer_name: str = Field(..., description="Customer name")
    load_type: str = Field(..., description="Type of load")
    commodity: str = Field(..., description="Commodity description")
    base_rate: float = Field(..., description="Base rate for the load")
    notes: Optional[str] = Field(None, description="Load notes")
    
    # Stops
    stops: List[LoadStopCreate] = Field(..., description="List of stops", min_items=2, max_items=5)
    
    # Accessorial charges
    accessorials: List[AccessorialCharge] = Field(default_factory=list, description="Accessorial charges")
    
    # Optional: Pre-assigned drivers for legs
    driver_assignments: Optional[Dict[str, str]] = Field(None, description="Driver assignments by leg number")

class LoadWithLegsResponse(BaseModel):
    id: str
    load_number: str
    customer_name: str
    load_type: str
    commodity: str
    base_rate: float
    total_rate: float
    status: str
    notes: Optional[str]
    stops: List[LoadStopResponse]
    legs: List[LoadLegResponse]
    accessorials: List[AccessorialCharge]
    created_at: datetime
    updated_at: datetime

class BOLUploadResponse(BaseModel):
    success: bool
    raw_text: str
    parsed_data: Dict[str, Any]
    error: Optional[str] = None

class AddressSuggestion(BaseModel):
    place_id: str
    description: str
    formatted_address: str
    types: List[str]

class DriverPaySummary(BaseModel):
    id: str
    name: str
    pay_type: str
    pay_rate: float
    status: str
    current_location: Optional[str]

class LegAssignmentUpdate(BaseModel):
    leg_id: int
    driver_id: Optional[str] = None
    status: Optional[str] = None
    dispatched: Optional[bool] = None

class LoadSummary(BaseModel):
    id: str
    load_number: str
    customer_name: str
    status: str
    total_rate: float
    driver_pay: float
    profit: float
    legs_count: int
    dispatched_legs: int
    created_at: datetime


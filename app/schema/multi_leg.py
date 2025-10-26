from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

class LoadLegCreate(BaseModel):
    origin: str = Field(..., description="Origin location for the leg")
    destination: str = Field(..., description="Destination location for the leg")
    handoff_location: Optional[str] = Field(None, description="Handoff location for coordination")
    pickup_time: datetime = Field(..., description="Scheduled pickup time")
    delivery_time: datetime = Field(..., description="Scheduled delivery time")
    equipment_type: Optional[str] = Field(None, description="Required equipment type")
    leg_rate: Optional[Decimal] = Field(None, description="Rate for this leg")
    driver_pay: Optional[Decimal] = Field(None, description="Driver pay for this leg")
    notes: Optional[str] = Field(None, description="Notes for this leg")
    special_instructions: Optional[str] = Field(None, description="Special instructions")

class LoadLegUpdate(BaseModel):
    driver_id: Optional[int] = Field(None, description="Assigned driver ID")
    status: Optional[str] = Field(None, description="Leg status")
    actual_pickup_time: Optional[datetime] = Field(None, description="Actual pickup time")
    actual_delivery_time: Optional[datetime] = Field(None, description="Actual delivery time")
    equipment_id: Optional[int] = Field(None, description="Assigned equipment ID")
    notes: Optional[str] = Field(None, description="Updated notes")

class LoadLegResponse(BaseModel):
    id: int
    load_id: int
    leg_number: int
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    origin: str
    destination: str
    handoff_location: Optional[str] = None
    pickup_time: datetime
    delivery_time: datetime
    actual_pickup_time: Optional[datetime] = None
    actual_delivery_time: Optional[datetime] = None
    status: str
    equipment_type: Optional[str] = None
    equipment_id: Optional[int] = None
    leg_rate: Optional[Decimal] = None
    driver_pay: Optional[Decimal] = None
    notes: Optional[str] = None
    special_instructions: Optional[str] = None
    assigned_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MultiLegLoadCreate(BaseModel):
    customer_name: str = Field(..., description="Customer name")
    reference_number: str = Field(..., description="Reference number")
    total_rate: Decimal = Field(..., description="Total rate for the entire load")
    legs: List[LoadLegCreate] = Field(..., description="List of legs for the load")

class MultiLegLoadResponse(BaseModel):
    id: int
    customer_name: str
    reference_number: str
    total_rate: Decimal
    legs: List[LoadLegResponse]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class TransloadOperationCreate(BaseModel):
    load_id: int = Field(..., description="Load ID")
    facility_id: int = Field(..., description="Facility ID")
    facility_name: str = Field(..., description="Facility name")
    facility_location: str = Field(..., description="Facility location")
    operation_type: str = Field(default="transload", description="Operation type")
    dock_door: Optional[int] = Field(None, description="Dock door number")
    inbound_leg_id: Optional[int] = Field(None, description="Inbound leg ID")
    outbound_leg_id: Optional[int] = Field(None, description="Outbound leg ID")
    scheduled_start: datetime = Field(..., description="Scheduled start time")
    scheduled_end: Optional[datetime] = Field(None, description="Scheduled end time")
    labor_assigned: Optional[int] = Field(0, description="Number of labor assigned")
    equipment_staged: Optional[str] = Field(None, description="Staged equipment (JSON)")
    handling_cost: Optional[Decimal] = Field(None, description="Handling cost")
    storage_cost: Optional[Decimal] = Field(None, description="Storage cost")
    notes: Optional[str] = Field(None, description="Operation notes")

class TransloadOperationResponse(BaseModel):
    id: int
    load_id: int
    facility_id: int
    facility_name: str
    facility_location: str
    operation_type: str
    dock_door: Optional[int] = None
    inbound_leg_id: Optional[int] = None
    outbound_leg_id: Optional[int] = None
    scheduled_start: datetime
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    status: str
    labor_assigned: Optional[int] = None
    equipment_staged: Optional[str] = None
    handling_cost: Optional[Decimal] = None
    storage_cost: Optional[Decimal] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TransloadFacilityCreate(BaseModel):
    name: str = Field(..., description="Facility name")
    location: str = Field(..., description="Facility location")
    address: Optional[str] = Field(None, description="Full address")
    capacity: int = Field(..., description="Facility capacity")
    dock_doors: int = Field(..., description="Number of dock doors")
    contact_name: Optional[str] = Field(None, description="Contact name")
    contact_phone: Optional[str] = Field(None, description="Contact phone")
    contact_email: Optional[str] = Field(None, description="Contact email")
    services: Optional[str] = Field(None, description="Services offered (JSON)")
    operating_hours: Optional[str] = Field(None, description="Operating hours (JSON)")

class TransloadFacilityResponse(BaseModel):
    id: int
    name: str
    location: str
    address: Optional[str] = None
    capacity: int
    dock_doors: int
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    services: Optional[str] = None
    operating_hours: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DriverMatchResponse(BaseModel):
    driver_id: int
    driver_name: str
    score: int = Field(..., description="Match score (0-100)")
    reasons: List[str] = Field(..., description="Reasons for match")
    location: str
    equipment: str
    hours_remaining: float
    performance: int
    estimated_cost: Decimal
    estimated_miles: int
    estimated_fuel_cost: Decimal

class AutomatedDispatchRequest(BaseModel):
    load_id: int = Field(..., description="Load ID to dispatch")
    rules: Optional[List[str]] = Field(None, description="Dispatch rules to apply")
    max_matches: Optional[int] = Field(5, description="Maximum number of matches to return")
    auto_assign: Optional[bool] = Field(False, description="Automatically assign best match")

class AutomatedDispatchResponse(BaseModel):
    load_id: int
    matches: List[DriverMatchResponse]
    processing_time: float
    rules_applied: List[str]
    auto_assigned: bool
    assigned_driver_id: Optional[int] = None

class LoadCoordinationStatus(BaseModel):
    load_id: int
    total_legs: int
    assigned_legs: int
    completed_legs: int
    in_progress_legs: int
    handoff_issues: List[dict]
    next_actions: List[dict]
    coordination_score: int
    estimated_completion: Optional[datetime] = None

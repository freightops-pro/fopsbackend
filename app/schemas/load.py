from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, validator


class AccessorialCharge(BaseModel):
    type: str
    amount: float
    description: Optional[str] = None


class BillingDetails(BaseModel):
    rate_type: Optional[str] = None
    loaded_miles: Optional[float] = None
    empty_miles: Optional[float] = None
    payment_terms: Optional[str] = None
    factoring_enabled: Optional[bool] = None
    factoring_rate: Optional[float] = None
    notes: Optional[str] = None


class CustomerProfile(BaseModel):
    customer_id: Optional[str] = None
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    billing_email: Optional[str] = None
    billing_address: Optional[str] = None
    address: Optional[str] = None
    dot_number: Optional[str] = None
    mc_number: Optional[str] = None


class LoadStopCreate(BaseModel):
    stop_type: Literal["pickup", "drop", "checkpoint"]
    location_name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    lat: Optional[float] = None  # GPS latitude for map display
    lng: Optional[float] = None  # GPS longitude for map display
    scheduled_at: Optional[datetime] = None
    instructions: Optional[str] = None
    metadata: Optional[dict] = None
    distance_miles: Optional[float] = None
    fuel_estimate_gallons: Optional[float] = None
    dwell_minutes_estimate: Optional[int] = None


class LoadCreate(BaseModel):
    customer_name: str
    load_type: str
    commodity: str
    base_rate: float
    notes: Optional[str] = None
    stops: List[LoadStopCreate] = Field(..., min_length=1)

    accessorials: List[AccessorialCharge] = Field(default_factory=list)
    billing_details: Optional[BillingDetails] = None
    customer_profile: Optional[CustomerProfile] = None

    container_number: Optional[str] = None
    container_size: Optional[str] = None
    container_type: Optional[str] = None
    vessel_name: Optional[str] = None
    voyage_number: Optional[str] = None
    origin_port_code: Optional[str] = None
    destination_port_code: Optional[str] = None
    drayage_appointment: Optional[str] = None
    customs_hold: Optional[str] = None
    customs_reference: Optional[str] = None
    preferred_driver_ids: Optional[list[str]] = None
    preferred_truck_ids: Optional[list[str]] = None
    required_skills: Optional[list[str]] = None

    @validator("container_number")
    def container_required_for_container_load(cls, value, values):
        if (values.get("load_type") == "container") and not value:
            raise ValueError("Container number required for container loads")
        return value

    @validator("origin_port_code")
    def origin_required_for_container_load(cls, value, values):
        if (values.get("load_type") == "container") and not value:
            raise ValueError("Origin port is required for container loads")
        return value


class LoadUpdate(LoadCreate):
    pass


class LoadStopResponse(BaseModel):
    id: str
    sequence: int
    stop_type: str
    location_name: str
    address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postal_code: Optional[str]
    lat: Optional[float] = None  # GPS latitude for map display
    lng: Optional[float] = None  # GPS longitude for map display
    scheduled_at: Optional[datetime]
    instructions: Optional[str]

    model_config = {"from_attributes": True}


class LoadExpense(BaseModel):
    """Expense item matched to a load (fuel, detention, accessorial, etc.)."""
    id: str
    entry_type: Literal["FUEL", "DETENTION", "ACCESSORIAL", "OTHER"]
    description: str
    amount: float
    quantity: Optional[float] = None
    unit: Optional[str] = None
    recorded_at: datetime


class LoadProfitSummary(BaseModel):
    """Profit calculation summary for a load."""
    total_expenses: float
    gross_profit: float
    profit_margin: float  # percentage (0-100)


class LoadResponse(BaseModel):
    id: str
    customer_name: str
    load_type: str
    commodity: str
    base_rate: float
    status: str
    notes: Optional[str]
    container_number: Optional[str]
    container_size: Optional[str]
    container_type: Optional[str]
    vessel_name: Optional[str]
    voyage_number: Optional[str]
    origin_port_code: Optional[str]
    destination_port_code: Optional[str]
    drayage_appointment: Optional[str]
    customs_hold: Optional[str]
    customs_reference: Optional[str]

    # Port appointment fields (ePass/entry code)
    port_appointment_id: Optional[str] = None
    port_appointment_number: Optional[str] = None
    port_entry_code: Optional[str] = None
    port_appointment_time: Optional[datetime] = None
    port_appointment_gate: Optional[str] = None
    port_appointment_status: Optional[str] = None
    port_appointment_terminal: Optional[str] = None

    # Assignment fields
    driver_id: Optional[str] = None
    truck_id: Optional[str] = None

    # Live location tracking (from ELD/driver app)
    last_known_lat: Optional[float] = None
    last_known_lng: Optional[float] = None
    last_location_update: Optional[datetime] = None

    # Pickup/delivery location tracking
    pickup_arrival_lat: Optional[float] = None
    pickup_arrival_lng: Optional[float] = None
    pickup_arrival_time: Optional[datetime] = None
    delivery_arrival_lat: Optional[float] = None
    delivery_arrival_lng: Optional[float] = None
    delivery_arrival_time: Optional[datetime] = None

    metadata: Optional[dict] = Field(None, validation_alias="metadata_json")
    created_at: datetime
    updated_at: datetime
    stops: List[LoadStopResponse]

    # Expense tracking (populated from fuel transactions and other sources)
    expenses: List[LoadExpense] = []
    profit_summary: Optional[LoadProfitSummary] = None

    # Factoring fields
    factoring_enabled: Optional[str] = None
    factoring_status: Optional[str] = None
    factoring_rate_override: Optional[float] = None
    factored_amount: Optional[float] = None
    factoring_fee_amount: Optional[float] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class LoadStopScheduleUpdate(BaseModel):
    scheduled_at: datetime


class LoadAssignmentUpdate(BaseModel):
    driver_id: Optional[str] = None
    truck_id: Optional[str] = None


class CreatePortAppointmentRequest(BaseModel):
    """Request to create a port appointment for a load."""
    appointment_time: datetime
    transaction_type: str = "PUI"  # PUI=Pick Up Import, DOE=Drop Off Export
    trucking_company: str
    driver_license: Optional[str] = None
    truck_license: Optional[str] = None


class PortAppointmentResponse(BaseModel):
    """Response after creating a port appointment."""
    load_id: str
    appointment_id: str
    appointment_number: str
    entry_code: Optional[str] = None
    appointment_time: datetime
    gate: Optional[str] = None
    terminal: Optional[str] = None
    status: str


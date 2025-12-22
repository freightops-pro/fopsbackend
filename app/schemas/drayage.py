"""
Pydantic schemas for drayage operations.

Supports container lifecycle management, steamship line integration,
chassis pool tracking, and demurrage/detention calculations.
"""

from datetime import datetime, date
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, validator


# ==================== STEAMSHIP LINE SCHEMAS ====================


class SteamshipLineCreate(BaseModel):
    """Schema for creating a steamship line configuration."""
    scac_code: str = Field(..., min_length=4, max_length=4, description="Standard Carrier Alpha Code")
    name: str = Field(..., min_length=1, max_length=255)
    short_name: Optional[str] = Field(None, max_length=50)
    logo_url: Optional[str] = Field(None, max_length=500)

    # API Configuration
    api_type: Optional[str] = Field(None, max_length=50)  # maersk, msc, cma_cgm, hapag
    api_base_url: Optional[str] = Field(None, max_length=500)
    api_credentials: Optional[dict] = None
    api_status: str = Field(default="not_configured", max_length=50)

    # Free Time Rules
    port_free_days: int = Field(default=4, ge=0)
    rail_free_days: int = Field(default=2, ge=0)
    detention_free_days: int = Field(default=4, ge=0)
    weekend_counts: bool = Field(default=False)
    holiday_counts: bool = Field(default=False)

    # Demurrage rates (USD per day)
    demurrage_rate_tier1: Optional[float] = Field(None, ge=0)  # Days 1-5
    demurrage_rate_tier2: Optional[float] = Field(None, ge=0)  # Days 6-10
    demurrage_rate_tier3: Optional[float] = Field(None, ge=0)  # Days 11+
    detention_rate_per_day: Optional[float] = Field(None, ge=0)

    # Per diem rates
    per_diem_rate_20: Optional[float] = Field(None, ge=0)
    per_diem_rate_40: Optional[float] = Field(None, ge=0)
    per_diem_rate_45: Optional[float] = Field(None, ge=0)

    # Contact Information
    customer_service_phone: Optional[str] = Field(None, max_length=50)
    customer_service_email: Optional[str] = Field(None, max_length=255)
    equipment_return_email: Optional[str] = Field(None, max_length=255)
    demurrage_dispute_email: Optional[str] = Field(None, max_length=255)

    # Metadata
    notes: Optional[str] = None
    is_active: bool = Field(default=True)


class SteamshipLineUpdate(SteamshipLineCreate):
    """Schema for updating a steamship line configuration."""
    scac_code: Optional[str] = Field(None, min_length=4, max_length=4)
    name: Optional[str] = Field(None, min_length=1, max_length=255)


class SteamshipLineResponse(BaseModel):
    """Schema for steamship line response."""
    id: str
    company_id: str
    scac_code: str
    name: str
    short_name: Optional[str]
    logo_url: Optional[str]

    api_type: Optional[str]
    api_base_url: Optional[str]
    api_status: str

    port_free_days: int
    rail_free_days: int
    detention_free_days: int
    weekend_counts: bool
    holiday_counts: bool

    demurrage_rate_tier1: Optional[float]
    demurrage_rate_tier2: Optional[float]
    demurrage_rate_tier3: Optional[float]
    detention_rate_per_day: Optional[float]

    per_diem_rate_20: Optional[float]
    per_diem_rate_40: Optional[float]
    per_diem_rate_45: Optional[float]

    customer_service_phone: Optional[str]
    customer_service_email: Optional[str]
    equipment_return_email: Optional[str]
    demurrage_dispute_email: Optional[str]

    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==================== CHASSIS POOL SCHEMAS ====================


class ChassisPoolCreate(BaseModel):
    """Schema for creating a chassis pool configuration."""
    pool_code: str = Field(..., min_length=1, max_length=20)  # DCLI, TRAC, FLXV
    name: str = Field(..., min_length=1, max_length=255)
    provider_type: str = Field(..., max_length=50)  # pool, private, ssl_provided

    # API Configuration
    api_base_url: Optional[str] = Field(None, max_length=500)
    api_credentials: Optional[dict] = None
    api_status: str = Field(default="not_configured", max_length=50)

    # Per Diem Rates (USD per day)
    per_diem_rate_20: Optional[float] = Field(None, ge=0)
    per_diem_rate_40: Optional[float] = Field(None, ge=0)
    per_diem_rate_45: Optional[float] = Field(None, ge=0)
    per_diem_rate_reefer: Optional[float] = Field(None, ge=0)

    # Free time
    free_days: int = Field(default=1, ge=0)
    split_free_time: bool = Field(default=True)

    # Pool restrictions
    allowed_terminals: Optional[dict] = None
    restricted_steamship_lines: Optional[dict] = None
    operating_regions: Optional[dict] = None

    # Billing
    billing_contact_email: Optional[str] = Field(None, max_length=255)
    billing_portal_url: Optional[str] = Field(None, max_length=500)
    account_number: Optional[str] = Field(None, max_length=100)

    # Metadata
    notes: Optional[str] = None
    is_active: bool = Field(default=True)


class ChassisPoolUpdate(ChassisPoolCreate):
    """Schema for updating a chassis pool configuration."""
    pool_code: Optional[str] = Field(None, min_length=1, max_length=20)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    provider_type: Optional[str] = Field(None, max_length=50)


class ChassisPoolResponse(BaseModel):
    """Schema for chassis pool response."""
    id: str
    company_id: str
    pool_code: str
    name: str
    provider_type: str

    api_base_url: Optional[str]
    api_status: str

    per_diem_rate_20: Optional[float]
    per_diem_rate_40: Optional[float]
    per_diem_rate_45: Optional[float]
    per_diem_rate_reefer: Optional[float]

    free_days: int
    split_free_time: bool

    allowed_terminals: Optional[dict]
    restricted_steamship_lines: Optional[dict]
    operating_regions: Optional[dict]

    billing_contact_email: Optional[str]
    billing_portal_url: Optional[str]
    account_number: Optional[str]

    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==================== CHASSIS USAGE SCHEMAS ====================


class ChassisCheckout(BaseModel):
    """Schema for checking out a chassis from a pool."""
    chassis_number: str = Field(..., min_length=1, max_length=20)
    chassis_size: str = Field(..., max_length=10)  # 20, 40, 45
    chassis_type: str = Field(..., max_length=20)  # STANDARD, EXTENDABLE, REEFER, FLATBED
    chassis_pool_id: str
    outgate_terminal: Optional[str] = Field(None, max_length=20)
    outgate_at: datetime
    notes: Optional[str] = None


class ChassisReturn(BaseModel):
    """Schema for returning a chassis to a pool."""
    ingate_terminal: Optional[str] = Field(None, max_length=20)
    ingate_at: datetime
    notes: Optional[str] = None


class ChassisUsageResponse(BaseModel):
    """Schema for chassis usage response."""
    id: str
    company_id: str
    container_id: str
    chassis_pool_id: str

    chassis_number: str
    chassis_size: str
    chassis_type: str

    outgate_terminal: Optional[str]
    outgate_at: datetime
    ingate_terminal: Optional[str]
    ingate_at: Optional[datetime]

    free_days: int
    chargeable_days: int
    rate_per_day: Optional[float]
    total_amount: Optional[float]

    status: str  # ACTIVE, RETURNED, INVOICED
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==================== TERMINAL SCHEMAS ====================


class TerminalCreate(BaseModel):
    """Schema for creating a terminal configuration."""
    port_code: str = Field(..., min_length=1, max_length=10)  # USLAX, USLGB
    terminal_code: str = Field(..., min_length=1, max_length=20)  # TRAPAC, LBCT, PNCT
    firms_code: Optional[str] = Field(None, max_length=10)
    name: str = Field(..., min_length=1, max_length=255)

    # Appointment System
    appointment_system: Optional[str] = Field(None, max_length=50)  # advent, tideworks, n4
    appointment_lead_time_hours: int = Field(default=24, ge=0)
    appointment_window_minutes: int = Field(default=60, ge=0)
    dual_transaction_allowed: bool = Field(default=True)
    same_day_appointments: bool = Field(default=False)

    # Operating Hours
    gate_hours: Optional[dict] = None
    first_shift: Optional[str] = Field(None, max_length=20)
    second_shift: Optional[str] = Field(None, max_length=20)
    third_shift: Optional[str] = Field(None, max_length=20)

    # Cut-off Times
    vessel_cutoff_hours: int = Field(default=48, ge=0)
    reefer_cutoff_hours: int = Field(default=72, ge=0)
    hazmat_cutoff_hours: int = Field(default=96, ge=0)

    # Turn Times
    avg_turn_time_import: Optional[int] = Field(None, ge=0)
    avg_turn_time_export: Optional[int] = Field(None, ge=0)
    avg_turn_time_dual: Optional[int] = Field(None, ge=0)

    # Contact Information
    dispatch_phone: Optional[str] = Field(None, max_length=50)
    trouble_phone: Optional[str] = Field(None, max_length=50)
    gate_email: Optional[str] = Field(None, max_length=255)

    # API Credentials
    api_credentials: Optional[dict] = None
    api_status: str = Field(default="not_configured", max_length=50)

    # Metadata
    notes: Optional[str] = None
    is_active: bool = Field(default=True)


class TerminalUpdate(TerminalCreate):
    """Schema for updating a terminal configuration."""
    port_code: Optional[str] = Field(None, min_length=1, max_length=10)
    terminal_code: Optional[str] = Field(None, min_length=1, max_length=20)
    name: Optional[str] = Field(None, min_length=1, max_length=255)


class TerminalResponse(BaseModel):
    """Schema for terminal response."""
    id: str
    company_id: str
    port_code: str
    terminal_code: str
    firms_code: Optional[str]
    name: str

    appointment_system: Optional[str]
    appointment_lead_time_hours: int
    appointment_window_minutes: int
    dual_transaction_allowed: bool
    same_day_appointments: bool

    gate_hours: Optional[dict]
    first_shift: Optional[str]
    second_shift: Optional[str]
    third_shift: Optional[str]

    vessel_cutoff_hours: int
    reefer_cutoff_hours: int
    hazmat_cutoff_hours: int

    avg_turn_time_import: Optional[int]
    avg_turn_time_export: Optional[int]
    avg_turn_time_dual: Optional[int]

    dispatch_phone: Optional[str]
    trouble_phone: Optional[str]
    gate_email: Optional[str]

    api_status: str
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==================== CONTAINER SCHEMAS ====================


class ContainerCreate(BaseModel):
    """Schema for creating a drayage container."""
    container_number: str = Field(..., min_length=1, max_length=20)
    container_size: str = Field(..., max_length=10)  # 20, 40, 40HC, 45
    container_type: str = Field(..., max_length=20)  # DRY, REEFER, FLAT, TANK

    # Hazmat and weight
    is_hazmat: bool = Field(default=False)
    hazmat_class: Optional[str] = Field(None, max_length=20)
    is_overweight: bool = Field(default=False)
    gross_weight_lbs: Optional[int] = Field(None, ge=0)

    # References
    booking_number: Optional[str] = Field(None, max_length=50)
    bill_of_lading: Optional[str] = Field(None, max_length=50)
    house_bill: Optional[str] = Field(None, max_length=50)
    seal_number: Optional[str] = Field(None, max_length=50)
    reference_number: Optional[str] = Field(None, max_length=100)

    # Steamship Line
    steamship_line_id: Optional[str] = None
    ssl_scac: Optional[str] = Field(None, max_length=4)

    # Terminal/Port
    terminal_id: Optional[str] = None
    port_code: Optional[str] = Field(None, max_length=10)
    terminal_code: Optional[str] = Field(None, max_length=20)

    # Vessel Information
    vessel_name: Optional[str] = Field(None, max_length=100)
    voyage_number: Optional[str] = Field(None, max_length=50)
    vessel_eta: Optional[datetime] = None
    vessel_ata: Optional[datetime] = None

    # Status
    status: str = Field(default="BOOKING", max_length=30)

    # Critical Dates
    discharge_date: Optional[datetime] = None
    last_free_day: Optional[datetime] = None
    per_diem_start_date: Optional[datetime] = None
    detention_start_date: Optional[datetime] = None
    empty_return_by: Optional[datetime] = None

    # Pickup Information
    pickup_terminal_code: Optional[str] = Field(None, max_length=20)
    pickup_scheduled_at: Optional[datetime] = None
    delivery_location: Optional[str] = Field(None, max_length=500)
    delivery_appointment_at: Optional[datetime] = None

    # Empty Return Information
    return_terminal_code: Optional[str] = Field(None, max_length=20)
    return_scheduled_at: Optional[datetime] = None

    # Holds
    holds: Optional[dict] = None
    hold_notes: Optional[str] = None

    # Metadata
    notes: Optional[str] = None
    metadata_json: Optional[dict] = None


class ContainerUpdate(BaseModel):
    """Schema for updating a container."""
    container_size: Optional[str] = Field(None, max_length=10)
    container_type: Optional[str] = Field(None, max_length=20)

    is_hazmat: Optional[bool] = None
    hazmat_class: Optional[str] = Field(None, max_length=20)
    is_overweight: Optional[bool] = None
    gross_weight_lbs: Optional[int] = Field(None, ge=0)

    booking_number: Optional[str] = Field(None, max_length=50)
    bill_of_lading: Optional[str] = Field(None, max_length=50)
    house_bill: Optional[str] = Field(None, max_length=50)
    seal_number: Optional[str] = Field(None, max_length=50)
    reference_number: Optional[str] = Field(None, max_length=100)

    steamship_line_id: Optional[str] = None
    ssl_scac: Optional[str] = Field(None, max_length=4)

    terminal_id: Optional[str] = None
    port_code: Optional[str] = Field(None, max_length=10)
    terminal_code: Optional[str] = Field(None, max_length=20)

    vessel_name: Optional[str] = Field(None, max_length=100)
    voyage_number: Optional[str] = Field(None, max_length=50)
    vessel_eta: Optional[datetime] = None
    vessel_ata: Optional[datetime] = None

    status: Optional[str] = Field(None, max_length=30)

    discharge_date: Optional[datetime] = None
    last_free_day: Optional[datetime] = None
    per_diem_start_date: Optional[datetime] = None
    detention_start_date: Optional[datetime] = None
    empty_return_by: Optional[datetime] = None

    pickup_terminal_code: Optional[str] = Field(None, max_length=20)
    pickup_scheduled_at: Optional[datetime] = None
    delivery_location: Optional[str] = Field(None, max_length=500)
    delivery_appointment_at: Optional[datetime] = None

    return_terminal_code: Optional[str] = Field(None, max_length=20)
    return_scheduled_at: Optional[datetime] = None

    holds: Optional[dict] = None
    hold_notes: Optional[str] = None

    notes: Optional[str] = None
    metadata_json: Optional[dict] = None


class ContainerResponse(BaseModel):
    """Schema for container response."""
    id: str
    company_id: str
    load_id: Optional[str]

    container_number: str
    container_size: str
    container_type: str
    is_hazmat: bool
    hazmat_class: Optional[str]
    is_overweight: bool
    gross_weight_lbs: Optional[int]

    booking_number: Optional[str]
    bill_of_lading: Optional[str]
    house_bill: Optional[str]
    seal_number: Optional[str]
    reference_number: Optional[str]

    steamship_line_id: Optional[str]
    ssl_scac: Optional[str]

    terminal_id: Optional[str]
    port_code: Optional[str]
    terminal_code: Optional[str]

    vessel_name: Optional[str]
    voyage_number: Optional[str]
    vessel_eta: Optional[datetime]
    vessel_ata: Optional[datetime]

    status: str

    discharge_date: Optional[datetime]
    last_free_day: Optional[datetime]
    per_diem_start_date: Optional[datetime]
    detention_start_date: Optional[datetime]
    empty_return_by: Optional[datetime]

    pickup_terminal_code: Optional[str]
    pickup_appointment_id: Optional[str]
    pickup_scheduled_at: Optional[datetime]
    pickup_actual_at: Optional[datetime]
    outgate_at: Optional[datetime]

    delivery_location: Optional[str]
    delivery_appointment_at: Optional[datetime]
    delivery_actual_at: Optional[datetime]

    return_terminal_code: Optional[str]
    return_appointment_id: Optional[str]
    return_scheduled_at: Optional[datetime]
    return_actual_at: Optional[datetime]
    ingate_at: Optional[datetime]

    chassis_number: Optional[str]
    chassis_pool_id: Optional[str]
    chassis_pool_code: Optional[str]
    chassis_outgate_at: Optional[datetime]
    chassis_return_at: Optional[datetime]

    holds: Optional[dict]
    hold_notes: Optional[str]

    demurrage_days: int
    demurrage_amount: Optional[float]
    per_diem_days: int
    per_diem_amount: Optional[float]
    detention_days: int
    detention_amount: Optional[float]
    chassis_per_diem_amount: Optional[float]
    total_accessorial_charges: Optional[float]

    port_raw_data: Optional[dict]
    notes: Optional[str]
    metadata_json: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContainerAssignLoad(BaseModel):
    """Schema for assigning a container to a load."""
    load_id: str


class ContainerUpdateStatus(BaseModel):
    """Schema for updating container status."""
    status: Literal[
        "BOOKING",
        "RELEASED",
        "AVAILABLE",
        "HOLD",
        "DISPATCHED",
        "PICKED_UP",
        "IN_TRANSIT",
        "DELIVERED",
        "EMPTY",
        "RETURNED",
        "CANCELLED"
    ]
    notes: Optional[str] = None


# ==================== APPOINTMENT SCHEMAS ====================


class AppointmentCreate(BaseModel):
    """Schema for creating a terminal appointment."""
    container_id: str
    terminal_id: str

    appointment_type: Literal["PICKUP", "RETURN", "DUAL"]
    transaction_type: Literal["IMPORT_PICKUP", "EXPORT_RETURN", "EMPTY_RETURN"]

    # Port appointment reference
    port_appointment_id: Optional[str] = Field(None, max_length=100)
    port_confirmation_number: Optional[str] = Field(None, max_length=50)
    port_entry_code: Optional[str] = Field(None, max_length=20)

    # Scheduling
    scheduled_date: datetime
    scheduled_window_start: datetime
    scheduled_window_end: datetime
    shift: Optional[Literal["1ST", "2ND", "3RD"]] = None

    # Driver/Equipment assignment
    driver_id: Optional[str] = None
    truck_id: Optional[str] = None
    truck_license: Optional[str] = Field(None, max_length=20)
    driver_license: Optional[str] = Field(None, max_length=50)

    # Dual transaction
    is_dual_transaction: bool = Field(default=False)
    dual_container_id: Optional[str] = None
    dual_container_number: Optional[str] = Field(None, max_length=20)

    # Metadata
    notes: Optional[str] = None


class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment."""
    scheduled_date: Optional[datetime] = None
    scheduled_window_start: Optional[datetime] = None
    scheduled_window_end: Optional[datetime] = None
    shift: Optional[Literal["1ST", "2ND", "3RD"]] = None

    driver_id: Optional[str] = None
    truck_id: Optional[str] = None
    truck_license: Optional[str] = Field(None, max_length=20)
    driver_license: Optional[str] = Field(None, max_length=50)

    status: Optional[Literal[
        "SCHEDULED",
        "CONFIRMED",
        "IN_PROGRESS",
        "COMPLETED",
        "CANCELLED",
        "MISSED",
        "RESCHEDULED"
    ]] = None

    notes: Optional[str] = None


class AppointmentResponse(BaseModel):
    """Schema for appointment response."""
    id: str
    company_id: str
    container_id: str
    terminal_id: str

    appointment_type: str
    transaction_type: str

    port_appointment_id: Optional[str]
    port_confirmation_number: Optional[str]
    port_entry_code: Optional[str]

    scheduled_date: datetime
    scheduled_window_start: datetime
    scheduled_window_end: datetime
    shift: Optional[str]

    gate_in_at: Optional[datetime]
    gate_out_at: Optional[datetime]
    actual_turn_time_minutes: Optional[int]

    driver_id: Optional[str]
    truck_id: Optional[str]
    truck_license: Optional[str]
    driver_license: Optional[str]

    status: str

    is_dual_transaction: bool
    dual_container_id: Optional[str]
    dual_container_number: Optional[str]

    notes: Optional[str]
    port_raw_response: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==================== CHARGE SCHEMAS ====================


class ChargeCreate(BaseModel):
    """Schema for creating a drayage charge."""
    container_id: str

    charge_type: Literal[
        "DEMURRAGE",
        "PER_DIEM",
        "DETENTION",
        "CHASSIS_PER_DIEM",
        "FLIP",
        "STORAGE",
        "EXAM_FEE",
        "REEFER_FUEL",
        "OVERWEIGHT",
        "HAZMAT",
        "PRE_PULL",
        "YARD_STORAGE"
    ]

    description: Optional[str] = Field(None, max_length=500)
    source: Literal["SSL", "TERMINAL", "CHASSIS_POOL", "TRUCKING_CO"]

    charge_start_date: Optional[datetime] = None
    charge_end_date: Optional[datetime] = None
    chargeable_days: int = Field(default=0, ge=0)

    rate_per_day: Optional[float] = Field(None, ge=0)
    rate_tier: Optional[Literal["TIER1", "TIER2", "TIER3"]] = None
    quantity: float = Field(default=1, ge=0)
    amount: float = Field(..., ge=0)

    status: Literal["PENDING", "INVOICED", "DISPUTED", "WAIVED", "PAID"] = Field(default="PENDING")

    invoice_id: Optional[str] = None
    invoice_number: Optional[str] = Field(None, max_length=50)

    notes: Optional[str] = None


class ChargeUpdate(BaseModel):
    """Schema for updating a charge."""
    description: Optional[str] = Field(None, max_length=500)

    charge_start_date: Optional[datetime] = None
    charge_end_date: Optional[datetime] = None
    chargeable_days: Optional[int] = Field(None, ge=0)

    rate_per_day: Optional[float] = Field(None, ge=0)
    rate_tier: Optional[Literal["TIER1", "TIER2", "TIER3"]] = None
    quantity: Optional[float] = Field(None, ge=0)
    amount: Optional[float] = Field(None, ge=0)

    status: Optional[Literal["PENDING", "INVOICED", "DISPUTED", "WAIVED", "PAID"]] = None

    invoice_id: Optional[str] = None
    invoice_number: Optional[str] = Field(None, max_length=50)

    notes: Optional[str] = None


class ChargeResponse(BaseModel):
    """Schema for charge response."""
    id: str
    company_id: str
    container_id: str

    charge_type: str
    description: Optional[str]
    source: str

    charge_start_date: Optional[datetime]
    charge_end_date: Optional[datetime]
    chargeable_days: int

    rate_per_day: Optional[float]
    rate_tier: Optional[str]
    quantity: float
    amount: float

    status: str

    invoice_id: Optional[str]
    invoice_number: Optional[str]

    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==================== EVENT SCHEMAS ====================


class EventCreate(BaseModel):
    """Schema for creating a drayage event."""
    container_id: str

    event_type: Literal[
        "VESSEL_ARRIVAL",
        "DISCHARGE",
        "AVAILABLE",
        "HOLD_PLACED",
        "HOLD_RELEASED",
        "LFD_SET",
        "LFD_EXTENDED",
        "APPOINTMENT_CREATED",
        "OUTGATE",
        "DELIVERY",
        "EMPTY",
        "INGATE",
        "RETURNED",
        "DEMURRAGE_START",
        "DETENTION_START"
    ]

    event_at: datetime
    location: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    source: Literal["PORT_API", "SSL_API", "DRIVER", "DISPATCHER", "SYSTEM"]

    related_entity_type: Optional[str] = Field(None, max_length=30)
    related_entity_id: Optional[str] = None

    metadata_json: Optional[dict] = None


class EventResponse(BaseModel):
    """Schema for event response."""
    id: str
    company_id: str
    container_id: str

    event_type: str
    event_at: datetime
    location: Optional[str]
    description: Optional[str]

    source: str

    related_entity_type: Optional[str]
    related_entity_id: Optional[str]

    metadata_json: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


# ==================== EXTENDED RESPONSE SCHEMAS ====================


class ContainerDetailedResponse(ContainerResponse):
    """Extended container response with related entities."""
    appointments: List[AppointmentResponse] = []
    charges: List[ChargeResponse] = []
    chassis_usages: List[ChassisUsageResponse] = []
    events: List[EventResponse] = []
    steamship_line: Optional[SteamshipLineResponse] = None
    terminal: Optional[TerminalResponse] = None

    model_config = {"from_attributes": True}


# ==================== BULK OPERATIONS ====================


class ContainerBulkCreate(BaseModel):
    """Schema for bulk container creation."""
    containers: List[ContainerCreate]


class ContainerBulkStatusUpdate(BaseModel):
    """Schema for bulk container status updates."""
    container_ids: List[str]
    status: Literal[
        "BOOKING",
        "RELEASED",
        "AVAILABLE",
        "HOLD",
        "DISPATCHED",
        "PICKED_UP",
        "IN_TRANSIT",
        "DELIVERED",
        "EMPTY",
        "RETURNED",
        "CANCELLED"
    ]
    notes: Optional[str] = None

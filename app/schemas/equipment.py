from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class EquipmentCreate(BaseModel):
    unit_number: str = Field(alias="unitNumber")
    equipment_type: str = Field(alias="equipmentKind")  # TRACTOR, TRAILER from frontend
    status: str = "ACTIVE"
    operational_status: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = Field(default=None, ge=1900, le=2100)
    vin: Optional[str] = Field(default=None, alias="vinNumber")
    current_mileage: Optional[int] = Field(default=None, ge=0)
    current_engine_hours: Optional[float] = Field(default=None, ge=0)
    gps_provider: Optional[str] = None
    gps_device_id: Optional[str] = None
    eld_provider: Optional[str] = None
    eld_device_id: Optional[str] = None
    assigned_driver_id: Optional[str] = None

    model_config = {"populate_by_name": True}


class EquipmentUsageEventCreate(BaseModel):
    recorded_at: Optional[datetime] = None
    odometer: Optional[int] = Field(default=None, ge=0)
    engine_hours: Optional[float] = Field(default=None, ge=0)
    source: Optional[str] = None
    notes: Optional[str] = None


class EquipmentMaintenanceCreate(BaseModel):
    service_type: str
    service_date: date
    vendor: Optional[str] = None
    odometer: Optional[int] = Field(default=None, ge=0)
    engine_hours: Optional[float] = Field(default=None, ge=0)
    cost: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None
    next_due_date: Optional[date] = None
    next_due_mileage: Optional[int] = Field(default=None, ge=0)
    invoice_id: Optional[str] = None


class EquipmentUsageEventResponse(BaseModel):
    id: str
    equipment_id: str
    recorded_at: datetime
    odometer: Optional[int]
    engine_hours: Optional[float]
    source: Optional[str]
    notes: Optional[str]

    model_config = {"from_attributes": True}


class EquipmentMaintenanceEventResponse(BaseModel):
    id: str
    equipment_id: str
    service_type: str
    service_date: date
    vendor: Optional[str]
    odometer: Optional[int]
    engine_hours: Optional[float]
    cost: Optional[float]
    notes: Optional[str]
    next_due_date: Optional[date]
    next_due_mileage: Optional[int]
    invoice_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class EquipmentMaintenanceForecastResponse(BaseModel):
    id: str
    equipment_id: str
    service_type: str
    status: str
    projected_service_date: Optional[date]
    projected_service_mileage: Optional[int]
    confidence: float
    risk_score: float
    notes: Optional[str]
    generated_at: datetime

    model_config = {"from_attributes": True}


class TruckLoadExpenseBreakdown(BaseModel):
    """Expense breakdown by category for a load."""
    fuel: float = 0
    detention: float = 0
    accessorial: float = 0
    other: float = 0
    total: float = 0


class TruckLoadExpense(BaseModel):
    """Expense summary for a single load assigned to a truck (for settlement)."""
    load_id: str
    load_reference: str
    customer_name: str
    base_rate: float
    expenses: TruckLoadExpenseBreakdown
    profit: float
    completed_at: Optional[datetime] = None


class EquipmentResponse(BaseModel):
    id: str
    company_id: str
    unit_number: str
    equipment_type: str
    status: str
    operational_status: Optional[str]
    make: Optional[str]
    model: Optional[str]
    year: Optional[int]
    vin: Optional[str]
    current_mileage: Optional[int]
    current_engine_hours: Optional[float]
    gps_provider: Optional[str]
    gps_device_id: Optional[str]
    eld_provider: Optional[str]
    eld_device_id: Optional[str]

    # Live location tracking (from ELD/GPS telemetry)
    current_lat: Optional[float] = None
    current_lng: Optional[float] = None
    current_city: Optional[str] = None
    current_state: Optional[str] = None
    last_location_update: Optional[datetime] = None
    heading: Optional[float] = None
    speed_mph: Optional[float] = None

    assigned_driver_id: Optional[str]
    assigned_truck_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    maintenance_events: List[EquipmentMaintenanceEventResponse] = []
    usage_events: List[EquipmentUsageEventResponse] = []
    maintenance_forecasts: List[EquipmentMaintenanceForecastResponse] = []

    # Expense tracking for settlement (populated from fuel transactions matched to loads)
    load_expenses: List[TruckLoadExpense] = []

    model_config = {"from_attributes": True}


class LocationUpdate(BaseModel):
    """Schema for updating equipment location from ELD/driver app/telemetry."""
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    city: Optional[str] = None
    state: Optional[str] = None
    heading: Optional[float] = Field(default=None, ge=0, le=360)
    speed_mph: Optional[float] = Field(default=None, ge=0)
    odometer: Optional[int] = Field(default=None, ge=0)
    source: Optional[str] = None  # "eld", "driver_app", "samsara", "motive"


class BulkLocationUpdate(BaseModel):
    """Schema for bulk location updates from telemetry providers."""
    updates: List["EquipmentLocationUpdate"]


class EquipmentLocationUpdate(LocationUpdate):
    """Location update with equipment identifier."""
    equipment_id: Optional[str] = None
    unit_number: Optional[str] = None  # Alternative to equipment_id
    eld_device_id: Optional[str] = None  # Alternative lookup key


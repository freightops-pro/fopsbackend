from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class LocationType(str, Enum):
    TERMINAL = "terminal"
    OFFICE = "office"
    WAREHOUSE = "warehouse"
    YARD = "yard"


# Location Schemas

class LocationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    location_type: LocationType
    address: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=50)
    zip_code: str = Field(..., min_length=5, max_length=20)
    country: str = Field(default="US", max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    contact_person: Optional[str] = Field(None, max_length=100)
    is_primary: bool = False
    timezone: str = Field(default="UTC", max_length=50)
    capacity_trucks: Optional[int] = Field(None, ge=0)
    capacity_trailers: Optional[int] = Field(None, ge=0)
    has_fuel_island: bool = False
    has_scale: bool = False
    has_shop: bool = False
    has_office: bool = False
    latitude: Optional[str] = Field(None, max_length=20)
    longitude: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None
    operating_hours: Optional[Dict[str, Any]] = None
    facilities: Optional[Dict[str, Any]] = None


class LocationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    location_type: Optional[LocationType] = None
    address: Optional[str] = Field(None, min_length=1)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, min_length=2, max_length=50)
    zip_code: Optional[str] = Field(None, min_length=5, max_length=20)
    country: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    contact_person: Optional[str] = Field(None, max_length=100)
    is_primary: Optional[bool] = None
    timezone: Optional[str] = Field(None, max_length=50)
    capacity_trucks: Optional[int] = Field(None, ge=0)
    capacity_trailers: Optional[int] = Field(None, ge=0)
    has_fuel_island: Optional[bool] = None
    has_scale: Optional[bool] = None
    has_shop: Optional[bool] = None
    has_office: Optional[bool] = None
    latitude: Optional[str] = Field(None, max_length=20)
    longitude: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = None
    operating_hours: Optional[Dict[str, Any]] = None
    facilities: Optional[Dict[str, Any]] = None


class LocationResponse(BaseModel):
    id: int
    company_id: int
    name: str
    location_type: str
    address: str
    city: str
    state: str
    zip_code: str
    country: str
    phone: Optional[str]
    email: Optional[str]
    contact_person: Optional[str]
    is_active: bool
    is_primary: bool
    timezone: str
    capacity_trucks: Optional[int]
    capacity_trailers: Optional[int]
    has_fuel_island: bool
    has_scale: bool
    has_shop: bool
    has_office: bool
    latitude: Optional[str]
    longitude: Optional[str]
    notes: Optional[str]
    operating_hours: Optional[Dict[str, Any]]
    facilities: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Location User Schemas

class LocationUserCreate(BaseModel):
    user_id: int
    can_view: bool = True
    can_edit: bool = False
    can_manage: bool = False
    can_dispatch: bool = False
    can_view_financials: bool = False
    is_primary_location: bool = False


class LocationUserResponse(BaseModel):
    id: int
    location_id: int
    user_id: int
    can_view: bool
    can_edit: bool
    can_manage: bool
    can_dispatch: bool
    can_view_financials: bool
    is_primary_location: bool
    assigned_at: datetime
    assigned_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Location Equipment Schemas

class LocationEquipmentCreate(BaseModel):
    vehicle_id: int
    assigned_by_id: Optional[int] = None
    status: str = Field(default="assigned", max_length=20)
    notes: Optional[str] = None


class LocationEquipmentResponse(BaseModel):
    id: int
    location_id: int
    vehicle_id: int
    assigned_at: datetime
    assigned_by_id: Optional[int]
    is_active: bool
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Inter-Location Transfer Schemas

class InterLocationTransferCreate(BaseModel):
    from_location_id: int
    to_location_id: int
    vehicle_id: int
    transfer_date: datetime
    scheduled_date: Optional[datetime] = None
    driver_id: Optional[int] = None
    requested_by_id: int
    approved_by_id: Optional[int] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    estimated_cost: Optional[int] = Field(None, ge=0)  # Cost in cents


class InterLocationTransferResponse(BaseModel):
    id: int
    company_id: int
    from_location_id: int
    to_location_id: int
    vehicle_id: int
    transfer_date: datetime
    scheduled_date: Optional[datetime]
    completed_date: Optional[datetime]
    status: str
    driver_id: Optional[int]
    requested_by_id: int
    approved_by_id: Optional[int]
    reason: Optional[str]
    notes: Optional[str]
    estimated_cost: Optional[int]
    actual_cost: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Location Financials Schemas

class LocationFinancialsResponse(BaseModel):
    id: int
    location_id: int
    period_start: datetime
    period_end: datetime
    period_type: str
    total_revenue: int  # Revenue in cents
    load_count: int
    average_rate: int  # Average rate per load in cents
    fuel_cost: int
    maintenance_cost: int
    driver_pay: int
    overhead_cost: int
    total_expenses: int
    gross_profit: int
    net_profit: int
    profit_margin: int  # Percentage * 100 (e.g., 1500 = 15%)
    trucks_utilized: int
    trailers_utilized: int
    driver_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Analytics Schemas

class LocationAnalytics(BaseModel):
    total_locations: int
    equipment_by_location: List[Dict[str, Any]]
    recent_transfers: int
    period_days: int


class LocationSummary(BaseModel):
    id: int
    name: str
    location_type: str
    city: str
    state: str
    is_primary: bool
    equipment_count: int
    driver_count: int
    revenue: Optional[int]  # Revenue in cents
    profit_margin: Optional[int]  # Percentage * 100
    status: str  # active, maintenance, inactive

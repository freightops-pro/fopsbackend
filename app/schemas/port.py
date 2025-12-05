from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# Port Information Schemas
class PortInfo(BaseModel):
    id: str
    port_code: str
    port_name: str
    unlocode: Optional[str] = None
    region: Optional[str] = None
    state: Optional[str] = None
    country: str = "US"
    services_supported: Optional[List[str]] = None
    adapter_class: Optional[str] = None
    auth_type: Optional[str] = None
    rate_limits: Optional[dict] = None
    compliance_standards: Optional[List[str]] = None
    logo_url: Optional[str] = None
    is_active: str = "true"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PortListResponse(BaseModel):
    ports: List[PortInfo]


# Port Integration Schemas
class PortIntegrationCreate(BaseModel):
    port_id: str
    credentials: Optional[dict] = None
    config: Optional[dict] = None


class PortIntegrationUpdate(BaseModel):
    credentials: Optional[dict] = None
    config: Optional[dict] = None
    status: Optional[str] = None
    auto_sync: Optional[bool] = None
    sync_interval_minutes: Optional[int] = None


class PortIntegrationResponse(BaseModel):
    id: str
    company_id: str
    port_id: str
    status: str
    last_sync_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error_message: Optional[str] = None
    consecutive_failures: int
    auto_sync: str  # Stored as string "true"/"false" in database
    sync_interval_minutes: int
    activated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    port: Optional[PortInfo] = None

    model_config = {"from_attributes": True}


# Container Tracking Schemas
class VesselInfo(BaseModel):
    name: Optional[str] = None
    voyage: Optional[str] = None
    eta: Optional[datetime] = None
    imo: Optional[str] = None


class ContainerLocation(BaseModel):
    terminal: Optional[str] = None
    yard_location: Optional[str] = None
    gate_status: Optional[str] = None
    port: Optional[str] = None
    country: Optional[str] = None
    timestamp: Optional[datetime] = None


class ContainerDates(BaseModel):
    discharge_date: Optional[datetime] = None
    last_free_day: Optional[datetime] = None
    return_by_date: Optional[datetime] = None
    ingate_timestamp: Optional[datetime] = None
    outgate_timestamp: Optional[datetime] = None


class ContainerCharges(BaseModel):
    demurrage: Optional[float] = None
    per_diem: Optional[float] = None
    detention: Optional[float] = None
    total_charges: Optional[float] = None


class ContainerDetails(BaseModel):
    size: Optional[str] = None
    type: Optional[str] = None
    weight: Optional[float] = None
    seal_number: Optional[str] = None
    shipping_line: Optional[str] = None
    master_bill_of_lading: Optional[str] = None


class ContainerTrackingRequest(BaseModel):
    port_code: str = Field(..., description="Port code (UN/LOCODE format)")
    container_number: str = Field(..., description="Container number")
    load_id: Optional[str] = Field(None, description="Optional load ID to link tracking")


class ContainerTrackingEventSchema(BaseModel):
    id: str
    event_type: str
    event_timestamp: datetime
    location: Optional[str] = None
    description: Optional[str] = None
    event_metadata: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ContainerTrackingResponse(BaseModel):
    container_number: str
    port_code: str
    terminal: Optional[str] = None
    status: str
    location: Optional[ContainerLocation] = None
    vessel: Optional[VesselInfo] = None
    dates: Optional[ContainerDates] = None
    container_details: Optional[ContainerDetails] = None
    holds: Optional[List[str]] = None
    charges: Optional[ContainerCharges] = None
    last_updated_at: datetime
    tracking_id: Optional[str] = None
    load_id: Optional[str] = None


class ContainerEventHistory(BaseModel):
    container_number: str
    events: List[ContainerTrackingEventSchema]
    total_events: int


class ContainerTrackingHistoryResponse(BaseModel):
    container_number: str
    port_code: str
    current_status: str
    tracking_records: List[ContainerTrackingResponse]
    events: List[ContainerTrackingEventSchema]
    load_id: Optional[str] = None


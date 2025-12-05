from datetime import datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field


class DispatchCalendarEntry(BaseModel):
    load_id: str
    stop_id: str
    reference: str
    customer_name: str
    driver_id: Optional[str] = None
    truck_id: Optional[str] = None
    stop_sequence: int
    location_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    start_time: datetime
    end_time: datetime
    status: str
    is_pickup: bool = Field(default=False, description="True when the stop is a pickup")


class DriverAvailability(BaseModel):
    driver_id: str
    driver_name: Optional[str] = None
    available_from: datetime
    available_until: Optional[datetime] = None
    status: str = "AVAILABLE"


class DispatchCalendarResponse(BaseModel):
    entries: List[DispatchCalendarEntry]
    driver_availability: List[DriverAvailability]
    generated_at: datetime


class DispatchFilterOption(BaseModel):
    label: str
    value: str
    count: int


class DispatchFiltersResponse(BaseModel):
    statuses: List[DispatchFilterOption]
    customers: List[DispatchFilterOption]
    drivers: List[DispatchFilterOption]


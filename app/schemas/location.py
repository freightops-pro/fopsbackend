from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LocationBase(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=255)
    location_type: Optional[str] = Field(None, max_length=50)  # shipper, consignee, both, warehouse, terminal
    address: str = Field(..., min_length=1, max_length=500)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=50)
    postal_code: str = Field(..., min_length=1, max_length=20)
    country: str = Field(default="US", max_length=2)
    lat: Optional[float] = None
    lng: Optional[float] = None
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    contact_email: Optional[str] = Field(None, max_length=255)
    special_instructions: Optional[str] = None
    operating_hours: Optional[str] = Field(None, max_length=255)


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    business_name: Optional[str] = Field(None, min_length=1, max_length=255)
    location_type: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, min_length=1, max_length=50)
    postal_code: Optional[str] = Field(None, min_length=1, max_length=20)
    country: Optional[str] = Field(None, max_length=2)
    lat: Optional[float] = None
    lng: Optional[float] = None
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)
    contact_email: Optional[str] = Field(None, max_length=255)
    special_instructions: Optional[str] = None
    operating_hours: Optional[str] = Field(None, max_length=255)


class LocationResponse(LocationBase):
    id: str
    company_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

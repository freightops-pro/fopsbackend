from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CompanySummaryResponse(BaseModel):
    id: str
    name: str
    type: str = "unknown"
    dot_number: Optional[str] = None
    mc_number: Optional[str] = None
    contact_phone: Optional[str] = None
    primary_contact_name: Optional[str] = None
    is_active: bool
    user_role: Optional[str] = None

    model_config = {"from_attributes": True}


class CompanyUserResponse(BaseModel):
    id: str
    user_id: str
    company_id: str
    first_name: str
    last_name: str
    email: str
    role: str
    permissions: List[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyProfileResponse(BaseModel):
    """Full company profile for settings page."""

    id: str
    name: str
    legal_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    fax: Optional[str] = None
    business_type: Optional[str] = None
    dot_number: Optional[str] = None
    mc_number: Optional[str] = None
    tax_id: Optional[str] = None
    primary_contact_name: Optional[str] = None

    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None

    # Additional
    description: Optional[str] = None
    website: Optional[str] = None
    year_founded: Optional[str] = None
    logo_url: Optional[str] = None
    preferred_language: Optional[str] = None

    # Regional configuration
    operating_region: Optional[str] = None
    regional_data: Optional[Dict[str, Any]] = None

    # Numbering configuration
    invoice_number_format: Optional[str] = None
    invoice_start_number: Optional[int] = None
    load_number_format: Optional[str] = None
    load_start_number: Optional[int] = None

    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyProfileUpdate(BaseModel):
    """Update company profile."""

    name: Optional[str] = None
    legal_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    business_type: Optional[str] = None
    dot_number: Optional[str] = None
    mc_number: Optional[str] = None
    tax_id: Optional[str] = None
    primary_contact_name: Optional[str] = None

    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None

    # Additional
    description: Optional[str] = None
    website: Optional[str] = None
    year_founded: Optional[str] = None
    logo_url: Optional[str] = None
    preferred_language: Optional[str] = None

    # Regional configuration
    operating_region: Optional[str] = None
    regional_data: Optional[Dict[str, Any]] = None

    # Numbering configuration
    invoice_number_format: Optional[str] = None
    invoice_start_number: Optional[int] = None
    load_number_format: Optional[str] = None
    load_start_number: Optional[int] = None


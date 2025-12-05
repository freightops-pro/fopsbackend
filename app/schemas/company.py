from datetime import datetime
from typing import List, Optional

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


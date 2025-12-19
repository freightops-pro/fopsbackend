from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserProfileResponse(BaseModel):
    """User profile for current user."""

    id: str
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = "America/Chicago"
    job_title: Optional[str] = None
    role: Optional[str] = None
    company_id: str
    company_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    """Update user's own profile."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    job_title: Optional[str] = None

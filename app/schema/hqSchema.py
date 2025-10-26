"""
HQ Admin Schemas - Separate from tenant authentication
"""
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class HQAdminCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: str = "hq_admin"
    notes: Optional[str] = None


class HQAdminUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class HQAdminResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True


class HQLoginRequest(BaseModel):
    email: EmailStr
    password: str


class HQLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: HQAdminResponse

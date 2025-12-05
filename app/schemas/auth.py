from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str
    last_name: str
    company_name: str
    business_type: Literal["carrier", "broker", "dispatcher", "forwarder", "other"]
    contact_phone: str = Field(..., min_length=7, max_length=20)
    dot_number: Optional[str] = Field(default=None, max_length=20)
    mc_number: Optional[str] = Field(default=None, max_length=20)


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    verification_code: str = Field(..., min_length=3, max_length=40)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    first_name: str
    last_name: str
    role: str
    company_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SessionUser(BaseModel):
    id: str
    email: EmailStr
    first_name: str
    last_name: str
    roles: List[str]
    avatar_url: Optional[str] = None
    must_change_password: bool = False


class SessionCompany(BaseModel):
    id: str
    name: str
    subscription_plan: str
    subscription_status: Literal["ACTIVE", "TRIAL", "PAST_DUE", "SUSPENDED"]
    business_type: Optional[str] = None
    contact_phone: Optional[str] = None
    primary_contact_name: Optional[str] = None
    dot_number: Optional[str] = None
    mc_number: Optional[str] = None
    features: List[str] = Field(default_factory=list)
    synctera_enabled: bool = False
    gusto_enabled: bool = False


class AuthSessionResponse(BaseModel):
    user: SessionUser
    company: SessionCompany
    access_token: Optional[str] = None  # Optional for /session endpoint, required for /login
    
    model_config = {
        "from_attributes": True,
    }


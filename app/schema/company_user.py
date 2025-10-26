from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class CompanyUserBase(BaseModel):
    role: str
    permissions: Optional[List[str]] = None
    is_active: bool = True

class CompanyUserCreate(CompanyUserBase):
    user_id: str
    company_id: str

class CompanyUserUpdate(BaseModel):
    role: Optional[str] = None
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None

class CompanyUserResponse(CompanyUserBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    user_id: str
    company_id: str
    created_at: datetime
    updated_at: datetime

class CompanyUserWithDetails(CompanyUserResponse):
    user: Optional[dict] = None  # Will contain user details
    company: Optional[dict] = None  # Will contain company details

from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class TeamBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_private: bool = False


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_private: Optional[bool] = None
    is_active: Optional[bool] = None


class TeamResponse(TeamBase):
    id: str
    company_id: str
    is_active: bool
    member_count: int
    created_at: datetime
    updated_at: datetime
    created_by: str
    created_by_type: str
    
    model_config = ConfigDict(from_attributes=True)


class TeamMemberBase(BaseModel):
    member_id: str
    member_type: str
    role: str = "member"


class TeamMemberCreate(TeamMemberBase):
    pass


class TeamMemberUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class TeamMemberResponse(TeamMemberBase):
    id: str
    team_id: str
    is_active: bool
    joined_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class TeamWithMembers(TeamResponse):
    members: List[TeamMemberResponse] = []

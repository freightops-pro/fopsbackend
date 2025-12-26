"""
User Invitation Schemas for API requests/responses.
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, Field


class InvitationCreate(BaseModel):
    """Request schema for creating a new invitation."""
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role_id: Optional[str] = None  # If not provided, uses default role
    message: Optional[str] = Field(None, max_length=500)


class InvitationResponse(BaseModel):
    """Response schema for a single invitation."""
    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role_id: Optional[str] = None
    role_name: Optional[str] = None
    company_id: str
    company_name: Optional[str] = None
    invited_by: str
    inviter_email: Optional[str] = None
    inviter_name: Optional[str] = None
    invited_at: datetime
    expires_at: datetime
    status: str
    accepted_at: Optional[datetime] = None
    message: Optional[str] = None

    model_config = {"from_attributes": True}


class InvitationListResponse(BaseModel):
    """Paginated list of invitations."""
    items: List[InvitationResponse]
    total: int
    page: int
    page_size: int


class AcceptInvitationRequest(BaseModel):
    """Request schema for accepting an invitation."""
    token: str
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)


class AcceptInvitationResponse(BaseModel):
    """Response after successfully accepting an invitation."""
    success: bool
    message: str
    user_id: Optional[str] = None
    email: Optional[str] = None
    redirect_url: Optional[str] = None


class ResendInvitationResponse(BaseModel):
    """Response after resending an invitation."""
    success: bool
    message: str
    new_expires_at: datetime


class InvitationStats(BaseModel):
    """Statistics about invitations."""
    pending_count: int
    accepted_count: int
    expired_count: int
    cancelled_count: int

"""
Tenant Schemas for HQ admin API.
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel


class TenantResponse(BaseModel):
    """Response schema for a single tenant/company."""
    id: str
    name: str
    legal_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    subscription_plan: Optional[str] = None
    is_active: bool
    dot_number: Optional[str] = None
    mc_number: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    created_at: Optional[datetime] = None
    # Computed fields
    user_count: int = 0
    driver_count: int = 0
    active_loads: int = 0
    last_activity: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TenantDetailResponse(TenantResponse):
    """Detailed tenant information including stats."""
    # Additional detail fields
    business_type: Optional[str] = None
    tax_id: Optional[str] = None
    website: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    zip_code: Optional[str] = None
    primary_contact_name: Optional[str] = None
    # Banking/KYB status
    banking_enabled: bool = False
    kyb_status: Optional[str] = None
    # Subscription details
    subscription_status: Optional[str] = None
    # Integration status
    integrations_count: int = 0
    # Recent activity
    recent_logins: int = 0


class TenantListResponse(BaseModel):
    """Paginated list of tenants."""
    items: List[TenantResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TenantFilter(BaseModel):
    """Filter parameters for tenant queries."""
    search: Optional[str] = None  # Name, email, DOT, MC
    is_active: Optional[bool] = None
    subscription_plan: Optional[str] = None
    state: Optional[str] = None
    has_banking: Optional[bool] = None


class TenantStatusUpdate(BaseModel):
    """Request to update tenant status."""
    is_active: bool
    reason: Optional[str] = None


class TenantUserResponse(BaseModel):
    """User info for tenant user list."""
    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    roles: List[str] = []
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TenantUsersListResponse(BaseModel):
    """List of users in a tenant."""
    items: List[TenantUserResponse]
    total: int


class PlatformStats(BaseModel):
    """Platform-wide statistics for HQ dashboard."""
    total_tenants: int
    active_tenants: int
    inactive_tenants: int
    total_users: int
    total_drivers: int
    total_loads_this_month: int
    revenue_this_month: float = 0.0
    new_tenants_this_month: int
    # By subscription
    tenants_by_plan: dict = {}
    # By state
    tenants_by_state: dict = {}

"""
RBAC (Role-Based Access Control) Schemas

Pydantic models for role and permission management API endpoints.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RoleResponse(BaseModel):
    """Response model for a role."""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    is_system_role: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PermissionResponse(BaseModel):
    """Response model for a permission."""
    id: str
    resource: str
    action: str
    description: Optional[str] = None
    category: Optional[str] = None

    model_config = {"from_attributes": True}

    @property
    def key(self) -> str:
        return f"{self.resource}:{self.action}"


class RoleWithPermissionsResponse(BaseModel):
    """Response model for a role with its permissions."""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    is_system_role: bool
    is_active: bool
    permissions: List[str] = Field(default_factory=list)  # List of permission keys like "banking:view"
    created_at: datetime

    model_config = {"from_attributes": True}


class UserRoleResponse(BaseModel):
    """Response model for a user's role assignment."""
    user_id: str
    role_id: str
    role_name: str
    role_display_name: str
    assigned_at: datetime
    assigned_by: Optional[str] = None

    model_config = {"from_attributes": True}


class UserWithRolesResponse(BaseModel):
    """Response model for a user with their roles."""
    id: str
    email: str
    first_name: str
    last_name: str
    is_active: bool
    roles: List[RoleResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AssignRoleRequest(BaseModel):
    """Request model to assign a role to a user."""
    user_id: str
    role_id: str


class RemoveRoleRequest(BaseModel):
    """Request model to remove a role from a user."""
    user_id: str
    role_id: str


class CreateCustomRoleRequest(BaseModel):
    """Request model to create a custom tenant role."""
    name: str = Field(..., min_length=2, max_length=50)
    display_name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    permission_ids: List[str] = Field(default_factory=list)


class UpdateRoleRequest(BaseModel):
    """Request model to update a role."""
    display_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    permission_ids: Optional[List[str]] = None

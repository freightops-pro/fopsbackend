"""
Role Management API Router

Endpoints for managing roles and user-role assignments.
Requires TENANT_ADMIN role or roles:manage permission.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.core.db import get_db
from app.core.rbac import Resource, Action
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User
from app.schemas.rbac import (
    AssignRoleRequest,
    CreateCustomRoleRequest,
    PermissionResponse,
    RemoveRoleRequest,
    RoleResponse,
    RoleWithPermissionsResponse,
    UpdateRoleRequest,
    UserWithRolesResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Role Listing
# =============================================================================


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RoleResponse]:
    """
    List all available roles for the current tenant.
    Includes system roles and any custom roles created by the tenant.
    """
    # Get system roles (company_id is NULL) and tenant-specific roles
    result = await db.execute(
        select(Role)
        .where(
            (Role.company_id == None) | (Role.company_id == current_user.company_id)
        )
        .where(Role.is_active == True)
        .order_by(Role.is_system_role.desc(), Role.name)
    )
    roles = result.scalars().all()

    return [
        RoleResponse(
            id=role.id,
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            is_system_role=role.is_system_role,
            is_active=role.is_active,
            created_at=role.created_at,
        )
        for role in roles
    ]


@router.get("/roles/{role_id}", response_model=RoleWithPermissionsResponse)
async def get_role(
    role_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RoleWithPermissionsResponse:
    """Get a role with its permissions."""
    # Filter by company_id in the query to prevent data leakage
    result = await db.execute(
        select(Role).where(
            Role.id == role_id,
            (
                (Role.company_id == None) |  # System roles
                (Role.company_id == current_user.company_id)  # Tenant's custom roles
            )
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    # Get permissions for this role
    result = await db.execute(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    permissions = result.scalars().all()

    return RoleWithPermissionsResponse(
        id=role.id,
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        is_system_role=role.is_system_role,
        is_active=role.is_active,
        permissions=[f"{p.resource}:{p.action}" for p in permissions],
        created_at=role.created_at,
    )


# =============================================================================
# Permission Listing
# =============================================================================


@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[PermissionResponse]:
    """List all available permissions."""
    result = await db.execute(
        select(Permission).order_by(Permission.category, Permission.resource, Permission.action)
    )
    permissions = result.scalars().all()

    return [
        PermissionResponse(
            id=perm.id,
            resource=perm.resource,
            action=perm.action,
            description=perm.description,
            category=perm.category,
        )
        for perm in permissions
    ]


# =============================================================================
# User Role Management
# =============================================================================


@router.get("/users/{user_id}/roles", response_model=List[RoleResponse])
async def get_user_roles(
    user_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RoleResponse]:
    """Get all roles assigned to a user."""
    # Filter by company_id in the query to prevent data leakage
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.company_id == current_user.company_id
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await db.execute(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
        .where(Role.is_active == True)
    )
    roles = result.scalars().all()

    return [
        RoleResponse(
            id=role.id,
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            is_system_role=role.is_system_role,
            is_active=role.is_active,
            created_at=role.created_at,
        )
        for role in roles
    ]


@router.get("/users-with-roles", response_model=List[UserWithRolesResponse])
async def list_users_with_roles(
    current_user: User = Depends(deps.require_permission(Resource.USERS, Action.VIEW)),
    db: AsyncSession = Depends(get_db),
) -> List[UserWithRolesResponse]:
    """List all users in the company with their roles."""
    result = await db.execute(
        select(User)
        .where(User.company_id == current_user.company_id)
        .order_by(User.email)
    )
    users = result.scalars().all()

    response = []
    for user in users:
        # Get roles for each user
        roles_result = await db.execute(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
            .where(Role.is_active == True)
        )
        roles = roles_result.scalars().all()

        response.append(
            UserWithRolesResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                is_active=user.is_active,
                roles=[
                    RoleResponse(
                        id=role.id,
                        name=role.name,
                        display_name=role.display_name,
                        description=role.description,
                        is_system_role=role.is_system_role,
                        is_active=role.is_active,
                        created_at=role.created_at,
                    )
                    for role in roles
                ],
            )
        )

    return response


@router.post("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_201_CREATED)
async def assign_role_to_user(
    user_id: str,
    role_id: str,
    current_user: User = Depends(deps.require_permission(Resource.ROLES, Action.MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Assign a role to a user."""
    # Filter by company_id in the query to prevent data leakage
    user_result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.company_id == current_user.company_id
        )
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check role exists and is accessible (system roles or tenant's custom roles)
    role_result = await db.execute(
        select(Role).where(
            Role.id == role_id,
            (
                (Role.company_id == None) |  # System roles
                (Role.company_id == current_user.company_id)  # Tenant's custom roles
            )
        )
    )
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    if not role.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role is inactive")

    # Prevent assigning HQ_ADMIN to regular users
    if role.name == "HQ_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot assign platform administrator role"
        )

    # Check if already assigned
    existing = await db.execute(
        select(UserRole)
        .where(UserRole.user_id == user_id)
        .where(UserRole.role_id == role_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role already assigned")

    # Assign role
    user_role = UserRole(
        user_id=user_id,
        role_id=role_id,
        assigned_by=current_user.id,
    )
    db.add(user_role)
    await db.commit()

    logger.info(f"Role {role.name} assigned to user {user.email} by {current_user.email}")

    return {"message": f"Role '{role.display_name}' assigned to user"}


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_200_OK)
async def remove_role_from_user(
    user_id: str,
    role_id: str,
    current_user: User = Depends(deps.require_permission(Resource.ROLES, Action.MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Remove a role from a user."""
    # Filter by company_id in the query to prevent data leakage
    user_result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.company_id == current_user.company_id
        )
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent removing own TENANT_ADMIN role
    role_result = await db.execute(
        select(Role).where(
            Role.id == role_id,
            (
                (Role.company_id == None) |  # System roles
                (Role.company_id == current_user.company_id)  # Tenant's custom roles
            )
        )
    )
    role = role_result.scalar_one_or_none()
    if role and role.name == "TENANT_ADMIN" and user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own administrator role"
        )

    # Find and remove the assignment
    result = await db.execute(
        select(UserRole)
        .where(UserRole.user_id == user_id)
        .where(UserRole.role_id == role_id)
    )
    user_role = result.scalar_one_or_none()

    if not user_role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role assignment not found")

    await db.delete(user_role)
    await db.commit()

    logger.info(f"Role {role.name if role else role_id} removed from user {user.email} by {current_user.email}")

    return {"message": "Role removed from user"}


# =============================================================================
# Custom Role Management (for tenants)
# =============================================================================


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_role(
    payload: CreateCustomRoleRequest,
    current_user: User = Depends(deps.require_permission(Resource.ROLES, Action.MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    """Create a custom role for the tenant."""
    # Check if role name already exists for this tenant
    existing = await db.execute(
        select(Role)
        .where(Role.name == payload.name.upper())
        .where(
            (Role.company_id == None) | (Role.company_id == current_user.company_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role with name '{payload.name}' already exists"
        )

    # Create the role
    role = Role(
        id=str(uuid.uuid4()),
        name=payload.name.upper(),
        display_name=payload.display_name,
        description=payload.description,
        company_id=current_user.company_id,
        is_system_role=False,
        is_active=True,
    )
    db.add(role)

    # Assign permissions if provided
    if payload.permission_ids:
        for perm_id in payload.permission_ids:
            perm = await db.get(Permission, perm_id)
            if perm:
                role_perm = RolePermission(role_id=role.id, permission_id=perm_id)
                db.add(role_perm)

    await db.commit()
    await db.refresh(role)

    logger.info(f"Custom role {role.name} created by {current_user.email}")

    return RoleResponse(
        id=role.id,
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        is_system_role=role.is_system_role,
        is_active=role.is_active,
        created_at=role.created_at,
    )


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    payload: UpdateRoleRequest,
    current_user: User = Depends(deps.require_permission(Resource.ROLES, Action.MANAGE)),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    """Update a custom role. System roles cannot be modified."""
    # Filter by company_id in the query to prevent data leakage
    result = await db.execute(
        select(Role).where(
            Role.id == role_id,
            Role.company_id == current_user.company_id  # Only tenant's custom roles
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    # Can only modify tenant's own custom roles (system roles have company_id=None)
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System roles cannot be modified"
        )

    # Update fields
    if payload.display_name is not None:
        role.display_name = payload.display_name
    if payload.description is not None:
        role.description = payload.description
    if payload.is_active is not None:
        role.is_active = payload.is_active

    # Update permissions if provided
    if payload.permission_ids is not None:
        # Remove existing permissions
        await db.execute(
            select(RolePermission).where(RolePermission.role_id == role_id)
        )
        existing_perms = (await db.execute(
            select(RolePermission).where(RolePermission.role_id == role_id)
        )).scalars().all()
        for rp in existing_perms:
            await db.delete(rp)

        # Add new permissions
        for perm_id in payload.permission_ids:
            perm = await db.get(Permission, perm_id)
            if perm:
                role_perm = RolePermission(role_id=role.id, permission_id=perm_id)
                db.add(role_perm)

    await db.commit()
    await db.refresh(role)

    logger.info(f"Role {role.name} updated by {current_user.email}")

    return RoleResponse(
        id=role.id,
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        is_system_role=role.is_system_role,
        is_active=role.is_active,
        created_at=role.created_at,
    )


@router.delete("/roles/{role_id}", status_code=status.HTTP_200_OK)
async def delete_role(
    role_id: str,
    current_user: User = Depends(deps.require_permission(Resource.ROLES, Action.MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom role. System roles cannot be deleted."""
    # Filter by company_id in the query to prevent data leakage
    result = await db.execute(
        select(Role).where(
            Role.id == role_id,
            Role.company_id == current_user.company_id  # Only tenant's custom roles
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System roles cannot be deleted"
        )

    # Check if role is assigned to any users
    result = await db.execute(
        select(UserRole).where(UserRole.role_id == role_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete role that is assigned to users"
        )

    await db.delete(role)
    await db.commit()

    logger.info(f"Role {role.name} deleted by {current_user.email}")

    return {"message": f"Role '{role.display_name}' deleted"}

"""
Permission Service

Provides methods for checking user permissions based on their roles.
Supports both database-driven permissions and fallback to RBAC definitions.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import List, Optional, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.rbac import Action, Resource, SystemRole, get_role_permissions
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User

logger = logging.getLogger(__name__)


class PermissionService:
    """
    Service for checking and managing user permissions.

    Supports:
    - Permission checking via database queries
    - Fallback to static RBAC definitions
    - Permission caching for performance
    - Wildcard permissions (e.g., resource:* or admin:*)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_user_roles(self, user_id: str) -> List[str]:
        """
        Get all role names for a user.

        Returns a list of role names (e.g., ["TENANT_ADMIN", "DISPATCHER"]).
        Falls back to legacy role column if no user_roles exist.
        """
        # Try new user_role table first
        result = await self.db.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .where(Role.is_active == True)
        )
        roles = [row[0] for row in result.fetchall()]

        if roles:
            return roles

        # Fallback to legacy role column
        user = await self.db.get(User, user_id)
        if user and user.role:
            # Normalize to uppercase
            legacy_role = user.role.upper()
            # Map legacy roles to system roles
            role_mapping = {
                "ADMIN": "TENANT_ADMIN",
                "OWNER": "TENANT_ADMIN",
                "PAYROLL": "ACCOUNTANT",
                "HR": "HR_SPECIALIST",
                "SAFETY": "OPERATIONS_MANAGER",
                "FLEET_MANAGER": "OPERATIONS_MANAGER",
            }
            return [role_mapping.get(legacy_role, legacy_role)]

        return []

    async def get_user_permissions(self, user_id: str) -> Set[str]:
        """
        Get all permission keys for a user based on their roles.

        Returns a set of permission keys (e.g., {"banking:view", "loads:manage"}).
        """
        roles = await self.get_user_roles(user_id)
        permissions: Set[str] = set()

        for role_name in roles:
            # Get permissions from database
            db_permissions = await self._get_role_permissions_from_db(role_name)
            if db_permissions:
                permissions.update(db_permissions)
            else:
                # Fallback to static definitions
                static_permissions = get_role_permissions(role_name)
                permissions.update(static_permissions)

        return permissions

    async def _get_role_permissions_from_db(self, role_name: str) -> Set[str]:
        """Get permissions for a role from the database."""
        result = await self.db.execute(
            select(Permission.resource, Permission.action)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .where(Role.name == role_name)
            .where(Role.is_active == True)
        )
        return {f"{row[0]}:{row[1]}" for row in result.fetchall()}

    async def has_permission(
        self,
        user_id: str,
        resource: Resource | str,
        action: Action | str,
    ) -> bool:
        """
        Check if a user has a specific permission.

        Supports wildcard matching:
        - If user has "resource:*", they have all actions on that resource
        - If user has "admin:*", they have access to everything
        - If user has "resource:manage", they have all CRUD on that resource

        Args:
            user_id: The user's ID
            resource: The resource to check (e.g., Resource.BANKING or "banking")
            action: The action to check (e.g., Action.VIEW or "view")

        Returns:
            True if user has permission, False otherwise
        """
        resource_str = resource.value if isinstance(resource, Resource) else resource
        action_str = action.value if isinstance(action, Action) else action
        permission_key = f"{resource_str}:{action_str}"

        permissions = await self.get_user_permissions(user_id)

        # Direct match
        if permission_key in permissions:
            return True

        # Admin wildcard (full access)
        if f"{Resource.ADMIN.value}:{Action.ALL.value}" in permissions:
            return True

        # Resource wildcard (e.g., banking:*)
        if f"{resource_str}:{Action.ALL.value}" in permissions:
            return True

        # Manage permission includes all CRUD actions
        if f"{resource_str}:{Action.MANAGE.value}" in permissions:
            if action_str in [Action.VIEW.value, Action.CREATE.value, Action.UPDATE.value, Action.DELETE.value]:
                return True

        return False

    async def has_any_permission(
        self,
        user_id: str,
        permissions: List[tuple],
    ) -> bool:
        """
        Check if user has any of the specified permissions.

        Args:
            user_id: The user's ID
            permissions: List of (resource, action) tuples

        Returns:
            True if user has at least one of the permissions
        """
        for resource, action in permissions:
            if await self.has_permission(user_id, resource, action):
                return True
        return False

    async def has_all_permissions(
        self,
        user_id: str,
        permissions: List[tuple],
    ) -> bool:
        """
        Check if user has all of the specified permissions.

        Args:
            user_id: The user's ID
            permissions: List of (resource, action) tuples

        Returns:
            True if user has all of the permissions
        """
        for resource, action in permissions:
            if not await self.has_permission(user_id, resource, action):
                return False
        return True

    async def has_role(self, user_id: str, role: SystemRole | str) -> bool:
        """Check if user has a specific role."""
        role_name = role.value if isinstance(role, SystemRole) else role
        roles = await self.get_user_roles(user_id)
        return role_name in roles

    async def has_any_role(self, user_id: str, roles: List[str]) -> bool:
        """Check if user has any of the specified roles."""
        user_roles = await self.get_user_roles(user_id)
        return any(role in user_roles for role in roles)

    async def assign_role(
        self,
        user_id: str,
        role_name: str,
        assigned_by: Optional[str] = None,
    ) -> bool:
        """
        Assign a role to a user.

        Args:
            user_id: The user to assign the role to
            role_name: The name of the role to assign
            assigned_by: The user who is assigning the role (for audit)

        Returns:
            True if role was assigned, False if already had the role
        """
        # Find the role
        result = await self.db.execute(
            select(Role).where(Role.name == role_name).where(Role.is_active == True)
        )
        role = result.scalar_one_or_none()
        if not role:
            raise ValueError(f"Role not found: {role_name}")

        # Check if user already has this role
        existing = await self.db.execute(
            select(UserRole)
            .where(UserRole.user_id == user_id)
            .where(UserRole.role_id == role.id)
        )
        if existing.scalar_one_or_none():
            return False  # Already has role

        # Assign role
        user_role = UserRole(
            user_id=user_id,
            role_id=role.id,
            assigned_by=assigned_by,
        )
        self.db.add(user_role)
        await self.db.commit()

        logger.info(f"Assigned role {role_name} to user {user_id} by {assigned_by}")
        return True

    async def remove_role(self, user_id: str, role_name: str) -> bool:
        """
        Remove a role from a user.

        Returns:
            True if role was removed, False if user didn't have the role
        """
        result = await self.db.execute(
            select(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user_id)
            .where(Role.name == role_name)
        )
        user_role = result.scalar_one_or_none()

        if not user_role:
            return False

        await self.db.delete(user_role)
        await self.db.commit()

        logger.info(f"Removed role {role_name} from user {user_id}")
        return True

    async def get_available_roles(self, company_id: Optional[str] = None) -> List[Role]:
        """
        Get all available roles for a company.

        Includes system roles and any custom roles for the company.
        """
        query = select(Role).where(Role.is_active == True)

        if company_id:
            # System roles (company_id is NULL) + company-specific roles
            query = query.where(
                (Role.company_id == None) | (Role.company_id == company_id)
            )
        else:
            # Only system roles
            query = query.where(Role.company_id == None)

        result = await self.db.execute(query.order_by(Role.name))
        return list(result.scalars().all())

"""
Role-Based Access Control (RBAC) Models

This module implements a flexible RBAC system with:
- System roles (predefined, immutable)
- Custom tenant roles (company-specific)
- Granular permissions (resource:action pattern)
- Multi-role support per user
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class Role(Base):
    """
    Represents a role that can be assigned to users.

    System roles (is_system_role=True) are predefined and available to all tenants.
    Custom roles (company_id set) are specific to a tenant.
    """
    __tablename__ = "role"

    id = Column(String, primary_key=True)
    name = Column(String(50), nullable=False)  # e.g., "TENANT_ADMIN"
    display_name = Column(String(100), nullable=False)  # e.g., "Administrator"
    description = Column(Text, nullable=True)

    # NULL = system role available to all tenants
    # Set = custom role for specific tenant
    company_id = Column(String, ForeignKey("company.id", ondelete="CASCADE"), nullable=True, index=True)

    is_system_role = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company", back_populates="custom_roles")
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")

    __table_args__ = (
        # Ensure unique role names within a company (or globally for system roles)
        UniqueConstraint("name", "company_id", name="uq_role_name_company"),
    )


class Permission(Base):
    """
    Represents a granular permission using resource:action pattern.

    Examples:
    - resource="banking", action="view" -> Can view banking dashboard
    - resource="banking", action="transfer" -> Can make transfers
    - resource="loads", action="create" -> Can create new loads
    - resource="*", action="*" -> Full access (admin)
    """
    __tablename__ = "permission"

    id = Column(String, primary_key=True)
    resource = Column(String(50), nullable=False, index=True)  # e.g., "banking", "loads", "settings"
    action = Column(String(50), nullable=False)  # e.g., "view", "create", "update", "delete", "*"
    description = Column(Text, nullable=True)

    # Group permissions for UI display
    category = Column(String(50), nullable=True)  # e.g., "Finance", "Operations", "Administration"

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    role_permissions = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
    )

    @property
    def key(self) -> str:
        """Returns permission key in resource:action format."""
        return f"{self.resource}:{self.action}"


class RolePermission(Base):
    """
    Many-to-many relationship between roles and permissions.
    """
    __tablename__ = "role_permission"

    role_id = Column(String, ForeignKey("role.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(String, ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="role_permissions")


class UserRole(Base):
    """
    Many-to-many relationship between users and roles.
    Supports audit trail with assigned_at and assigned_by.
    """
    __tablename__ = "user_role"

    user_id = Column(String, ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(String, ForeignKey("role.id", ondelete="CASCADE"), primary_key=True)

    assigned_at = Column(DateTime, nullable=False, server_default=func.now())
    assigned_by = Column(String, ForeignKey("user.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    user = relationship("User", back_populates="user_roles", foreign_keys=[user_id])
    role = relationship("Role", back_populates="user_roles")
    assigner = relationship("User", foreign_keys=[assigned_by])

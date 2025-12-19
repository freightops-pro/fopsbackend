"""Add RBAC tables for role-based access control

Revision ID: 20251218_rbac
Revises: 20251216_add_banking_transfers
Create Date: 2025-12-18

This migration creates the RBAC (Role-Based Access Control) system:
- role: Defines roles (system-wide and tenant-specific)
- permission: Granular permissions using resource:action pattern
- role_permission: Many-to-many between roles and permissions
- user_role: Many-to-many between users and roles
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251218_rbac"
down_revision = "20251216_add_banking_transfers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create role table
    op.create_table(
        "role",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("company_id", sa.String(), nullable=True),
        sa.Column("is_system_role", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_role_company_id", "role", ["company_id"])
    op.create_unique_constraint("uq_role_name_company", "role", ["name", "company_id"])

    # Create permission table
    op.create_table(
        "permission",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("resource", sa.String(50), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_permission_resource", "permission", ["resource"])
    op.create_unique_constraint("uq_permission_resource_action", "permission", ["resource", "action"])

    # Create role_permission junction table
    op.create_table(
        "role_permission",
        sa.Column("role_id", sa.String(), nullable=False),
        sa.Column("permission_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permission.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    # Create user_role junction table
    op.create_table(
        "user_role",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("role_id", sa.String(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("assigned_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    # Make the legacy role column nullable for transition
    op.alter_column("user", "role", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Restore role column to not nullable with default
    op.alter_column("user", "role", existing_type=sa.String(), nullable=False, server_default="dispatcher")

    # Drop tables in reverse order
    op.drop_table("user_role")
    op.drop_table("role_permission")
    op.drop_constraint("uq_permission_resource_action", "permission", type_="unique")
    op.drop_index("ix_permission_resource", "permission")
    op.drop_table("permission")
    op.drop_constraint("uq_role_name_company", "role", type_="unique")
    op.drop_index("ix_role_company_id", "role")
    op.drop_table("role")

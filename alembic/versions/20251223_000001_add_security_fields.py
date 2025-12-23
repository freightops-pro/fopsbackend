"""Add security fields for banking-grade security

Revision ID: 20251223_000001
Revises: c163090b4da8
Create Date: 2025-12-23

Adds:
- Email verification fields to user
- Account lockout fields to user
- Login tracking fields to user
- Audit log table
- Login attempts table
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251223_000001"
down_revision: Union[str, None] = "c163090b4da8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add email verification fields to user
    op.add_column("user", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("user", sa.Column("email_verification_token", sa.String(), nullable=True))
    op.add_column("user", sa.Column("email_verification_sent_at", sa.DateTime(), nullable=True))

    # Add account security fields to user
    op.add_column("user", sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user", sa.Column("locked_until", sa.DateTime(), nullable=True))
    op.add_column("user", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    op.add_column("user", sa.Column("last_login_ip", sa.String(), nullable=True))
    op.add_column("user", sa.Column("password_changed_at", sa.DateTime(), nullable=True))

    # Create audit_log table
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("company_id", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="success"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_company_id", "audit_log", ["company_id"])
    op.create_index("ix_audit_log_event_type", "audit_log", ["event_type"])
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])

    # Create login_attempts table for detailed tracking
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_login_attempts_email", "login_attempts", ["email"])
    op.create_index("ix_login_attempts_ip_address", "login_attempts", ["ip_address"])
    op.create_index("ix_login_attempts_attempted_at", "login_attempts", ["attempted_at"])


def downgrade() -> None:
    # Drop login_attempts table
    op.drop_index("ix_login_attempts_attempted_at", table_name="login_attempts")
    op.drop_index("ix_login_attempts_ip_address", table_name="login_attempts")
    op.drop_index("ix_login_attempts_email", table_name="login_attempts")
    op.drop_table("login_attempts")

    # Drop audit_log table
    op.drop_index("ix_audit_log_timestamp", table_name="audit_log")
    op.drop_index("ix_audit_log_event_type", table_name="audit_log")
    op.drop_index("ix_audit_log_company_id", table_name="audit_log")
    op.drop_index("ix_audit_log_user_id", table_name="audit_log")
    op.drop_table("audit_log")

    # Remove account security fields from user
    op.drop_column("user", "password_changed_at")
    op.drop_column("user", "last_login_ip")
    op.drop_column("user", "last_login_at")
    op.drop_column("user", "locked_until")
    op.drop_column("user", "failed_login_attempts")

    # Remove email verification fields from user
    op.drop_column("user", "email_verification_sent_at")
    op.drop_column("user", "email_verification_token")
    op.drop_column("user", "email_verified")

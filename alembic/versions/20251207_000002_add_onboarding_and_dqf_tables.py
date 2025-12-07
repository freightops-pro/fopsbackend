"""Add onboarding and DQF tables for comprehensive worker onboarding

Revision ID: 20251207_000002
Revises: 20251207_000001
Create Date: 2025-12-07 01:00:00

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20251207_000002"
down_revision = "20251207_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add onboarding and DQF tracking tables"""

    # Onboarding workflow table
    op.create_table(
        "onboarding_workflow",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("worker_id", sa.String(), sa.ForeignKey("worker.id"), nullable=True, index=True),
        sa.Column("driver_id", sa.String(), sa.ForeignKey("driver.id"), nullable=True, index=True),

        # Onboarding details
        sa.Column("worker_type", sa.String(20), nullable=False),  # employee, contractor, driver
        sa.Column("role_type", sa.String(20), nullable=False),  # driver, office, mechanic, etc.
        sa.Column("is_dot_driver", sa.Boolean(), nullable=False, default=False),

        # Contact info (before worker/driver created)
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),

        # Onboarding link
        sa.Column("onboarding_token", sa.String(), nullable=True, unique=True, index=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("onboarding_url", sa.String(), nullable=True),

        # Status tracking
        sa.Column("status", sa.String(20), nullable=False, default="pending"),  # pending, in_progress, completed, cancelled
        sa.Column("current_step", sa.String(50), nullable=True),
        sa.Column("completed_steps", sa.JSON(), nullable=True),  # List of completed step names

        # Background checks (for DOT drivers)
        sa.Column("background_checks_status", sa.JSON(), nullable=True),  # Status of MVR, PSP, CDL, Clearinghouse
        sa.Column("background_checks_cost", sa.Numeric(10, 2), nullable=True, default=0),

        # Metadata
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # DQF (Driver Qualification File) documents table
    op.create_table(
        "dqf_document",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("driver_id", sa.String(), sa.ForeignKey("driver.id"), nullable=False, index=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),

        # Document classification
        sa.Column("document_category", sa.String(50), nullable=False),  # application, license, medical, background, training, etc.
        sa.Column("document_type", sa.String(100), nullable=False),  # cdl, medical_card, mvr, psp, clearinghouse, etc.
        sa.Column("document_name", sa.String(), nullable=False),

        # File storage
        sa.Column("file_url", sa.String(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_type", sa.String(50), nullable=True),

        # Expiration tracking
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("is_expired", sa.Boolean(), nullable=False, default=False),

        # Verification status
        sa.Column("verification_status", sa.String(20), nullable=False, default="pending"),  # pending, verified, rejected, expired
        sa.Column("verified_by", sa.String(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("verification_notes", sa.Text(), nullable=True),

        # Metadata
        sa.Column("uploaded_by", sa.String(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Background check results table (for audit trail and billing)
    op.create_table(
        "background_check",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("onboarding_id", sa.String(), sa.ForeignKey("onboarding_workflow.id"), nullable=True, index=True),
        sa.Column("driver_id", sa.String(), sa.ForeignKey("driver.id"), nullable=True, index=True),

        # Check details
        sa.Column("check_type", sa.String(50), nullable=False),  # mvr, psp, cdl_verification, clearinghouse
        sa.Column("provider", sa.String(100), nullable=True),  # e.g., "Foley Services", "HireRight", etc.
        sa.Column("provider_reference_id", sa.String(), nullable=True),

        # Subject information
        sa.Column("subject_name", sa.String(), nullable=False),
        sa.Column("subject_cdl_number", sa.String(), nullable=True),
        sa.Column("subject_cdl_state", sa.String(2), nullable=True),
        sa.Column("subject_dob", sa.Date(), nullable=True),

        # Status and results
        sa.Column("status", sa.String(20), nullable=False, default="pending"),  # pending, completed, failed, error
        sa.Column("result", sa.String(20), nullable=True),  # pass, fail, review_required
        sa.Column("result_data", sa.JSON(), nullable=True),  # Full result payload from provider
        sa.Column("result_summary", sa.Text(), nullable=True),

        # Flags and violations
        sa.Column("has_violations", sa.Boolean(), nullable=True),
        sa.Column("violation_count", sa.Integer(), nullable=True, default=0),
        sa.Column("violation_summary", sa.JSON(), nullable=True),

        # Billing
        sa.Column("cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("billed_to_company", sa.Boolean(), nullable=False, default=True),
        sa.Column("billing_status", sa.String(20), nullable=True, default="pending"),  # pending, invoiced, paid

        # Timestamps
        sa.Column("requested_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create indices for common queries
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.create_index("ix_onboarding_workflow_status", "onboarding_workflow", ["status"])
        op.create_index("ix_onboarding_workflow_token", "onboarding_workflow", ["onboarding_token"])
        op.create_index("ix_dqf_document_category", "dqf_document", ["document_category"])
        op.create_index("ix_dqf_document_expiration", "dqf_document", ["expiration_date"])
        op.create_index("ix_dqf_document_verification", "dqf_document", ["verification_status"])
        op.create_index("ix_background_check_type", "background_check", ["check_type"])
        op.create_index("ix_background_check_status", "background_check", ["status"])


def downgrade() -> None:
    """Remove onboarding and DQF tables"""

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_index("ix_background_check_status", "background_check")
        op.drop_index("ix_background_check_type", "background_check")
        op.drop_index("ix_dqf_document_verification", "dqf_document")
        op.drop_index("ix_dqf_document_expiration", "dqf_document")
        op.drop_index("ix_dqf_document_category", "dqf_document")
        op.drop_index("ix_onboarding_workflow_token", "onboarding_workflow")
        op.drop_index("ix_onboarding_workflow_status", "onboarding_workflow")

    op.drop_table("background_check")
    op.drop_table("dqf_document")
    op.drop_table("onboarding_workflow")

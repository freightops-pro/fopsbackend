"""Add CRM and Commission tables

Revision ID: 20251225_000004
Revises: 20251225_000003
Create Date: 2025-12-25 09:00:00.000000

Creates the CRM and commission tracking tables:
- hq_lead (sales leads)
- hq_opportunity (sales opportunities/pipeline)
- hq_sales_rep_commission (commission config per rep)
- hq_commission_record (commission per deal)
- hq_commission_payment (actual commission payments)

Also adds assigned_sales_rep_id to hq_quote and hq_contract.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251225_000004"
down_revision: Union[str, None] = "20251225_000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add assigned_sales_rep_id to hq_quote
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_quote' AND column_name = 'assigned_sales_rep_id'
            ) THEN
                ALTER TABLE hq_quote ADD COLUMN assigned_sales_rep_id VARCHAR(36);
                CREATE INDEX IF NOT EXISTS ix_hq_quote_assigned_sales_rep_id ON hq_quote(assigned_sales_rep_id);
            END IF;
        END $$;
    """)

    # Add assigned_sales_rep_id to hq_contract
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_contract' AND column_name = 'assigned_sales_rep_id'
            ) THEN
                ALTER TABLE hq_contract ADD COLUMN assigned_sales_rep_id VARCHAR(36);
                CREATE INDEX IF NOT EXISTS ix_hq_contract_assigned_sales_rep_id ON hq_contract(assigned_sales_rep_id);
            END IF;
        END $$;
    """)

    # Create hq_opportunity table first (referenced by hq_lead)
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_opportunity (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            opportunity_number VARCHAR(50) NOT NULL UNIQUE,
            lead_id VARCHAR(36),
            tenant_id VARCHAR(36),
            company_name VARCHAR(255) NOT NULL,
            contact_name VARCHAR(255),
            contact_email VARCHAR(255),
            contact_phone VARCHAR(50),
            title VARCHAR(255) NOT NULL,
            description TEXT,
            stage VARCHAR(20) NOT NULL DEFAULT 'discovery',
            probability DECIMAL(5,2) DEFAULT 20,
            estimated_mrr DECIMAL(10,2) NOT NULL,
            estimated_setup_fee DECIMAL(10,2) DEFAULT 0,
            estimated_trucks VARCHAR(50),
            estimated_close_date TIMESTAMP,
            actual_close_date TIMESTAMP,
            assigned_sales_rep_id VARCHAR(36),
            converted_to_quote_id VARCHAR(36),
            converted_at TIMESTAMP,
            lost_reason VARCHAR(500),
            competitor VARCHAR(255),
            notes TEXT,
            created_by_id VARCHAR(36),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS ix_hq_opportunity_opportunity_number ON hq_opportunity(opportunity_number);
        CREATE INDEX IF NOT EXISTS ix_hq_opportunity_lead_id ON hq_opportunity(lead_id);
        CREATE INDEX IF NOT EXISTS ix_hq_opportunity_tenant_id ON hq_opportunity(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_hq_opportunity_assigned_sales_rep_id ON hq_opportunity(assigned_sales_rep_id);
        CREATE INDEX IF NOT EXISTS ix_hq_opportunity_stage ON hq_opportunity(stage);
    """)

    # Create hq_lead table
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_lead (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            lead_number VARCHAR(50) NOT NULL UNIQUE,
            company_name VARCHAR(255) NOT NULL,
            contact_name VARCHAR(255),
            contact_email VARCHAR(255),
            contact_phone VARCHAR(50),
            contact_title VARCHAR(100),
            source VARCHAR(20) NOT NULL DEFAULT 'other',
            status VARCHAR(20) NOT NULL DEFAULT 'new',
            estimated_mrr DECIMAL(10,2),
            estimated_trucks VARCHAR(50),
            estimated_drivers VARCHAR(50),
            assigned_sales_rep_id VARCHAR(36),
            next_follow_up_date TIMESTAMP,
            last_contacted_at TIMESTAMP,
            notes TEXT,
            converted_to_opportunity_id VARCHAR(36),
            converted_at TIMESTAMP,
            created_by_id VARCHAR(36),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS ix_hq_lead_lead_number ON hq_lead(lead_number);
        CREATE INDEX IF NOT EXISTS ix_hq_lead_contact_email ON hq_lead(contact_email);
        CREATE INDEX IF NOT EXISTS ix_hq_lead_assigned_sales_rep_id ON hq_lead(assigned_sales_rep_id);
        CREATE INDEX IF NOT EXISTS ix_hq_lead_status ON hq_lead(status);
    """)

    # Create hq_sales_rep_commission table
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_sales_rep_commission (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            sales_rep_id VARCHAR(36) NOT NULL UNIQUE,
            commission_rate DECIMAL(5,2) NOT NULL DEFAULT 5.00,
            tier_level VARCHAR(20) NOT NULL DEFAULT 'junior',
            effective_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            effective_until TIMESTAMP,
            notes TEXT,
            created_by_id VARCHAR(36),
            updated_by_id VARCHAR(36),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS ix_hq_sales_rep_commission_sales_rep_id ON hq_sales_rep_commission(sales_rep_id);
    """)

    # Create hq_commission_record table
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_commission_record (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            sales_rep_id VARCHAR(36) NOT NULL,
            contract_id VARCHAR(36) NOT NULL,
            tenant_id VARCHAR(36) NOT NULL,
            commission_rate DECIMAL(5,2) NOT NULL,
            base_mrr DECIMAL(10,2) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            deal_closed_at TIMESTAMP NOT NULL,
            eligible_at TIMESTAMP NOT NULL,
            total_paid_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
            payment_count VARCHAR(10) NOT NULL DEFAULT '0',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            deactivated_at TIMESTAMP,
            deactivated_reason VARCHAR(500),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS ix_hq_commission_record_sales_rep_id ON hq_commission_record(sales_rep_id);
        CREATE INDEX IF NOT EXISTS ix_hq_commission_record_contract_id ON hq_commission_record(contract_id);
        CREATE INDEX IF NOT EXISTS ix_hq_commission_record_tenant_id ON hq_commission_record(tenant_id);
        CREATE INDEX IF NOT EXISTS ix_hq_commission_record_status ON hq_commission_record(status);
    """)

    # Create hq_commission_payment table
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_commission_payment (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            commission_record_id VARCHAR(36) NOT NULL,
            sales_rep_id VARCHAR(36) NOT NULL,
            period_start TIMESTAMP NOT NULL,
            period_end TIMESTAMP NOT NULL,
            mrr_amount DECIMAL(10,2) NOT NULL,
            commission_rate DECIMAL(5,2) NOT NULL,
            commission_amount DECIMAL(10,2) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            payment_date TIMESTAMP,
            payment_reference VARCHAR(100),
            payment_method VARCHAR(50),
            approved_by_id VARCHAR(36),
            approved_at TIMESTAMP,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS ix_hq_commission_payment_commission_record_id ON hq_commission_payment(commission_record_id);
        CREATE INDEX IF NOT EXISTS ix_hq_commission_payment_sales_rep_id ON hq_commission_payment(sales_rep_id);
        CREATE INDEX IF NOT EXISTS ix_hq_commission_payment_status ON hq_commission_payment(status);
        CREATE INDEX IF NOT EXISTS ix_hq_commission_payment_period ON hq_commission_payment(period_start, period_end);
    """)


def downgrade() -> None:
    # Drop tables in reverse order of dependencies
    op.execute("DROP TABLE IF EXISTS hq_commission_payment CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_commission_record CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_sales_rep_commission CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_lead CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_opportunity CASCADE;")

    # Remove added columns
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_quote' AND column_name = 'assigned_sales_rep_id'
            ) THEN
                ALTER TABLE hq_quote DROP COLUMN assigned_sales_rep_id;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_contract' AND column_name = 'assigned_sales_rep_id'
            ) THEN
                ALTER TABLE hq_contract DROP COLUMN assigned_sales_rep_id;
            END IF;
        END $$;
    """)

"""Add HQ Deal and Subscription tables

Revision ID: 20251225_hq_deal_sub
Revises: 20251225_fix_cols
Create Date: 2025-12-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251225_hq_deal_sub'
down_revision: Union[str, None] = '20251225_fix_cols'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing tables if they exist (from partial runs)
    op.execute("DROP TABLE IF EXISTS hq_subscription_rate_change CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_deal_activity CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_deal CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_subscription CASCADE;")

    # Drop and recreate enum types to ensure correct values
    op.execute("DROP TYPE IF EXISTS dealstage CASCADE;")
    op.execute("DROP TYPE IF EXISTS dealsource CASCADE;")
    op.execute("DROP TYPE IF EXISTS hqsubscriptionstatus CASCADE;")
    op.execute("DROP TYPE IF EXISTS hqbillinginterval CASCADE;")

    # Create enum types with correct values
    op.execute("CREATE TYPE dealstage AS ENUM ('lead', 'contacted', 'qualified', 'demo', 'closing', 'won', 'lost');")
    op.execute("CREATE TYPE dealsource AS ENUM ('inbound', 'outbound', 'referral', 'partner', 'fmcsa_import', 'other');")
    op.execute("CREATE TYPE hqsubscriptionstatus AS ENUM ('active', 'paused', 'cancelled', 'past_due', 'trialing');")
    op.execute("CREATE TYPE hqbillinginterval AS ENUM ('monthly', 'annual');")

    # Create hq_subscription table FIRST (because hq_deal references it)
    op.execute("""
        CREATE TABLE hq_subscription (
            id VARCHAR PRIMARY KEY,
            subscription_number VARCHAR UNIQUE NOT NULL,
            tenant_id VARCHAR NOT NULL REFERENCES hq_tenant(id),
            deal_id VARCHAR,
            status hqsubscriptionstatus NOT NULL DEFAULT 'active',
            billing_interval hqbillinginterval NOT NULL DEFAULT 'monthly',
            monthly_rate NUMERIC(10, 2) NOT NULL,
            annual_rate NUMERIC(10, 2),
            current_mrr NUMERIC(10, 2) NOT NULL,
            setup_fee NUMERIC(10, 2) DEFAULT 0,
            setup_fee_paid BOOLEAN NOT NULL DEFAULT FALSE,
            trial_ends_at TIMESTAMP,
            started_at TIMESTAMP NOT NULL,
            paused_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            cancellation_reason VARCHAR,
            next_billing_date TIMESTAMP,
            truck_limit VARCHAR,
            user_limit VARCHAR,
            notes TEXT,
            created_by_id VARCHAR REFERENCES hq_employee(id),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)

    op.execute("CREATE INDEX ix_hq_subscription_subscription_number ON hq_subscription(subscription_number);")
    op.execute("CREATE INDEX ix_hq_subscription_tenant_id ON hq_subscription(tenant_id);")
    op.execute("CREATE INDEX ix_hq_subscription_status ON hq_subscription(status);")

    # Create hq_deal table (references hq_subscription)
    op.execute("""
        CREATE TABLE hq_deal (
            id VARCHAR PRIMARY KEY,
            deal_number VARCHAR UNIQUE NOT NULL,
            stage dealstage NOT NULL DEFAULT 'lead',
            source dealsource NOT NULL DEFAULT 'inbound',
            company_name VARCHAR NOT NULL,
            dot_number VARCHAR,
            mc_number VARCHAR,
            phone VARCHAR,
            email VARCHAR,
            website VARCHAR,
            address VARCHAR,
            city VARCHAR,
            state VARCHAR,
            zip_code VARCHAR,
            contact_name VARCHAR,
            contact_title VARCHAR,
            contact_phone VARCHAR,
            contact_email VARCHAR,
            fleet_size VARCHAR,
            estimated_trucks INTEGER,
            estimated_mrr NUMERIC(10, 2),
            estimated_setup_fee NUMERIC(10, 2),
            assigned_rep_id VARCHAR REFERENCES hq_employee(id),
            expected_close_date DATE,
            probability INTEGER,
            last_contacted_at TIMESTAMP,
            next_followup_at TIMESTAMP,
            won_at TIMESTAMP,
            lost_at TIMESTAMP,
            lost_reason VARCHAR,
            tenant_id VARCHAR REFERENCES hq_tenant(id),
            customer_id VARCHAR REFERENCES hq_customer(id),
            subscription_id VARCHAR REFERENCES hq_subscription(id),
            notes TEXT,
            tags VARCHAR,
            fmcsa_data JSONB,
            created_by_id VARCHAR REFERENCES hq_employee(id),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)

    op.execute("CREATE INDEX ix_hq_deal_deal_number ON hq_deal(deal_number);")
    op.execute("CREATE INDEX ix_hq_deal_stage ON hq_deal(stage);")
    op.execute("CREATE INDEX ix_hq_deal_source ON hq_deal(source);")
    op.execute("CREATE INDEX ix_hq_deal_assigned_rep_id ON hq_deal(assigned_rep_id);")
    op.execute("CREATE INDEX ix_hq_deal_dot_number ON hq_deal(dot_number);")
    op.execute("CREATE INDEX ix_hq_deal_tenant_id ON hq_deal(tenant_id);")
    op.execute("CREATE INDEX ix_hq_deal_customer_id ON hq_deal(customer_id);")

    # Now add foreign key from hq_subscription.deal_id to hq_deal.id
    op.execute("ALTER TABLE hq_subscription ADD CONSTRAINT fk_subscription_deal FOREIGN KEY (deal_id) REFERENCES hq_deal(id);")

    # Create hq_deal_activity table
    op.execute("""
        CREATE TABLE hq_deal_activity (
            id VARCHAR PRIMARY KEY,
            deal_id VARCHAR NOT NULL REFERENCES hq_deal(id) ON DELETE CASCADE,
            activity_type VARCHAR NOT NULL,
            description TEXT,
            metadata JSONB,
            created_by_id VARCHAR REFERENCES hq_employee(id),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)

    op.execute("CREATE INDEX ix_hq_deal_activity_deal_id ON hq_deal_activity(deal_id);")
    op.execute("CREATE INDEX ix_hq_deal_activity_activity_type ON hq_deal_activity(activity_type);")

    # Create hq_subscription_rate_change table
    op.execute("""
        CREATE TABLE hq_subscription_rate_change (
            id VARCHAR PRIMARY KEY,
            subscription_id VARCHAR NOT NULL REFERENCES hq_subscription(id) ON DELETE CASCADE,
            previous_mrr NUMERIC(10, 2) NOT NULL,
            new_mrr NUMERIC(10, 2) NOT NULL,
            reason VARCHAR,
            effective_date TIMESTAMP NOT NULL,
            changed_by_id VARCHAR REFERENCES hq_employee(id),
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        );
    """)

    op.execute("CREATE INDEX ix_hq_subscription_rate_change_subscription_id ON hq_subscription_rate_change(subscription_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hq_subscription_rate_change CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_deal_activity CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_deal CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_subscription CASCADE;")
    op.execute("DROP TYPE IF EXISTS hqbillinginterval;")
    op.execute("DROP TYPE IF EXISTS hqsubscriptionstatus;")
    op.execute("DROP TYPE IF EXISTS dealsource;")
    op.execute("DROP TYPE IF EXISTS dealstage;")

"""Fix missing columns in hq_contract, hq_quote, and hq_ai_actions

Revision ID: 20251225_fix_cols
Revises: 20251225_ai_queue
Create Date: 2025-12-25

This migration ensures missing columns exist.
Uses IF NOT EXISTS to be safe for re-runs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251225_fix_cols'
down_revision: Union[str, None] = '20251225_ai_queue'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add assigned_sales_rep_id to hq_contract if missing
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

    # Add assigned_sales_rep_id to hq_quote if missing
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

    # Add entity_data to hq_ai_actions if missing
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_ai_actions' AND column_name = 'entity_data'
            ) THEN
                ALTER TABLE hq_ai_actions ADD COLUMN entity_data JSON;
            END IF;
        END $$;
    """)

    # Add risk_factors to hq_ai_actions if missing
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_ai_actions' AND column_name = 'risk_factors'
            ) THEN
                ALTER TABLE hq_ai_actions ADD COLUMN risk_factors JSON;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # We don't drop these columns on downgrade since they're needed by the model
    pass

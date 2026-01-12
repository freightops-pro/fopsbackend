"""Fix HQ Deal schema to match model

Revision ID: 20260112_fix_deal_schema
Revises: 20251225_hq_deal_sub
Create Date: 2026-01-12

Fixes mismatches between hq_deal table and Python model:
- Rename expected_close_date -> estimated_close_date
- Rename assigned_rep_id -> assigned_sales_rep_id
- Add missing columns: carrier_type, competitor, next_follow_up_date
- Fix column types and constraints
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260112_fix_deal_schema'
down_revision: Union[str, None] = '20251225_hq_deal_sub'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename expected_close_date to estimated_close_date
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'expected_close_date'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'estimated_close_date'
            ) THEN
                ALTER TABLE hq_deal RENAME COLUMN expected_close_date TO estimated_close_date;
            END IF;
        END $$;
    """)

    # Rename assigned_rep_id to assigned_sales_rep_id
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'assigned_rep_id'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'assigned_sales_rep_id'
            ) THEN
                ALTER TABLE hq_deal RENAME COLUMN assigned_rep_id TO assigned_sales_rep_id;
                -- Rename the index as well
                DROP INDEX IF EXISTS ix_hq_deal_assigned_rep_id;
                CREATE INDEX IF NOT EXISTS ix_hq_deal_assigned_sales_rep_id ON hq_deal(assigned_sales_rep_id);
            END IF;
        END $$;
    """)

    # Rename next_followup_at to next_follow_up_date
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'next_followup_at'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'next_follow_up_date'
            ) THEN
                ALTER TABLE hq_deal RENAME COLUMN next_followup_at TO next_follow_up_date;
            END IF;
        END $$;
    """)

    # Add carrier_type if missing
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'carrier_type'
            ) THEN
                ALTER TABLE hq_deal ADD COLUMN carrier_type VARCHAR;
            END IF;
        END $$;
    """)

    # Add competitor if missing
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'competitor'
            ) THEN
                ALTER TABLE hq_deal ADD COLUMN competitor VARCHAR;
            END IF;
        END $$;
    """)

    # Add state column with 2-char constraint if missing
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'state'
            ) THEN
                ALTER TABLE hq_deal ADD COLUMN state VARCHAR(2);
                CREATE INDEX IF NOT EXISTS ix_hq_deal_state ON hq_deal(state);
            END IF;
        END $$;
    """)

    # Add mc_number index if missing
    op.execute("CREATE INDEX IF NOT EXISTS ix_hq_deal_mc_number ON hq_deal(mc_number);")

    # Add company_name index if missing
    op.execute("CREATE INDEX IF NOT EXISTS ix_hq_deal_company_name ON hq_deal(company_name);")

    # Add contact_email index if missing
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'contact_email'
            ) THEN
                CREATE INDEX IF NOT EXISTS ix_hq_deal_contact_email ON hq_deal(contact_email);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Reverse the changes
    op.execute("DROP INDEX IF EXISTS ix_hq_deal_contact_email;")
    op.execute("DROP INDEX IF EXISTS ix_hq_deal_company_name;")
    op.execute("DROP INDEX IF EXISTS ix_hq_deal_mc_number;")

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'state'
            ) THEN
                DROP INDEX IF EXISTS ix_hq_deal_state;
                ALTER TABLE hq_deal DROP COLUMN state;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'competitor'
            ) THEN
                ALTER TABLE hq_deal DROP COLUMN competitor;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'carrier_type'
            ) THEN
                ALTER TABLE hq_deal DROP COLUMN carrier_type;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'next_follow_up_date'
            ) THEN
                ALTER TABLE hq_deal RENAME COLUMN next_follow_up_date TO next_followup_at;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'assigned_sales_rep_id'
            ) THEN
                DROP INDEX IF EXISTS ix_hq_deal_assigned_sales_rep_id;
                ALTER TABLE hq_deal RENAME COLUMN assigned_sales_rep_id TO assigned_rep_id;
                CREATE INDEX IF NOT EXISTS ix_hq_deal_assigned_rep_id ON hq_deal(assigned_rep_id);
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal' AND column_name = 'estimated_close_date'
            ) THEN
                ALTER TABLE hq_deal RENAME COLUMN estimated_close_date TO expected_close_date;
            END IF;
        END $$;
    """)

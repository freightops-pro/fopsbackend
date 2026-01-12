"""Fix DealSource enum to match model

Revision ID: 6a46bc2e4680
Revises: 19feb2d2f1bf
Create Date: 2026-01-11 22:19:26.871223

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6a46bc2e4680'
down_revision = '19feb2d2f1bf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Recreate DealSource enum to match the Python model
    # Old: ('inbound', 'outbound', 'referral', 'partner', 'fmcsa_import', 'other')
    # New: ('referral', 'website', 'cold_call', 'partner', 'trade_show', 'linkedin', 'fmcsa', 'other')

    op.execute("""
        DO $$
        BEGIN
            -- Drop default constraint first
            ALTER TABLE hq_deal ALTER COLUMN source DROP DEFAULT;

            -- Create new enum type with correct values
            CREATE TYPE dealsource_new AS ENUM (
                'referral', 'website', 'cold_call', 'partner',
                'trade_show', 'linkedin', 'fmcsa', 'other'
            );

            -- Alter the hq_deal.source column to use new type
            -- Map old values to new values where possible
            ALTER TABLE hq_deal ALTER COLUMN source TYPE dealsource_new
            USING (
                CASE source::text
                    WHEN 'inbound' THEN 'website'::dealsource_new
                    WHEN 'outbound' THEN 'cold_call'::dealsource_new
                    WHEN 'fmcsa_import' THEN 'fmcsa'::dealsource_new
                    WHEN 'referral' THEN 'referral'::dealsource_new
                    WHEN 'partner' THEN 'partner'::dealsource_new
                    WHEN 'other' THEN 'other'::dealsource_new
                    ELSE 'other'::dealsource_new
                END
            );

            -- Drop old enum type
            DROP TYPE dealsource;

            -- Rename new type to original name
            ALTER TYPE dealsource_new RENAME TO dealsource;

            -- Restore default (mapped to new enum value)
            ALTER TABLE hq_deal ALTER COLUMN source SET DEFAULT 'other'::dealsource;
        END $$;
    """)


def downgrade() -> None:
    # Revert to old enum values
    op.execute("""
        DO $$
        BEGIN
            -- Create old enum type
            CREATE TYPE dealsource_new AS ENUM (
                'inbound', 'outbound', 'referral', 'partner', 'fmcsa_import', 'other'
            );

            -- Alter column back to old type with reverse mapping
            ALTER TABLE hq_deal ALTER COLUMN source TYPE dealsource_new
            USING (
                CASE source::text
                    WHEN 'website' THEN 'inbound'::dealsource_new
                    WHEN 'cold_call' THEN 'outbound'::dealsource_new
                    WHEN 'fmcsa' THEN 'fmcsa_import'::dealsource_new
                    WHEN 'referral' THEN 'referral'::dealsource_new
                    WHEN 'partner' THEN 'partner'::dealsource_new
                    ELSE 'other'::dealsource_new
                END
            );

            -- Drop current enum type
            DROP TYPE dealsource;

            -- Rename back
            ALTER TYPE dealsource_new RENAME TO dealsource;
        END $$;
    """)


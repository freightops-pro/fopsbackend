"""Fix estimated_trucks column type to VARCHAR

Revision ID: 19feb2d2f1bf
Revises: a65a68d3ee84
Create Date: 2026-01-11 21:34:23.545741

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '19feb2d2f1bf'
down_revision = 'a65a68d3ee84'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change estimated_trucks from INTEGER to VARCHAR to match model
    # This allows storing ranges like "10-25" instead of just integers
    op.execute("""
        DO $$
        BEGIN
            -- Check if column exists and is INTEGER type
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal'
                AND column_name = 'estimated_trucks'
                AND data_type = 'integer'
            ) THEN
                -- Alter the column type to VARCHAR
                ALTER TABLE hq_deal ALTER COLUMN estimated_trucks TYPE VARCHAR USING estimated_trucks::VARCHAR;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Revert back to INTEGER (data loss may occur for ranges)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'hq_deal'
                AND column_name = 'estimated_trucks'
                AND data_type = 'character varying'
            ) THEN
                -- Try to convert back to INTEGER, NULL for non-numeric values
                ALTER TABLE hq_deal ALTER COLUMN estimated_trucks TYPE INTEGER USING (
                    CASE
                        WHEN estimated_trucks ~ '^[0-9]+$' THEN estimated_trucks::INTEGER
                        ELSE NULL
                    END
                );
            END IF;
        END $$;
    """)


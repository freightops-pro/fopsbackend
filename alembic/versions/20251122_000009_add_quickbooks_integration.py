"""Add QuickBooks Online integration to catalog

Revision ID: 20251122_000009
Revises: 20251122_000008
Create Date: 2024-11-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '20251122_000009'
down_revision = '20251122_000008'  # Depends on port tables migration
branch_labels = None
depends_on = None


def upgrade():
    # Insert QuickBooks Online integration into the catalog
    # Uses PostgreSQL syntax: ON CONFLICT DO NOTHING and NOW()
    op.execute("""
        INSERT INTO integration (
            id,
            integration_key,
            display_name,
            description,
            integration_type,
            auth_type,
            requires_oauth,
            features,
            is_active,
            created_at,
            updated_at
        ) VALUES (
            'quickbooks-online',
            'quickbooks',
            'QuickBooks Online',
            'Accounting and financial management platform. Sync invoices, payments, customers, vendors, and financial reports.',
            'accounting',
            'oauth2',
            true,
            '["invoices", "payments", "customers", "vendors", "accounts", "reports", "journal_entries", "bills", "estimates"]',
            true,
            NOW(),
            NOW()
        )
        ON CONFLICT (integration_key) DO NOTHING
    """)


def downgrade():
    # Remove QuickBooks integration
    op.execute("""
        DELETE FROM integration WHERE integration_key = 'quickbooks'
    """)


"""Enable pgvector extension and add embeddings.

Revision ID: 20251214_000001
Revises: 20251212_000001
Create Date: 2025-12-14 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251214_000001'
down_revision = '20251212_000001'
branch_labels = None
depends_on = None


def upgrade():
    """Enable pgvector extension and add embedding columns."""
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Add embedding column to drivers for semantic matching
    op.add_column('driver', sa.Column('preference_embedding', sa.String(), nullable=True))

    # Add embedding column to freight_load for similarity search
    op.add_column('freight_load', sa.Column('route_embedding', sa.String(), nullable=True))

    # Create vector indexes for fast similarity search
    # Note: Using text format for vectors, will convert when querying
    op.execute('CREATE INDEX IF NOT EXISTS driver_preference_embedding_idx ON driver USING btree (preference_embedding) WHERE preference_embedding IS NOT NULL')
    op.execute('CREATE INDEX IF NOT EXISTS load_route_embedding_idx ON freight_load USING btree (route_embedding) WHERE route_embedding IS NOT NULL')


def downgrade():
    """Remove embedding columns and pgvector extension."""
    op.execute('DROP INDEX IF EXISTS load_route_embedding_idx')
    op.execute('DROP INDEX IF EXISTS driver_preference_embedding_idx')
    op.drop_column('freight_load', 'route_embedding')
    op.drop_column('driver', 'preference_embedding')
    op.execute('DROP EXTENSION IF EXISTS vector')

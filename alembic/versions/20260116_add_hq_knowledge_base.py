"""Add HQ Knowledge Base tables for RAG.

Revision ID: 20260116_hq_knowledge
Revises: 20260115_add_hq_ai_task
Create Date: 2026-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260116_hq_knowledge'
down_revision: Union[str, None] = '20260115_add_hq_ai_task'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension is enabled
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create knowledge category enum
    conn = op.get_bind()
    conn.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'knowledgecategory') THEN
                CREATE TYPE knowledgecategory AS ENUM (
                    'accounting', 'taxes', 'hr', 'payroll',
                    'marketing', 'compliance', 'operations', 'general'
                );
            END IF;
        END $$;
    """))

    # Create hq_knowledge_documents table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS hq_knowledge_documents (
            id VARCHAR(36) PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            category knowledgecategory NOT NULL,
            source VARCHAR(500),
            content TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """))

    # Create hq_knowledge_chunks table with vector embedding
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS hq_knowledge_chunks (
            id VARCHAR(36) PRIMARY KEY,
            document_id VARCHAR(36) NOT NULL REFERENCES hq_knowledge_documents(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1536),
            category knowledgecategory NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))

    # Add indexes
    op.create_index('ix_hq_knowledge_documents_category', 'hq_knowledge_documents', ['category'])
    op.create_index('ix_hq_knowledge_documents_created_at', 'hq_knowledge_documents', ['created_at'])
    op.create_index('ix_hq_knowledge_chunks_document_id', 'hq_knowledge_chunks', ['document_id'])
    op.create_index('ix_hq_knowledge_chunks_category', 'hq_knowledge_chunks', ['category'])

    # Create IVFFlat index for fast vector similarity search
    # Using cosine distance (vector_cosine_ops)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_hq_knowledge_chunks_embedding
        ON hq_knowledge_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def downgrade() -> None:
    # Drop indexes
    op.execute('DROP INDEX IF EXISTS ix_hq_knowledge_chunks_embedding')
    op.drop_index('ix_hq_knowledge_chunks_category', table_name='hq_knowledge_chunks')
    op.drop_index('ix_hq_knowledge_chunks_document_id', table_name='hq_knowledge_chunks')
    op.drop_index('ix_hq_knowledge_documents_created_at', table_name='hq_knowledge_documents')
    op.drop_index('ix_hq_knowledge_documents_category', table_name='hq_knowledge_documents')

    # Drop tables
    op.drop_table('hq_knowledge_chunks')
    op.drop_table('hq_knowledge_documents')

    # Drop enum
    op.execute('DROP TYPE IF EXISTS knowledgecategory')

"""Add HQ Learning tables for continuous AI improvement.

Revision ID: 20260116_hq_learning
Revises: 20260116_hq_knowledge
Create Date: 2026-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260116_hq_learning'
down_revision: Union[str, None] = '20260116_hq_knowledge'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Create enum types
    conn.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feedbacktype') THEN
                CREATE TYPE feedbacktype AS ENUM (
                    'helpful', 'unhelpful', 'inaccurate', 'incomplete', 'outdated'
                );
            END IF;
        END $$;
    """))

    conn.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'gaptype') THEN
                CREATE TYPE gaptype AS ENUM (
                    'missing_topic', 'low_relevance', 'contradiction', 'outdated', 'insufficient_depth'
                );
            END IF;
        END $$;
    """))

    # Create hq_agent_interactions table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS hq_agent_interactions (
            id VARCHAR(36) PRIMARY KEY,
            agent_type VARCHAR(50) NOT NULL,
            task_id VARCHAR(36),
            user_query TEXT NOT NULL,
            query_embedding vector(1536),
            retrieved_chunk_ids TEXT,
            retrieval_scores TEXT,
            final_response TEXT,
            response_length INTEGER,
            retrieval_quality_score FLOAT,
            response_confidence FLOAT,
            user_context TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            response_time_ms INTEGER
        )
    """))

    # Create hq_knowledge_feedback table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS hq_knowledge_feedback (
            id VARCHAR(36) PRIMARY KEY,
            interaction_id VARCHAR(36) NOT NULL,
            feedback_type feedbacktype NOT NULL,
            user_rating INTEGER,
            user_comment TEXT,
            suggested_correction TEXT,
            affected_chunk_ids TEXT,
            feedback_source VARCHAR(50) DEFAULT 'user',
            processed INTEGER DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMP
        )
    """))

    # Create hq_knowledge_gaps table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS hq_knowledge_gaps (
            id VARCHAR(36) PRIMARY KEY,
            gap_type gaptype NOT NULL,
            topic TEXT NOT NULL,
            topic_embedding vector(1536),
            detection_method VARCHAR(100) NOT NULL,
            confidence_score FLOAT DEFAULT 0.5,
            related_interaction_ids TEXT,
            suggested_category knowledgecategory,
            status VARCHAR(20) DEFAULT 'open',
            resolution_notes TEXT,
            resolved_by_document_id VARCHAR(36),
            occurrence_count INTEGER DEFAULT 1,
            priority_score FLOAT DEFAULT 0.5,
            detected_at TIMESTAMP NOT NULL DEFAULT NOW(),
            last_occurred_at TIMESTAMP DEFAULT NOW(),
            resolved_at TIMESTAMP
        )
    """))

    # Create hq_chunk_confidence table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS hq_chunk_confidence (
            id VARCHAR(36) PRIMARY KEY,
            chunk_id VARCHAR(36) NOT NULL UNIQUE,
            confidence_score FLOAT DEFAULT 1.0,
            usage_count INTEGER DEFAULT 0,
            helpful_count INTEGER DEFAULT 0,
            unhelpful_count INTEGER DEFAULT 0,
            helpfulness_ratio FLOAT DEFAULT 1.0,
            avg_retrieval_rank FLOAT,
            last_used_at TIMESTAMP,
            is_stale INTEGER DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """))

    # Create hq_learning_metrics table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS hq_learning_metrics (
            id VARCHAR(36) PRIMARY KEY,
            date TIMESTAMP NOT NULL,
            agent_type VARCHAR(50),
            total_documents INTEGER DEFAULT 0,
            total_chunks INTEGER DEFAULT 0,
            avg_chunk_confidence FLOAT DEFAULT 1.0,
            new_chunks_added INTEGER DEFAULT 0,
            chunks_updated INTEGER DEFAULT 0,
            chunks_deprecated INTEGER DEFAULT 0,
            gaps_detected INTEGER DEFAULT 0,
            gaps_resolved INTEGER DEFAULT 0,
            open_gaps_count INTEGER DEFAULT 0,
            total_interactions INTEGER DEFAULT 0,
            avg_retrieval_quality FLOAT DEFAULT 0.0,
            feedback_received INTEGER DEFAULT 0,
            positive_feedback_pct FLOAT DEFAULT 0.0,
            avg_user_rating FLOAT,
            knowledge_coverage_pct FLOAT DEFAULT 0.0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))

    # Create indexes
    op.create_index('ix_hq_agent_interactions_agent_type', 'hq_agent_interactions', ['agent_type'])
    op.create_index('ix_hq_agent_interactions_created_at', 'hq_agent_interactions', ['created_at'])
    op.create_index('ix_hq_agent_interactions_task_id', 'hq_agent_interactions', ['task_id'])

    op.create_index('ix_hq_knowledge_feedback_interaction_id', 'hq_knowledge_feedback', ['interaction_id'])
    op.create_index('ix_hq_knowledge_feedback_processed', 'hq_knowledge_feedback', ['processed'])

    op.create_index('ix_hq_knowledge_gaps_status', 'hq_knowledge_gaps', ['status'])
    op.create_index('ix_hq_knowledge_gaps_priority', 'hq_knowledge_gaps', ['priority_score'])

    op.create_index('ix_hq_chunk_confidence_chunk_id', 'hq_chunk_confidence', ['chunk_id'])

    op.create_index('ix_hq_learning_metrics_date', 'hq_learning_metrics', ['date'])
    op.create_index('ix_hq_learning_metrics_date_agent', 'hq_learning_metrics', ['date', 'agent_type'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_hq_learning_metrics_date_agent', table_name='hq_learning_metrics')
    op.drop_index('ix_hq_learning_metrics_date', table_name='hq_learning_metrics')
    op.drop_index('ix_hq_chunk_confidence_chunk_id', table_name='hq_chunk_confidence')
    op.drop_index('ix_hq_knowledge_gaps_priority', table_name='hq_knowledge_gaps')
    op.drop_index('ix_hq_knowledge_gaps_status', table_name='hq_knowledge_gaps')
    op.drop_index('ix_hq_knowledge_feedback_processed', table_name='hq_knowledge_feedback')
    op.drop_index('ix_hq_knowledge_feedback_interaction_id', table_name='hq_knowledge_feedback')
    op.drop_index('ix_hq_agent_interactions_task_id', table_name='hq_agent_interactions')
    op.drop_index('ix_hq_agent_interactions_created_at', table_name='hq_agent_interactions')
    op.drop_index('ix_hq_agent_interactions_agent_type', table_name='hq_agent_interactions')

    # Drop tables
    op.drop_table('hq_learning_metrics')
    op.drop_table('hq_chunk_confidence')
    op.drop_table('hq_knowledge_gaps')
    op.drop_table('hq_knowledge_feedback')
    op.drop_table('hq_agent_interactions')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS gaptype')
    op.execute('DROP TYPE IF EXISTS feedbacktype')

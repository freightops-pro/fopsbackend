"""Add IT Operations tables

Revision ID: 20251227_000001
Revises:
Create Date: 2025-12-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251227_000001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Feature Flags table
    op.create_table(
        'hq_feature_flag',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('key', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('enabled', sa.Boolean, default=False, nullable=False),
        sa.Column('environment', sa.String(20), default='development', nullable=False),
        sa.Column('rollout_percentage', sa.Integer, default=0, nullable=False),
        sa.Column('target_tenants', sa.JSON, nullable=True),
        sa.Column('created_by_id', sa.String(36), nullable=False),
        sa.Column('created_by_name', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Service Health table
    op.create_table(
        'hq_service_health',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('service_type', sa.String(20), nullable=False),
        sa.Column('endpoint', sa.String(500), nullable=False),
        sa.Column('health_check_url', sa.String(500), nullable=True),
        sa.Column('region', sa.String(50), default='US-East', nullable=False),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('current_status', sa.String(20), default='operational', nullable=False),
        sa.Column('current_latency_ms', sa.Integer, default=0, nullable=False),
        sa.Column('uptime_30d', sa.Float, default=100.0, nullable=False),
        sa.Column('last_checked_at', sa.DateTime, nullable=True),
        sa.Column('last_error', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Deployment History table
    op.create_table(
        'hq_deployment',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('environment', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), default='in_progress', nullable=False),
        sa.Column('commit_hash', sa.String(40), nullable=True),
        sa.Column('changes_count', sa.Integer, default=0, nullable=False),
        sa.Column('duration_seconds', sa.Integer, nullable=True),
        sa.Column('deployed_by_id', sa.String(36), nullable=False),
        sa.Column('deployed_by_name', sa.String(200), nullable=True),
        sa.Column('started_at', sa.DateTime, nullable=False),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('rollback_of_id', sa.String(36), nullable=True),
    )

    # Create indexes
    op.create_index('ix_hq_deployment_environment', 'hq_deployment', ['environment'])
    op.create_index('ix_hq_deployment_started_at', 'hq_deployment', ['started_at'])
    op.create_index('ix_hq_service_health_service_type', 'hq_service_health', ['service_type'])


def downgrade() -> None:
    op.drop_index('ix_hq_service_health_service_type')
    op.drop_index('ix_hq_deployment_started_at')
    op.drop_index('ix_hq_deployment_environment')
    op.drop_table('hq_deployment')
    op.drop_table('hq_service_health')
    op.drop_table('hq_feature_flag')

"""Add team messaging for Enterprise tier

Revision ID: 004_add_team_messaging
Revises: 003_add_stripe_subscription_tables
Create Date: 2024-01-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision = '004_add_team_messaging'
down_revision = '003_add_stripe_subscription_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create teams table
    op.create_table('teams',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_private', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('member_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=False),
        sa.Column('created_by_type', sa.String(10), server_default='user', nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_teams_id'), 'teams', ['id'], unique=False)
    op.create_index(op.f('ix_teams_company_id'), 'teams', ['company_id'], unique=False)

    # Create team_members table
    op.create_table('team_members',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('team_id', sa.String(36), nullable=False),
        sa.Column('member_id', sa.String(36), nullable=False),
        sa.Column('member_type', sa.String(10), nullable=False),
        sa.Column('role', sa.String(20), server_default='member', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('joined_at', sa.DateTime(), server_default=func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=func.now(), onupdate=func.now(), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'member_id', name='uq_team_member')
    )
    op.create_index(op.f('ix_team_members_id'), 'team_members', ['id'], unique=False)
    op.create_index(op.f('ix_team_members_team_id'), 'team_members', ['team_id'], unique=False)

    # Add new columns to conversations table
    op.add_column('conversations', sa.Column('conversation_type', sa.Enum('direct', 'team', name='conversationtype'), server_default='direct', nullable=False))
    op.add_column('conversations', sa.Column('participant1_id', sa.String(36), nullable=True))
    op.add_column('conversations', sa.Column('participant2_id', sa.String(36), nullable=True))
    op.add_column('conversations', sa.Column('participant1_type', sa.String(10), nullable=True))
    op.add_column('conversations', sa.Column('participant2_type', sa.String(10), nullable=True))
    op.add_column('conversations', sa.Column('team_id', sa.String(36), nullable=True))
    op.add_column('conversations', sa.Column('team_name', sa.String(255), nullable=True))

    # Add foreign key constraint for team_id in conversations
    op.create_foreign_key('fk_conversations_team_id', 'conversations', 'teams', ['team_id'], ['id'])

    # Create index for team_id in conversations
    op.create_index(op.f('ix_conversations_team_id'), 'conversations', ['team_id'], unique=False)

    # Migrate existing data: set existing conversations as 'direct' type
    # and populate participant fields from existing structure
    op.execute("""
        UPDATE conversations 
        SET conversation_type = 'direct',
            participant1_id = participant1_id,
            participant2_id = participant2_id,
            participant1_type = participant1_type,
            participant2_type = participant2_type
        WHERE conversation_type IS NULL
    """)


def downgrade() -> None:
    # Remove foreign key and index from conversations
    op.drop_index(op.f('ix_conversations_team_id'), table_name='conversations')
    op.drop_constraint('fk_conversations_team_id', 'conversations', type_='foreignkey')
    
    # Remove new columns from conversations table
    op.drop_column('conversations', 'team_name')
    op.drop_column('conversations', 'team_id')
    op.drop_column('conversations', 'participant2_type')
    op.drop_column('conversations', 'participant1_type')
    op.drop_column('conversations', 'participant2_id')
    op.drop_column('conversations', 'participant1_id')
    op.drop_column('conversations', 'conversation_type')
    
    # Drop teams and team_members tables
    op.drop_index(op.f('ix_team_members_team_id'), table_name='team_members')
    op.drop_index(op.f('ix_team_members_id'), table_name='team_members')
    op.drop_table('team_members')
    
    op.drop_index(op.f('ix_teams_company_id'), table_name='teams')
    op.drop_index(op.f('ix_teams_id'), table_name='teams')
    op.drop_table('teams')
    
    # Drop the enum type
    op.execute('DROP TYPE conversationtype')

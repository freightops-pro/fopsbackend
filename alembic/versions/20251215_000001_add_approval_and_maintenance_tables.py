"""Add AI approval requests and maintenance work orders tables.

Revision ID: 20251215_000001
Revises: dcb45630b7ab
Create Date: 2025-12-15 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '20251215_000001'
down_revision = 'dcb45630b7ab'
branch_labels = None
depends_on = None


def upgrade():
    """Create driver_settlements, ai_approval_requests, and maintenance_work_orders tables."""

    # Driver Settlements Table (needed by CFO Analyst for margin calculations)
    op.create_table(
        'driver_settlements',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), nullable=False, index=True),
        sa.Column('driver_id', sa.String(), nullable=False, index=True),
        sa.Column('load_id', sa.String(), nullable=True, index=True),

        # Settlement details
        sa.Column('settlement_type', sa.String(), nullable=False),  # driver_pay, bonus, deduction, etc.
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        # Payment info
        sa.Column('settlement_date', sa.Date(), nullable=False, index=True),
        sa.Column('pay_period_start', sa.Date(), nullable=True),
        sa.Column('pay_period_end', sa.Date(), nullable=True),
        sa.Column('payment_method', sa.String(), nullable=True),  # direct_deposit, check, etc.
        sa.Column('payment_status', sa.String(), nullable=False, default='pending'),  # pending, paid, cancelled

        # Reference info
        sa.Column('reference_number', sa.String(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False),

        # Foreign keys
        sa.ForeignKeyConstraint(['driver_id'], ['driver.id'], ),
        sa.ForeignKeyConstraint(['load_id'], ['freight_load.id'], ),
    )

    # Create indexes for driver settlements
    op.create_index('idx_driver_settlements_driver_date', 'driver_settlements', ['driver_id', 'settlement_date'])
    op.create_index('idx_driver_settlements_load', 'driver_settlements', ['load_id'])
    op.create_index('idx_driver_settlements_status', 'driver_settlements', ['payment_status', 'settlement_date'])


    # AI Approval Requests Table
    op.create_table(
        'ai_approval_requests',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), nullable=False, index=True),
        sa.Column('agent_type', sa.String(), nullable=False),  # fleet_manager, cfo_analyst, etc.
        sa.Column('agent_task_id', sa.String(), nullable=True),  # Related AI task if any

        # Request details
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('urgency', sa.String(), nullable=False),  # low, medium, high, critical

        # Financial info (for CFO Analyst)
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('estimated_cost', sa.Numeric(precision=10, scale=2), nullable=True),

        # Request metadata
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('context', sa.JSON(), nullable=True),

        # Status and decision
        sa.Column('status', sa.String(), nullable=False, default='pending'),  # pending, approved, rejected
        sa.Column('reviewed_by', sa.String(), nullable=True),  # User ID
        sa.Column('review_decision', sa.String(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False),
    )

    # Create indexes for approval requests
    op.create_index('idx_approval_requests_company_status', 'ai_approval_requests', ['company_id', 'status'])
    op.create_index('idx_approval_requests_urgency', 'ai_approval_requests', ['urgency', 'status'])
    op.create_index('idx_approval_requests_agent_type', 'ai_approval_requests', ['agent_type', 'status'])


    # Maintenance Work Orders Table
    op.create_table(
        'maintenance_work_orders',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), nullable=False, index=True),
        sa.Column('equipment_id', sa.String(), nullable=False, index=True),

        # Work order details
        sa.Column('maintenance_type', sa.String(), nullable=False),  # oil_change, inspection, tire_rotation, etc.
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(), nullable=False),  # routine, urgent, critical

        # Scheduling
        sa.Column('scheduled_date', sa.DateTime(), nullable=False),
        sa.Column('estimated_hours', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('actual_start_date', sa.DateTime(), nullable=True),
        sa.Column('actual_completion_date', sa.DateTime(), nullable=True),
        sa.Column('actual_hours', sa.Numeric(precision=5, scale=2), nullable=True),

        # Status tracking
        sa.Column('status', sa.String(), nullable=False, default='scheduled'),  # scheduled, in_progress, completed, cancelled
        sa.Column('completion_percentage', sa.Integer(), nullable=True, default=0),

        # Parts and costs
        sa.Column('parts_needed', sa.JSON(), nullable=True),
        sa.Column('parts_cost', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('labor_cost', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('total_cost', sa.Numeric(precision=10, scale=2), nullable=True),

        # Assignment
        sa.Column('assigned_to', sa.String(), nullable=True),  # Mechanic or vendor ID
        sa.Column('vendor_id', sa.String(), nullable=True),

        # AI tracking
        sa.Column('created_by_ai', sa.Boolean(), default=False),
        sa.Column('ai_agent_type', sa.String(), nullable=True),  # fleet_manager
        sa.Column('ai_task_id', sa.String(), nullable=True),

        # Notes and documentation
        sa.Column('technician_notes', sa.Text(), nullable=True),
        sa.Column('completion_notes', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False),

        # Foreign keys - removed for now due to equipment table not existing in this database
        # sa.ForeignKeyConstraint(['equipment_id'], ['equipment.id'], ),
    )

    # Create indexes for maintenance work orders
    op.create_index('idx_maintenance_wo_equipment_status', 'maintenance_work_orders', ['equipment_id', 'status'])
    op.create_index('idx_maintenance_wo_scheduled', 'maintenance_work_orders', ['scheduled_date', 'status'])
    op.create_index('idx_maintenance_wo_priority', 'maintenance_work_orders', ['priority', 'status'])
    op.create_index('idx_maintenance_wo_company', 'maintenance_work_orders', ['company_id', 'created_at'])


def downgrade():
    """Drop driver_settlements, ai_approval_requests, and maintenance_work_orders tables."""

    # Drop maintenance work orders
    op.drop_index('idx_maintenance_wo_company', table_name='maintenance_work_orders')
    op.drop_index('idx_maintenance_wo_priority', table_name='maintenance_work_orders')
    op.drop_index('idx_maintenance_wo_scheduled', table_name='maintenance_work_orders')
    op.drop_index('idx_maintenance_wo_equipment_status', table_name='maintenance_work_orders')
    op.drop_table('maintenance_work_orders')

    # Drop approval requests
    op.drop_index('idx_approval_requests_agent_type', table_name='ai_approval_requests')
    op.drop_index('idx_approval_requests_urgency', table_name='ai_approval_requests')
    op.drop_index('idx_approval_requests_company_status', table_name='ai_approval_requests')
    op.drop_table('ai_approval_requests')

    # Drop driver settlements
    op.drop_index('idx_driver_settlements_status', table_name='driver_settlements')
    op.drop_index('idx_driver_settlements_load', table_name='driver_settlements')
    op.drop_index('idx_driver_settlements_driver_date', table_name='driver_settlements')
    op.drop_table('driver_settlements')

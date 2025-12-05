"""Add port tables

Revision ID: 20251122_000008
Revises: 20251120_000007
Create Date: 2025-11-22 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251122_000008"
down_revision: Union[str, None] = "20251122_000007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create port table
    op.create_table(
        "port",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("port_code", sa.String(), nullable=False),
        sa.Column("port_name", sa.String(), nullable=False),
        sa.Column("unlocode", sa.String(), nullable=True),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=False, server_default="US"),
        sa.Column("services_supported", sa.JSON(), nullable=True),
        sa.Column("adapter_class", sa.String(), nullable=True),
        sa.Column("auth_type", sa.String(), nullable=True),
        sa.Column("rate_limits", sa.JSON(), nullable=True),
        sa.Column("compliance_standards", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.String(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_port_port_code", "port", ["port_code"], unique=True)

    # Create port_integration table
    op.create_table(
        "port_integration",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("port_id", sa.String(), sa.ForeignKey("port.id"), nullable=False),
        sa.Column("credentials", sa.JSON(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_sync", sa.String(), nullable=False, server_default="true"),
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_port_integration_company_id", "port_integration", ["company_id"])
    op.create_index("ix_port_integration_port_id", "port_integration", ["port_id"])

    # Create container_tracking table
    op.create_table(
        "container_tracking",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("load_id", sa.String(), sa.ForeignKey("freight_load.id"), nullable=True),
        sa.Column("port_integration_id", sa.String(), sa.ForeignKey("port_integration.id"), nullable=True),
        sa.Column("container_number", sa.String(), nullable=False),
        sa.Column("port_code", sa.String(), nullable=False),
        sa.Column("terminal", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("location", sa.JSON(), nullable=True),
        sa.Column("vessel", sa.JSON(), nullable=True),
        sa.Column("dates", sa.JSON(), nullable=True),
        sa.Column("container_details", sa.JSON(), nullable=True),
        sa.Column("holds", sa.JSON(), nullable=True),
        sa.Column("charges", sa.JSON(), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_container_tracking_company_id", "container_tracking", ["company_id"])
    op.create_index("ix_container_tracking_load_id", "container_tracking", ["load_id"])
    op.create_index("ix_container_tracking_port_integration_id", "container_tracking", ["port_integration_id"])
    op.create_index("ix_container_tracking_container_number", "container_tracking", ["container_number"])
    op.create_index("ix_container_tracking_port_code", "container_tracking", ["port_code"])

    # Create container_tracking_event table
    op.create_table(
        "container_tracking_event",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("container_tracking_id", sa.String(), sa.ForeignKey("container_tracking.id"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_container_tracking_event_container_tracking_id", "container_tracking_event", ["container_tracking_id"])
    op.create_index("ix_container_tracking_event_event_timestamp", "container_tracking_event", ["event_timestamp"])

    # Seed major ports
    op.execute("""
        INSERT INTO port (id, port_code, port_name, unlocode, region, state, adapter_class, auth_type, is_active)
        VALUES
            ('port-houston', 'USHOU', 'Port of Houston', 'USHOU', 'Gulf Coast', 'TX', 'PortHoustonAdapter', 'oauth2', 'true'),
            ('port-virginia', 'USORF', 'Port of Virginia (Norfolk)', 'USORF', 'East Coast', 'VA', 'PortVirginiaAdapter', 'api_key', 'true'),
            ('port-savannah', 'USSAV', 'Port of Savannah', 'USSAV', 'East Coast', 'GA', 'SavannahAdapter', 'password', 'true'),
            ('port-los-angeles', 'USLAX', 'Port of Los Angeles', 'USLAX', 'West Coast', 'CA', 'LALBAdapter', 'api_key', 'true'),
            ('port-long-beach', 'USLGB', 'Port of Long Beach', 'USLGB', 'West Coast', 'CA', 'LALBAdapter', 'api_key', 'true'),
            ('port-new-york', 'USNYC', 'Port of New York', 'USNYC', 'East Coast', 'NY', 'NYNJAdapter', 'api_key', 'true'),
            ('port-newark', 'USEWR', 'Port of Newark', 'USEWR', 'East Coast', 'NJ', 'NYNJAdapter', 'api_key', 'true')
    """)


def downgrade() -> None:
    op.drop_index("ix_container_tracking_event_event_timestamp", table_name="container_tracking_event")
    op.drop_index("ix_container_tracking_event_container_tracking_id", table_name="container_tracking_event")
    op.drop_table("container_tracking_event")
    
    op.drop_index("ix_container_tracking_port_code", table_name="container_tracking")
    op.drop_index("ix_container_tracking_container_number", table_name="container_tracking")
    op.drop_index("ix_container_tracking_port_integration_id", table_name="container_tracking")
    op.drop_index("ix_container_tracking_load_id", table_name="container_tracking")
    op.drop_index("ix_container_tracking_company_id", table_name="container_tracking")
    op.drop_table("container_tracking")
    
    op.drop_index("ix_port_integration_port_id", table_name="port_integration")
    op.drop_index("ix_port_integration_company_id", table_name="port_integration")
    op.drop_table("port_integration")
    
    op.drop_index("ix_port_port_code", table_name="port")
    op.drop_table("port")


"""Add fields to support load matching heuristics

Revision ID: 20251111_000002
Revises: 20251111_000001
Create Date: 2025-11-11 15:45:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251111_000002"
down_revision = "20251111_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("driver", sa.Column("preference_profile", sa.JSON(), nullable=True))
    op.add_column("driver", sa.Column("compliance_score", sa.Float(), nullable=True))
    op.add_column("driver", sa.Column("average_rating", sa.Float(), nullable=True))
    op.add_column("driver", sa.Column("total_completed_loads", sa.Float(), nullable=False, server_default="0"))

    op.add_column("freight_load", sa.Column("required_skills", sa.JSON(), nullable=True))
    op.add_column("freight_load", sa.Column("preferred_driver_ids", sa.JSON(), nullable=True))
    op.add_column("freight_load", sa.Column("preferred_truck_ids", sa.JSON(), nullable=True))

    op.add_column("freight_load_stop", sa.Column("distance_miles", sa.Float(), nullable=True))
    op.add_column("freight_load_stop", sa.Column("fuel_estimate_gallons", sa.Float(), nullable=True))
    op.add_column("freight_load_stop", sa.Column("dwell_minutes_estimate", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("freight_load_stop", "dwell_minutes_estimate")
    op.drop_column("freight_load_stop", "fuel_estimate_gallons")
    op.drop_column("freight_load_stop", "distance_miles")

    op.drop_column("freight_load", "preferred_truck_ids")
    op.drop_column("freight_load", "preferred_driver_ids")
    op.drop_column("freight_load", "required_skills")

    op.drop_column("driver", "total_completed_loads")
    op.drop_column("driver", "average_rating")
    op.drop_column("driver", "compliance_score")
    op.drop_column("driver", "preference_profile")


"""fix_drivers_table_defaults

Revision ID: 1851b353dec5
Revises: 189d04cb05ba
Create Date: 2025-09-26 21:01:56.496876

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1851b353dec5'
down_revision: Union[str, None] = '189d04cb05ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    # Create new table with correct defaults
    op.execute("""
        CREATE TABLE drivers_new (
            id VARCHAR(255) PRIMARY KEY,
            companyId VARCHAR(255) NOT NULL,
            firstName VARCHAR(255) NOT NULL,
            lastName VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            phone VARCHAR(50) NOT NULL,
            licenseNumber VARCHAR(50) NOT NULL,
            licenseClass VARCHAR(10) NOT NULL,
            licenseExpiry TIMESTAMP NOT NULL,
            dateOfBirth TIMESTAMP NOT NULL,
            address VARCHAR(500) NOT NULL,
            city VARCHAR(100) NOT NULL,
            state VARCHAR(50) NOT NULL,
            zipCode VARCHAR(20) NOT NULL,
            emergencyContact VARCHAR(255) NOT NULL,
            emergencyPhone VARCHAR(50) NOT NULL,
            hireDate TIMESTAMP NOT NULL,
            status VARCHAR(50) DEFAULT 'available',
            payRate DECIMAL NOT NULL,
            payType VARCHAR(50) NOT NULL,
            hoursRemaining DECIMAL,
            currentLocation VARCHAR(500),
            isActive BOOLEAN DEFAULT true,
            createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (companyId) REFERENCES companies (id)
        )
    """)
    
    # Copy data from old table
    op.execute("INSERT INTO drivers_new SELECT * FROM drivers")
    
    # Drop old table and rename new one
    op.execute("DROP TABLE drivers")
    op.execute("ALTER TABLE drivers_new RENAME TO drivers")


def downgrade() -> None:
    # Recreate table with old defaults (for rollback)
    op.execute("""
        CREATE TABLE drivers_old (
            id VARCHAR(255) PRIMARY KEY,
            companyId VARCHAR(255) NOT NULL,
            firstName VARCHAR(255) NOT NULL,
            lastName VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            phone VARCHAR(50) NOT NULL,
            licenseNumber VARCHAR(50) NOT NULL,
            licenseClass VARCHAR(10) NOT NULL,
            licenseExpiry TIMESTAMP NOT NULL,
            dateOfBirth TIMESTAMP NOT NULL,
            address VARCHAR(500) NOT NULL,
            city VARCHAR(100) NOT NULL,
            state VARCHAR(50) NOT NULL,
            zipCode VARCHAR(20) NOT NULL,
            emergencyContact VARCHAR(255) NOT NULL,
            emergencyPhone VARCHAR(50) NOT NULL,
            hireDate TIMESTAMP NOT NULL,
            status VARCHAR(50) DEFAULT 'available',
            payRate DECIMAL NOT NULL,
            payType VARCHAR(50) NOT NULL,
            hoursRemaining DECIMAL,
            currentLocation VARCHAR(500),
            isActive BOOLEAN DEFAULT true,
            createdAt TIMESTAMP DEFAULT 'now()',
            updatedAt TIMESTAMP DEFAULT 'now()',
            FOREIGN KEY (companyId) REFERENCES companies (id)
        )
    """)
    
    # Copy data back
    op.execute("INSERT INTO drivers_old SELECT * FROM drivers")
    
    # Drop and rename
    op.execute("DROP TABLE drivers")
    op.execute("ALTER TABLE drivers_old RENAME TO drivers")

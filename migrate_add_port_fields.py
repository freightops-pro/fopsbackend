"""Migration script to add missing port appointment fields to freight_load table."""

import asyncio
import sys
from sqlalchemy import text
from app.core.db import AsyncSessionFactory

# Fix Windows event loop issue for psycopg async
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def migrate():
    """Add missing port appointment columns to freight_load table."""
    async with AsyncSessionFactory() as session:
        # Add port appointment columns if they don't exist
        alter_commands = [
            """
            ALTER TABLE freight_load
            ADD COLUMN IF NOT EXISTS port_appointment_id VARCHAR;
            """,
            """
            ALTER TABLE freight_load
            ADD COLUMN IF NOT EXISTS port_appointment_number VARCHAR;
            """,
            """
            ALTER TABLE freight_load
            ADD COLUMN IF NOT EXISTS port_entry_code VARCHAR;
            """,
            """
            ALTER TABLE freight_load
            ADD COLUMN IF NOT EXISTS port_appointment_time TIMESTAMP;
            """,
            """
            ALTER TABLE freight_load
            ADD COLUMN IF NOT EXISTS port_appointment_gate VARCHAR;
            """,
            """
            ALTER TABLE freight_load
            ADD COLUMN IF NOT EXISTS port_appointment_status VARCHAR;
            """,
            """
            ALTER TABLE freight_load
            ADD COLUMN IF NOT EXISTS port_appointment_terminal VARCHAR;
            """
        ]

        for command in alter_commands:
            try:
                await session.execute(text(command))
                print(f"[OK] Executed: {command.strip()[:60]}...")
            except Exception as e:
                print(f"[ERROR] {e}")

        await session.commit()
        print("\n[OK] Migration completed successfully!")

if __name__ == "__main__":
    asyncio.run(migrate())

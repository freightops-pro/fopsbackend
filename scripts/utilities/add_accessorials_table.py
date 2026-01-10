"""
Add Load Accessorials Table

Adds load_accessorials table to store accessorial charges for loads (detention, lumper, etc.).

Run: python -m scripts.utilities.add_accessorials_table
"""

# Set up Windows-compatible event loop BEFORE any database imports
import sys
if sys.platform == "win32":
    import asyncio
    import selectors
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    asyncio.set_event_loop(loop)

import asyncio
from sqlalchemy import text

from app.core.db import AsyncSessionFactory


async def add_accessorials_table():
    """Add load_accessorials table if it doesn't exist."""

    async with AsyncSessionFactory() as db:
        print("Checking for load_accessorials table...")

        # Check if table already exists
        check_sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = 'load_accessorials'
        """

        result = await db.execute(text(check_sql))
        existing_tables = {row[0] for row in result.fetchall()}

        if 'load_accessorials' in existing_tables:
            print("Load accessorials table already exists!")
            return

        print("Creating load_accessorials table...")

        # Create the table
        create_table_sql = """
        CREATE TABLE load_accessorials (
            id VARCHAR PRIMARY KEY,
            load_id VARCHAR NOT NULL REFERENCES freight_load(id) ON DELETE CASCADE,
            charge_type VARCHAR NOT NULL,
            description VARCHAR NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            quantity NUMERIC(10, 2) DEFAULT 1,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL
        )
        """

        await db.execute(text(create_table_sql))

        # Create index on load_id for faster lookups
        create_index_sql = """
        CREATE INDEX ix_load_accessorials_load_id ON load_accessorials(load_id)
        """

        await db.execute(text(create_index_sql))

        await db.commit()

        print("SUCCESS: Created load_accessorials table with index")


async def main():
    """Main entry point."""
    print("=" * 60)
    print("ADD LOAD ACCESSORIALS TABLE")
    print("=" * 60)
    print()

    await add_accessorials_table()

    print()
    print("=" * 60)
    print("COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    else:
        asyncio.run(main())

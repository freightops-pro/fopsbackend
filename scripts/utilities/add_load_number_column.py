"""
Add Load Number Column

Adds load_number column to freight_load table for formatted load references.

Run: python -m scripts.utilities.add_load_number_column
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


async def add_load_number_column():
    """Add load_number column to freight_load table if it doesn't exist."""

    async with AsyncSessionFactory() as db:
        print("Checking for load_number column...")

        # Check if column already exists
        check_sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'freight_load'
        AND column_name = 'load_number'
        """

        result = await db.execute(text(check_sql))
        existing_columns = {row[0] for row in result.fetchall()}

        if 'load_number' in existing_columns:
            print("Column load_number already exists!")
            return

        print("Adding load_number column to freight_load table...")

        # Add the column
        add_column_sql = """
        ALTER TABLE freight_load
        ADD COLUMN load_number VARCHAR UNIQUE
        """

        await db.execute(text(add_column_sql))

        # Create index for faster lookups
        create_index_sql = """
        CREATE INDEX ix_freight_load_load_number ON freight_load(load_number)
        """

        await db.execute(text(create_index_sql))

        await db.commit()

        print("SUCCESS: Added load_number column with unique constraint and index")


async def main():
    """Main entry point."""
    print("=" * 60)
    print("ADD LOAD NUMBER COLUMN")
    print("=" * 60)
    print()

    await add_load_number_column()

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

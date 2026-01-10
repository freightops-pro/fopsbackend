"""
Add Missing Factoring Columns to freight_load Table

This script manually adds the factoring columns that were supposed to be
added by the migration but are missing.

Run: python -m scripts.utilities.add_missing_factoring_columns
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


async def add_factoring_columns():
    """Add factoring columns to freight_load table if they don't exist."""

    async with AsyncSessionFactory() as db:
        print("Checking for missing factoring columns...")

        # Check if columns already exist
        check_sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'freight_load'
        AND column_name IN ('factoring_enabled', 'factoring_status',
                           'factoring_rate_override', 'factored_amount',
                           'factoring_fee_amount')
        """

        result = await db.execute(text(check_sql))
        existing_columns = {row[0] for row in result.fetchall()}

        columns_to_add = []

        if 'factoring_enabled' not in existing_columns:
            columns_to_add.append("ALTER TABLE freight_load ADD COLUMN factoring_enabled VARCHAR")

        if 'factoring_status' not in existing_columns:
            columns_to_add.append("ALTER TABLE freight_load ADD COLUMN factoring_status VARCHAR")

        if 'factoring_rate_override' not in existing_columns:
            columns_to_add.append("ALTER TABLE freight_load ADD COLUMN factoring_rate_override FLOAT")

        if 'factored_amount' not in existing_columns:
            columns_to_add.append("ALTER TABLE freight_load ADD COLUMN factored_amount NUMERIC(12, 2)")

        if 'factoring_fee_amount' not in existing_columns:
            columns_to_add.append("ALTER TABLE freight_load ADD COLUMN factoring_fee_amount NUMERIC(12, 2)")

        if not columns_to_add:
            print("All factoring columns already exist!")
            return

        print(f"Adding {len(columns_to_add)} missing columns...")

        for sql in columns_to_add:
            print(f"  Executing: {sql}")
            await db.execute(text(sql))

        await db.commit()

        print(f"\nSUCCESS: Added {len(columns_to_add)} factoring columns to freight_load table")


async def main():
    """Main entry point."""
    print("=" * 60)
    print("ADD MISSING FACTORING COLUMNS")
    print("=" * 60)
    print()

    await add_factoring_columns()

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

"""
Add Numbering Configuration to Company Table

Adds columns for configurable invoice and load numbering formats.

Run: python -m scripts.utilities.add_numbering_config
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


async def add_numbering_config_columns():
    """Add numbering configuration columns to company table."""

    async with AsyncSessionFactory() as db:
        print("Checking for numbering configuration columns...")

        # Check if columns already exist
        check_sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'company'
        AND column_name IN (
            'invoice_number_format',
            'invoice_start_number',
            'load_number_format',
            'load_start_number',
            'last_load_number'
        )
        """

        result = await db.execute(text(check_sql))
        existing_columns = {row[0] for row in result.fetchall()}

        columns_to_add = []

        if 'invoice_number_format' not in existing_columns:
            columns_to_add.append(
                "ALTER TABLE company ADD COLUMN invoice_number_format VARCHAR DEFAULT 'INV-{YEAR}-{NUMBER:05}'"
            )

        if 'invoice_start_number' not in existing_columns:
            columns_to_add.append(
                "ALTER TABLE company ADD COLUMN invoice_start_number INTEGER NOT NULL DEFAULT 1"
            )

        if 'load_number_format' not in existing_columns:
            columns_to_add.append(
                "ALTER TABLE company ADD COLUMN load_number_format VARCHAR DEFAULT 'LOAD-{YEAR}-{NUMBER:05}'"
            )

        if 'load_start_number' not in existing_columns:
            columns_to_add.append(
                "ALTER TABLE company ADD COLUMN load_start_number INTEGER NOT NULL DEFAULT 1"
            )

        if 'last_load_number' not in existing_columns:
            columns_to_add.append(
                "ALTER TABLE company ADD COLUMN last_load_number INTEGER NOT NULL DEFAULT 0"
            )

        if not columns_to_add:
            print("All numbering configuration columns already exist!")
            return

        print(f"Adding {len(columns_to_add)} numbering configuration columns...")

        for sql in columns_to_add:
            await db.execute(text(sql))
            print(f"  * Added column")

        await db.commit()

        print("SUCCESS: Added all numbering configuration columns to company table")
        print()
        print("Default formats:")
        print("  Invoices: INV-{YEAR}-{NUMBER:05}  (e.g., INV-2024-00001)")
        print("  Loads:    LOAD-{YEAR}-{NUMBER:05} (e.g., LOAD-2024-00001)")
        print()
        print("Available tokens:")
        print("  {YEAR}             - Current year (e.g., 2024)")
        print("  {MONTH}            - Current month (e.g., 01)")
        print("  {DAY}              - Current day (e.g., 15)")
        print("  {NUMBER}           - Sequential number")
        print("  {NUMBER:05}        - Sequential number zero-padded to 5 digits")
        print("  {CUSTOMER_PREFIX}  - First 3 letters of customer name")


async def main():
    """Main entry point."""
    print("=" * 70)
    print("ADD NUMBERING CONFIGURATION")
    print("=" * 70)
    print()

    await add_numbering_config_columns()

    print()
    print("=" * 70)
    print("COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    else:
        asyncio.run(main())

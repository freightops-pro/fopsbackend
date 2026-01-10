"""
Add Invoice Number Counter to Company Table

Adds a column to track the last invoice number for sequential generation.

Run: python -m scripts.utilities.add_invoice_counter
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


async def add_invoice_counter():
    """Add last_invoice_number column to company table if it doesn't exist."""

    async with AsyncSessionFactory() as db:
        print("Checking for last_invoice_number column...")

        # Check if column already exists
        check_sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'company' AND column_name = 'last_invoice_number'
        """

        result = await db.execute(text(check_sql))
        existing_columns = {row[0] for row in result.fetchall()}

        if 'last_invoice_number' in existing_columns:
            print("Invoice counter column already exists!")
            return

        print("Adding last_invoice_number column to company table...")

        # Add the column
        add_column_sql = """
        ALTER TABLE company
        ADD COLUMN last_invoice_number INTEGER DEFAULT 0 NOT NULL
        """

        await db.execute(text(add_column_sql))
        await db.commit()

        print("SUCCESS: Added last_invoice_number column to company table")


async def main():
    """Main entry point."""
    print("=" * 60)
    print("ADD INVOICE NUMBER COUNTER")
    print("=" * 60)
    print()

    await add_invoice_counter()

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

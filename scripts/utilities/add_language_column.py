"""
Add Language Column to Company Table

Adds preferred_language field to support multi-language UI and documents.

Run: python -m scripts.utilities.add_language_column
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


async def add_language_column():
    """Add preferred_language column to company table if it doesn't exist."""

    async with AsyncSessionFactory() as db:
        print("Checking for language column...")

        # Check if column already exists
        check_sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'company'
        AND column_name = 'preferred_language'
        """

        result = await db.execute(text(check_sql))
        existing_columns = {row[0] for row in result.fetchall()}

        if 'preferred_language' in existing_columns:
            print("Language column already exists!")
            return

        print("Adding preferred_language column...")

        # Add the column with default value 'en' (English)
        add_column_sql = """
        ALTER TABLE company
        ADD COLUMN preferred_language VARCHAR DEFAULT 'en'
        """

        await db.execute(text(add_column_sql))
        await db.commit()

        print("SUCCESS: Added preferred_language column to company table")


async def main():
    """Main entry point."""
    print("=" * 60)
    print("ADD LANGUAGE COLUMN TO COMPANY")
    print("=" * 60)
    print()

    await add_language_column()

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

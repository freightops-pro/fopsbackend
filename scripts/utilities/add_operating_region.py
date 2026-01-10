"""
Add Operating Region to Company Table

Adds operating_region and regional_data columns to support
region-specific requirements and compliance.

Run: python -m scripts.utilities.add_operating_region
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


async def add_operating_region_columns():
    """Add operating_region and regional_data columns to company table."""

    async with AsyncSessionFactory() as db:
        print("Checking for operating region columns...")

        # Check if columns already exist
        check_sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'company'
        AND column_name IN ('operating_region', 'regional_data')
        """

        result = await db.execute(text(check_sql))
        existing_columns = {row[0] for row in result.fetchall()}

        columns_to_add = []

        if 'operating_region' not in existing_columns:
            columns_to_add.append(
                "ALTER TABLE company ADD COLUMN operating_region VARCHAR DEFAULT 'usa'"
            )

        if 'regional_data' not in existing_columns:
            # JSONB for PostgreSQL to store region-specific data
            columns_to_add.append(
                "ALTER TABLE company ADD COLUMN regional_data JSONB DEFAULT '{}'"
            )

        if not columns_to_add:
            print("All operating region columns already exist!")
            return

        print(f"Adding {len(columns_to_add)} operating region columns...")

        for sql in columns_to_add:
            await db.execute(text(sql))
            print(f"  * Added column")

        await db.commit()

        print("SUCCESS: Added operating region columns to company table")
        print()
        print("New fields:")
        print("  operating_region: Stores the company's operating region/country")
        print("  regional_data:    Stores region-specific field values (JSON)")
        print()
        print("Supported regions:")
        print("  North America:  usa, canada, mexico")
        print("  Europe:         eu, uk, germany, france, poland, netherlands, spain, italy")
        print("  Middle East:    uae, saudi_arabia")
        print("  Asia-Pacific:   china, india, japan, south_korea, australia")
        print("  South America:  brazil, argentina")


async def main():
    """Main entry point."""
    print("=" * 70)
    print("ADD OPERATING REGION SUPPORT")
    print("=" * 70)
    print()

    await add_operating_region_columns()

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

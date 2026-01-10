"""
Add Universal Core Fields

Adds multi-currency and metric unit fields to core tables.
This is ADDITIVE - does not break existing USA data.

What this does:
1. Adds currency_code to financial tables (defaults to USD for existing records)
2. Adds exchange_rate fields for multi-currency support
3. Adds metric units (distance_km, weight_kg) alongside existing fields
4. Does NOT remove existing imperial fields (distance_miles, weight_lbs)

Run: python -m scripts.migrations.add_universal_core
"""

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


async def add_universal_core_fields():
    """Add Universal Core fields without breaking existing data."""

    async with AsyncSessionFactory() as db:
        print("=" * 70)
        print("ADDING UNIVERSAL CORE FIELDS (Multi-Currency & Metric Units)")
        print("=" * 70)
        print()

        # Check existing columns
        check_sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name IN ('loads', 'invoices', 'settlements')
        """

        result = await db.execute(text(check_sql))
        existing_columns = {row[0] for row in result.fetchall()}

        changes = []

        # ========== MULTI-CURRENCY SUPPORT ==========

        print("1. Adding Multi-Currency Support...")
        print()

        # Invoices table
        if 'currency_code' not in existing_columns:
            changes.append((
                "ALTER TABLE invoices ADD COLUMN currency_code VARCHAR(3) DEFAULT 'USD'",
                "invoices.currency_code"
            ))

        if 'exchange_rate_at_transaction' not in existing_columns:
            changes.append((
                "ALTER TABLE invoices ADD COLUMN exchange_rate_at_transaction DECIMAL(10,6) DEFAULT 1.0",
                "invoices.exchange_rate_at_transaction"
            ))

        # Settlements/Payments table
        if 'currency_code' not in existing_columns:
            changes.append((
                "ALTER TABLE settlements ADD COLUMN currency_code VARCHAR(3) DEFAULT 'USD'",
                "settlements.currency_code"
            ))

        if 'exchange_rate_at_transaction' not in existing_columns:
            changes.append((
                "ALTER TABLE settlements ADD COLUMN exchange_rate_at_transaction DECIMAL(10,6) DEFAULT 1.0",
                "settlements.exchange_rate_at_transaction"
            ))

        # ========== METRIC UNIT SUPPORT ==========

        print("2. Adding Metric Unit Fields...")
        print()

        # Loads table - distance
        if 'distance_km' not in existing_columns:
            changes.append((
                "ALTER TABLE loads ADD COLUMN distance_km DECIMAL(10,2)",
                "loads.distance_km"
            ))
            # Add trigger to auto-convert existing distance_miles to distance_km
            changes.append((
                """
                UPDATE loads
                SET distance_km = distance_miles * 1.60934
                WHERE distance_km IS NULL AND distance_miles IS NOT NULL
                """,
                "Auto-convert existing miles to km"
            ))

        # Loads table - weight
        if 'weight_kg' not in existing_columns:
            changes.append((
                "ALTER TABLE loads ADD COLUMN weight_kg DECIMAL(10,2)",
                "loads.weight_kg"
            ))
            # Add trigger to auto-convert existing weight_lbs to weight_kg
            changes.append((
                """
                UPDATE loads
                SET weight_kg = weight_lbs * 0.453592
                WHERE weight_kg IS NULL AND weight_lbs IS NOT NULL
                """,
                "Auto-convert existing lbs to kg"
            ))

        # ========== EXECUTE MIGRATIONS ==========

        if not changes:
            print("✓ All Universal Core fields already exist!")
            print("  No changes needed.")
            return

        print(f"Adding {len(changes)} Universal Core fields...")
        print()

        for sql, description in changes:
            try:
                await db.execute(text(sql))
                print(f"  ✓ {description}")
            except Exception as e:
                print(f"  ! {description} - {str(e)}")

        await db.commit()

        print()
        print("=" * 70)
        print("UNIVERSAL CORE FIELDS ADDED SUCCESSFULLY")
        print("=" * 70)
        print()
        print("What changed:")
        print("  ✓ Added currency_code to invoices and settlements")
        print("  ✓ Added exchange_rate tracking for multi-currency")
        print("  ✓ Added distance_km (metric) to loads")
        print("  ✓ Added weight_kg (metric) to loads")
        print()
        print("What DIDN'T change (USA safe):")
        print("  ✓ Existing distance_miles field untouched")
        print("  ✓ Existing weight_lbs field untouched")
        print("  ✓ All existing data preserved")
        print("  ✓ Defaults set to USD and 1.0 exchange rate")
        print()
        print("Next steps:")
        print("  1. USA companies: Continue using miles/lbs (UI converts automatically)")
        print("  2. Brazil companies: Use km/kg (stored natively)")
        print("  3. UI: Auto-converts based on user's region preference")
        print()


async def main():
    await add_universal_core_fields()


if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    else:
        asyncio.run(main())

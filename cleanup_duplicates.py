"""Script to clean up duplicate equipment records before adding unique constraints."""
import asyncio
import sys
from sqlalchemy import select, text
from app.core.db import AsyncSessionFactory
from app.models.equipment import Equipment

# Fix for Windows event loop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def clean_duplicates():
    async with AsyncSessionFactory() as db:
        # Find duplicate unit numbers within same company
        result = await db.execute(text('''
            SELECT company_id, unit_number, COUNT(*) as cnt
            FROM fleet_equipment
            GROUP BY company_id, unit_number
            HAVING COUNT(*) > 1
        '''))
        duplicates = result.all()
        print(f"Found {len(duplicates)} duplicate unit numbers")

        for company_id, unit_number, count in duplicates:
            print(f"  Company {company_id[:8]}...: unit \"{unit_number}\" x{count}")

            # Get all equipment with this unit number, ordered by created_at
            equip_result = await db.execute(
                select(Equipment)
                .where(Equipment.company_id == company_id, Equipment.unit_number == unit_number)
                .order_by(Equipment.created_at)
            )
            all_equip = equip_result.scalars().all()
            # Keep the first one (oldest), delete the rest
            to_delete = all_equip[1:]
            for eq in to_delete:
                print(f"    Deleting: id={eq.id[:8]}...")
                await db.delete(eq)

        # Now handle VIN duplicates
        vin_result = await db.execute(text('''
            SELECT company_id, vin, COUNT(*) as cnt
            FROM fleet_equipment
            WHERE vin IS NOT NULL AND vin != ''
            GROUP BY company_id, vin
            HAVING COUNT(*) > 1
        '''))
        vin_dups = vin_result.all()
        print(f"Found {len(vin_dups)} duplicate VINs")

        for company_id, vin, count in vin_dups:
            print(f"  Company {company_id[:8]}...: VIN \"{vin}\" x{count}")

            equip_result = await db.execute(
                select(Equipment)
                .where(Equipment.company_id == company_id, Equipment.vin == vin)
                .order_by(Equipment.created_at)
            )
            all_equip = equip_result.scalars().all()
            to_delete = all_equip[1:]
            for eq in to_delete:
                print(f"    Deleting: id={eq.id[:8]}...")
                await db.delete(eq)

        await db.commit()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(clean_duplicates())

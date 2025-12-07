"""Check if there are any drivers in the database"""
import asyncio
import sys
from sqlalchemy import select, text
from app.core.db import AsyncSessionFactory
from app.models.driver import Driver

# Fix Windows event loop issue
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def check_drivers():
    async with AsyncSessionFactory() as session:
        # Count total drivers
        result = await session.execute(text("SELECT COUNT(*) FROM driver"))
        count = result.scalar()
        print(f"Total drivers in database: {count}")

        # Get all drivers
        result = await session.execute(select(Driver))
        drivers = result.scalars().all()

        if drivers:
            print("\nDrivers found:")
            for driver in drivers:
                print(f"  - {driver.first_name} {driver.last_name} (ID: {driver.id}, Company: {driver.company_id})")
        else:
            print("\nNo drivers found in database")

if __name__ == "__main__":
    asyncio.run(check_drivers())

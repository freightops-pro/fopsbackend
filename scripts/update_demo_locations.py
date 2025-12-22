"""
Update Demo Equipment Locations

Adds live GPS location data to existing demo equipment.
Run: python -m scripts.update_demo_locations
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
import random
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionFactory
from app.models.company import Company
from app.models.equipment import Equipment
from app.models.billing import Subscription  # noqa: F401 - needed for SQLAlchemy relationship resolution

# Cities for random locations
CITIES = [
    ("Los Angeles", "CA", 34.0522, -118.2437),
    ("Houston", "TX", 29.7604, -95.3698),
    ("Phoenix", "AZ", 33.4484, -112.0740),
    ("Dallas", "TX", 32.7767, -96.7970),
    ("San Diego", "CA", 32.7157, -117.1611),
    ("Denver", "CO", 39.7392, -104.9903),
    ("Las Vegas", "NV", 36.1699, -115.1398),
    ("Seattle", "WA", 47.6062, -122.3321),
    ("Portland", "OR", 45.5152, -122.6784),
    ("Salt Lake City", "UT", 40.7608, -111.8910),
    ("Albuquerque", "NM", 35.0844, -106.6504),
    ("Tucson", "AZ", 32.2226, -110.9747),
    ("Oklahoma City", "OK", 35.4676, -97.5164),
    ("El Paso", "TX", 31.7619, -106.4850),
    ("Sacramento", "CA", 38.5816, -121.4944),
]


async def update_demo_locations():
    """Update existing demo equipment with live location data."""
    print("\n" + "=" * 60)
    print("UPDATE DEMO EQUIPMENT LOCATIONS")
    print("=" * 60 + "\n")

    async with AsyncSessionFactory() as db:
        try:
            # Find the demo company
            result = await db.execute(
                select(Company).where(Company.name.ilike("%demo%"))
            )
            company = result.scalar_one_or_none()

            if not company:
                print("No demo company found. Run seed_demo_tenant.py first.")
                return

            print(f"Found demo company: {company.name} (ID: {company.id})")

            # Get all tractors/trucks for this company
            result = await db.execute(
                select(Equipment).where(
                    Equipment.company_id == company.id,
                    Equipment.equipment_type.in_(["TRACTOR", "TRUCK"])
                )
            )
            trucks = result.scalars().all()

            if not trucks:
                print("No trucks found in demo company.")
                return

            print(f"Found {len(trucks)} trucks to update")

            now = datetime.now()
            updated = 0

            for truck in trucks:
                # Pick a random city for current location
                city_data = random.choice(CITIES)
                city_name, state, base_lat, base_lng = city_data

                # Add some random offset to spread trucks around (within ~50 miles)
                lat_offset = random.uniform(-0.5, 0.5)
                lng_offset = random.uniform(-0.5, 0.5)

                # Simulate movement - some trucks moving, some parked
                is_moving = random.random() > 0.3  # 70% are moving
                speed = random.uniform(55, 75) if is_moving else 0
                heading = random.uniform(0, 360) if is_moving else None

                # Last update within the past 5 minutes for active tracking
                last_update = now - timedelta(seconds=random.randint(10, 300))

                # Update the truck
                truck.current_lat = base_lat + lat_offset
                truck.current_lng = base_lng + lng_offset
                truck.current_city = city_name
                truck.current_state = state
                truck.last_location_update = last_update
                truck.heading = heading
                truck.speed_mph = speed
                truck.operational_status = "IN_TRANSIT" if is_moving else "IN_SERVICE"

                updated += 1
                print(f"  Updated {truck.unit_number}: {city_name}, {state} "
                      f"({truck.current_lat:.4f}, {truck.current_lng:.4f}) "
                      f"{'Moving' if is_moving else 'Parked'}")

            await db.commit()

            print("\n" + "=" * 60)
            print(f"UPDATED {updated} TRUCKS WITH LIVE LOCATION DATA")
            print("=" * 60 + "\n")

        except Exception as e:
            await db.rollback()
            print(f"\nERROR: {e}")
            raise


if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(update_demo_locations())
        finally:
            loop.close()
    else:
        asyncio.run(update_demo_locations())

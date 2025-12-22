"""
Update Demo Load Stops with GPS Coordinates

Adds lat/lng coordinates to existing demo load stops for map display.
Run: python -m scripts.update_demo_load_stops
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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionFactory
from app.models.company import Company
from app.models.load import Load, LoadStop
from app.models.billing import Subscription  # noqa: F401 - needed for SQLAlchemy relationship resolution

# Major US cities with GPS coordinates (city, state, lat, lng)
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
    ("Memphis", "TN", 35.1495, -90.0490),
    ("Nashville", "TN", 36.1627, -86.7816),
    ("Atlanta", "GA", 33.7490, -84.3880),
    ("Chicago", "IL", 41.8781, -87.6298),
    ("Kansas City", "MO", 39.0997, -94.5786),
    ("Indianapolis", "IN", 39.7684, -86.1581),
    ("Columbus", "OH", 39.9612, -82.9988),
    ("Detroit", "MI", 42.3314, -83.0458),
    ("Minneapolis", "MN", 44.9778, -93.2650),
    ("San Antonio", "TX", 29.4241, -98.4936),
]


def find_city_coords(city_name: str, state: str) -> tuple[float, float] | None:
    """Try to find coordinates for a city by name and state."""
    city_lower = city_name.lower() if city_name else ""
    state_upper = state.upper() if state else ""

    for name, st, lat, lng in CITIES:
        if name.lower() == city_lower and st.upper() == state_upper:
            return (lat, lng)
    return None


def get_random_coords() -> tuple[float, float]:
    """Get random coordinates from one of the major cities."""
    city = random.choice(CITIES)
    # Add small random offset (within ~10 miles)
    lat_offset = random.uniform(-0.1, 0.1)
    lng_offset = random.uniform(-0.1, 0.1)
    return (city[2] + lat_offset, city[3] + lng_offset)


async def update_demo_load_stops():
    """Update existing demo load stops with GPS coordinates."""
    print("\n" + "=" * 60)
    print("UPDATE DEMO LOAD STOPS WITH GPS COORDINATES")
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

            # Get all loads for this company
            result = await db.execute(
                select(Load).where(Load.company_id == company.id)
            )
            loads = result.scalars().all()

            if not loads:
                print("No loads found in demo company.")
                return

            print(f"Found {len(loads)} loads")

            # Get all stops for these loads
            load_ids = [load.id for load in loads]
            result = await db.execute(
                select(LoadStop).where(LoadStop.load_id.in_(load_ids))
            )
            stops = result.scalars().all()

            print(f"Found {len(stops)} stops to update")

            updated = 0
            for stop in stops:
                # Try to match city/state to known coordinates
                coords = None
                if stop.city and stop.state:
                    coords = find_city_coords(stop.city, stop.state)

                if coords:
                    lat, lng = coords
                    # Add small offset to avoid exact same point for multiple stops
                    lat += random.uniform(-0.02, 0.02)
                    lng += random.uniform(-0.02, 0.02)
                else:
                    # Use random coordinates from a major city
                    lat, lng = get_random_coords()

                stop.lat = lat
                stop.lng = lng
                updated += 1

                city_state = f"{stop.city}, {stop.state}" if stop.city and stop.state else "Unknown"
                print(f"  Updated {stop.stop_type} stop: {city_state} -> ({lat:.4f}, {lng:.4f})")

            await db.commit()

            print("\n" + "=" * 60)
            print(f"UPDATED {updated} LOAD STOPS WITH GPS COORDINATES")
            print("=" * 60 + "\n")

        except Exception as e:
            await db.rollback()
            print(f"\nERROR: {e}")
            raise


if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(update_demo_load_stops())
        finally:
            loop.close()
    else:
        asyncio.run(update_demo_load_stops())

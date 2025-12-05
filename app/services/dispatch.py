from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.load import Load, LoadStop
from app.models.driver import Driver
from app.schemas.dispatch import (
    DispatchCalendarEntry,
    DispatchCalendarResponse,
    DispatchFilterOption,
    DispatchFiltersResponse,
    DriverAvailability,
)


class DispatchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _load_with_stops(self, company_id: str) -> List[Load]:
        result = await self.db.execute(
            select(Load)
            .where(Load.company_id == company_id)
            .options(selectinload(Load.stops))
            .order_by(Load.created_at.desc())
        )
        return list(result.scalars().all())

    async def _get_drivers(self, company_id: str) -> dict[str, Driver]:
        """Fetch all drivers for the company and return as a dict keyed by driver_id."""
        result = await self.db.execute(
            select(Driver).where(Driver.company_id == company_id)
        )
        drivers = list(result.scalars().all())
        return {driver.id: driver for driver in drivers}

    def _get_load_driver_id(self, load: Load) -> Optional[str]:
        """Extract driver_id from load metadata."""
        if not load.metadata_json:
            return None
        return load.metadata_json.get("assigned_driver_id")

    def _get_load_reference(self, load: Load) -> str:
        """Get load reference from metadata or use customer name + ID."""
        if load.metadata_json and "reference" in load.metadata_json:
            return str(load.metadata_json["reference"])
        # Generate a reference from customer name and load ID
        customer_prefix = load.customer_name[:4].upper() if load.customer_name else "LOAD"
        return f"{customer_prefix}-{load.id[:8].upper()}"

    async def calendar(self, company_id: str) -> DispatchCalendarResponse:
        loads = await self._load_with_stops(company_id)
        drivers = await self._get_drivers(company_id)

        entries: List[DispatchCalendarEntry] = []
        availability_map: dict[str, DriverAvailability] = {}

        for load in loads:
            driver_id = self._get_load_driver_id(load)
            truck_id = None
            if load.metadata_json:
                truck_id = load.metadata_json.get("assigned_truck_id")

            for stop in load.stops:
                # Use scheduled_at if available, otherwise use created_at
                start_time = stop.scheduled_at
                if start_time is None:
                    start_time = load.created_at
                if start_time is None:
                    start_time = datetime.utcnow()

                # Calculate end_time based on scheduled_at or estimate
                end_time = stop.scheduled_at
                if end_time is None:
                    # Estimate 2 hours for the stop if no scheduled end time
                    end_time = start_time + timedelta(hours=2)
                else:
                    # If scheduled_at exists, add estimated duration
                    end_time = end_time + timedelta(hours=1)

                entries.append(
                    DispatchCalendarEntry(
                        load_id=load.id,
                        stop_id=stop.id,
                        reference=self._get_load_reference(load),
                        customer_name=load.customer_name,
                        driver_id=driver_id,
                        truck_id=truck_id,
                        stop_sequence=stop.sequence,
                        location_name=stop.location_name,
                        city=stop.city,
                        state=stop.state,
                        start_time=start_time,
                        end_time=end_time,
                        status=load.status or "draft",
                        is_pickup=stop.stop_type.lower().startswith("pick") if stop.stop_type else False,
                    )
                )

            # Build driver availability from assigned drivers
            if driver_id and driver_id in drivers:
                driver = drivers[driver_id]
                if driver_id not in availability_map:
                    # Determine driver status based on assignments
                    status = "ASSIGNED" if driver_id else "AVAILABLE"
                    availability_map[driver_id] = DriverAvailability(
                        driver_id=driver.id,
                        driver_name=f"{driver.first_name} {driver.last_name}".strip(),
                        available_from=datetime.utcnow(),
                        available_until=None,
                        status=status,
                    )

        # Also include all drivers (not just assigned ones) for the scheduler
        for driver_id, driver in drivers.items():
            if driver_id not in availability_map:
                availability_map[driver_id] = DriverAvailability(
                    driver_id=driver.id,
                    driver_name=f"{driver.first_name} {driver.last_name}".strip(),
                    available_from=datetime.utcnow(),
                    available_until=None,
                    status="AVAILABLE",
                )

        driver_availability = list(availability_map.values())

        return DispatchCalendarResponse(
            entries=entries,
            driver_availability=driver_availability,
            generated_at=datetime.utcnow(),
        )

    async def filters(self, company_id: str) -> DispatchFiltersResponse:
        loads = await self._load_with_stops(company_id)
        drivers = await self._get_drivers(company_id)

        status_counter: Counter[str] = Counter()
        customer_counter: Counter[str] = Counter()
        driver_counter: Counter[str] = Counter()

        for load in loads:
            # Count statuses
            status = load.status or "draft"
            status_counter[status] += 1

            # Count customers
            customer_counter[load.customer_name] += 1

            # Count drivers
            driver_id = self._get_load_driver_id(load)
            if driver_id and driver_id in drivers:
                driver = drivers[driver_id]
                driver_name = f"{driver.first_name} {driver.last_name}".strip()
                driver_counter[driver_name] += 1

        def to_options(counter: Counter[str]) -> List[DispatchFilterOption]:
            return [
                DispatchFilterOption(label=key, value=key, count=value)
                for key, value in sorted(counter.items(), key=lambda item: item[0])
            ]

        return DispatchFiltersResponse(
            statuses=to_options(status_counter),
            customers=to_options(customer_counter),
            drivers=to_options(driver_counter),
        )



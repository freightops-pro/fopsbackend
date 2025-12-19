from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.equipment import (
    Equipment,
    EquipmentMaintenanceEvent,
    EquipmentMaintenanceForecast,
    EquipmentUsageEvent,
)
from app.schemas.equipment import (
    EquipmentCreate,
    EquipmentLocationUpdate,
    EquipmentMaintenanceCreate,
    EquipmentMaintenanceEventResponse,
    EquipmentMaintenanceForecastResponse,
    EquipmentResponse,
    EquipmentUsageEventCreate,
    EquipmentUsageEventResponse,
    LocationUpdate,
)


DEFAULT_MAINTENANCE_INTERVAL_DAYS = 180
DEFAULT_MAINTENANCE_INTERVAL_MILES = 20000
SOON_THRESHOLD_DAYS = 14
SOON_THRESHOLD_MILES = 1000

SERVICE_INTERVALS: Dict[str, Dict[str, int]] = {
    "PM_A": {"days": 90, "miles": 10000},
    "PM_B": {"days": 180, "miles": 20000},
    "PM_C": {"days": 365, "miles": 40000},
    "OIL_CHANGE": {"days": 120, "miles": 15000},
    "DOT_INSPECTION": {"days": 365, "miles": 0},
}


class EquipmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_equipment(self, company_id: str) -> List[EquipmentResponse]:
        result = await self.db.execute(
            select(Equipment)
            .where(Equipment.company_id == company_id)
            .options(
                selectinload(Equipment.maintenance_events),
                selectinload(Equipment.usage_events),
                selectinload(Equipment.maintenance_forecasts),
            )
            .order_by(Equipment.unit_number)
        )
        equipment_items = result.scalars().unique().all()
        return [EquipmentResponse.model_validate(equipment) for equipment in equipment_items]

    async def create_equipment(self, company_id: str, payload: EquipmentCreate) -> EquipmentResponse:
        # Check for duplicate unit number within company
        existing_unit = await self.db.execute(
            select(Equipment).where(
                Equipment.company_id == company_id,
                Equipment.unit_number == payload.unit_number,
            )
        )
        if existing_unit.scalar_one_or_none():
            raise ValueError(f"Equipment with unit number '{payload.unit_number}' already exists")

        # Check for duplicate VIN within company (only if VIN is provided)
        if payload.vin:
            existing_vin = await self.db.execute(
                select(Equipment).where(
                    Equipment.company_id == company_id,
                    Equipment.vin == payload.vin,
                )
            )
            if existing_vin.scalar_one_or_none():
                raise ValueError(f"Equipment with VIN '{payload.vin}' already exists")

        equipment = Equipment(
            id=str(uuid.uuid4()),
            company_id=company_id,
            unit_number=payload.unit_number,
            equipment_type=payload.equipment_type.upper(),
            status=payload.status,
            operational_status=payload.operational_status,
            make=payload.make,
            model=payload.model,
            year=payload.year,
            vin=payload.vin,
            current_mileage=payload.current_mileage,
            current_engine_hours=payload.current_engine_hours,
            gps_provider=payload.gps_provider,
            gps_device_id=payload.gps_device_id,
            eld_provider=payload.eld_provider,
            eld_device_id=payload.eld_device_id,
            assigned_driver_id=payload.assigned_driver_id,
        )
        self.db.add(equipment)
        await self.db.commit()

        # Expire the object to clear cached state, then re-fetch with eager loading
        # This avoids greenlet error from lazy-loaded relationships
        equipment_id = equipment.id
        self.db.expire(equipment)

        result = await self.db.execute(
            select(Equipment)
            .where(Equipment.id == equipment_id)
            .options(
                selectinload(Equipment.maintenance_events),
                selectinload(Equipment.usage_events),
                selectinload(Equipment.maintenance_forecasts),
            )
        )
        equipment_with_relations = result.scalar_one()
        return EquipmentResponse.model_validate(equipment_with_relations)

    async def log_usage(
        self,
        company_id: str,
        equipment_id: str,
        payload: EquipmentUsageEventCreate,
    ) -> EquipmentUsageEventResponse:
        equipment = await self._get_equipment(company_id, equipment_id)

        usage = EquipmentUsageEvent(
            id=str(uuid.uuid4()),
            company_id=company_id,
            equipment_id=equipment.id,
            recorded_at=payload.recorded_at or datetime.utcnow(),
            odometer=payload.odometer,
            engine_hours=payload.engine_hours,
            source=payload.source or "manual",
            notes=payload.notes,
        )
        self.db.add(usage)

        if payload.odometer is not None:
            equipment.current_mileage = payload.odometer
        if payload.engine_hours is not None:
            equipment.current_engine_hours = payload.engine_hours

        await self.db.flush()
        await self.refresh_forecasts(company_id, equipment_id, commit=False)

        await self.db.commit()
        await self.db.refresh(usage)
        return EquipmentUsageEventResponse.model_validate(usage)

    async def log_maintenance(
        self,
        company_id: str,
        equipment_id: str,
        payload: EquipmentMaintenanceCreate,
    ) -> EquipmentMaintenanceEventResponse:
        equipment = await self._get_equipment(company_id, equipment_id)

        event = EquipmentMaintenanceEvent(
            id=str(uuid.uuid4()),
            company_id=company_id,
            equipment_id=equipment.id,
            service_type=payload.service_type.upper(),
            service_date=payload.service_date,
            vendor=payload.vendor,
            odometer=payload.odometer,
            engine_hours=payload.engine_hours,
            cost=payload.cost,
            notes=payload.notes,
            next_due_date=payload.next_due_date,
            next_due_mileage=payload.next_due_mileage,
            invoice_id=payload.invoice_id,
        )
        self.db.add(event)

        if payload.odometer is not None:
            equipment.current_mileage = payload.odometer
        if payload.engine_hours is not None:
            equipment.current_engine_hours = payload.engine_hours

        await self.db.flush()
        await self.refresh_forecasts(company_id, equipment_id, commit=False)

        await self.db.commit()
        await self.db.refresh(event)
        return EquipmentMaintenanceEventResponse.model_validate(event)

    async def refresh_forecasts(
        self,
        company_id: str,
        equipment_id: str,
        commit: bool = True,
    ) -> List[EquipmentMaintenanceForecastResponse]:
        equipment = await self.db.execute(
            select(Equipment)
            .where(Equipment.company_id == company_id, Equipment.id == equipment_id)
            .options(
                selectinload(Equipment.maintenance_events),
                selectinload(Equipment.usage_events),
            )
        )
        equipment_obj = equipment.scalars().unique().one_or_none()
        if not equipment_obj:
            raise ValueError("Equipment not found")

        maintenance_by_type: Dict[str, EquipmentMaintenanceEvent] = {}
        for event in sorted(equipment_obj.maintenance_events, key=lambda e: e.service_date):
            maintenance_by_type[event.service_type] = event

        usage_events = sorted(equipment_obj.usage_events, key=lambda u: u.recorded_at, reverse=True)[:20]
        avg_daily_miles = self._calculate_avg_daily_miles(usage_events)
        current_mileage = equipment_obj.current_mileage
        if current_mileage is None and usage_events:
            current_mileage = usage_events[0].odometer

        forecasts: List[EquipmentMaintenanceForecast] = []
        for service_type, last_event in maintenance_by_type.items():
            interval = SERVICE_INTERVALS.get(
                service_type.upper(),
                {"days": DEFAULT_MAINTENANCE_INTERVAL_DAYS, "miles": DEFAULT_MAINTENANCE_INTERVAL_MILES},
            )
            proj_date = self._project_date(last_event, interval["days"], avg_daily_miles, current_mileage)
            proj_mileage = self._project_mileage(last_event, interval["miles"])
            status, risk_score, notes = self._determine_status(
                proj_date,
                proj_mileage,
                current_mileage,
                avg_daily_miles,
            )
            confidence = 0.9 if avg_daily_miles is not None else 0.6

            forecast = EquipmentMaintenanceForecast(
                id=str(uuid.uuid4()),
                company_id=company_id,
                equipment_id=equipment_obj.id,
                basis_event_id=last_event.id,
                service_type=service_type,
                status=status,
                projected_service_date=proj_date,
                projected_service_mileage=proj_mileage,
                confidence=confidence,
                risk_score=risk_score,
                notes=notes,
            )
            forecasts.append(forecast)

        # Replace existing forecasts for this equipment
        await self.db.execute(
            delete(EquipmentMaintenanceForecast).where(
                EquipmentMaintenanceForecast.company_id == company_id,
                EquipmentMaintenanceForecast.equipment_id == equipment_obj.id,
            )
        )
        for forecast in forecasts:
            self.db.add(forecast)

        if commit:
            await self.db.commit()
        else:
            await self.db.flush()

        result = await self.db.execute(
            select(EquipmentMaintenanceForecast)
                .where(
                    EquipmentMaintenanceForecast.company_id == company_id,
                    EquipmentMaintenanceForecast.equipment_id == equipment_obj.id,
                )
                .order_by(EquipmentMaintenanceForecast.generated_at.desc())
        )
        persisted = result.scalars().all()
        return [EquipmentMaintenanceForecastResponse.model_validate(item) for item in persisted]

    async def _get_equipment(self, company_id: str, equipment_id: str) -> Equipment:
        result = await self.db.execute(
            select(Equipment).where(Equipment.company_id == company_id, Equipment.id == equipment_id)
        )
        equipment = result.scalar_one_or_none()
        if not equipment:
            raise ValueError("Equipment not found")
        return equipment

    def _calculate_avg_daily_miles(self, usage_events: Sequence[EquipmentUsageEvent]) -> float | None:
        if len(usage_events) < 2:
            return None
        latest = usage_events[0]
        oldest = usage_events[-1]
        if latest.odometer is None or oldest.odometer is None:
            return None
        delta_miles = latest.odometer - oldest.odometer
        if delta_miles <= 0:
            return None
        delta_days = (latest.recorded_at.date() - oldest.recorded_at.date()).days
        if delta_days <= 0:
            return None
        return delta_miles / delta_days

    def _project_date(
        self,
        last_event: EquipmentMaintenanceEvent,
        interval_days: int,
        avg_daily_miles: float | None,
        current_mileage: int | None,
    ) -> date | None:
        if last_event.next_due_date:
            return last_event.next_due_date
        if interval_days <= 0:
            return None
        initial = last_event.service_date + timedelta(days=interval_days)
        if avg_daily_miles and last_event.next_due_mileage and current_mileage is not None:
            miles_remaining = last_event.next_due_mileage - current_mileage
            if miles_remaining > 0:
                days_until = miles_remaining / avg_daily_miles if avg_daily_miles > 0 else None
                if days_until:
                    estimated = datetime.utcnow().date() + timedelta(days=int(days_until))
                    return min(initial, estimated)
        return initial

    def _project_mileage(self, last_event: EquipmentMaintenanceEvent, interval_miles: int) -> int | None:
        if last_event.next_due_mileage:
            return last_event.next_due_mileage
        if interval_miles <= 0:
            return None
        if last_event.odometer is None:
            return None
        return last_event.odometer + interval_miles

    def _determine_status(
        self,
        projected_date: date | None,
        projected_mileage: int | None,
        current_mileage: int | None,
        avg_daily_miles: float | None,
    ) -> tuple[str, float, str]:
        today = datetime.utcnow().date()
        status = "OK"
        risk_score = 0.2
        notes = "On track."

        days_until = None
        if projected_date:
            days_until = (projected_date - today).days
        miles_until = None
        if projected_mileage is not None and current_mileage is not None:
            miles_until = projected_mileage - current_mileage

        if (days_until is not None and days_until <= 0) or (miles_until is not None and miles_until <= 0):
            status = "OVERDUE"
            risk_score = 0.95
            notes = "Service interval exceeded."
        elif (days_until is not None and days_until <= SOON_THRESHOLD_DAYS) or (
            miles_until is not None and miles_until <= SOON_THRESHOLD_MILES
        ):
            status = "DUE_SOON"
            risk_score = 0.65
            notes = "Schedule service soon."
        else:
            if avg_daily_miles:
                notes = f"Projected in {int(days_until or 0)} days at current utilization."

        return status, risk_score, notes

    # ============ Location Tracking Methods ============

    async def update_location(
        self,
        company_id: str,
        equipment_id: str,
        payload: LocationUpdate,
    ) -> EquipmentResponse:
        """Update the live location of a specific equipment unit."""
        equipment = await self._get_equipment(company_id, equipment_id)

        equipment.current_lat = payload.lat
        equipment.current_lng = payload.lng
        equipment.current_city = payload.city
        equipment.current_state = payload.state
        equipment.heading = payload.heading
        equipment.speed_mph = payload.speed_mph
        equipment.last_location_update = datetime.utcnow()

        if payload.odometer is not None:
            equipment.current_mileage = payload.odometer

        await self.db.commit()

        # Refresh with eager loading
        result = await self.db.execute(
            select(Equipment)
            .where(Equipment.id == equipment_id)
            .options(
                selectinload(Equipment.maintenance_events),
                selectinload(Equipment.usage_events),
                selectinload(Equipment.maintenance_forecasts),
            )
        )
        equipment_with_relations = result.scalar_one()
        return EquipmentResponse.model_validate(equipment_with_relations)

    async def bulk_update_locations(
        self,
        company_id: str,
        updates: List[EquipmentLocationUpdate],
    ) -> Dict[str, int]:
        """Bulk update locations for multiple equipment units."""
        updated = 0
        failed = 0

        for update in updates:
            try:
                # Find equipment by ID, unit number, or ELD device ID
                equipment = None
                if update.equipment_id:
                    result = await self.db.execute(
                        select(Equipment).where(
                            Equipment.company_id == company_id,
                            Equipment.id == update.equipment_id,
                        )
                    )
                    equipment = result.scalar_one_or_none()
                elif update.unit_number:
                    result = await self.db.execute(
                        select(Equipment).where(
                            Equipment.company_id == company_id,
                            Equipment.unit_number == update.unit_number,
                        )
                    )
                    equipment = result.scalar_one_or_none()
                elif update.eld_device_id:
                    result = await self.db.execute(
                        select(Equipment).where(
                            Equipment.company_id == company_id,
                            Equipment.eld_device_id == update.eld_device_id,
                        )
                    )
                    equipment = result.scalar_one_or_none()

                if equipment:
                    equipment.current_lat = update.lat
                    equipment.current_lng = update.lng
                    equipment.current_city = update.city
                    equipment.current_state = update.state
                    equipment.heading = update.heading
                    equipment.speed_mph = update.speed_mph
                    equipment.last_location_update = datetime.utcnow()
                    if update.odometer is not None:
                        equipment.current_mileage = update.odometer
                    updated += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        await self.db.commit()
        return {"updated": updated, "failed": failed}

    async def get_equipment_with_locations(self, company_id: str) -> List[EquipmentResponse]:
        """Get all equipment that has live location data."""
        result = await self.db.execute(
            select(Equipment)
            .where(
                Equipment.company_id == company_id,
                Equipment.current_lat.isnot(None),
                Equipment.current_lng.isnot(None),
            )
            .options(
                selectinload(Equipment.maintenance_events),
                selectinload(Equipment.usage_events),
                selectinload(Equipment.maintenance_forecasts),
            )
            .order_by(Equipment.unit_number)
        )
        equipment_items = result.scalars().unique().all()
        return [EquipmentResponse.model_validate(equipment) for equipment in equipment_items]


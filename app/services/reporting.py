from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting import Invoice, LedgerEntry
from app.models.automation import AutomationRule
from app.models.banking import BankingAccount
from app.models.load import Load, LoadStop
from app.models.driver import Driver
from app.models.equipment import Equipment
from app.schemas.reporting import DashboardMetrics
from app.schemas.dashboard import DashboardMetrics as DashboardMetricsV2


class ReportingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def dashboard(self, company_id: str) -> DashboardMetrics:
        total_loads = await self._count(select(func.count()).select_from(Load).where(Load.company_id == company_id))
        loads_in_progress = await self._count(
            select(func.count())
            .select_from(Load)
            .where(Load.company_id == company_id, Load.status.in_(["planned", "in_transit"]))
        )
        total_invoices = await self._count(
            select(func.count()).select_from(Invoice).where(Invoice.company_id == company_id)
        )
        accounts_active = await self._count(
            select(func.count())
            .select_from(BankingAccount)
            .where(BankingAccount.company_id == company_id, BankingAccount.status == "active")
        )
        last_run = await self._last_automation(company_id)
        return DashboardMetrics(
            total_loads=total_loads,
            loads_in_progress=loads_in_progress,
            total_invoices=total_invoices,
            accounts_active=accounts_active,
            last_automation_run=last_run,
        )

    async def _count(self, stmt) -> int:
        result = await self.db.execute(stmt)
        return int(result.scalar() or 0)

    async def _last_automation(self, company_id: str):
        result = await self.db.execute(
            select(func.max(AutomationRule.last_triggered_at)).where(AutomationRule.company_id == company_id)
        )
        value = result.scalar_one_or_none()
        return value.date() if value else None

    async def dashboard_metrics(self, company_id: str) -> DashboardMetricsV2:
        """Calculate comprehensive dashboard metrics."""
        # Fleet metrics
        equipment_result = await self.db.execute(
            select(Equipment).where(Equipment.company_id == company_id)
        )
        equipment = list(equipment_result.scalars().all())
        
        active_trucks = sum(1 for e in equipment if 
                           e.equipment_type and "TRACTOR" in e.equipment_type.upper() and
                           (e.status == "ACTIVE" or e.operational_status == "IN_SERVICE"))
        
        operational_trailers = sum(1 for e in equipment if
                                 e.equipment_type and "TRAILER" in e.equipment_type.upper() and
                                 (e.status == "ACTIVE" or e.operational_status == "IN_SERVICE"))
        
        # Get drivers from calendar/dispatch
        drivers_result = await self.db.execute(
            select(Driver).where(Driver.company_id == company_id)
        )
        drivers = list(drivers_result.scalars().all())
        drivers_dispatched = len([d for d in drivers if d.id])  # Simplified - would need load assignments
        
        # Dispatch metrics
        loads_result = await self.db.execute(
            select(Load).where(Load.company_id == company_id)
        )
        loads = list(loads_result.scalars().all())
        
        loads_in_progress = sum(1 for l in loads if l.status and l.status.upper() in ["IN_PROGRESS", "PICKUP", "IN_TRANSIT"])
        loads_at_pickup = sum(1 for l in loads if l.status and l.status.upper() == "PICKUP")
        
        # Calculate delayed legs
        now = datetime.utcnow()
        stops_result = await self.db.execute(
            select(LoadStop).join(Load).where(Load.company_id == company_id)
        )
        stops = list(stops_result.scalars().all())
        delayed_legs = sum(1 for s in stops if s.scheduled_at and s.scheduled_at < now)
        
        # Calculate rate per mile
        import json
        loads_with_rate = []
        for l in loads:
            if not l.metadata_json:
                continue
            try:
                if isinstance(l.metadata_json, str):
                    metadata = json.loads(l.metadata_json)
                else:
                    metadata = l.metadata_json
                if metadata.get("base_rate") and metadata.get("total_miles"):
                    loads_with_rate.append(metadata)
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue
        
        total_miles = 0.0
        if loads_with_rate:
            total_revenue = sum(float(m.get("base_rate", 0)) for m in loads_with_rate)
            total_miles = sum(float(m.get("total_miles", 0)) for m in loads_with_rate)
            rate_per_mile = total_revenue / total_miles if total_miles > 0 else 0.0
        else:
            rate_per_mile = 0.0
        
        # Accounting metrics
        invoices_result = await self.db.execute(
            select(Invoice).where(Invoice.company_id == company_id)
        )
        invoices = list(invoices_result.scalars().all())
        
        invoices_pending = sum(1 for inv in invoices if 
                              inv.status and inv.status.upper() in ["PENDING", "SENT", "OVERDUE"])
        
        outstanding_amount = sum(float(inv.total or 0) for inv in invoices if
                                inv.status and inv.status.upper() in ["PENDING", "SENT", "OVERDUE"])
        
        # Calculate fuel cost per mile from ledger
        fuel_entries_result = await self.db.execute(
            select(LedgerEntry).where(
                LedgerEntry.company_id == company_id,
                LedgerEntry.category == "expense"
            )
        )
        fuel_entries = list(fuel_entries_result.scalars().all())
        fuel_cost = sum(float(e.amount or 0) for e in fuel_entries)
        fuel_cost_per_mile = fuel_cost / total_miles if total_miles > 0 else 0.0

        # === CHART DATA ===

        # Revenue Trend (Last 4 weeks)
        revenue_trend = []
        for i in range(4):
            week_start = now - timedelta(days=(4-i)*7)
            week_end = week_start + timedelta(days=7)

            week_loads = [l for l in loads if
                         l.status and l.status.upper() in ["DELIVERED", "COMPLETED"] and
                         l.created_at and week_start <= l.created_at < week_end]

            week_revenue = 0.0
            for l in week_loads:
                if l.metadata_json:
                    try:
                        import json
                        if isinstance(l.metadata_json, str):
                            metadata = json.loads(l.metadata_json)
                        else:
                            metadata = l.metadata_json
                        week_revenue += float(metadata.get("base_rate", 0))
                    except:
                        pass

            from app.schemas.dashboard import ChartDataPoint
            revenue_trend.append(ChartDataPoint(name=f"Week {i+1}", value=round(week_revenue, 2)))

        # Load Volume (Last 5 days)
        load_volume = []
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']

        for i in range(5):
            day_start = now - timedelta(days=5-i)
            day_end = day_start + timedelta(days=1)

            completed = sum(1 for l in loads if
                          l.status and l.status.upper() in ["DELIVERED", "COMPLETED"] and
                          l.created_at and day_start <= l.created_at < day_end)

            in_progress = sum(1 for l in loads if
                            l.status and l.status.upper() in ["IN_PROGRESS", "PICKUP", "IN_TRANSIT"] and
                            l.created_at and l.created_at < day_end)

            pending = sum(1 for l in loads if
                        l.status and l.status.upper() in ["PENDING", "DISPATCHED"] and
                        l.created_at and day_start <= l.created_at < day_end)

            load_volume.append(ChartDataPoint(
                name=days[i] if i < len(days) else f"Day {i+1}",
                completed=completed,
                inProgress=in_progress,
                pending=pending
            ))

        # Equipment Utilization
        total_trucks = sum(1 for e in equipment if
                          e.equipment_type and "TRACTOR" in e.equipment_type.upper())
        total_trailers = sum(1 for e in equipment if
                            e.equipment_type and "TRAILER" in e.equipment_type.upper())
        total_drivers = len(drivers)

        truck_utilization = int((active_trucks / total_trucks) * 100) if total_trucks > 0 else 0
        trailer_utilization = int((operational_trailers / total_trailers) * 100) if total_trailers > 0 else 0
        driver_utilization = int((drivers_dispatched / total_drivers) * 100) if total_drivers > 0 else 0

        utilization_data = [
            ChartDataPoint(name="Trucks", utilization=truck_utilization, target=85),
            ChartDataPoint(name="Trailers", utilization=trailer_utilization, target=80),
            ChartDataPoint(name="Drivers", utilization=driver_utilization, target=85)
        ]

        from app.schemas.dashboard import (
            DashboardFleetMetrics,
            DashboardDispatchMetrics,
            DashboardAccountingMetrics,
            DashboardChartsData,
        )

        return DashboardMetricsV2(
            fleet=DashboardFleetMetrics(
                activeTrucks=active_trucks,
                operationalTrailers=operational_trailers,
                driversDispatched=drivers_dispatched,
            ),
            dispatch=DashboardDispatchMetrics(
                loadsInProgress=loads_in_progress,
                loadsAtPickup=loads_at_pickup,
                delayedLegs=delayed_legs,
                avgPickupCompliance=0.0,  # Would need geofence data
                avgPickupTimeMinutes=0.0,  # Would need geofence data
                ratePerMile=rate_per_mile,
            ),
            accounting=DashboardAccountingMetrics(
                invoicesPending=invoices_pending,
                outstandingAmount=outstanding_amount,
                fuelCostPerMile=fuel_cost_per_mile,
            ),
            charts=DashboardChartsData(
                revenueTrend=revenue_trend,
                loadVolume=load_volume,
                utilization=utilization_data
            ),
        )


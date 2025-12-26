"""Service for driver settlements operations."""

import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting import Settlement
from app.models.driver import Driver
from app.models.load import Load
from app.schemas.settlements import (
    SettlementResponse,
    SettlementBreakdownItem,
    CurrentWeekSettlementResponse,
    PayStubResponse,
    WeekSummaryResponse,
)

logger = logging.getLogger(__name__)


class SettlementsService:
    """Service for managing driver settlements."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _get_week_bounds(self, target_date: Optional[date] = None) -> Tuple[date, date]:
        """Get the start (Monday) and end (Sunday) of the week."""
        if target_date is None:
            target_date = date.today()

        # Get Monday of the week
        days_since_monday = target_date.weekday()
        week_start = target_date - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)

        return week_start, week_end

    async def get_current_week_settlement(
        self, driver_id: str, company_id: str
    ) -> CurrentWeekSettlementResponse:
        """Get the current week's settlement progress for a driver."""
        week_start, week_end = self._get_week_bounds()

        # Get completed loads for this week
        completed_loads_query = select(Load).where(
            and_(
                Load.company_id == company_id,
                Load.driver_id == driver_id,
                Load.status.in_(["delivered", "completed"]),
                Load.delivery_date >= week_start,
                Load.delivery_date <= week_end,
            )
        )
        completed_result = await self.db.execute(completed_loads_query)
        completed_loads = completed_result.scalars().all()

        # Get assigned loads (pending)
        assigned_loads_query = select(Load).where(
            and_(
                Load.company_id == company_id,
                Load.driver_id == driver_id,
                Load.status.in_(["assigned", "dispatched", "in_transit", "at_pickup", "at_delivery"]),
            )
        )
        assigned_result = await self.db.execute(assigned_loads_query)
        assigned_loads = assigned_result.scalars().all()

        # Calculate earnings from completed loads
        earnings_breakdown = []
        gross_earnings = Decimal("0.00")
        total_miles = Decimal("0.00")

        for load in completed_loads:
            # Calculate driver pay (example: percentage of load revenue or per-mile rate)
            load_pay = Decimal(str(load.driver_pay or 0))
            if load_pay == 0 and load.total_miles:
                # Default rate of $0.55/mile if no driver_pay set
                load_pay = Decimal(str(load.total_miles)) * Decimal("0.55")

            gross_earnings += load_pay
            total_miles += Decimal(str(load.total_miles or 0))

            earnings_breakdown.append(
                SettlementBreakdownItem(
                    description=f"Load {load.reference_number or load.id[:8]}",
                    category="earnings",
                    amount=load_pay,
                    load_id=load.id,
                    load_reference=load.reference_number,
                )
            )

        # Calculate projected earnings from assigned loads
        projected_earnings = gross_earnings
        for load in assigned_loads:
            load_pay = Decimal(str(load.driver_pay or 0))
            if load_pay == 0 and load.total_miles:
                load_pay = Decimal(str(load.total_miles)) * Decimal("0.55")
            projected_earnings += load_pay

        # Get standard deductions (fuel advances, etc.)
        # This would typically come from a deductions table
        deductions_breakdown = []
        total_deductions = Decimal("0.00")

        return CurrentWeekSettlementResponse(
            driver_id=driver_id,
            week_start=week_start,
            week_end=week_end,
            status="in_progress",
            gross_earnings=gross_earnings,
            projected_earnings=projected_earnings,
            total_deductions=total_deductions,
            net_pay=gross_earnings - total_deductions,
            completed_loads=len(completed_loads),
            assigned_loads=len(assigned_loads),
            total_miles=total_miles,
            earnings_breakdown=earnings_breakdown,
            deductions_breakdown=deductions_breakdown,
        )

    async def get_settlement_history(
        self, driver_id: str, company_id: str, limit: int = 10, offset: int = 0
    ) -> Tuple[List[SettlementResponse], int]:
        """Get historical settlements for a driver."""
        # Query settlements from accounting_settlement table
        query = (
            select(Settlement)
            .where(
                and_(
                    Settlement.company_id == company_id,
                    Settlement.driver_id == driver_id,
                )
            )
            .order_by(Settlement.settlement_date.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db.execute(query)
        settlements = result.scalars().all()

        # Get total count
        count_query = select(func.count(Settlement.id)).where(
            and_(
                Settlement.company_id == company_id,
                Settlement.driver_id == driver_id,
            )
        )
        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar() or 0

        # Convert to response models
        settlement_responses = []
        for s in settlements:
            # Parse breakdown from JSON
            breakdown_items = []
            if s.breakdown:
                for item in s.breakdown.get("items", []):
                    breakdown_items.append(
                        SettlementBreakdownItem(
                            description=item.get("description", ""),
                            category=item.get("category", "earnings"),
                            amount=Decimal(str(item.get("amount", 0))),
                            load_id=item.get("load_id"),
                            load_reference=item.get("load_reference"),
                        )
                    )

            # Calculate period (assuming weekly settlements, use settlement_date as period end)
            period_end = s.settlement_date
            period_start = period_end - timedelta(days=6)

            settlement_responses.append(
                SettlementResponse(
                    id=s.id,
                    driver_id=s.driver_id,
                    period_start=period_start,
                    period_end=period_end,
                    status=s.metadata_json.get("status", "paid") if s.metadata_json else "paid",
                    gross_earnings=s.total_earnings,
                    total_deductions=s.total_deductions,
                    net_pay=s.net_pay,
                    total_miles=Decimal(str(s.breakdown.get("total_miles", 0))) if s.breakdown else Decimal("0.00"),
                    total_loads=s.breakdown.get("total_loads", 0) if s.breakdown else 0,
                    breakdown=breakdown_items,
                    created_at=s.created_at,
                    paid_at=s.metadata_json.get("paid_at") if s.metadata_json else None,
                )
            )

        return settlement_responses, total_count

    async def get_pay_stubs(
        self, driver_id: str, company_id: str, limit: int = 10
    ) -> List[PayStubResponse]:
        """Get pay stubs for a driver (derived from settlements)."""
        settlements, _ = await self.get_settlement_history(
            driver_id, company_id, limit=limit
        )

        pay_stubs = []
        for s in settlements:
            pay_stubs.append(
                PayStubResponse(
                    id=f"ps_{s.id}",
                    driver_id=s.driver_id,
                    settlement_id=s.id,
                    period_start=s.period_start,
                    period_end=s.period_end,
                    pay_date=s.period_end + timedelta(days=3),  # Typical pay delay
                    gross_pay=s.gross_earnings,
                    total_deductions=s.total_deductions,
                    net_pay=s.net_pay,
                    total_loads=s.total_loads,
                    total_miles=s.total_miles,
                    download_url=f"/api/settlements/paystubs/{s.id}/download",
                    pdf_generated=True,
                    created_at=s.created_at,
                )
            )

        return pay_stubs

    async def get_week_summary(
        self, driver_id: str, company_id: str
    ) -> WeekSummaryResponse:
        """Get weekly summary for driver dashboard."""
        current = await self.get_current_week_settlement(driver_id, company_id)

        # Get last week's data for comparison
        last_week_start, last_week_end = self._get_week_bounds(
            date.today() - timedelta(days=7)
        )

        last_week_query = select(Load).where(
            and_(
                Load.company_id == company_id,
                Load.driver_id == driver_id,
                Load.status.in_(["delivered", "completed"]),
                Load.delivery_date >= last_week_start,
                Load.delivery_date <= last_week_end,
            )
        )
        last_week_result = await self.db.execute(last_week_query)
        last_week_loads = last_week_result.scalars().all()

        last_week_earnings = Decimal("0.00")
        for load in last_week_loads:
            load_pay = Decimal(str(load.driver_pay or 0))
            if load_pay == 0 and load.total_miles:
                load_pay = Decimal(str(load.total_miles)) * Decimal("0.55")
            last_week_earnings += load_pay

        # Calculate percentage change
        vs_last_week = 0.0
        if last_week_earnings > 0:
            vs_last_week = float(
                ((current.gross_earnings - last_week_earnings) / last_week_earnings) * 100
            )

        # Calculate completion percentage
        total_loads = current.completed_loads + current.assigned_loads
        completion_percentage = 0.0
        if total_loads > 0:
            completion_percentage = (current.completed_loads / total_loads) * 100

        return WeekSummaryResponse(
            driver_id=driver_id,
            week_start=current.week_start,
            week_end=current.week_end,
            current_earnings=current.gross_earnings,
            projected_total=current.projected_earnings,
            completed_loads=current.completed_loads,
            pending_loads=current.assigned_loads,
            completion_percentage=completion_percentage,
            vs_last_week=vs_last_week,
            vs_average=0.0,  # Would need more historical data
        )

    async def generate_pay_stub_pdf(
        self, settlement_id: str, driver_id: str, company_id: str
    ) -> Optional[bytes]:
        """Generate PDF for a pay stub. Returns PDF bytes or None if not found."""
        # Query the settlement
        query = select(Settlement).where(
            and_(
                Settlement.id == settlement_id,
                Settlement.company_id == company_id,
                Settlement.driver_id == driver_id,
            )
        )
        result = await self.db.execute(query)
        settlement = result.scalar_one_or_none()

        if not settlement:
            return None

        # Get driver info
        driver_query = select(Driver).where(Driver.id == driver_id)
        driver_result = await self.db.execute(driver_query)
        driver = driver_result.scalar_one_or_none()

        # Generate a simple text-based receipt (in production, use a proper PDF library)
        # For now, return a placeholder - would integrate with reportlab or weasyprint
        logger.info(f"Generating pay stub PDF for settlement {settlement_id}")

        # Return None to indicate PDF generation not yet implemented
        # In production, this would return actual PDF bytes
        return None

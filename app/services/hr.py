from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver import Driver
from app.models.accounting import Settlement


class HRService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def payroll_summary(self, company_id: str) -> dict:
        """Get payroll summary for the company."""
        # Count total employees (drivers)
        drivers_result = await self.db.execute(
            select(func.count(Driver.id)).where(Driver.company_id == company_id)
        )
        total_employees = int(drivers_result.scalar() or 0)
        
        # Get settlements for current period
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        settlements_result = await self.db.execute(
            select(Settlement).where(
                Settlement.company_id == company_id,
                Settlement.created_at >= month_start
            )
        )
        settlements = list(settlements_result.scalars().all())
        
        total_payroll = sum(float(s.net_pay or 0) for s in settlements)
        taxes_withheld = total_payroll * 0.15  # Simplified - would need actual tax calculation
        benefits_cost = total_payroll * 0.10  # Simplified - would need actual benefits data
        w2s_generated = len(settlements)  # Simplified
        
        # Quarterly taxes (simplified)
        quarter_start = month_start - timedelta(days=90)
        quarterly_settlements_result = await self.db.execute(
            select(Settlement).where(
                Settlement.company_id == company_id,
                Settlement.created_at >= quarter_start
            )
        )
        quarterly_settlements = list(quarterly_settlements_result.scalars().all())
        quarterly_payroll = sum(float(s.net_pay or 0) for s in quarterly_settlements)
        quarterly_taxes = quarterly_payroll * 0.15  # Simplified
        
        # Calculate next payroll date (simplified - next Friday)
        days_until_friday = (4 - now.weekday()) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        next_payroll = (now + timedelta(days=days_until_friday)).date().isoformat()
        
        # Last processed
        if settlements:
            last_settlement = max(settlements, key=lambda s: s.created_at)
            last_processed = last_settlement.created_at.date().isoformat()
        else:
            last_processed = None
        
        return {
            "totalPayroll": total_payroll,
            "totalEmployees": total_employees,
            "taxesWithheld": taxes_withheld,
            "benefitsCost": benefits_cost,
            "w2sGenerated": w2s_generated,
            "quarterlyTaxes": quarterly_taxes,
            "upcomingPayroll": next_payroll,
            "lastProcessed": last_processed,
        }


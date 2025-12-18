"""
Demurrage and Per Diem Calculation Service.

Calculates demurrage (port storage) and per diem (container rental) charges
based on port data and container events.

Key terms:
- Demurrage: Port/terminal storage charges after free time expires
- Per Diem: Container rental charges from carrier
- LFD (Last Free Day): Last day container can sit without charges
- Free Time: Days allowed at port before charges start
"""

import logging
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ChargeType(str, Enum):
    """Types of drayage charges."""
    DEMURRAGE = "DEMURRAGE"  # Port storage
    PER_DIEM = "PER_DIEM"    # Container rental
    DETENTION = "DETENTION"   # Chassis rental


@dataclass
class FreeTimeRules:
    """Free time rules for a port/terminal."""
    port_free_days: int = 4
    detention_free_days: int = 4
    per_diem_free_days: int = 4
    weekend_counts: bool = False
    holiday_counts: bool = False

    demurrage_rates: Dict[str, float] = field(default_factory=lambda: {
        "days_1_5": 150.00,
        "days_6_10": 250.00,
        "days_11_plus": 350.00,
    })

    per_diem_rates: Dict[str, float] = field(default_factory=lambda: {
        "days_1_4": 0.00,
        "days_5_10": 75.00,
        "days_11_plus": 150.00,
    })


@dataclass
class DemurrageCalculation:
    """Result of demurrage/per diem calculation."""
    container_number: str
    port_code: Optional[str] = None

    # Key dates
    discharge_date: Optional[datetime] = None
    last_free_day: Optional[datetime] = None
    outgate_date: Optional[datetime] = None
    empty_return_date: Optional[datetime] = None

    # Demurrage (port storage)
    demurrage_days: int = 0
    demurrage_amount: float = 0.0

    # Per diem (container rental)
    per_diem_days: int = 0
    per_diem_amount: float = 0.0

    # Detention (chassis)
    detention_days: int = 0
    detention_amount: float = 0.0

    # Total
    total_amount: float = 0.0

    # Status
    is_incurring_charges: bool = False
    days_until_lfd: Optional[int] = None
    warning_level: str = "none"  # none, warning (3 days), urgent (1 day), overdue

    # Breakdown by tier
    demurrage_breakdown: List[Dict] = field(default_factory=list)
    per_diem_breakdown: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "container_number": self.container_number,
            "port_code": self.port_code,
            "discharge_date": self.discharge_date.isoformat() if self.discharge_date else None,
            "last_free_day": self.last_free_day.isoformat() if self.last_free_day else None,
            "outgate_date": self.outgate_date.isoformat() if self.outgate_date else None,
            "empty_return_date": self.empty_return_date.isoformat() if self.empty_return_date else None,
            "demurrage_days": self.demurrage_days,
            "demurrage_amount": self.demurrage_amount,
            "per_diem_days": self.per_diem_days,
            "per_diem_amount": self.per_diem_amount,
            "detention_days": self.detention_days,
            "detention_amount": self.detention_amount,
            "total_amount": self.total_amount,
            "is_incurring_charges": self.is_incurring_charges,
            "days_until_lfd": self.days_until_lfd,
            "warning_level": self.warning_level,
            "demurrage_breakdown": self.demurrage_breakdown,
            "per_diem_breakdown": self.per_diem_breakdown,
        }


# Default free time rules by port
PORT_FREE_TIME_RULES: Dict[str, FreeTimeRules] = {
    "USHOU": FreeTimeRules(port_free_days=4, weekend_counts=False),
    "USLAX": FreeTimeRules(port_free_days=4, weekend_counts=False),
    "USLGB": FreeTimeRules(port_free_days=4, weekend_counts=False),
    "USNYC": FreeTimeRules(port_free_days=4, weekend_counts=False),
    "USEWR": FreeTimeRules(port_free_days=4, weekend_counts=False),
    "USSAV": FreeTimeRules(port_free_days=5, weekend_counts=False),
}


class DemurrageService:
    """
    Service for calculating demurrage and per diem charges.

    Uses port data for calculations since port terminals track:
    - Container discharge date
    - Last Free Day
    - Current demurrage accrued
    - Hold status affecting free time

    Usage:
        service = DemurrageService()
        calc = await service.calculate_charges(
            container_number="MAEU1234567",
            port_code="USHOU",
            discharge_date=datetime(2024, 1, 15),
        )
        print(f"Total charges: ${calc.total_amount}")
    """

    # US Federal Holidays
    US_HOLIDAYS_2024 = [
        date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19),
        date(2024, 5, 27), date(2024, 6, 19), date(2024, 7, 4),
        date(2024, 9, 2), date(2024, 10, 14), date(2024, 11, 11),
        date(2024, 11, 28), date(2024, 12, 25),
    ]

    US_HOLIDAYS_2025 = [
        date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17),
        date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4),
        date(2025, 9, 1), date(2025, 10, 13), date(2025, 11, 11),
        date(2025, 11, 27), date(2025, 12, 25),
    ]

    def __init__(self):
        self.holidays = set(self.US_HOLIDAYS_2024 + self.US_HOLIDAYS_2025)

    def get_free_time_rules(self, port_code: str) -> FreeTimeRules:
        """Get free time rules for a port."""
        return PORT_FREE_TIME_RULES.get(port_code.upper(), FreeTimeRules())

    def calculate_last_free_day(
        self,
        discharge_date: datetime,
        free_days: int,
        weekend_counts: bool = False,
        holiday_counts: bool = False,
    ) -> datetime:
        """Calculate Last Free Day from discharge date."""
        current_date = discharge_date.date()
        days_counted = 0

        while days_counted < free_days:
            current_date += timedelta(days=1)

            if not weekend_counts and current_date.weekday() >= 5:
                continue

            if not holiday_counts and current_date in self.holidays:
                continue

            days_counted += 1

        return datetime.combine(current_date, datetime.min.time())

    def count_chargeable_days(
        self,
        start_date: datetime,
        end_date: datetime,
        weekend_counts: bool = False,
        holiday_counts: bool = False,
    ) -> int:
        """Count chargeable days between two dates."""
        if end_date <= start_date:
            return 0

        current_date = start_date.date()
        end = end_date.date()
        days = 0

        while current_date <= end:
            is_weekend = current_date.weekday() >= 5
            is_holiday = current_date in self.holidays

            if is_weekend and not weekend_counts:
                pass
            elif is_holiday and not holiday_counts:
                pass
            else:
                days += 1

            current_date += timedelta(days=1)

        return days

    def calculate_tiered_charges(
        self,
        days: int,
        rates: Dict[str, float],
    ) -> tuple[float, List[Dict]]:
        """Calculate charges using tiered rate structure."""
        if days <= 0:
            return 0.0, []

        total = 0.0
        breakdown = []

        tier1_rate = rates.get("days_1_5", rates.get("days_1_4", 0))
        tier2_rate = rates.get("days_6_10", rates.get("days_5_10", 0))
        tier3_rate = rates.get("days_11_plus", 0)

        # Tier 1 (days 1-5)
        tier1_days = min(days, 5)
        if tier1_days > 0 and tier1_rate > 0:
            tier1_amount = tier1_days * tier1_rate
            total += tier1_amount
            breakdown.append({
                "tier": 1,
                "days": tier1_days,
                "rate": tier1_rate,
                "amount": tier1_amount,
                "description": f"Days 1-5: {tier1_days} days @ ${tier1_rate}/day",
            })

        # Tier 2 (days 6-10)
        if days > 5:
            tier2_days = min(days - 5, 5)
            if tier2_days > 0 and tier2_rate > 0:
                tier2_amount = tier2_days * tier2_rate
                total += tier2_amount
                breakdown.append({
                    "tier": 2,
                    "days": tier2_days,
                    "rate": tier2_rate,
                    "amount": tier2_amount,
                    "description": f"Days 6-10: {tier2_days} days @ ${tier2_rate}/day",
                })

        # Tier 3 (days 11+)
        if days > 10:
            tier3_days = days - 10
            if tier3_days > 0 and tier3_rate > 0:
                tier3_amount = tier3_days * tier3_rate
                total += tier3_amount
                breakdown.append({
                    "tier": 3,
                    "days": tier3_days,
                    "rate": tier3_rate,
                    "amount": tier3_amount,
                    "description": f"Days 11+: {tier3_days} days @ ${tier3_rate}/day",
                })

        return total, breakdown

    async def calculate_charges(
        self,
        container_number: str,
        port_code: str,
        discharge_date: Optional[datetime] = None,
        outgate_date: Optional[datetime] = None,
        empty_return_date: Optional[datetime] = None,
        last_free_day: Optional[datetime] = None,
    ) -> DemurrageCalculation:
        """
        Calculate demurrage and per diem charges for a container.

        Args:
            container_number: Container number
            port_code: Port UN/LOCODE
            discharge_date: Date container was discharged from vessel
            outgate_date: Date container left the port (picked up)
            empty_return_date: Date empty container was returned
            last_free_day: Override LFD if known (from port API)

        Returns:
            DemurrageCalculation with all charge details
        """
        rules = self.get_free_time_rules(port_code)

        calc = DemurrageCalculation(
            container_number=container_number,
            port_code=port_code,
            discharge_date=discharge_date,
            outgate_date=outgate_date,
            empty_return_date=empty_return_date,
        )

        if not discharge_date:
            return calc

        # Calculate LFD if not provided
        if not last_free_day:
            last_free_day = self.calculate_last_free_day(
                discharge_date=discharge_date,
                free_days=rules.port_free_days,
                weekend_counts=rules.weekend_counts,
                holiday_counts=rules.holiday_counts,
            )

        calc.last_free_day = last_free_day

        # Calculate days until LFD
        today = datetime.utcnow()
        if last_free_day > today:
            calc.days_until_lfd = (last_free_day.date() - today.date()).days

            if calc.days_until_lfd <= 1:
                calc.warning_level = "urgent"
            elif calc.days_until_lfd <= 3:
                calc.warning_level = "warning"
            else:
                calc.warning_level = "none"
        else:
            calc.days_until_lfd = -1 * (today.date() - last_free_day.date()).days
            calc.warning_level = "overdue"

        # Calculate DEMURRAGE (port storage)
        demurrage_end = outgate_date or today

        if demurrage_end > last_free_day:
            calc.demurrage_days = self.count_chargeable_days(
                start_date=last_free_day + timedelta(days=1),
                end_date=demurrage_end,
                weekend_counts=rules.weekend_counts,
                holiday_counts=rules.holiday_counts,
            )

            calc.demurrage_amount, calc.demurrage_breakdown = self.calculate_tiered_charges(
                days=calc.demurrage_days,
                rates=rules.demurrage_rates,
            )

        # Calculate PER DIEM (container rental after outgate)
        if outgate_date:
            per_diem_start = self.calculate_last_free_day(
                discharge_date=outgate_date,
                free_days=rules.per_diem_free_days,
                weekend_counts=rules.weekend_counts,
                holiday_counts=rules.holiday_counts,
            )

            per_diem_end = empty_return_date or today

            if per_diem_end > per_diem_start:
                calc.per_diem_days = self.count_chargeable_days(
                    start_date=per_diem_start + timedelta(days=1),
                    end_date=per_diem_end,
                    weekend_counts=rules.weekend_counts,
                    holiday_counts=rules.holiday_counts,
                )

                calc.per_diem_amount, calc.per_diem_breakdown = self.calculate_tiered_charges(
                    days=calc.per_diem_days,
                    rates=rules.per_diem_rates,
                )

        calc.total_amount = calc.demurrage_amount + calc.per_diem_amount + calc.detention_amount
        calc.is_incurring_charges = calc.total_amount > 0

        return calc

    async def calculate_from_container_lookup(
        self,
        container_number: str,
        port_code: Optional[str] = None,
    ) -> DemurrageCalculation:
        """
        Calculate charges by looking up container from port API.

        Args:
            container_number: Container number
            port_code: Optional port code (searches all if not provided)

        Returns:
            DemurrageCalculation
        """
        from app.services.drayage.container_lookup_service import ContainerLookupService

        service = ContainerLookupService()
        result = await service.lookup_container(
            container_number=container_number,
            port_code=port_code,
        )

        if not result.success:
            return DemurrageCalculation(
                container_number=container_number,
                port_code=port_code,
            )

        # If port returned demurrage amount, use it directly
        if result.demurrage_amount is not None:
            calc = DemurrageCalculation(
                container_number=container_number,
                port_code=result.port_code,
                discharge_date=result.discharge_date,
                last_free_day=result.last_free_day,
                outgate_date=result.outgate_date,
                demurrage_amount=result.demurrage_amount,
                per_diem_amount=result.per_diem_amount or 0.0,
            )
            calc.total_amount = calc.demurrage_amount + calc.per_diem_amount
            calc.is_incurring_charges = calc.total_amount > 0

            if result.last_free_day:
                today = datetime.utcnow()
                if result.last_free_day > today:
                    calc.days_until_lfd = (result.last_free_day.date() - today.date()).days
                    calc.warning_level = "urgent" if calc.days_until_lfd <= 1 else (
                        "warning" if calc.days_until_lfd <= 3 else "none"
                    )
                else:
                    calc.days_until_lfd = -1 * (today.date() - result.last_free_day.date()).days
                    calc.warning_level = "overdue"

            return calc

        # Otherwise calculate from dates
        return await self.calculate_charges(
            container_number=container_number,
            port_code=result.port_code or "UNKNOWN",
            discharge_date=result.discharge_date,
            outgate_date=result.outgate_date,
            last_free_day=result.last_free_day,
        )


async def calculate_demurrage(
    container_number: str,
    port_code: str,
    discharge_date: datetime,
    outgate_date: Optional[datetime] = None,
    last_free_day: Optional[datetime] = None,
) -> DemurrageCalculation:
    """Quick demurrage calculation."""
    service = DemurrageService()
    return await service.calculate_charges(
        container_number=container_number,
        port_code=port_code,
        discharge_date=discharge_date,
        outgate_date=outgate_date,
        last_free_day=last_free_day,
    )

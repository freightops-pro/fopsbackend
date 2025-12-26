"""Schemas for driver settlements API."""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


class SettlementBreakdownItem(BaseModel):
    """Individual line item in settlement breakdown."""
    description: str
    category: str  # earnings, deductions, reimbursements
    amount: Decimal
    load_id: Optional[str] = None
    load_reference: Optional[str] = None


class SettlementResponse(BaseModel):
    """Settlement response for driver."""
    id: str
    driver_id: str
    period_start: date
    period_end: date
    status: str = "pending"  # pending, processing, paid

    # Totals
    gross_earnings: Decimal = Field(default=Decimal("0.00"))
    total_deductions: Decimal = Field(default=Decimal("0.00"))
    net_pay: Decimal = Field(default=Decimal("0.00"))

    # Summary stats
    total_miles: Decimal = Field(default=Decimal("0.00"))
    total_loads: int = 0

    # Breakdown
    breakdown: List[SettlementBreakdownItem] = []

    created_at: datetime
    paid_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CurrentWeekSettlementResponse(BaseModel):
    """Current week's settlement progress."""
    driver_id: str
    week_start: date
    week_end: date
    status: str = "in_progress"  # in_progress, pending_review, approved

    # Current totals
    gross_earnings: Decimal = Field(default=Decimal("0.00"))
    projected_earnings: Decimal = Field(default=Decimal("0.00"))
    total_deductions: Decimal = Field(default=Decimal("0.00"))
    net_pay: Decimal = Field(default=Decimal("0.00"))

    # Stats
    completed_loads: int = 0
    assigned_loads: int = 0
    total_miles: Decimal = Field(default=Decimal("0.00"))

    # Breakdown
    earnings_breakdown: List[SettlementBreakdownItem] = []
    deductions_breakdown: List[SettlementBreakdownItem] = []


class PayStubResponse(BaseModel):
    """Pay stub record for driver."""
    id: str
    driver_id: str
    settlement_id: Optional[str] = None

    # Period
    period_start: date
    period_end: date
    pay_date: date

    # Amounts
    gross_pay: Decimal
    total_deductions: Decimal
    net_pay: Decimal

    # Stats
    total_loads: int = 0
    total_miles: Decimal = Field(default=Decimal("0.00"))

    # Download
    download_url: Optional[str] = None
    pdf_generated: bool = False

    created_at: datetime

    model_config = {"from_attributes": True}


class WeekSummaryResponse(BaseModel):
    """Weekly summary for driver dashboard."""
    driver_id: str
    week_start: date
    week_end: date

    # Earnings
    current_earnings: Decimal = Field(default=Decimal("0.00"))
    projected_total: Decimal = Field(default=Decimal("0.00"))

    # Progress
    completed_loads: int = 0
    pending_loads: int = 0
    completion_percentage: float = 0.0

    # Comparison
    vs_last_week: float = 0.0  # Percentage change from last week
    vs_average: float = 0.0  # Percentage vs 4-week average


class SettlementHistoryResponse(BaseModel):
    """List of historical settlements."""
    settlements: List[SettlementResponse]
    total_count: int
    page: int = 1
    page_size: int = 10


class PayStubListResponse(BaseModel):
    """List of pay stubs."""
    pay_stubs: List[PayStubResponse]
    total_count: int

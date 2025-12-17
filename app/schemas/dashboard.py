from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DashboardFleetMetrics(BaseModel):
    activeTrucks: int
    operationalTrailers: int
    driversDispatched: int
    trucksChange: Optional[str] = None
    trailersChange: Optional[str] = None
    driversChange: Optional[str] = None


class DashboardDispatchMetrics(BaseModel):
    loadsInProgress: int
    loadsAtPickup: int
    delayedLegs: int
    avgPickupCompliance: float
    avgPickupTimeMinutes: float
    ratePerMile: float
    rateChangePercent: Optional[float] = None


class DashboardAccountingMetrics(BaseModel):
    invoicesPending: int
    outstandingAmount: float
    fuelCostPerMile: float
    fuelCostChangePercent: Optional[float] = None


class ChartDataPoint(BaseModel):
    name: str
    value: Optional[float] = None
    completed: Optional[int] = None
    inProgress: Optional[int] = None
    pending: Optional[int] = None
    utilization: Optional[int] = None
    target: Optional[int] = None


class DashboardChartsData(BaseModel):
    revenueTrend: list[ChartDataPoint]
    loadVolume: list[ChartDataPoint]
    utilization: list[ChartDataPoint]


class DashboardMetrics(BaseModel):
    fleet: DashboardFleetMetrics
    dispatch: DashboardDispatchMetrics
    accounting: DashboardAccountingMetrics
    charts: Optional[DashboardChartsData] = None


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


class DashboardMetrics(BaseModel):
    fleet: DashboardFleetMetrics
    dispatch: DashboardDispatchMetrics
    accounting: DashboardAccountingMetrics


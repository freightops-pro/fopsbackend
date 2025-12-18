"""
Container Lookup API Router.

Provides endpoints for container tracking via PORT APIs (not steamship lines).
One port API connection gives data for ALL carriers at that terminal.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.services.drayage.container_lookup_service import (
    ContainerLookupService,
    ContainerLookupResult,
)
from app.services.drayage.demurrage_service import DemurrageService

router = APIRouter(prefix="/drayage/container", tags=["Drayage - Container Tracking"])


# ==================== CONTAINER LOOKUP ====================


class ContainerLookupRequest(BaseModel):
    """Request to look up container information."""
    container_number: str = Field(..., description="Container number (e.g., MAEU1234567)")
    port_code: Optional[str] = Field(None, description="Port UN/LOCODE (e.g., USHOU, USLAX)")
    terminal: Optional[str] = Field(None, description="Specific terminal code")


class VesselInfoResponse(BaseModel):
    """Vessel information."""
    name: Optional[str] = None
    voyage: Optional[str] = None
    eta: Optional[datetime] = None
    ata: Optional[datetime] = None


class ContainerLookupResponse(BaseModel):
    """Container lookup response."""
    success: bool
    container_number: str
    port_code: Optional[str] = None
    terminal: Optional[str] = None
    error: Optional[str] = None

    # Container data
    status: Optional[str] = None
    status_description: Optional[str] = None
    is_available: Optional[bool] = None
    holds: Optional[List[str]] = None
    carrier_scac: Optional[str] = None

    # Vessel
    vessel_name: Optional[str] = None
    vessel_voyage: Optional[str] = None
    vessel_eta: Optional[datetime] = None

    # Critical dates
    last_free_day: Optional[datetime] = None
    discharge_date: Optional[datetime] = None
    empty_return_by: Optional[datetime] = None

    # Container details
    size: Optional[str] = None
    container_type: Optional[str] = None

    # Charges from port
    demurrage_amount: Optional[float] = None


class SupportedPortsResponse(BaseModel):
    """List of supported ports."""
    ports: dict


@router.post("/lookup", response_model=ContainerLookupResponse)
async def lookup_container(request: ContainerLookupRequest):
    """
    Look up container information from PORT API.

    Queries terminal operating systems (Navis N4, eModal, etc.) for:
    - Container status and availability
    - Vessel info and ETA
    - Last Free Day
    - Hold status
    - Current demurrage

    If port_code not provided, searches across all supported ports.
    """
    service = ContainerLookupService()
    result = await service.lookup_container(
        container_number=request.container_number,
        port_code=request.port_code,
        terminal=request.terminal,
    )

    return ContainerLookupResponse(
        success=result.success,
        container_number=result.container_number,
        port_code=result.port_code,
        terminal=result.terminal,
        error=result.error,
        status=result.status,
        status_description=result.status_description,
        is_available=result.is_available,
        holds=result.holds,
        carrier_scac=result.carrier_scac,
        vessel_name=result.vessel_name,
        vessel_voyage=result.vessel_voyage,
        vessel_eta=result.vessel_eta,
        last_free_day=result.last_free_day,
        discharge_date=result.discharge_date,
        empty_return_by=result.empty_return_by,
        size=result.size,
        container_type=result.container_type,
        demurrage_amount=result.demurrage_amount,
    )


@router.get("/lookup/{container_number}", response_model=ContainerLookupResponse)
async def lookup_container_get(
    container_number: str,
    port_code: Optional[str] = Query(None, description="Port UN/LOCODE"),
):
    """Look up container information (GET method)."""
    request = ContainerLookupRequest(
        container_number=container_number,
        port_code=port_code,
    )
    return await lookup_container(request)


@router.get("/ports", response_model=SupportedPortsResponse)
async def get_supported_ports():
    """
    Get list of supported ports for container tracking.

    Returns port codes and names.
    """
    return SupportedPortsResponse(
        ports=ContainerLookupService.SUPPORTED_PORTS
    )


# ==================== DEMURRAGE CALCULATION ====================


class DemurrageCalculateRequest(BaseModel):
    """Request to calculate demurrage/per diem charges."""
    container_number: str = Field(..., description="Container number")
    port_code: str = Field(..., description="Port UN/LOCODE (e.g., USHOU)")
    discharge_date: datetime = Field(..., description="Date container was discharged from vessel")
    outgate_date: Optional[datetime] = Field(None, description="Date container left the port")
    empty_return_date: Optional[datetime] = Field(None, description="Date empty was returned")
    last_free_day: Optional[datetime] = Field(None, description="Override LFD if known")


class ChargeBreakdown(BaseModel):
    """Breakdown of charges by tier."""
    tier: int
    days: int
    rate: float
    amount: float
    description: str


class DemurrageResponse(BaseModel):
    """Demurrage calculation response."""
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
    demurrage_breakdown: List[ChargeBreakdown] = []

    # Per diem (container rental)
    per_diem_days: int = 0
    per_diem_amount: float = 0.0
    per_diem_breakdown: List[ChargeBreakdown] = []

    # Total
    total_amount: float = 0.0
    is_incurring_charges: bool = False

    # Warnings
    days_until_lfd: Optional[int] = None
    warning_level: str = "none"  # none, warning, urgent, overdue


@router.post("/demurrage/calculate", response_model=DemurrageResponse)
async def calculate_demurrage(request: DemurrageCalculateRequest):
    """
    Calculate demurrage and per diem charges for a container.

    Demurrage = Port/terminal storage charges after free time expires
    Per Diem = Container rental charges from carrier after outgate

    Returns:
    - Days of demurrage/per diem incurred
    - Dollar amounts at port's tiered rates
    - Warning level based on LFD proximity
    """
    service = DemurrageService()
    calc = await service.calculate_charges(
        container_number=request.container_number,
        port_code=request.port_code,
        discharge_date=request.discharge_date,
        outgate_date=request.outgate_date,
        empty_return_date=request.empty_return_date,
        last_free_day=request.last_free_day,
    )

    return DemurrageResponse(
        container_number=calc.container_number,
        port_code=calc.port_code,
        discharge_date=calc.discharge_date,
        last_free_day=calc.last_free_day,
        outgate_date=calc.outgate_date,
        empty_return_date=calc.empty_return_date,
        demurrage_days=calc.demurrage_days,
        demurrage_amount=calc.demurrage_amount,
        demurrage_breakdown=[ChargeBreakdown(**b) for b in calc.demurrage_breakdown],
        per_diem_days=calc.per_diem_days,
        per_diem_amount=calc.per_diem_amount,
        per_diem_breakdown=[ChargeBreakdown(**b) for b in calc.per_diem_breakdown],
        total_amount=calc.total_amount,
        is_incurring_charges=calc.is_incurring_charges,
        days_until_lfd=calc.days_until_lfd,
        warning_level=calc.warning_level,
    )


@router.get("/demurrage/{container_number}", response_model=DemurrageResponse)
async def get_demurrage_from_port(
    container_number: str,
    port_code: Optional[str] = Query(None, description="Port UN/LOCODE (searches all if not provided)"),
):
    """
    Calculate demurrage by looking up container from port API.

    Automatically fetches discharge date and LFD from port,
    then calculates current charges.
    """
    service = DemurrageService()
    calc = await service.calculate_from_container_lookup(
        container_number=container_number,
        port_code=port_code,
    )

    return DemurrageResponse(
        container_number=calc.container_number,
        port_code=calc.port_code,
        discharge_date=calc.discharge_date,
        last_free_day=calc.last_free_day,
        outgate_date=calc.outgate_date,
        empty_return_date=calc.empty_return_date,
        demurrage_days=calc.demurrage_days,
        demurrage_amount=calc.demurrage_amount,
        demurrage_breakdown=[ChargeBreakdown(**b) for b in calc.demurrage_breakdown],
        per_diem_days=calc.per_diem_days,
        per_diem_amount=calc.per_diem_amount,
        per_diem_breakdown=[ChargeBreakdown(**b) for b in calc.per_diem_breakdown],
        total_amount=calc.total_amount,
        is_incurring_charges=calc.is_incurring_charges,
        days_until_lfd=calc.days_until_lfd,
        warning_level=calc.warning_level,
    )


@router.get("/lfd/{container_number}")
async def get_last_free_day(
    container_number: str,
    port_code: Optional[str] = Query(None, description="Port UN/LOCODE"),
):
    """
    Get Last Free Day for a container.

    Returns LFD and warning status for dispatch prioritization.
    """
    service = DemurrageService()
    calc = await service.calculate_from_container_lookup(
        container_number=container_number,
        port_code=port_code,
    )

    return {
        "container_number": calc.container_number,
        "port_code": calc.port_code,
        "last_free_day": calc.last_free_day.isoformat() if calc.last_free_day else None,
        "days_until_lfd": calc.days_until_lfd,
        "warning_level": calc.warning_level,
        "is_incurring_charges": calc.is_incurring_charges,
        "current_demurrage": calc.demurrage_amount,
    }

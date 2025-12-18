"""
Container Auto-Lookup Service.

Queries PORT terminal APIs (not steamship lines) for container data.
One port API gives container info for ALL carriers at that terminal.

Supported ports:
- Port Houston (USHOU) - Navis N4 EVP
- LA/Long Beach (USLAX/USLGB) - Multiple terminals
- NY/NJ (USNYC/USEWR) - Multiple terminals
- Savannah (USSAV) - Navis N4 EVP
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ContainerLookupResult:
    """Result of container lookup from port API."""
    success: bool
    container_number: str
    port_code: Optional[str] = None
    terminal: Optional[str] = None
    error: Optional[str] = None

    # Container status
    status: Optional[str] = None
    status_description: Optional[str] = None
    is_available: bool = False
    holds: List[str] = None

    # Vessel info
    vessel_name: Optional[str] = None
    vessel_voyage: Optional[str] = None
    vessel_eta: Optional[datetime] = None
    vessel_ata: Optional[datetime] = None

    # Critical dates
    discharge_date: Optional[datetime] = None
    last_free_day: Optional[datetime] = None
    empty_return_by: Optional[datetime] = None
    outgate_date: Optional[datetime] = None

    # Container details
    size: Optional[str] = None
    container_type: Optional[str] = None
    carrier_scac: Optional[str] = None

    # Shipment references
    booking_number: Optional[str] = None
    bill_of_lading: Optional[str] = None

    # Charges from port
    demurrage_amount: Optional[float] = None
    per_diem_amount: Optional[float] = None

    # Raw response
    raw_data: Optional[Dict] = None

    def __post_init__(self):
        if self.holds is None:
            self.holds = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "success": self.success,
            "container_number": self.container_number,
            "port_code": self.port_code,
            "terminal": self.terminal,
            "error": self.error,
            "status": self.status,
            "status_description": self.status_description,
            "is_available": self.is_available,
            "holds": self.holds,
            "vessel_name": self.vessel_name,
            "vessel_voyage": self.vessel_voyage,
            "vessel_eta": self.vessel_eta.isoformat() if self.vessel_eta else None,
            "discharge_date": self.discharge_date.isoformat() if self.discharge_date else None,
            "last_free_day": self.last_free_day.isoformat() if self.last_free_day else None,
            "empty_return_by": self.empty_return_by.isoformat() if self.empty_return_by else None,
            "size": self.size,
            "container_type": self.container_type,
            "carrier_scac": self.carrier_scac,
            "booking_number": self.booking_number,
            "bill_of_lading": self.bill_of_lading,
            "demurrage_amount": self.demurrage_amount,
        }


class ContainerLookupService:
    """
    Service for container lookup via PORT APIs.

    Uses terminal APIs instead of steamship line APIs because:
    1. One port API = all carriers at that port
    2. More accurate terminal-specific data (availability, holds, LFD)
    3. Fewer API credentials to maintain
    4. Better for demurrage tracking (port charges)

    Usage:
        service = ContainerLookupService()
        result = await service.lookup_container("MAEU1234567", port_code="USHOU")
    """

    # Major US port codes
    SUPPORTED_PORTS = {
        "USHOU": "Port Houston",
        "USLAX": "Los Angeles",
        "USLGB": "Long Beach",
        "USNYC": "New York",
        "USEWR": "Newark/Elizabeth",
        "USSAV": "Savannah",
        # Florida ports
        "USPEF": "Port Everglades",
        "USMIA": "Port Miami",
        "USJAX": "Jacksonville (JAXPORT)",
    }

    def __init__(self, db=None):
        self.db = db

    async def lookup_container(
        self,
        container_number: str,
        port_code: Optional[str] = None,
        terminal: Optional[str] = None,
        scac_code: Optional[str] = None,  # Kept for backwards compatibility
        carrier_name: Optional[str] = None,  # Kept for backwards compatibility
    ) -> ContainerLookupResult:
        """
        Look up container information from port terminal API.

        Args:
            container_number: Container number (e.g., "MAEU1234567")
            port_code: Port UN/LOCODE (e.g., "USHOU", "USLAX")
            terminal: Optional specific terminal code

        Returns:
            ContainerLookupResult with container data from port
        """
        container_number = self._normalize_container_number(container_number)

        if not self._validate_container_number(container_number):
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                error="Invalid container number format. Expected: ABCD1234567",
            )

        # If port not specified, try to search across major ports
        if not port_code:
            return await self._search_all_ports(container_number)

        # Query specific port
        return await self._query_port(container_number, port_code, terminal)

    async def _query_port(
        self,
        container_number: str,
        port_code: str,
        terminal: Optional[str] = None,
    ) -> ContainerLookupResult:
        """Query a specific port's API for container data."""
        port_code = port_code.upper()

        try:
            if port_code == "USHOU":
                return await self._query_houston(container_number)
            elif port_code in ("USLAX", "USLGB"):
                return await self._query_la_lb(container_number, port_code, terminal)
            elif port_code in ("USNYC", "USEWR"):
                return await self._query_ny_nj(container_number, port_code, terminal)
            elif port_code == "USSAV":
                return await self._query_savannah(container_number)
            elif port_code == "USPEF":
                return await self._query_port_everglades(container_number)
            elif port_code == "USMIA":
                return await self._query_port_miami(container_number)
            elif port_code == "USJAX":
                return await self._query_jaxport(container_number)
            else:
                return ContainerLookupResult(
                    success=False,
                    container_number=container_number,
                    error=f"Port {port_code} not supported. Supported: {', '.join(self.SUPPORTED_PORTS.keys())}",
                )
        except Exception as e:
            logger.exception(f"Error querying port {port_code} for {container_number}")
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                port_code=port_code,
                error=f"Port API error: {str(e)}",
            )

    async def _search_all_ports(self, container_number: str) -> ContainerLookupResult:
        """Search across all supported ports for the container."""
        # Try major ports in order of volume
        for port_code in ["USLAX", "USLGB", "USNYC", "USEWR", "USHOU", "USSAV", "USPEF", "USMIA", "USJAX"]:
            try:
                result = await self._query_port(container_number, port_code)
                if result.success:
                    return result
            except Exception:
                continue

        return ContainerLookupResult(
            success=False,
            container_number=container_number,
            error="Container not found at any supported port. Specify port_code if known.",
        )

    async def _query_houston(self, container_number: str) -> ContainerLookupResult:
        """Query Port Houston Navis N4 EVP API."""
        from app.services.port.adapters.port_houston_adapter import PortHoustonAdapter

        adapter = PortHoustonAdapter(
            credentials={
                "client_id": settings.port_houston_client_id,
                "client_secret": settings.port_houston_client_secret,
            }
        )

        try:
            tracking = await adapter.track_container(container_number, "USHOU")
            return self._convert_port_response(tracking, "USHOU")
        except Exception as e:
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                port_code="USHOU",
                error=str(e),
            )

    async def _query_la_lb(
        self,
        container_number: str,
        port_code: str,
        terminal: Optional[str] = None,
    ) -> ContainerLookupResult:
        """Query LA/Long Beach terminal APIs.

        Priority order:
        1. LBCT API (if terminal=lbct or searching Long Beach)
        2. APM Terminals API (Pier 400)
        3. eModal (TraPac, YTI, SSA, etc.)
        4. Fallback adapter
        """
        terminal_lower = terminal.lower() if terminal else ""

        # 1. Try LBCT first for Long Beach
        if port_code == "USLGB" or terminal_lower == "lbct":
            try:
                result = await self._query_lbct(container_number)
                if result.success:
                    return result
            except Exception:
                pass

        # 2. Try APM Terminals for Pier 400
        apm_terminals = ["pier400", "apm", "apmt"]
        if terminal_lower in apm_terminals or (settings.apm_client_id and settings.apm_client_secret):
            try:
                result = await self._query_apm(container_number, port_code)
                if result.success:
                    return result
            except Exception:
                pass

        # 3. Try eModal for other LA/LB terminals (TraPac, YTI, SSA, etc.)
        emodal_terminals = ["trapac", "yti", "everport", "ssa", "tti", "pct"]
        if terminal_lower in emodal_terminals or settings.emodal_api_key:
            try:
                result = await self._query_emodal(container_number, port_code, terminal)
                if result.success:
                    return result
            except Exception:
                pass

        # 4. Try ITS for Long Beach
        if terminal_lower == "its" or (settings.its_username and settings.its_password):
            try:
                result = await self._query_its(container_number)
                if result.success:
                    return result
            except Exception:
                pass

        # 5. Fallback to generic LA/LB adapter
        from app.services.port.adapters.la_lb_adapter import LALBAdapter
        adapter = LALBAdapter()

        try:
            tracking = await adapter.track_container(container_number, port_code)
            return self._convert_port_response(tracking, port_code)
        except Exception as e:
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                port_code=port_code,
                error=str(e),
            )

    async def _query_ny_nj(
        self,
        container_number: str,
        port_code: str,
        terminal: Optional[str] = None,
    ) -> ContainerLookupResult:
        """Query NY/NJ terminal APIs.

        APM Terminals Elizabeth (USEWR) has API access.
        Other terminals fall back to NY/NJ adapter.
        """
        # Try APM Terminals first for Elizabeth
        apm_terminals = ["elizabeth", "apm", "apmt"]
        if terminal and terminal.lower() in apm_terminals:
            try:
                return await self._query_apm(container_number, "USEWN")  # APM uses USEWN code
            except Exception:
                pass  # Fall through to generic adapter

        # If no terminal specified or not APM, try APM first then fallback
        if settings.apm_client_id and settings.apm_client_secret:
            try:
                result = await self._query_apm(container_number, "USEWN")
                if result.success:
                    return result
            except Exception:
                pass  # Fall through to generic adapter

        from app.services.port.adapters.ny_nj_adapter import NYNJAdapter
        adapter = NYNJAdapter()

        try:
            tracking = await adapter.track_container(container_number, port_code)
            return self._convert_port_response(tracking, port_code)
        except Exception as e:
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                port_code=port_code,
                error=str(e),
            )

    async def _query_savannah(self, container_number: str) -> ContainerLookupResult:
        """Query GPA Savannah Navis N4 EVP API."""
        from app.services.port.adapters.savannah_adapter import SavannahAdapter

        adapter = SavannahAdapter(
            credentials={
                "client_id": settings.gpa_savannah_client_id,
                "client_secret": settings.gpa_savannah_client_secret,
            }
        )

        try:
            tracking = await adapter.track_container(container_number, "USSAV")
            return self._convert_port_response(tracking, "USSAV")
        except Exception as e:
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                port_code="USSAV",
                error=str(e),
            )

    async def _query_apm(self, container_number: str, port_code: str) -> ContainerLookupResult:
        """Query APM Terminals API.

        APM Terminals (Maersk subsidiary) operates:
        - APM Terminals Los Angeles (Pier 400) - USLAX
        - APM Terminals Elizabeth (NJ) - USEWN
        - APM Terminals Mobile (AL) - USMOB
        """
        from app.services.port.adapters.apm_terminals_adapter import APMTerminalsAdapter

        adapter = APMTerminalsAdapter(
            credentials={
                "client_id": settings.apm_client_id,
                "client_secret": settings.apm_client_secret,
            }
        )

        try:
            tracking = await adapter.track_container(container_number, port_code)
            return self._convert_port_response(tracking, port_code)
        except Exception as e:
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                port_code=port_code,
                error=str(e),
            )

    async def _query_lbct(self, container_number: str) -> ContainerLookupResult:
        """Query LBCT (Long Beach Container Terminal) API.

        LBCT was the first LA/LB terminal to offer a public API.
        Docs: http://coredocs.envaseconnect.cloud/track-trace/providers/rt/lbct.html
        """
        from app.services.port.adapters.lbct_adapter import LBCTAdapter

        adapter = LBCTAdapter(
            credentials={"api_key": settings.lbct_api_key}
        )

        try:
            tracking = await adapter.track_container(container_number, "USLGB")
            return self._convert_port_response(tracking, "USLGB")
        except Exception as e:
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                port_code="USLGB",
                error=str(e),
            )

    async def _query_emodal(
        self,
        container_number: str,
        port_code: str,
        terminal: Optional[str] = None,
    ) -> ContainerLookupResult:
        """Query eModal API (used by TraPac, YTI, Everport, SSA, TTI, PCT).

        Docs: http://coredocs.envaseconnect.cloud/track-trace/providers/pr/emodal.html
        """
        from app.services.port.adapters.emodal_adapter import EModalAdapter

        adapter = EModalAdapter(
            credentials={
                "api_key": settings.emodal_api_key,
                "sas_token": settings.emodal_sas_token,
                "topic": settings.emodal_topic,
            }
        )

        try:
            tracking = await adapter.track_container(container_number, port_code)
            return self._convert_port_response(tracking, port_code)
        except Exception as e:
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                port_code=port_code,
                error=str(e),
            )

    async def _query_bnsf(self, container_number: str) -> ContainerLookupResult:
        """Query BNSF Railway for rail intermodal tracking.

        Docs: http://coredocs.envaseconnect.cloud/track-trace/providers/rt/bnsf.html
        """
        from app.services.port.adapters.bnsf_adapter import BNSFAdapter

        adapter = BNSFAdapter(
            credentials={
                "client_id": settings.bnsf_client_id,
                "client_secret": settings.bnsf_client_secret,
            }
        )

        try:
            tracking = await adapter.track_container(container_number, "RAIL")
            return self._convert_port_response(tracking, "RAIL")
        except Exception as e:
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                port_code="RAIL",
                error=str(e),
            )

    async def _query_port_everglades(self, container_number: str) -> ContainerLookupResult:
        """Query Port Everglades via Tideworks scraper.

        Port Everglades Terminal uses Tideworks: https://pet.tideworks.io/fc-PET-AWS
        """
        from app.services.port.adapters.tideworks_scraper import TideworksScraper

        adapter = TideworksScraper()

        try:
            tracking = await adapter.track_container(container_number, "USPEF")
            return self._convert_port_response(tracking, "USPEF")
        except Exception as e:
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                port_code="USPEF",
                error=str(e),
            )

    async def _query_port_miami(self, container_number: str) -> ContainerLookupResult:
        """Query Port Miami via APM Terminals.

        Port Miami has APM Terminals facility.
        """
        from app.services.port.adapters.apm_terminals_adapter import APMTerminalsAdapter

        adapter = APMTerminalsAdapter(
            credentials={
                "client_id": settings.apm_client_id,
                "client_secret": settings.apm_client_secret,
            }
        )

        try:
            tracking = await adapter.track_container(container_number, "USMIA")
            return self._convert_port_response(tracking, "USMIA")
        except Exception as e:
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                port_code="USMIA",
                error=str(e),
            )

    async def _query_jaxport(self, container_number: str) -> ContainerLookupResult:
        """Query JAXPORT (Jacksonville).

        JAXPORT has SSA Marine at Blount Island.
        Falls back to generic lookup if no specific adapter available.
        """
        # JAXPORT doesn't have a known public API yet
        # Return not found - can be enhanced when API becomes available
        return ContainerLookupResult(
            success=False,
            container_number=container_number,
            port_code="USJAX",
            error="JAXPORT API not yet available. Contact terminal directly.",
        )

    async def _query_its(self, container_number: str) -> ContainerLookupResult:
        """Query ITS (International Transportation Service) Long Beach.

        Docs: http://coredocs.envaseconnect.cloud/track-trace/providers/rt/its.html
        """
        from app.services.port.adapters.its_adapter import ITSAdapter

        adapter = ITSAdapter(
            credentials={
                "username": settings.its_username,
                "password": settings.its_password,
            }
        )

        try:
            tracking = await adapter.track_container(container_number, "USLGB")
            return self._convert_port_response(tracking, "USLGB")
        except Exception as e:
            return ContainerLookupResult(
                success=False,
                container_number=container_number,
                port_code="USLGB",
                error=str(e),
            )

    def _convert_port_response(self, tracking, port_code: str) -> ContainerLookupResult:
        """Convert port adapter response to ContainerLookupResult."""
        # Handle ContainerTrackingResponse schema
        return ContainerLookupResult(
            success=True,
            container_number=tracking.container_number,
            port_code=port_code,
            terminal=tracking.terminal,
            status=tracking.status,
            status_description=getattr(tracking, "status_description", None),
            is_available=tracking.status in ("AVAILABLE", "RELEASED") and len(tracking.holds or []) == 0,
            holds=tracking.holds or [],
            vessel_name=tracking.vessel.name if tracking.vessel else None,
            vessel_voyage=tracking.vessel.voyage if tracking.vessel else None,
            vessel_eta=tracking.vessel.eta if tracking.vessel else None,
            vessel_ata=tracking.vessel.ata if tracking.vessel else None,
            discharge_date=tracking.dates.discharge_date if tracking.dates else None,
            last_free_day=tracking.dates.last_free_day if tracking.dates else None,
            empty_return_by=tracking.dates.empty_return_by if tracking.dates else None,
            outgate_date=tracking.dates.outgate_date if tracking.dates else None,
            size=tracking.container_details.size if tracking.container_details else None,
            container_type=tracking.container_details.container_type if tracking.container_details else None,
            carrier_scac=tracking.container_details.carrier_scac if tracking.container_details else None,
            demurrage_amount=tracking.charges.demurrage_amount if tracking.charges else None,
            per_diem_amount=tracking.charges.per_diem_amount if tracking.charges else None,
        )

    def _normalize_container_number(self, container_number: str) -> str:
        """Normalize container number format."""
        return container_number.replace(" ", "").replace("-", "").upper()

    def _validate_container_number(self, container_number: str) -> bool:
        """Validate container number format per ISO 6346."""
        if len(container_number) != 11:
            return False
        if not container_number[:4].isalpha():
            return False
        if not container_number[4:].isdigit():
            return False
        return True


async def lookup_container(
    container_number: str,
    port_code: Optional[str] = None,
) -> ContainerLookupResult:
    """
    Quick container lookup via port API.

    Args:
        container_number: Container number
        port_code: Optional port code (searches all if not provided)

    Returns:
        ContainerLookupResult
    """
    service = ContainerLookupService()
    return await service.lookup_container(container_number, port_code)

"""
LBCT (Long Beach Container Terminal) API Adapter.

LBCT was the first Marine Terminal Operator at LA/LB to provide an API solution.
API documentation: http://coredocs.envaseconnect.cloud/track-trace/providers/rt/lbct.html

Endpoints:
- Container Search: GET http://api.lbct.com/<API_KEY>/API/LBCTCargoSearchWebService/cargo-numbers/{containers}
- Vessel Schedule: GET http://api.lbct.com/<API_KEY>/API/LBCTGetActiveVesselVisitsWebService

To get API access, register at https://portal.lbct.com/
"""

import httpx
from datetime import datetime
from typing import Optional, List

from app.schemas.port import (
    ContainerCharges,
    ContainerDates,
    ContainerDetails,
    ContainerLocation,
    ContainerTrackingResponse,
    VesselInfo,
)
from app.services.port.adapters.base_adapter import (
    PortAdapter,
    PortAdapterError,
    PortAuthenticationError,
    PortNotFoundError,
)


class LBCTAdapter(PortAdapter):
    """
    Adapter for Long Beach Container Terminal (LBCT) API.

    LBCT provides direct REST API access for container tracking.
    Requires an API key obtained from LBCT portal.

    API Features:
    - Container search (up to 20 containers per request)
    - Vessel schedule and ETA information
    - Booking information
    - Hold status and availability
    """

    BASE_URL = "http://api.lbct.com"
    MAX_CONTAINERS_PER_REQUEST = 20

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)
        from app.core.config import get_settings
        settings = get_settings()

        # API key from credentials or settings
        self.api_key = self.credentials.get("api_key") or getattr(settings, "lbct_api_key", None)

    def _get_url(self, endpoint: str) -> str:
        """Build URL with API key."""
        if not self.api_key:
            raise PortAuthenticationError("LBCT API key is required")
        return f"{self.BASE_URL}/{self.api_key}/API/{endpoint}"

    async def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make GET API request."""
        url = self._get_url(endpoint)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=30.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError("Invalid LBCT API key")
                elif e.response.status_code == 404:
                    raise PortNotFoundError(f"Resource not found: {endpoint}")
                elif e.response.status_code == 429:
                    raise PortAdapterError("Rate limit exceeded")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """
        Track container using LBCT API.

        Uses LBCTCargoSearchWebService endpoint.

        Response fields:
        - container-id: Container number
        - category: IMPRT (import), EXPRT (export)
        - freight-kind: FCL, MTY
        - visit-state, transit-state: Status codes
        - time-in, time-out: Gate timestamps
        - line-operator: Shipping line SCAC
        - vessel-name, in-voyage-nbr: Vessel info
        - available-for-pickup: Availability flag
        """
        try:
            data = await self._make_request(
                f"LBCTCargoSearchWebService/cargo-numbers/{container_number}"
            )

            # Check for not found
            if data.get("not-found", 0) > 0:
                not_found_list = data.get("not-found-numbers", [])
                if container_number in not_found_list:
                    raise PortNotFoundError(f"Container {container_number} not found at LBCT")

            # Get container data from response
            containers = data.get("containers", [])
            if not containers:
                raise PortNotFoundError(f"Container {container_number} not found at LBCT")

            container = containers[0]

            # Map status
            visit_state = container.get("visit-state", "")
            transit_state = container.get("transit-state", "")
            status = self._map_lbct_status(visit_state, transit_state)

            # Extract location
            location = ContainerLocation(
                terminal="LBCT",
                yard_location=container.get("position") or container.get("yard-location"),
                gate_status=visit_state,
                port="Long Beach",
                country="US",
                timestamp=self._parse_timestamp(container.get("time-in")),
            )

            # Extract vessel info
            vessel = None
            vessel_name = container.get("vessel-name")
            if vessel_name:
                vessel = VesselInfo(
                    name=vessel_name,
                    voyage=container.get("in-voyage-nbr") or container.get("voyage-number"),
                    eta=None,  # Need to call vessel schedule endpoint for ETA
                )

            # Extract dates
            dates = ContainerDates(
                discharge_date=self._parse_timestamp(container.get("discharge-time")),
                last_free_day=self._parse_timestamp(container.get("last-free-day")),
                ingate_timestamp=self._parse_timestamp(container.get("time-in")),
                outgate_timestamp=self._parse_timestamp(container.get("time-out")),
            )

            # Extract container details
            container_details = ContainerDetails(
                size=container.get("nominal-length") or container.get("eq-size"),
                type=container.get("eq-type") or container.get("freight-kind"),
                weight=container.get("gross-weight"),
                seal_number=container.get("seal-number"),
                shipping_line=container.get("line-operator"),
            )

            # Extract holds
            holds = self._extract_holds(container)

            # Check availability
            is_available = container.get("available-for-pickup", False)
            if is_available and status != "AVAILABLE":
                status = "AVAILABLE"

            # Extract charges (demurrage)
            charges = None
            demurrage = container.get("demurrage") or container.get("demurrage-amount")
            if demurrage:
                charges = ContainerCharges(
                    demurrage=float(demurrage) if demurrage else None,
                )

            return self.normalize_tracking_response(
                container_number=container_number,
                port_code=port_code,
                status=status,
                location=location,
                vessel=vessel,
                dates=dates,
                container_details=container_details,
                holds=holds,
                charges=charges,
                terminal="LBCT",
                raw_data=container,
            )

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error tracking container: {str(e)}")

    async def track_multiple_containers(
        self, container_numbers: List[str], port_code: str
    ) -> List[ContainerTrackingResponse]:
        """
        Track multiple containers in a single request.

        LBCT API supports up to 20 containers per request.
        """
        if len(container_numbers) > self.MAX_CONTAINERS_PER_REQUEST:
            raise PortAdapterError(
                f"Maximum {self.MAX_CONTAINERS_PER_REQUEST} containers per request"
            )

        try:
            # Join container numbers with commas
            containers_param = ",".join(container_numbers)
            data = await self._make_request(
                f"LBCTCargoSearchWebService/cargo-numbers/{containers_param}"
            )

            results = []
            containers = data.get("containers", [])

            for container in containers:
                container_id = container.get("container-id")
                if container_id:
                    # Build response for each container
                    result = await self._build_tracking_response(container, port_code)
                    results.append(result)

            return results

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error tracking containers: {str(e)}")

    async def _build_tracking_response(
        self, container: dict, port_code: str
    ) -> ContainerTrackingResponse:
        """Build ContainerTrackingResponse from LBCT container data."""
        container_number = container.get("container-id", "")
        visit_state = container.get("visit-state", "")
        transit_state = container.get("transit-state", "")

        return self.normalize_tracking_response(
            container_number=container_number,
            port_code=port_code,
            status=self._map_lbct_status(visit_state, transit_state),
            location=ContainerLocation(
                terminal="LBCT",
                yard_location=container.get("position"),
                port="Long Beach",
                country="US",
            ),
            vessel=VesselInfo(
                name=container.get("vessel-name"),
                voyage=container.get("in-voyage-nbr"),
            ) if container.get("vessel-name") else None,
            dates=ContainerDates(
                discharge_date=self._parse_timestamp(container.get("discharge-time")),
                last_free_day=self._parse_timestamp(container.get("last-free-day")),
                ingate_timestamp=self._parse_timestamp(container.get("time-in")),
                outgate_timestamp=self._parse_timestamp(container.get("time-out")),
            ),
            container_details=ContainerDetails(
                size=container.get("nominal-length"),
                type=container.get("eq-type"),
                shipping_line=container.get("line-operator"),
            ),
            holds=self._extract_holds(container),
            terminal="LBCT",
            raw_data=container,
        )

    def _map_lbct_status(self, visit_state: str, transit_state: str) -> str:
        """Map LBCT status codes to normalized status."""
        # LBCT uses similar codes to Navis N4
        visit_map = {
            "1ACTIVE": "IN_YARD",
            "2ADVISED": "ADVISED",
            "3DEPARTED": "DEPARTED",
        }

        transit_map = {
            "S10_ADVISED": "ADVISED",
            "S20_INBOUND": "IN_TRANSIT",
            "S30_ECIN": "INGATE",
            "S40_YARD": "IN_YARD",
            "S50_ECOUT": "OUTGATE",
            "S60_RETIRED": "DEPARTED",
        }

        # Try transit state first, then visit state
        if transit_state and transit_state in transit_map:
            return transit_map[transit_state]
        if visit_state and visit_state in visit_map:
            return visit_map[visit_state]

        return transit_state or visit_state or "UNKNOWN"

    def _extract_holds(self, container: dict) -> List[str]:
        """Extract hold information from container data."""
        holds = []

        # Check various hold flags
        if container.get("customs-hold"):
            holds.append("CUSTOMS_HOLD")
        if container.get("freight-hold"):
            holds.append("FREIGHT_HOLD")
        if container.get("line-hold"):
            holds.append("LINE_HOLD")
        if container.get("terminal-hold"):
            holds.append("TERMINAL_HOLD")
        if container.get("usda-hold"):
            holds.append("USDA_HOLD")
        if container.get("tmf-hold"):
            holds.append("TMF_HOLD")

        # Also check hold-flags array if present
        hold_flags = container.get("hold-flags", [])
        if isinstance(hold_flags, list):
            for flag in hold_flags:
                if isinstance(flag, str) and flag not in holds:
                    holds.append(flag.upper())
                elif isinstance(flag, dict):
                    hold_type = flag.get("type") or flag.get("holdType")
                    if hold_type and hold_type not in holds:
                        holds.append(hold_type.upper())

        return holds

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse LBCT timestamp format to datetime."""
        if not timestamp_str:
            return None
        try:
            # LBCT uses ISO 8601 format
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            try:
                # Try alternative format
                return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
            except (ValueError, AttributeError):
                return None

    async def get_container_events(
        self, container_number: str, port_code: str, since: Optional[datetime] = None
    ) -> list[dict]:
        """Get container event history from LBCT."""
        # LBCT doesn't have a separate events endpoint
        # Return basic info from container lookup
        try:
            tracking = await self.track_container(container_number, port_code)
            events = []

            if tracking.dates and tracking.dates.ingate_timestamp:
                events.append({
                    "event_type": "INGATE",
                    "timestamp": tracking.dates.ingate_timestamp,
                    "location": "LBCT",
                    "description": "Container entered terminal",
                })

            if tracking.dates and tracking.dates.discharge_date:
                events.append({
                    "event_type": "DISCHARGE",
                    "timestamp": tracking.dates.discharge_date,
                    "location": "LBCT",
                    "description": "Container discharged from vessel",
                })

            if tracking.dates and tracking.dates.outgate_timestamp:
                events.append({
                    "event_type": "OUTGATE",
                    "timestamp": tracking.dates.outgate_timestamp,
                    "location": "LBCT",
                    "description": "Container exited terminal",
                })

            return events
        except Exception as e:
            raise PortAdapterError(f"Error getting container events: {str(e)}")

    async def get_vessel_schedule(
        self, vessel_name: Optional[str] = None, port_code: Optional[str] = None
    ) -> list[dict]:
        """
        Get vessel schedule from LBCT.

        Uses LBCTGetActiveVesselVisitsWebService endpoint.
        Returns all active vessel visits at LBCT.
        """
        try:
            data = await self._make_request("LBCTGetActiveVesselVisitsWebService")

            vessels = data if isinstance(data, list) else data.get("vessels", data.get("vesselVisits", []))

            results = []
            for vessel in vessels:
                vessel_info = {
                    "vessel_name": vessel.get("vessel-name") or vessel.get("vesselName"),
                    "voyage": vessel.get("in-voyage-nbr") or vessel.get("voyage"),
                    "eta": self._parse_timestamp(vessel.get("eta") or vessel.get("published-eta")),
                    "etd": self._parse_timestamp(vessel.get("etd") or vessel.get("published-etd")),
                    "ata": self._parse_timestamp(vessel.get("ata")),
                    "atd": self._parse_timestamp(vessel.get("atd")),
                    "berth": vessel.get("berth"),
                    "terminal": "LBCT",
                    "status": vessel.get("visit-phase") or vessel.get("status"),
                }

                # Filter by vessel name if provided
                if vessel_name:
                    if vessel_info["vessel_name"] and vessel_name.lower() in vessel_info["vessel_name"].lower():
                        results.append(vessel_info)
                else:
                    results.append(vessel_info)

            return results
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting vessel schedule: {str(e)}")

    async def test_connection(self) -> bool:
        """Test connection by attempting to get vessel schedule."""
        try:
            await self.get_vessel_schedule()
            return True
        except Exception:
            return False

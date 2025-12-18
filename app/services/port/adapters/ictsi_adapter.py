"""
ICTSI (International Container Terminal Services Inc.) Adapter.

ICTSI is a global terminal operator headquartered in Manila.
They operate terminals in multiple countries including US ports.

Documentation: http://coredocs.envaseconnect.cloud/track-trace/providers/rt/ictsi.html

Endpoints:
- Container Details: POST https://dev-api.ictsi.net/external/tms/api/v2/getContainerDetails

Authentication: Requires subscription headers:
- x-subscription-id
- Ocp-Apim-Subscription-Key
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


class ICTSIAdapter(PortAdapter):
    """
    Adapter for ICTSI terminal operations.

    ICTSI uses Azure API Management with subscription keys.

    US Terminals:
    - Portland (Oregon)
    - Other facilities via acquisitions

    Response includes:
    - Container status and location
    - Vessel information
    - Hold status
    - Dates (discharge, LFD, etc.)
    """

    # Production and development endpoints
    BASE_URL = "https://api.ictsi.net/external/tms/api/v2"
    DEV_URL = "https://dev-api.ictsi.net/external/tms/api/v2"

    # Facility IDs for different terminals
    FACILITY_IDS = {
        "PORTLAND": "PDX",
        "USPDX": "PDX",
        # Add other ICTSI facilities as discovered
    }

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)
        from app.core.config import get_settings
        settings = get_settings()

        self.subscription_id = (
            self.credentials.get("subscription_id") if self.credentials else None
        ) or getattr(settings, "ictsi_subscription_id", None)

        self.subscription_key = (
            self.credentials.get("subscription_key") if self.credentials else None
        ) or getattr(settings, "ictsi_subscription_key", None)

        # Use development endpoint by default, can be overridden
        self.use_production = (
            self.config.get("use_production") if self.config else False
        )
        self.base_url = self.BASE_URL if self.use_production else self.DEV_URL

    async def _make_request(self, endpoint: str, params: dict) -> dict:
        """Make authenticated API request to ICTSI."""
        if not self.subscription_id or not self.subscription_key:
            raise PortAuthenticationError(
                "ICTSI credentials (subscription_id, subscription_key) are required"
            )

        headers = {
            "x-subscription-id": self.subscription_id,
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    json=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError("Invalid ICTSI subscription credentials")
                elif e.response.status_code == 404:
                    raise PortNotFoundError("Container not found")
                elif e.response.status_code == 429:
                    raise PortAdapterError("Rate limit exceeded")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """
        Track container via ICTSI API.

        Request format:
        {
            "container-type": "IMPORT",
            "facility-id": "PDX",
            "container-number": "MAEU1234567"
        }
        """
        try:
            # Determine facility ID from port code
            facility_id = self.FACILITY_IDS.get(port_code.upper(), port_code)

            params = {
                "container-type": "IMPORT",  # Could be IMPORT or EXPORT
                "facility-id": facility_id,
                "container-number": container_number.upper(),
            }

            response = await self._make_request("/getContainerDetails", params)

            # Parse response
            container_data = response.get("data") or response.get("container") or response
            if not container_data:
                raise PortNotFoundError(f"Container {container_number} not found")

            return self._build_tracking_response(container_number, port_code, container_data)

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error tracking container: {str(e)}")

    async def track_containers_bulk(
        self, container_numbers: List[str], port_code: str
    ) -> List[ContainerTrackingResponse]:
        """
        Track multiple containers at once.

        Some ICTSI endpoints support bulk queries.
        """
        results = []
        for container_number in container_numbers:
            try:
                result = await self.track_container(container_number, port_code)
                results.append(result)
            except PortNotFoundError:
                continue
            except Exception:
                continue
        return results

    def _build_tracking_response(
        self,
        container_number: str,
        port_code: str,
        data: dict,
    ) -> ContainerTrackingResponse:
        """Build ContainerTrackingResponse from ICTSI data."""

        # Map status
        status = data.get("status") or data.get("containerStatus") or "UNKNOWN"
        status = self._map_ictsi_status(status)

        # Location
        location = ContainerLocation(
            terminal=data.get("facility") or data.get("terminal"),
            yard_location=data.get("yardPosition") or data.get("location"),
            port=port_code,
            country="US",
            timestamp=self._parse_timestamp(data.get("lastMoveDateTime")),
        )

        # Vessel info
        vessel = None
        vessel_name = data.get("vesselName") or data.get("vessel")
        if vessel_name:
            vessel = VesselInfo(
                name=vessel_name,
                voyage=data.get("voyage") or data.get("voyageNumber"),
                eta=self._parse_timestamp(data.get("vesselETA")),
                ata=self._parse_timestamp(data.get("vesselATA")),
            )

        # Dates
        dates = ContainerDates(
            discharge_date=self._parse_timestamp(data.get("dischargeDate")),
            last_free_day=self._parse_timestamp(data.get("lastFreeDay") or data.get("LFD")),
            ingate_timestamp=self._parse_timestamp(data.get("ingateDateTime")),
            outgate_timestamp=self._parse_timestamp(data.get("outgateDateTime")),
            empty_return_by=self._parse_timestamp(data.get("emptyReturnBy")),
        )

        # Container details
        container_details = ContainerDetails(
            size=data.get("containerSize") or data.get("size"),
            type=data.get("containerType") or data.get("type"),
            weight=data.get("grossWeight") or data.get("weight"),
            shipping_line=data.get("shippingLine") or data.get("line"),
        )

        # Holds
        holds = []
        hold_data = data.get("holds") or data.get("holdFlags") or []
        if isinstance(hold_data, list):
            holds = [h.get("holdType", h) if isinstance(h, dict) else h for h in hold_data]
        elif isinstance(hold_data, str) and hold_data:
            holds = [h.strip() for h in hold_data.split(",") if h.strip()]

        # Customs hold specific
        if data.get("customsHold"):
            holds.append("CUSTOMS")
        if data.get("freightHold"):
            holds.append("FREIGHT")
        if data.get("lineHold"):
            holds.append("LINE")

        # Charges
        charges = None
        if data.get("demurrage") or data.get("storage"):
            charges = ContainerCharges(
                demurrage_amount=data.get("demurrage"),
                per_diem_amount=data.get("perDiem"),
                total_amount=data.get("totalCharges"),
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
            terminal=data.get("facility") or data.get("terminal"),
            raw_data=data,
        )

    def _map_ictsi_status(self, status: str) -> str:
        """Map ICTSI status to normalized status."""
        status_lower = status.lower()

        if "available" in status_lower or "released" in status_lower:
            return "AVAILABLE"
        elif "yard" in status_lower or "grounded" in status_lower:
            return "IN_YARD"
        elif "discharged" in status_lower:
            return "DISCHARGED"
        elif "vessel" in status_lower or "onboard" in status_lower:
            return "ON_VESSEL"
        elif "departed" in status_lower or "delivered" in status_lower:
            return "DEPARTED"
        elif "hold" in status_lower:
            return "ON_HOLD"
        elif "inbound" in status_lower or "advised" in status_lower:
            return "ADVISED"

        return status.upper() or "UNKNOWN"

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse timestamp to datetime."""
        if not timestamp_str:
            return None
        try:
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            try:
                return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
            except (ValueError, AttributeError):
                try:
                    return datetime.strptime(timestamp_str, "%Y-%m-%d")
                except (ValueError, AttributeError):
                    return None

    async def get_container_events(
        self, container_number: str, port_code: str, since: Optional[datetime] = None
    ) -> list[dict]:
        """Get container event history if available."""
        # ICTSI may have an events endpoint
        return []

    async def get_vessel_schedule(
        self, vessel_name: Optional[str] = None, port_code: Optional[str] = None
    ) -> list[dict]:
        """Vessel schedule not implemented."""
        return []

    async def test_connection(self) -> bool:
        """Test connection by making a dummy request."""
        try:
            # Try to query with an invalid container to test auth
            await self._make_request("/getContainerDetails", {
                "container-type": "IMPORT",
                "facility-id": "TEST",
                "container-number": "TEST0000000",
            })
            return True
        except PortNotFoundError:
            # 404 means auth worked but container not found
            return True
        except PortAuthenticationError:
            return False
        except Exception:
            return False

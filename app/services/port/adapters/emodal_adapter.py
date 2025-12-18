"""
eModal API Adapter.

eModal is used by multiple LA/LB terminals for appointments and container tracking:
- TraPac
- Yusen Terminals (YTI)
- Everport
- SSA Marine
- TTI
- PCT (Pilot)

Documentation: http://coredocs.envaseconnect.cloud/track-trace/providers/pr/emodal.html

Architecture:
- Publish containers to track via POST with X-API-KEY
- Receive updates via Azure Service Bus queue with SharedAccessSignature
- Check status via GET with X-API-KEY
"""

import httpx
from datetime import datetime
from typing import Optional, List, Dict, Any

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


class EModalAdapter(PortAdapter):
    """
    Adapter for eModal container tracking.

    eModal uses a publish/subscribe model:
    1. Publish containers you want to track
    2. Check publish status to confirm tracking
    3. Receive updates via Service Bus queue

    For simpler use cases, this adapter uses the status check endpoint
    which returns current container information.

    Terminals using eModal:
    - TraPac (Los Angeles)
    - Yusen Terminals (YTI)
    - Everport Terminal
    - SSA Marine (multiple locations)
    - TTI (Total Terminals International)
    - PCT (Pacific Container Terminal)
    """

    # eModal API endpoints
    BASE_URL = "https://api.emodal.com"
    PUBLISH_URL = f"{BASE_URL}/trace/containers"
    STATUS_URL = f"{BASE_URL}/trace/containers/status"

    # Service Bus for receiving updates
    SERVICE_BUS_URL = "https://sb-emodalpro.servicebus.windows.net"

    # Terminal codes mapped to eModal facility IDs
    TERMINAL_CODES = {
        "trapac": "TRAPAC",
        "yti": "YTI",
        "everport": "EVERPORT",
        "ssa": "SSA",
        "tti": "TTI",
        "pct": "PCT",
    }

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)
        from app.core.config import get_settings
        settings = get_settings()

        # API key for publishing/checking status
        self.api_key = self.credentials.get("api_key") or getattr(settings, "emodal_api_key", None)

        # SharedAccessSignature for Service Bus queue consumption
        self.sas_token = self.credentials.get("sas_token") or getattr(settings, "emodal_sas_token", None)

        # Topic/subscription for updates
        self.topic = self.credentials.get("topic") or getattr(settings, "emodal_topic", "envase")

    async def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[dict] = None,
        json_data: Optional[dict] = None,
    ) -> dict:
        """Make API request with proper headers."""
        if not headers:
            headers = {}

        if self.api_key:
            headers["X-API-KEY"] = self.api_key

        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    response = await client.get(url, headers=headers, timeout=30.0)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=json_data, timeout=30.0)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers, timeout=30.0)
                else:
                    raise PortAdapterError(f"Unsupported method: {method}")

                if response.status_code == 401:
                    raise PortAuthenticationError("Invalid eModal API key or SAS token")
                elif response.status_code == 404:
                    raise PortNotFoundError("Container not found")
                elif response.status_code == 204:
                    return {"status": "no_content"}

                response.raise_for_status()
                return response.json() if response.content else {}

            except httpx.HTTPStatusError as e:
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    async def publish_container(self, container_number: str, terminal: Optional[str] = None) -> dict:
        """
        Publish a container to start tracking.

        After publishing, eModal will start querying the terminal
        and push updates to the Service Bus queue.
        """
        if not self.api_key:
            raise PortAuthenticationError("eModal API key is required")

        data = {
            "containers": [container_number],
        }

        if terminal:
            data["facility"] = self.TERMINAL_CODES.get(terminal.lower(), terminal)

        result = await self._make_request("POST", self.PUBLISH_URL, json_data=data)
        return result

    async def check_publish_status(self, container_number: str) -> dict:
        """
        Check if a container was successfully published and can be traced.

        Returns current tracking status and container info.
        """
        if not self.api_key:
            raise PortAuthenticationError("eModal API key is required")

        url = f"{self.STATUS_URL}/{container_number}"
        result = await self._make_request("GET", url)
        return result

    async def consume_update(self) -> Optional[dict]:
        """
        Consume one update from the Service Bus queue.

        Returns None if queue is empty (204 response).
        Uses SharedAccessSignature authentication.
        """
        if not self.sas_token:
            raise PortAuthenticationError("eModal SAS token is required for queue consumption")

        url = f"{self.SERVICE_BUS_URL}/{self.topic}/subscriptions/containerupdates/messages/head"
        headers = {"Authorization": f"SharedAccessSignature {self.sas_token}"}

        result = await self._make_request("DELETE", url, headers=headers)

        if result.get("status") == "no_content":
            return None

        return result

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """
        Track container via eModal.

        This method:
        1. Publishes the container if not already tracked
        2. Checks the publish status for current info
        3. Returns normalized container data
        """
        try:
            # First try to get status (works if already published)
            try:
                data = await self.check_publish_status(container_number)
            except PortNotFoundError:
                # Not published yet, publish and check again
                await self.publish_container(container_number)
                data = await self.check_publish_status(container_number)

            if not data or data.get("status") == "not_found":
                raise PortNotFoundError(f"Container {container_number} not found in eModal")

            # Map eModal response to standard format
            status = self._map_emodal_status(data.get("status", "UNKNOWN"))

            # Extract location
            location = ContainerLocation(
                terminal=data.get("facility") or data.get("terminal"),
                yard_location=data.get("location") or data.get("position"),
                port=data.get("port", "Los Angeles/Long Beach"),
                country="US",
                timestamp=self._parse_timestamp(data.get("lastUpdate")),
            )

            # Extract vessel info
            vessel = None
            if data.get("vesselName"):
                vessel = VesselInfo(
                    name=data.get("vesselName"),
                    voyage=data.get("voyage"),
                    eta=self._parse_timestamp(data.get("eta")),
                )

            # Extract dates
            dates = ContainerDates(
                discharge_date=self._parse_timestamp(data.get("dischargeDate")),
                last_free_day=self._parse_timestamp(data.get("lastFreeDay") or data.get("lfd")),
                ingate_timestamp=self._parse_timestamp(data.get("ingateTime")),
                outgate_timestamp=self._parse_timestamp(data.get("outgateTime")),
            )

            # Extract container details
            container_details = ContainerDetails(
                size=data.get("size") or data.get("length"),
                type=data.get("type") or data.get("equipmentType"),
                weight=data.get("weight"),
                shipping_line=data.get("line") or data.get("shippingLine"),
            )

            # Extract holds
            holds = data.get("holds", [])
            if isinstance(holds, str):
                holds = [holds] if holds else []

            # Extract charges
            charges = None
            if data.get("demurrage") or data.get("charges"):
                charges = ContainerCharges(
                    demurrage=data.get("demurrage"),
                    total_charges=data.get("charges"),
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

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error tracking container: {str(e)}")

    def _map_emodal_status(self, emodal_status: str) -> str:
        """Map eModal status to normalized status."""
        status_map = {
            "INBOUND": "IN_TRANSIT",
            "ARRIVED": "ARRIVED",
            "DISCHARGED": "DISCHARGED",
            "ON_TERMINAL": "IN_YARD",
            "AVAILABLE": "AVAILABLE",
            "HOLD": "ON_HOLD",
            "RELEASED": "RELEASED",
            "OUTGATED": "OUTGATE",
            "DEPARTED": "DEPARTED",
            "NOT_FOUND": "NOT_FOUND",
        }
        return status_map.get(emodal_status.upper(), emodal_status or "UNKNOWN")

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse eModal timestamp to datetime."""
        if not timestamp_str:
            return None
        try:
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    async def get_container_events(
        self, container_number: str, port_code: str, since: Optional[datetime] = None
    ) -> list[dict]:
        """Get container events - consume from queue."""
        events = []

        # Consume up to 10 events from queue
        for _ in range(10):
            update = await self.consume_update()
            if not update:
                break

            if update.get("containerNumber") == container_number:
                events.append({
                    "event_type": update.get("eventType", "UPDATE"),
                    "timestamp": self._parse_timestamp(update.get("timestamp")),
                    "location": update.get("facility"),
                    "description": update.get("description"),
                    "metadata": update,
                })

        return events

    async def get_vessel_schedule(
        self, vessel_name: Optional[str] = None, port_code: Optional[str] = None
    ) -> list[dict]:
        """eModal doesn't provide vessel schedule - return empty list."""
        return []

    async def test_connection(self) -> bool:
        """Test connection by checking API key validity."""
        try:
            # Try to check status of a dummy container
            await self.check_publish_status("TEST0000000")
            return True
        except PortNotFoundError:
            # 404 is expected for dummy container, but means API is working
            return True
        except Exception:
            return False

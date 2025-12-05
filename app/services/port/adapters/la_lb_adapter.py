import httpx
from datetime import datetime
from typing import Optional

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


class LALBAdapter(PortAdapter):
    """Adapter for LA/Long Beach terminals (APM Terminals and others)."""

    APM_BASE_URL = "https://api.apmterminals.com"
    # Terminal-specific URLs may vary

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)
        self.api_key = self.credentials.get("api_key")
        self.terminal = config.get("terminal", "APM") if config else "APM"  # APM, TTI, Fenix, etc.

    async def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make authenticated API request."""
        if not self.api_key:
            raise PortAuthenticationError("LA/LB terminal API key is required")

        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.APM_BASE_URL}{endpoint}",
                    headers=headers,
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError("Invalid API key")
                elif e.response.status_code == 404:
                    raise PortNotFoundError(f"Container not found: {endpoint}")
                elif e.response.status_code == 429:
                    raise PortAdapterError("Rate limit exceeded")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """Track container using APM Terminals or terminal-specific API."""
        try:
            # Use import availability endpoint
            data = await self._make_request(
                "/import-availability",
                params={"container_number": container_number, "terminal": self.terminal},
            )

            # Parse response and normalize
            container_data = data.get("container", {})
            status = container_data.get("status", "UNKNOWN")
            terminal = container_data.get("terminal", self.terminal)

            # Determine port name based on terminal
            port_name = "Los Angeles" if "LA" in terminal or "Los Angeles" in terminal else "Long Beach"

            # Extract location information
            location = ContainerLocation(
                terminal=terminal,
                yard_location=container_data.get("yard_location"),
                gate_status=container_data.get("gate_status"),
                port=port_name,
                country="US",
                timestamp=datetime.fromisoformat(container_data["timestamp"]) if container_data.get("timestamp") else None,
            )

            # Extract vessel information
            vessel = None
            if container_data.get("vessel_name"):
                vessel = VesselInfo(
                    name=container_data.get("vessel_name"),
                    voyage=container_data.get("voyage_number"),
                    eta=datetime.fromisoformat(container_data["eta"]) if container_data.get("eta") else None,
                )

            # Extract dates
            dates = None
            if container_data.get("discharge_date") or container_data.get("last_free_day"):
                dates = ContainerDates(
                    discharge_date=datetime.fromisoformat(container_data["discharge_date"])
                    if container_data.get("discharge_date")
                    else None,
                    last_free_day=datetime.fromisoformat(container_data["last_free_day"])
                    if container_data.get("last_free_day")
                    else None,
                    ingate_timestamp=datetime.fromisoformat(container_data["ingate_timestamp"])
                    if container_data.get("ingate_timestamp")
                    else None,
                    outgate_timestamp=datetime.fromisoformat(container_data["outgate_timestamp"])
                    if container_data.get("outgate_timestamp")
                    else None,
                )

            # Extract container details
            container_details = None
            if container_data.get("size") or container_data.get("type"):
                container_details = ContainerDetails(
                    size=container_data.get("size"),
                    type=container_data.get("type"),
                    weight=container_data.get("weight"),
                    seal_number=container_data.get("seal_number"),
                    shipping_line=container_data.get("shipping_line"),
                )

            # Extract holds
            holds = container_data.get("holds", [])

            # Extract charges
            charges = None
            if container_data.get("demurrage") or container_data.get("per_diem"):
                charges = ContainerCharges(
                    demurrage=container_data.get("demurrage"),
                    per_diem=container_data.get("per_diem"),
                    detention=container_data.get("detention"),
                    total_charges=container_data.get("total_charges"),
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
                terminal=terminal,
                raw_data=container_data,
            )

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error tracking container: {str(e)}")

    async def get_container_events(
        self, container_number: str, port_code: str, since: Optional[datetime] = None
    ) -> list[dict]:
        """Get container event history."""
        try:
            params = {"container_number": container_number, "terminal": self.terminal}
            if since:
                params["since"] = since.isoformat()

            data = await self._make_request("/container-events", params=params)
            events = data.get("events", [])

            return [
                {
                    "event_type": event.get("event_type"),
                    "timestamp": datetime.fromisoformat(event["timestamp"]) if event.get("timestamp") else None,
                    "location": event.get("location"),
                    "description": event.get("description"),
                    "metadata": event,
                }
                for event in events
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting container events: {str(e)}")

    async def get_vessel_schedule(self, vessel_name: Optional[str] = None, port_code: Optional[str] = None) -> list[dict]:
        """Get vessel schedule from APM Terminals."""
        try:
            params = {"terminal": self.terminal}
            if vessel_name:
                params["vessel_name"] = vessel_name
            if port_code:
                params["port_code"] = port_code

            data = await self._make_request("/vessel-schedules", params=params)
            return data.get("schedules", [])
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting vessel schedule: {str(e)}")

    async def test_connection(self) -> bool:
        """Test connection by making a simple API request."""
        try:
            await self.get_vessel_schedule()
            return True
        except PortAuthenticationError:
            return False
        except Exception:
            # Other errors might be OK for connection test
            return True


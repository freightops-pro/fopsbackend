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


class SavannahAdapter(PortAdapter):
    """Adapter for Georgia Ports Authority (Savannah) WebAccess integration."""

    BASE_URL = "https://gaports.com"
    WEBACCESS_URL = "https://gaports.com/tools/tracking"

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)
        self.username = self.credentials.get("username")
        self.password = self.credentials.get("password")
        # WebAccess may require session-based authentication
        self.session_token: Optional[str] = None

    async def _authenticate(self) -> str:
        """Authenticate with WebAccess and get session token."""
        if self.session_token:
            return self.session_token

        if not self.username or not self.password:
            raise PortAuthenticationError("Savannah WebAccess credentials (username, password) are required")

        # Note: This is a placeholder - actual implementation may require
        # web scraping with Selenium/Playwright for WebAccess portal
        # For now, we'll use a mock API approach if available
        async with httpx.AsyncClient() as client:
            try:
                # Attempt API-based auth if available
                response = await client.post(
                    f"{self.BASE_URL}/api/auth/login",
                    json={"username": self.username, "password": self.password},
                    timeout=30.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    self.session_token = data.get("token")
                    return self.session_token
                else:
                    # Fallback: WebAccess uses web portal, would need browser automation
                    raise PortAuthenticationError(
                        "WebAccess requires web portal authentication. Browser automation not yet implemented."
                    )
            except httpx.HTTPStatusError:
                raise PortAuthenticationError("Invalid WebAccess credentials")
            except Exception as e:
                raise PortAdapterError(f"Error authenticating: {str(e)}")

    async def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make authenticated API request."""
        token = await self._authenticate()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}{endpoint}",
                    headers=headers,
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError("Authentication failed")
                elif e.response.status_code == 404:
                    raise PortNotFoundError(f"Container not found: {endpoint}")
                elif e.response.status_code == 429:
                    raise PortAdapterError("Rate limit exceeded")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """Track container using Georgia Ports Authority WebAccess."""
        try:
            # Try API endpoint first
            try:
                data = await self._make_request(
                    "/api/tracking/containers",
                    params={"container_number": container_number},
                )
            except PortAuthenticationError:
                # If API not available, would need web scraping
                raise PortAdapterError(
                    "Savannah WebAccess requires web portal access. "
                    "Browser automation (Selenium/Playwright) implementation needed."
                )

            # Parse response and normalize
            container_data = data.get("container", {})
            status = container_data.get("status", "UNKNOWN")
            terminal = container_data.get("terminal", "Garden City Terminal")

            # Extract location information
            location = ContainerLocation(
                terminal=terminal,
                yard_location=container_data.get("yard_location"),
                gate_status=container_data.get("gate_status"),
                port="Savannah",
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
            params = {"container_number": container_number}
            if since:
                params["since"] = since.isoformat()

            data = await self._make_request("/api/tracking/containers/events", params=params)
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
        """Get vessel schedule."""
        try:
            params = {}
            if vessel_name:
                params["vessel_name"] = vessel_name
            if port_code:
                params["port_code"] = port_code

            data = await self._make_request("/api/tracking/vessel-schedules", params=params)
            return data.get("schedules", [])
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting vessel schedule: {str(e)}")

    async def test_connection(self) -> bool:
        """Test connection by attempting authentication."""
        try:
            await self._authenticate()
            return True
        except Exception:
            return False


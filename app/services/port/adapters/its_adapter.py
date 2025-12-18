"""
ITS (International Transportation Service) Adapter.

ITS operates a container terminal at the Port of Long Beach.

Documentation: http://coredocs.envaseconnect.cloud/track-trace/providers/rt/its.html

Endpoints:
- Login: POST https://api.itslb.com/tms2/account/login
- Container Availability: POST https://api.itslb.com/tms2/import/containeravailability
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


class ITSAdapter(PortAdapter):
    """
    Adapter for ITS (International Transportation Service) Long Beach.

    ITS is a container terminal at the Port of Long Beach.
    Requires username/password authentication.

    Response includes:
    - Container availability status
    - Last free day
    - Holds and fees
    - Vessel information
    """

    BASE_URL = "https://api.itslb.com/tms2"
    LOGIN_URL = f"{BASE_URL}/account/login"
    AVAILABILITY_URL = f"{BASE_URL}/import/containeravailability"

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)
        from app.core.config import get_settings
        settings = get_settings()

        self.username = self.credentials.get("username") if self.credentials else None
        self.password = self.credentials.get("password") if self.credentials else None

        # Fall back to settings if no credentials passed
        if not self.username:
            self.username = getattr(settings, "its_username", None)
        if not self.password:
            self.password = getattr(settings, "its_password", None)

        self.auth_token: Optional[str] = None

    async def _login(self) -> str:
        """Authenticate and get session token."""
        if not self.username or not self.password:
            raise PortAuthenticationError("ITS credentials (username, password) are required")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.LOGIN_URL,
                    json={
                        "username": self.username,
                        "password": self.password,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

                self.auth_token = data.get("token") or data.get("access_token")
                if not self.auth_token:
                    raise PortAuthenticationError("No token in login response")

                return self.auth_token

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError("Invalid ITS credentials")
                raise PortAdapterError(f"Login failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error during login: {str(e)}")

    async def _make_request(self, endpoint: str, data: dict) -> dict:
        """Make authenticated API request."""
        if not self.auth_token:
            await self._login()

        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}{endpoint}",
                    headers=headers,
                    json=data,
                    timeout=30.0,
                )

                # Re-auth if token expired
                if response.status_code == 401:
                    await self._login()
                    headers["Authorization"] = f"Bearer {self.auth_token}"
                    response = await client.post(
                        f"{self.BASE_URL}{endpoint}",
                        headers=headers,
                        json=data,
                        timeout=30.0,
                    )

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise PortNotFoundError("Container not found")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """
        Track container via ITS API.

        Request format:
        {
            "containerNumbers": ["MAEU1234567"]
        }
        """
        try:
            data = {"containerNumbers": [container_number.upper()]}
            response = await self._make_request("/import/containeravailability", data)

            # Parse response - format may vary
            containers = response.get("containers", response.get("data", []))
            if not containers:
                raise PortNotFoundError(f"Container {container_number} not found at ITS")

            container = containers[0] if isinstance(containers, list) else containers

            return self._build_tracking_response(container_number, port_code, container)

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error tracking container: {str(e)}")

    def _build_tracking_response(
        self,
        container_number: str,
        port_code: str,
        data: dict,
    ) -> ContainerTrackingResponse:
        """Build ContainerTrackingResponse from ITS data."""

        # Map status
        status = data.get("status") or data.get("availability") or "UNKNOWN"
        status = self._map_its_status(status)

        # Location
        location = ContainerLocation(
            terminal="ITS",
            yard_location=data.get("location") or data.get("yardLocation"),
            port=port_code,
            country="US",
            timestamp=self._parse_timestamp(data.get("lastMoveTime")),
        )

        # Vessel info
        vessel = None
        vessel_name = data.get("vesselName") or data.get("vessel")
        if vessel_name:
            vessel = VesselInfo(
                name=vessel_name,
                voyage=data.get("voyage") or data.get("voyageNumber"),
                eta=self._parse_timestamp(data.get("eta")),
                ata=self._parse_timestamp(data.get("ata")),
            )

        # Dates
        dates = ContainerDates(
            discharge_date=self._parse_timestamp(data.get("dischargeDate")),
            last_free_day=self._parse_timestamp(data.get("lastFreeDay") or data.get("lfd")),
            ingate_timestamp=self._parse_timestamp(data.get("ingateTime")),
            outgate_timestamp=self._parse_timestamp(data.get("outgateTime")),
        )

        # Container details
        container_details = ContainerDetails(
            size=data.get("size") or data.get("containerSize"),
            type=data.get("type") or data.get("containerType"),
            weight=data.get("weight") or data.get("grossWeight"),
            shipping_line=data.get("line") or data.get("shippingLine") or data.get("ssl"),
        )

        # Holds
        holds = []
        hold_data = data.get("holds") or data.get("holdStatus") or []
        if isinstance(hold_data, list):
            holds = hold_data
        elif isinstance(hold_data, str) and hold_data:
            holds = [h.strip() for h in hold_data.split(",") if h.strip()]

        # Charges
        charges = None
        if data.get("demurrage") or data.get("fees"):
            charges = ContainerCharges(
                demurrage_amount=data.get("demurrage"),
                per_diem_amount=data.get("perDiem"),
                total_amount=data.get("totalFees") or data.get("fees"),
            )

        # Check availability
        is_available = data.get("available", False) or status == "AVAILABLE"
        if is_available and holds:
            status = "ON_HOLD"

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
            terminal="ITS",
            raw_data=data,
        )

    def _map_its_status(self, status: str) -> str:
        """Map ITS status to normalized status."""
        status_lower = status.lower()

        if "available" in status_lower or "released" in status_lower:
            return "AVAILABLE"
        elif "yard" in status_lower or "on terminal" in status_lower:
            return "IN_YARD"
        elif "discharged" in status_lower:
            return "DISCHARGED"
        elif "vessel" in status_lower or "inbound" in status_lower:
            return "ON_VESSEL"
        elif "departed" in status_lower or "out" in status_lower:
            return "DEPARTED"
        elif "hold" in status_lower:
            return "ON_HOLD"

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
                    return datetime.strptime(timestamp_str, "%m/%d/%Y %H:%M")
                except (ValueError, AttributeError):
                    return None

    async def get_container_events(
        self, container_number: str, port_code: str, since: Optional[datetime] = None
    ) -> list[dict]:
        """ITS may not provide detailed event history."""
        return []

    async def get_vessel_schedule(
        self, vessel_name: Optional[str] = None, port_code: Optional[str] = None
    ) -> list[dict]:
        """Vessel schedule not implemented."""
        return []

    async def test_connection(self) -> bool:
        """Test connection by attempting login."""
        try:
            await self._login()
            return True
        except Exception:
            return False

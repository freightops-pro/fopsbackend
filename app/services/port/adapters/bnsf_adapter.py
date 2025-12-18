"""
BNSF Railway Intermodal API Adapter.

BNSF is one of the largest freight railroad networks in North America.
This adapter provides container tracking for rail intermodal shipments.

Documentation: http://coredocs.envaseconnect.cloud/track-trace/providers/rt/bnsf.html

Endpoints:
- Unit Details: POST https://api.bnsf.com:6443/v3/unit-details
- J1 Receipts: POST https://api.bnsf.com:6443/v1/j1-receipts

Authentication: OAuth2 Bearer token
"""

import httpx
from datetime import datetime, timedelta
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


class BNSFAdapter(PortAdapter):
    """
    Adapter for BNSF Railway Intermodal API.

    Tracks containers moving via BNSF rail network.
    Useful for inland intermodal moves after port pickup.

    Response includes:
    - Equipment status (in inventory, departed, etc.)
    - Origin/destination stations
    - Load/empty status
    - Equipment dimensions and weight
    - J1 receipts for outgate documentation
    """

    BASE_URL = "https://api.bnsf.com:6443"
    TOKEN_URL = "https://api.bnsf.com:6443/oauth/token"

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)
        from app.core.config import get_settings
        settings = get_settings()

        self.client_id = self.credentials.get("client_id") or getattr(settings, "bnsf_client_id", None)
        self.client_secret = self.credentials.get("client_secret") or getattr(settings, "bnsf_client_secret", None)
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    async def _get_access_token(self) -> str:
        """Get OAuth2 access token."""
        if self.access_token and self.token_expires_at and datetime.utcnow() < self.token_expires_at:
            return self.access_token

        if not self.client_id or not self.client_secret:
            raise PortAuthenticationError("BNSF credentials (client_id, client_secret) are required")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)
                self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
                return self.access_token
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError("Invalid BNSF credentials")
                raise PortAdapterError(f"Failed to get access token: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error getting access token: {str(e)}")

    async def _make_request(self, endpoint: str, data: dict) -> dict:
        """Make authenticated POST API request."""
        token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
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
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError("Authentication failed")
                elif e.response.status_code == 404:
                    raise PortNotFoundError("Unit not found")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    def _parse_container_number(self, container_number: str) -> dict:
        """
        Parse container number into BNSF format.

        BNSF requires:
        - equipmentInitial: First 4 characters (owner code)
        - equipmentNumber: Last 6-7 characters (serial number)
        """
        container_number = container_number.replace(" ", "").replace("-", "").upper()

        if len(container_number) >= 10:
            return {
                "equipmentInitial": container_number[:4],
                "equipmentNumber": container_number[4:],
            }
        else:
            raise PortAdapterError(f"Invalid container number format: {container_number}")

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """
        Track container via BNSF unit-details endpoint.

        Request format:
        {
            "intermodalUnits": [
                {"equipmentInitial": "MAEU", "equipmentNumber": "1234567"}
            ]
        }
        """
        try:
            unit_info = self._parse_container_number(container_number)

            data = {
                "intermodalUnits": [unit_info]
            }

            response = await self._make_request("/v3/unit-details", data)

            # Parse response
            units = response.get("intermodalUnits", [])
            if not units:
                raise PortNotFoundError(f"Container {container_number} not found in BNSF")

            unit = units[0]

            # Check if in BNSF inventory
            status_name = unit.get("derivedEquipmentStatusName", "")
            if "Not in BNSF Inventory" in status_name:
                # Container not currently on BNSF network
                return self.normalize_tracking_response(
                    container_number=container_number,
                    port_code=port_code,
                    status="NOT_IN_NETWORK",
                    location=None,
                    raw_data=unit,
                )

            # Map status
            status = self._map_bnsf_status(status_name, unit.get("loadEmptyChassisCode", ""))

            # Extract location
            location = ContainerLocation(
                terminal=unit.get("currentStation") or unit.get("originStation"),
                yard_location=unit.get("trackLocation"),
                port=unit.get("originStation"),
                country="US",
                timestamp=self._parse_timestamp(unit.get("lastEventDateTime")),
            )

            # Extract dates
            dates = ContainerDates(
                ingate_timestamp=self._parse_timestamp(unit.get("receivedDateTime")),
                outgate_timestamp=self._parse_timestamp(unit.get("releasedDateTime")),
            )

            # Extract container details
            container_details = ContainerDetails(
                size=unit.get("equipmentLength"),
                type=unit.get("equipmentType"),
                weight=unit.get("grossWeight"),
                shipping_line=unit.get("ownerCode") or unit_info["equipmentInitial"],
            )

            # Determine if loaded or empty
            load_status = unit.get("loadEmptyChassisCode", "")
            if load_status == "L":
                container_details.type = f"{container_details.type or ''} (LOADED)"
            elif load_status == "E":
                container_details.type = f"{container_details.type or ''} (EMPTY)"

            return self.normalize_tracking_response(
                container_number=container_number,
                port_code=port_code,
                status=status,
                location=location,
                dates=dates,
                container_details=container_details,
                terminal=unit.get("currentStation"),
                raw_data=unit,
            )

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error tracking container: {str(e)}")

    async def get_j1_receipts(
        self,
        container_numbers: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_pdf: bool = False,
    ) -> List[dict]:
        """
        Get J1 receipts (outgate documentation) for containers.

        J1 receipts document when containers were released from BNSF.

        Args:
            container_numbers: List of container numbers
            start_date: Start of date range
            end_date: End of date range
            include_pdf: Whether to include PDF receipt documents

        Returns:
            List of J1 receipt data
        """
        try:
            # Default to last 30 days
            if not start_date:
                start_date = datetime.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = datetime.utcnow()

            data = {
                "unitList": container_numbers,
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
                "j1ReceiptData": True,
                "j1ReceiptPdf": include_pdf,
            }

            response = await self._make_request("/v1/j1-receipts", data)

            receipts = response.get("j1Receipts", [])
            return [
                {
                    "container_number": r.get("equipmentId"),
                    "receipt_date": self._parse_timestamp(r.get("receiptDate")),
                    "station": r.get("station"),
                    "shipper": r.get("shipper"),
                    "consignee": r.get("consignee"),
                    "weight": r.get("weight"),
                    "seal_number": r.get("sealNumber"),
                    "pdf_data": r.get("pdfData") if include_pdf else None,
                    "metadata": r,
                }
                for r in receipts
            ]

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting J1 receipts: {str(e)}")

    def _map_bnsf_status(self, status_name: str, load_code: str) -> str:
        """Map BNSF status to normalized status."""
        status_lower = status_name.lower()

        if "not in" in status_lower or "not found" in status_lower:
            return "NOT_IN_NETWORK"
        elif "received" in status_lower or "in terminal" in status_lower:
            return "IN_YARD"
        elif "loaded" in status_lower or "on train" in status_lower:
            return "IN_TRANSIT"
        elif "arrived" in status_lower:
            return "ARRIVED"
        elif "released" in status_lower or "outgated" in status_lower:
            return "RELEASED"
        elif "available" in status_lower:
            return "AVAILABLE"

        return status_name or "UNKNOWN"

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse BNSF timestamp to datetime."""
        if not timestamp_str:
            return None
        try:
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            try:
                return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
            except (ValueError, AttributeError):
                return None

    async def get_container_events(
        self, container_number: str, port_code: str, since: Optional[datetime] = None
    ) -> list[dict]:
        """Get container events from BNSF."""
        # BNSF doesn't have a separate events endpoint
        # Return J1 receipts as events
        try:
            receipts = await self.get_j1_receipts([container_number], start_date=since)
            return [
                {
                    "event_type": "J1_RECEIPT",
                    "timestamp": r["receipt_date"],
                    "location": r["station"],
                    "description": f"J1 Receipt at {r['station']}",
                    "metadata": r["metadata"],
                }
                for r in receipts
            ]
        except Exception as e:
            raise PortAdapterError(f"Error getting container events: {str(e)}")

    async def get_vessel_schedule(
        self, vessel_name: Optional[str] = None, port_code: Optional[str] = None
    ) -> list[dict]:
        """BNSF is rail, not vessel - return empty list."""
        return []

    async def test_connection(self) -> bool:
        """Test connection by getting access token."""
        try:
            await self._get_access_token()
            return True
        except Exception:
            return False

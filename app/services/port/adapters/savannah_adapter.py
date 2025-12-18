"""
Georgia Ports Authority (Savannah) Adapter - Navis N4 EVP Integration.

GPA operates two major terminals using Navis N4 TOS:
- Garden City Terminal (GCT) - One of the largest container terminals in North America
- Ocean Terminal - Breakbulk and container operations

Uses Navis N4 EVP (External Visibility Platform) API, similar to Port Houston.
Also supports WebAccess portal for legacy access.
"""

import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, List

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


# GPA Terminal configurations
TERMINAL_CONFIGS = {
    "GCT": {
        "name": "Garden City Terminal",
        "firms_code": "S401",
        "port": "Savannah",
        "facility_id": "GCT",
    },
    "OCEAN": {
        "name": "Ocean Terminal",
        "firms_code": "S403",
        "port": "Savannah",
        "facility_id": "OCEAN",
    },
}


class SavannahAdapter(PortAdapter):
    """
    Adapter for Georgia Ports Authority (Savannah) using Navis N4 EVP API.

    GPA uses Navis N4 as their Terminal Operating System (TOS), similar to Port Houston.
    The EVP API provides container tracking, vessel schedules, and gate information.

    Authentication:
    - OAuth2 client credentials flow for N4 EVP API
    - WebAccess portal for web-based access (legacy)

    Terminals:
    - Garden City Terminal (GCT): Main container terminal
    - Ocean Terminal: Breakbulk and container operations
    """

    # GPA Navis N4 EVP API endpoints
    BASE_URL = "https://api.gaports.naviscloudops.com/v3/evp"
    TOKEN_URL = "https://auth.gaports.naviscloudops.com/auth/realms/gpaprod/protocol/openid-connect/token"

    # Alternative: WebAccess portal (requires session auth)
    WEBACCESS_URL = "https://webaccess.gaports.com"

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)
        from app.core.config import get_settings
        settings = get_settings()

        # Terminal selection
        self.terminal = (config or {}).get("terminal", "GCT")
        self.terminal_config = TERMINAL_CONFIGS.get(self.terminal, TERMINAL_CONFIGS["GCT"])

        # N4 EVP API credentials (OAuth2)
        self.client_id = self.credentials.get("client_id") or settings.gpa_savannah_client_id
        self.client_secret = self.credentials.get("client_secret") or settings.gpa_savannah_client_secret

        # WebAccess credentials (session-based, fallback)
        self.username = self.credentials.get("username")
        self.password = self.credentials.get("password")

        # Token caching
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    async def _get_access_token(self) -> str:
        """Get OAuth2 access token using client credentials flow."""
        if self.access_token and self.token_expires_at and datetime.utcnow() < self.token_expires_at:
            return self.access_token

        if not self.client_id or not self.client_secret:
            raise PortAuthenticationError(
                "GPA Savannah credentials (client_id, client_secret) are required. "
                "Contact GPA for N4 EVP API access."
            )

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
                    raise PortAuthenticationError("Invalid GPA Savannah credentials")
                raise PortAdapterError(f"Failed to get access token: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error getting access token: {str(e)}")

    async def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make authenticated GET request to N4 EVP API."""
        token = await self._get_access_token()
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
                    # Clear token and retry once
                    self.access_token = None
                    self.token_expires_at = None
                    raise PortAuthenticationError("Authentication failed")
                elif e.response.status_code == 404:
                    raise PortNotFoundError(f"Resource not found: {endpoint}")
                elif e.response.status_code == 429:
                    raise PortAdapterError("Rate limit exceeded")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    async def _make_post_request(self, endpoint: str, data: dict, params: Optional[dict] = None) -> dict:
        """Make authenticated POST request to N4 EVP API."""
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}{endpoint}",
                    headers=headers,
                    json=data,
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError("Authentication failed")
                elif e.response.status_code == 404:
                    raise PortNotFoundError(f"Resource not found: {endpoint}")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """
        Track container using GPA Navis N4 EVP API.

        Uses the /inventory/units endpoint similar to Port Houston.
        Response follows Navis UnitPayload structure.
        """
        try:
            # Add facility filter for terminal
            params = {
                "unitId": container_number,
                "facilityId": self.terminal_config.get("facility_id"),
            }

            data = await self._make_request("/inventory/units", params=params)

            # Handle Navis response format
            units = data if isinstance(data, list) else data.get("units", data.get("content", []))
            if not units:
                raise PortNotFoundError(f"Container {container_number} not found at GPA Savannah")

            unit = units[0] if isinstance(units, list) else units

            # Map Navis status
            transit_state = unit.get("transitState", "")
            visit_state = unit.get("visitState", "")
            status = self._map_navis_status(transit_state, visit_state)

            # Extract terminal
            scope = unit.get("scope", {})
            terminal = scope.get("facility_id") or unit.get("facility", {}).get("facilityId", "")
            terminal_name = self.terminal_config.get("name", terminal)

            # Extract location
            last_known_position = unit.get("lastKnownPosition", {})
            location = ContainerLocation(
                terminal=terminal_name,
                yard_location=last_known_position.get("posSlot") or last_known_position.get("positionSlot"),
                gate_status=visit_state,
                port="Savannah",
                country="US",
                timestamp=self._parse_navis_timestamp(unit.get("timeIn")),
            )

            # Extract vessel info
            vessel = None
            actual_ib_visit = unit.get("actualIbVisit", {})
            if actual_ib_visit:
                vessel = VesselInfo(
                    name=actual_ib_visit.get("vesselName") or actual_ib_visit.get("carrierName"),
                    voyage=actual_ib_visit.get("visitId") or actual_ib_visit.get("inVoyNbr"),
                    eta=self._parse_navis_timestamp(actual_ib_visit.get("eta") or actual_ib_visit.get("publishedEta")),
                )

            # Extract dates
            ufv_billing = unit.get("ufvBilling", {})
            dates = ContainerDates(
                discharge_date=self._parse_navis_timestamp(unit.get("timeOfLoading") or unit.get("timeDischarge")),
                last_free_day=self._parse_navis_timestamp(ufv_billing.get("lastFreeDay") or ufv_billing.get("paidThruDay")),
                ingate_timestamp=self._parse_navis_timestamp(unit.get("timeIn")),
                outgate_timestamp=self._parse_navis_timestamp(unit.get("timeOut")),
            )

            # Extract container details
            contents = unit.get("contents", {})
            seals = unit.get("seals", [])
            seal_number = None
            if seals and isinstance(seals, list) and len(seals) > 0:
                seal_number = seals[0].get("sealId") if isinstance(seals[0], dict) else seals[0]
            else:
                seal_number = unit.get("sealNbr1")

            container_details = ContainerDetails(
                size=unit.get("basicLength") or unit.get("nominalLength"),
                type=unit.get("freightKind"),
                weight=contents.get("goodsAndCtrWtKg") or unit.get("grossWeight"),
                seal_number=seal_number,
                shipping_line=unit.get("line") or unit.get("lineOperator", {}).get("id"),
            )

            # Extract holds
            holds = self._extract_holds(unit.get("stopFlags", {}))

            # Extract charges
            charges = None
            if ufv_billing:
                charges = ContainerCharges(
                    demurrage=ufv_billing.get("demurrageOwed") or ufv_billing.get("demurrage"),
                    per_diem=ufv_billing.get("storageOwed") or ufv_billing.get("storage"),
                    detention=ufv_billing.get("detention"),
                    total_charges=ufv_billing.get("totalOwed") or ufv_billing.get("totalCharges"),
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
                terminal=terminal_name,
                raw_data=unit,
            )

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error tracking container: {str(e)}")

    def _map_navis_status(self, transit_state: str, visit_state: str) -> str:
        """Map Navis transitState/visitState to normalized status."""
        status_map = {
            "S10_ADVISED": "ADVISED",
            "S20_INBOUND": "IN_TRANSIT",
            "S30_ECIN": "INGATE",
            "S40_YARD": "IN_YARD",
            "S50_ECOUT": "OUTGATE",
            "S60_RETIRED": "DEPARTED",
        }
        return status_map.get(transit_state, transit_state or "UNKNOWN")

    def _parse_navis_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse Navis timestamp format to datetime."""
        if not timestamp_str:
            return None
        try:
            return datetime.fromisoformat(str(timestamp_str).replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _extract_holds(self, stop_flags: dict) -> list[str]:
        """Extract hold flags from Navis stopFlags."""
        holds = []
        if stop_flags.get("stoppedVessel"):
            holds.append("VESSEL_HOLD")
        if stop_flags.get("stoppedRail"):
            holds.append("RAIL_HOLD")
        if stop_flags.get("stoppedRoad"):
            holds.append("ROAD_HOLD")
        if stop_flags.get("stoppedCustoms"):
            holds.append("CUSTOMS_HOLD")
        if stop_flags.get("stoppedUsda"):
            holds.append("USDA_HOLD")
        if stop_flags.get("stoppedFda"):
            holds.append("FDA_HOLD")
        if stop_flags.get("stoppedLine"):
            holds.append("LINE_HOLD")
        if stop_flags.get("stoppedTerminal"):
            holds.append("TERMINAL_HOLD")
        return holds

    async def get_container_events(
        self, container_number: str, port_code: str, since: Optional[datetime] = None
    ) -> list[dict]:
        """Get container event history from N4 EVP API."""
        try:
            params = {
                "appliedToId": container_number,
                "facilityId": self.terminal_config.get("facility_id"),
            }
            if since:
                params["fromDate"] = since.isoformat()

            data = await self._make_request("/service/events", params=params)
            events = data if isinstance(data, list) else data.get("events", data.get("content", []))

            return [
                {
                    "event_type": event.get("eventType") or event.get("eventTypeId"),
                    "timestamp": self._parse_navis_timestamp(event.get("eventTime") or event.get("placedTime")),
                    "location": event.get("facility", {}).get("facilityId")
                    if isinstance(event.get("facility"), dict)
                    else event.get("facilityId"),
                    "description": event.get("notes") or event.get("eventType"),
                    "metadata": event,
                }
                for event in events
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting container events: {str(e)}")

    async def get_vessel_schedule(
        self, vessel_name: Optional[str] = None, port_code: Optional[str] = None
    ) -> list[dict]:
        """Get vessel schedule from N4 EVP API."""
        try:
            params = {"facilityId": self.terminal_config.get("facility_id")}
            if vessel_name:
                params["vesName"] = vessel_name

            data = await self._make_request("/vessel/vesselvisits", params=params)
            schedules = data if isinstance(data, list) else data.get("vesselVisits", data.get("content", []))

            return [
                {
                    "vessel_name": schedule.get("vesName") or schedule.get("vesselName"),
                    "voyage": schedule.get("visitId"),
                    "eta": self._parse_navis_timestamp(schedule.get("publishedEta") or schedule.get("eta")),
                    "etd": self._parse_navis_timestamp(schedule.get("publishedEtd") or schedule.get("etd")),
                    "ata": self._parse_navis_timestamp(schedule.get("ata")),
                    "atd": self._parse_navis_timestamp(schedule.get("atd")),
                    "berth": schedule.get("berth"),
                    "terminal": self.terminal_config.get("name"),
                    "status": schedule.get("visitPhase"),
                }
                for schedule in schedules
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting vessel schedule: {str(e)}")

    async def get_active_vessel_visits(self) -> list[dict]:
        """Get active vessel visits at GPA terminals."""
        try:
            params = {"facilityId": self.terminal_config.get("facility_id")}
            data = await self._make_request("/vessel/vesselvisits/active", params=params)
            visits = data if isinstance(data, list) else data.get("vesselVisits", data.get("content", []))

            return [
                {
                    "visit_id": visit.get("visitId"),
                    "vessel_name": visit.get("vesName") or visit.get("vesselName"),
                    "vessel_class": visit.get("vesclassId"),
                    "eta": self._parse_navis_timestamp(visit.get("publishedEta")),
                    "etd": self._parse_navis_timestamp(visit.get("publishedEtd")),
                    "ata": self._parse_navis_timestamp(visit.get("ata")),
                    "atd": self._parse_navis_timestamp(visit.get("atd")),
                    "berth": visit.get("berth"),
                    "visit_phase": visit.get("visitPhase"),
                    "lines": visit.get("lines", []),
                    "metadata": visit,
                }
                for visit in visits
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting active vessel visits: {str(e)}")

    async def get_gate_appointments(
        self,
        container_number: Optional[str] = None,
        appointment_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get gate appointments from N4 EVP API."""
        try:
            params = {"facilityId": self.terminal_config.get("facility_id")}
            if container_number:
                params["unitId"] = container_number
            if appointment_date:
                params["appointmentDate"] = appointment_date.strftime("%Y-%m-%d")

            data = await self._make_request("/road/gateappointments", params=params)
            appointments = data if isinstance(data, list) else data.get("appointments", data.get("content", []))

            return [
                {
                    "appointment_id": appt.get("gkey") or appt.get("gapptNbr"),
                    "appointment_number": appt.get("gapptNbr"),
                    "unit_id": appt.get("unitId"),
                    "transaction_type": appt.get("tranType"),
                    "appointment_time": self._parse_navis_timestamp(appt.get("requestedDate")),
                    "time_slot": appt.get("timeSlot"),
                    "trucking_company": appt.get("trkCompany", {}).get("id")
                    if isinstance(appt.get("trkCompany"), dict)
                    else appt.get("trkCompany"),
                    "status": appt.get("gapptState"),
                    "gate": appt.get("gate"),
                    "terminal": self.terminal_config.get("name"),
                    "metadata": appt,
                }
                for appt in appointments
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting gate appointments: {str(e)}")

    async def create_gate_appointment(
        self,
        container_number: str,
        transaction_type: str,
        appointment_time: datetime,
        trucking_company: str,
        driver_license: Optional[str] = None,
        truck_license: Optional[str] = None,
    ) -> dict:
        """Create a gate appointment at GPA. Requires tenant credentials."""
        try:
            data = {
                "unitId": container_number,
                "tranType": transaction_type,
                "requestedDate": appointment_time.isoformat(),
                "trkCompany": trucking_company,
                "facilityId": self.terminal_config.get("facility_id"),
            }
            if driver_license:
                data["driverLicenseNbr"] = driver_license
            if truck_license:
                data["truckLicenseNbr"] = truck_license

            result = await self._make_post_request("/road/gateappointments", data)
            return {
                "appointment_id": result.get("gkey") or result.get("gapptNbr"),
                "appointment_number": result.get("gapptNbr"),
                "status": result.get("gapptState"),
                "terminal": self.terminal_config.get("name"),
                "metadata": result,
            }
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error creating gate appointment: {str(e)}")

    async def get_gate_transactions(
        self,
        container_number: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """Get gate transaction history."""
        try:
            params = {"facilityId": self.terminal_config.get("facility_id")}
            if container_number:
                params["unitId"] = container_number
            if since:
                params["fromDate"] = since.isoformat()

            data = await self._make_request("/road/gatetransactions", params=params)
            transactions = data if isinstance(data, list) else data.get("transactions", data.get("content", []))

            return [
                {
                    "transaction_id": txn.get("gkey"),
                    "unit_id": txn.get("unitId"),
                    "transaction_type": txn.get("tranType"),
                    "stage": txn.get("stage"),
                    "status": txn.get("status"),
                    "trucking_company": txn.get("trkCompany", {}).get("id")
                    if isinstance(txn.get("trkCompany"), dict)
                    else txn.get("trkCompany"),
                    "truck_license": txn.get("truckLicenseNbr"),
                    "driver_name": txn.get("driverName"),
                    "timestamp": self._parse_navis_timestamp(txn.get("created")),
                    "gate": txn.get("gate"),
                    "lane": txn.get("lane"),
                    "terminal": self.terminal_config.get("name"),
                    "metadata": txn,
                }
                for txn in transactions
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting gate transactions: {str(e)}")

    async def get_truck_visits(
        self,
        truck_license: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """Get truck visit information."""
        try:
            params = {"facilityId": self.terminal_config.get("facility_id")}
            if truck_license:
                params["truckLicenseNbr"] = truck_license
            if since:
                params["fromDate"] = since.isoformat()

            data = await self._make_request("/road/truckvisits", params=params)
            visits = data if isinstance(data, list) else data.get("truckVisits", data.get("content", []))

            return [
                {
                    "visit_id": visit.get("tvdtlsGkey") or visit.get("gkey"),
                    "truck_license": visit.get("truckLicenseNbr"),
                    "trucking_company": visit.get("trkCompany", {}).get("id")
                    if isinstance(visit.get("trkCompany"), dict)
                    else visit.get("trkCompany"),
                    "driver_name": visit.get("driverName"),
                    "driver_license": visit.get("driverLicenseNbr"),
                    "entered_yard": self._parse_navis_timestamp(visit.get("enteredYard")),
                    "exited_yard": self._parse_navis_timestamp(visit.get("exitedYard")),
                    "status": visit.get("tvdtlsStatus"),
                    "terminal": self.terminal_config.get("name"),
                    "metadata": visit,
                }
                for visit in visits
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting truck visits: {str(e)}")

    async def get_billable_events(
        self,
        container_number: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """Get billable events for demurrage/storage calculation."""
        try:
            params = {"facilityId": self.terminal_config.get("facility_id")}
            if container_number:
                params["unitId"] = container_number
            if since:
                params["fromDate"] = since.isoformat()

            data = await self._make_request("/billing/unitevents", params=params)
            events = data if isinstance(data, list) else data.get("events", data.get("content", []))

            return [
                {
                    "event_id": event.get("gkey"),
                    "unit_id": event.get("unitId"),
                    "event_type": event.get("eventType"),
                    "is_billable": event.get("isBillable"),
                    "freight_kind": event.get("freightKind"),
                    "timestamp": self._parse_navis_timestamp(event.get("eventTime")),
                    "quantity": event.get("quantity"),
                    "rate": event.get("rate"),
                    "amount": event.get("amount"),
                    "currency": event.get("currency"),
                    "terminal": self.terminal_config.get("name"),
                    "metadata": event,
                }
                for event in events
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting billable events: {str(e)}")

    async def test_connection(self) -> bool:
        """Test connection by attempting to get access token."""
        try:
            await self._get_access_token()
            return True
        except Exception:
            return False

    @staticmethod
    def get_available_terminals() -> List[dict]:
        """Get list of GPA terminals."""
        return [
            {
                "code": code,
                "name": config["name"],
                "port": config["port"],
                "firms_code": config.get("firms_code"),
                "facility_id": config.get("facility_id"),
            }
            for code, config in TERMINAL_CONFIGS.items()
        ]

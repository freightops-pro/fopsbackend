import httpx
from datetime import datetime, timedelta
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


class PortHoustonAdapter(PortAdapter):
    """
    Adapter for Port Houston (Navis N4) API integration.

    Uses the Navis EVP (External Visibility Platform) API for container tracking.

    FreightOps has API credentials for container tracking (available to paying tenants).
    For appointment/express pass features, tenants must provide their own port credentials
    since those actions are tied to their specific port account.
    """

    # Real Navis API endpoints for Port Houston
    BASE_URL = "https://api.america.naviscloudops.com/v3/evp"
    TOKEN_URL = "https://auth-v1.america.naviscloudops.com/auth/realms/phaprod/protocol/openid-connect/token"

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)
        from app.core.config import get_settings
        settings = get_settings()

        # Use tenant credentials if provided (needed for appointments/express passes)
        # Fall back to FreightOps credentials for basic container tracking
        self.client_id = self.credentials.get("client_id") or settings.port_houston_client_id
        self.client_secret = self.credentials.get("client_secret") or settings.port_houston_client_secret
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    async def _get_access_token(self) -> str:
        """Get OAuth2 access token using client credentials flow."""
        if self.access_token and self.token_expires_at and datetime.utcnow() < self.token_expires_at:
            return self.access_token

        if not self.client_id or not self.client_secret:
            raise PortAuthenticationError("Port Houston credentials (client_id, client_secret) are required")

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
                self.token_expires_at = datetime.utcnow().replace(microsecond=0) + timedelta(seconds=expires_in - 60)
                return self.access_token
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError("Invalid Port Houston credentials")
                raise PortAdapterError(f"Failed to get access token: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error getting access token: {str(e)}")

    async def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make authenticated GET API request."""
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
                    raise PortAuthenticationError("Authentication failed")
                elif e.response.status_code == 404:
                    raise PortNotFoundError(f"Resource not found: {endpoint}")
                elif e.response.status_code == 429:
                    raise PortAdapterError("Rate limit exceeded")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    async def _make_post_request(self, endpoint: str, data: dict, params: Optional[dict] = None) -> dict:
        """Make authenticated POST API request."""
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
                elif e.response.status_code == 429:
                    raise PortAdapterError("Rate limit exceeded")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    async def _make_delete_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make authenticated DELETE API request."""
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.BASE_URL}{endpoint}",
                    headers=headers,
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json() if response.content else {}
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError("Authentication failed")
                elif e.response.status_code == 404:
                    raise PortNotFoundError(f"Resource not found: {endpoint}")
                elif e.response.status_code == 429:
                    raise PortAdapterError("Rate limit exceeded")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """
        Track container using Port Houston Navis EVP API.

        Uses the /inventory/units endpoint to query container status.
        Response follows the Navis UnitPayload structure.

        Key UnitPayload fields:
        - unitId: container number
        - transitState: S10_ADVISED, S20_INBOUND, S30_ECIN, S40_YARD, S50_ECOUT, S60_RETIRED
        - visitState: 1ACTIVE, 2ADVISED, etc.
        - lastKnownPosition.posSlot: yard location
        - scope.facility_id: terminal/facility
        - line: shipping line operator ID
        - contents.goodsAndCtrWtKg: weight in kg
        - actualIbVisit: inbound vessel visit info
        - seals: array of seal objects
        - stopFlags: hold flags (customs, freight, etc.)
        - ufvBilling: billing info (demurrage, storage, lastFreeDay, paidThruDay)
        """
        try:
            # Query Navis inventory units endpoint
            data = await self._make_request(
                "/inventory/units",
                params={"unitId": container_number},
            )

            # Navis may return list directly or wrapped in "units" key
            units = data if isinstance(data, list) else data.get("units", data.get("content", []))
            if not units:
                raise PortNotFoundError(f"Container {container_number} not found at Port Houston")

            unit = units[0] if isinstance(units, list) else units

            # Map Navis transitState/visitState to status
            transit_state = unit.get("transitState", "")
            visit_state = unit.get("visitState", "")
            status = self._map_navis_status(transit_state, visit_state)

            # Extract terminal from scope.facility_id or facility object
            scope = unit.get("scope", {})
            terminal = scope.get("facility_id") or unit.get("facility", {}).get("facilityId", "")

            # Extract location from lastKnownPosition (Navis UnitPayload field)
            last_known_position = unit.get("lastKnownPosition", {})
            location = ContainerLocation(
                terminal=terminal,
                yard_location=last_known_position.get("posSlot") or last_known_position.get("positionSlot"),
                gate_status=visit_state,
                port="Houston",
                country="US",
                timestamp=self._parse_navis_timestamp(unit.get("timeIn")),
            )

            # Extract vessel info from actualIbVisit (inbound vessel visit)
            vessel = None
            actual_ib_visit = unit.get("actualIbVisit", {})
            if actual_ib_visit:
                vessel = VesselInfo(
                    name=actual_ib_visit.get("vesselName") or actual_ib_visit.get("carrierName"),
                    voyage=actual_ib_visit.get("visitId") or actual_ib_visit.get("inVoyNbr"),
                    eta=self._parse_navis_timestamp(
                        actual_ib_visit.get("eta") or actual_ib_visit.get("publishedEta")
                    ),
                )

            # Extract dates from unit fields and ufvBilling
            ufv_billing = unit.get("ufvBilling", {})
            dates = ContainerDates(
                discharge_date=self._parse_navis_timestamp(
                    unit.get("timeOfLoading") or unit.get("timeDischarge")
                ),
                last_free_day=self._parse_navis_timestamp(
                    ufv_billing.get("lastFreeDay") or ufv_billing.get("paidThruDay")
                ),
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

            # Extract holds from stopFlags
            holds = self._extract_holds(unit.get("stopFlags", {}))

            # Extract charges from ufvBilling
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
                terminal=terminal,
                raw_data=unit,
            )

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error tracking container: {str(e)}")

    def _map_navis_status(self, transit_state: str, visit_state: str) -> str:
        """Map Navis transitState/visitState to normalized status."""
        # Transit states: S10_ADVISED, S20_INBOUND, S30_ECIN, S40_YARD, S50_ECOUT, S60_RETIRED
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
            # Navis uses ISO 8601 format
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
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
        """
        Get container event history from Port Houston Navis EVP API.

        Uses the /service/events endpoint for event data.
        EventPayload includes: eventType, eventTime, facility, notes, appliedToId, etc.
        """
        try:
            params = {"appliedToId": container_number}
            if since:
                params["fromDate"] = since.isoformat()

            data = await self._make_request("/service/events", params=params)
            events = data if isinstance(data, list) else data.get("events", data.get("content", []))

            return [
                {
                    "event_type": event.get("eventType") or event.get("eventTypeId"),
                    "timestamp": self._parse_navis_timestamp(
                        event.get("eventTime") or event.get("placedTime")
                    ),
                    "location": event.get("facility", {}).get("facilityId")
                    if isinstance(event.get("facility"), dict)
                    else event.get("facilityId"),
                    "description": event.get("notes") or event.get("eventType") or event.get("eventTypeId"),
                    "metadata": event,
                }
                for event in events
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting container events: {str(e)}")

    async def get_vessel_schedule(self, vessel_name: Optional[str] = None, port_code: Optional[str] = None) -> list[dict]:
        """
        Get vessel schedule from Port Houston Navis EVP API.

        Uses the /vessel/vesselvisits endpoint for vessel information.
        VesselVisitPayload includes: visitId, vesName, vesclassId, visitPhase,
        publishedEta, publishedEtd, ata, atd, lines, estMoveCount, etc.
        """
        try:
            params = {}
            if vessel_name:
                params["vesName"] = vessel_name

            data = await self._make_request("/vessel/vesselvisits", params=params)
            schedules = data if isinstance(data, list) else data.get("vesselVisits", data.get("content", []))

            return [
                {
                    "vessel_name": schedule.get("vesName") or schedule.get("vesselName"),
                    "voyage": schedule.get("visitId"),
                    "eta": self._parse_navis_timestamp(
                        schedule.get("publishedEta") or schedule.get("eta")
                    ),
                    "etd": self._parse_navis_timestamp(
                        schedule.get("publishedEtd") or schedule.get("etd")
                    ),
                    "ata": self._parse_navis_timestamp(schedule.get("ata")),
                    "atd": self._parse_navis_timestamp(schedule.get("atd")),
                    "berth": schedule.get("berth"),
                    "terminal": schedule.get("facility", {}).get("facilityId")
                    if isinstance(schedule.get("facility"), dict)
                    else schedule.get("facilityId"),
                    "status": schedule.get("visitPhase"),
                }
                for schedule in schedules
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting vessel schedule: {str(e)}")

    async def test_connection(self) -> bool:
        """Test connection by attempting to get access token."""
        try:
            await self._get_access_token()
            return True
        except Exception:
            return False

    # ==================== INVENTORY SERVICE ====================

    async def get_move_events(
        self, container_number: Optional[str] = None, since: Optional[datetime] = None
    ) -> list[dict]:
        """
        Get container move events from /inventory/moveevents endpoint.

        Move events track physical movements of containers within the terminal.
        """
        try:
            params = {}
            if container_number:
                params["unitId"] = container_number
            if since:
                params["fromDate"] = since.isoformat()

            data = await self._make_request("/inventory/moveevents", params=params)
            events = data if isinstance(data, list) else data.get("moveEvents", data.get("content", []))

            return [
                {
                    "event_id": event.get("gkey"),
                    "unit_id": event.get("unitId"),
                    "move_kind": event.get("moveKind"),
                    "from_position": event.get("fromPosition"),
                    "to_position": event.get("toPosition"),
                    "timestamp": self._parse_navis_timestamp(event.get("moveTime")),
                    "carrier": event.get("carrier"),
                    "facility": event.get("facility", {}).get("facilityId")
                    if isinstance(event.get("facility"), dict)
                    else event.get("facilityId"),
                    "metadata": event,
                }
                for event in events
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting move events: {str(e)}")

    # ==================== VESSEL SERVICE ====================

    async def get_active_vessel_visits(self) -> list[dict]:
        """
        Get active vessel visits from /vessel/vesselvisits/active endpoint.

        Returns only vessels currently at berth or expected soon.
        """
        try:
            data = await self._make_request("/vessel/vesselvisits/active")
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

    async def get_vessels(self, vessel_name: Optional[str] = None) -> list[dict]:
        """
        Get vessel master data from /vessel/vessels endpoint.

        Returns vessel information (not visits).
        """
        try:
            params = {}
            if vessel_name:
                params["vesName"] = vessel_name

            data = await self._make_request("/vessel/vessels", params=params)
            vessels = data if isinstance(data, list) else data.get("vessels", data.get("content", []))

            return [
                {
                    "vessel_id": vessel.get("vesId") or vessel.get("id"),
                    "vessel_name": vessel.get("vesName") or vessel.get("name"),
                    "vessel_class": vessel.get("vesclassId"),
                    "call_sign": vessel.get("callSign"),
                    "imo_number": vessel.get("imoNbr"),
                    "lloyds_id": vessel.get("lloydsId"),
                    "line_operator": vessel.get("lineOperator", {}).get("id")
                    if isinstance(vessel.get("lineOperator"), dict)
                    else vessel.get("lineOperator"),
                    "metadata": vessel,
                }
                for vessel in vessels
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting vessels: {str(e)}")

    # ==================== ROAD SERVICE ====================

    async def get_truck_visits(
        self,
        truck_license: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """
        Get truck visit information from /road/truckvisits endpoint.

        TruckVisit represents a truck's presence at the terminal.
        """
        try:
            params = {}
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
                    "facility": visit.get("facility", {}).get("facilityId")
                    if isinstance(visit.get("facility"), dict)
                    else visit.get("facilityId"),
                    "metadata": visit,
                }
                for visit in visits
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting truck visits: {str(e)}")

    async def get_gate_appointments(
        self,
        container_number: Optional[str] = None,
        appointment_date: Optional[datetime] = None,
    ) -> list[dict]:
        """
        Get gate appointments from /road/gateappointments endpoint.

        Gate appointments are scheduled times for trucks to pick up/drop off containers.
        """
        try:
            params = {}
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
                    "facility": appt.get("facility", {}).get("facilityId")
                    if isinstance(appt.get("facility"), dict)
                    else appt.get("facilityId"),
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
        """
        Create a gate appointment via /road/gateappointments endpoint.

        Requires tenant credentials (not FreightOps credentials).

        Args:
            container_number: Container ID for the appointment
            transaction_type: Type of transaction (PUI=Pick Up Import, DOE=Drop Off Export, etc.)
            appointment_time: Requested appointment time
            trucking_company: Trucking company ID
            driver_license: Optional driver license number
            truck_license: Optional truck license plate
        """
        try:
            data = {
                "unitId": container_number,
                "tranType": transaction_type,
                "requestedDate": appointment_time.isoformat(),
                "trkCompany": trucking_company,
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
                "metadata": result,
            }
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error creating gate appointment: {str(e)}")

    async def cancel_gate_appointment(self, appointment_id: str) -> dict:
        """
        Cancel a gate appointment.

        Requires tenant credentials (not FreightOps credentials).
        """
        try:
            result = await self._make_delete_request(f"/road/gateappointments/{appointment_id}")
            return {"success": True, "metadata": result}
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error canceling gate appointment: {str(e)}")

    async def get_gate_transactions(
        self,
        container_number: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """
        Get gate transactions from /road/gatetransactions endpoint.

        Gate transactions record actual truck movements through gates.
        """
        try:
            params = {}
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
                    "facility": txn.get("facility", {}).get("facilityId")
                    if isinstance(txn.get("facility"), dict)
                    else txn.get("facilityId"),
                    "metadata": txn,
                }
                for txn in transactions
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting gate transactions: {str(e)}")

    # ==================== ORDERS SERVICE ====================

    async def get_service_orders(
        self,
        container_number: Optional[str] = None,
        order_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Get service orders from /orders/serviceorder endpoint.

        Service orders are work orders for terminal operations.
        """
        try:
            params = {}
            if container_number:
                params["unitId"] = container_number
            if order_type:
                params["orderType"] = order_type

            data = await self._make_request("/orders/serviceorder", params=params)
            orders = data if isinstance(data, list) else data.get("serviceOrders", data.get("content", []))

            return [
                {
                    "order_id": order.get("gkey") or order.get("orderNbr"),
                    "order_number": order.get("orderNbr"),
                    "order_type": order.get("orderType"),
                    "unit_id": order.get("unitId"),
                    "status": order.get("orderStatus"),
                    "requested_time": self._parse_navis_timestamp(order.get("requestedTime")),
                    "completed_time": self._parse_navis_timestamp(order.get("completedTime")),
                    "service_type": order.get("serviceType"),
                    "notes": order.get("notes"),
                    "facility": order.get("facility", {}).get("facilityId")
                    if isinstance(order.get("facility"), dict)
                    else order.get("facilityId"),
                    "metadata": order,
                }
                for order in orders
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting service orders: {str(e)}")

    async def create_service_order(
        self,
        container_number: str,
        order_type: str,
        service_type: str,
        requested_time: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """
        Create a service order via /orders/serviceorder endpoint.

        Requires tenant credentials (not FreightOps credentials).
        """
        try:
            data = {
                "unitId": container_number,
                "orderType": order_type,
                "serviceType": service_type,
            }
            if requested_time:
                data["requestedTime"] = requested_time.isoformat()
            if notes:
                data["notes"] = notes

            result = await self._make_post_request("/orders/serviceorder", data)
            return {
                "order_id": result.get("gkey") or result.get("orderNbr"),
                "order_number": result.get("orderNbr"),
                "status": result.get("orderStatus"),
                "metadata": result,
            }
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error creating service order: {str(e)}")

    async def get_bookings(
        self,
        booking_number: Optional[str] = None,
        vessel_visit: Optional[str] = None,
    ) -> list[dict]:
        """
        Get bookings from /orders/bookings endpoint.

        Bookings are reservations for shipping containers on vessels.
        """
        try:
            params = {}
            if booking_number:
                params["bookingNbr"] = booking_number
            if vessel_visit:
                params["vesselVisit"] = vessel_visit

            data = await self._make_request("/orders/bookings", params=params)
            bookings = data if isinstance(data, list) else data.get("bookings", data.get("content", []))

            return [
                {
                    "booking_id": booking.get("gkey"),
                    "booking_number": booking.get("bookingNbr"),
                    "line_operator": booking.get("lineOperator", {}).get("id")
                    if isinstance(booking.get("lineOperator"), dict)
                    else booking.get("lineOperator"),
                    "vessel_visit": booking.get("vesselVisit"),
                    "shipper": booking.get("shipper", {}).get("id")
                    if isinstance(booking.get("shipper"), dict)
                    else booking.get("shipper"),
                    "quantity": booking.get("eqoQuantity"),
                    "eq_type": booking.get("eqType"),
                    "status": booking.get("bookingStatus"),
                    "origin": booking.get("origin"),
                    "destination": booking.get("destination"),
                    "metadata": booking,
                }
                for booking in bookings
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting bookings: {str(e)}")

    # ==================== BILLING SERVICE ====================

    async def get_billable_events(
        self,
        container_number: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """
        Get billable unit events from /billing/unitevents endpoint.

        Billable events are chargeable activities on containers.
        """
        try:
            params = {}
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
                    "facility": event.get("facility", {}).get("facilityId")
                    if isinstance(event.get("facility"), dict)
                    else event.get("facilityId"),
                    "metadata": event,
                }
                for event in events
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting billable events: {str(e)}")


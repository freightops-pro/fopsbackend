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


class APMTerminalsAdapter(PortAdapter):
    """
    Adapter for APM Terminals API integration.

    APM Terminals (Maersk subsidiary) operates several US terminals including:
    - APM Terminals Mobile (Alabama) - USMOB
    - APM Terminals Los Angeles - USLAX (Pier 400)
    - APM Terminals Elizabeth (New Jersey) - USEWN

    Uses OAuth2 client credentials flow for authentication.
    API documentation: https://developer.apmterminals.com

    FreightOps has API credentials for container tracking (available to paying tenants).
    For appointment/ePass features, tenants must provide their own port credentials
    since those actions are tied to their specific port account.
    """

    # APM Terminals API endpoints
    BASE_URL = "https://api.apmterminals.com/v1"
    TOKEN_URL = "https://api.apmterminals.com/oauth/token"

    # Terminal facility codes
    TERMINAL_CODES = {
        "USMOB": "mobile",
        "USEWN": "elizabeth",
        "USLAX": "losangeles",
    }

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)
        from app.core.config import get_settings
        settings = get_settings()

        # Use tenant credentials if provided (needed for appointments/ePass)
        # Fall back to FreightOps credentials for basic container tracking
        self.client_id = self.credentials.get("client_id") or getattr(settings, "apm_client_id", None)
        self.client_secret = self.credentials.get("client_secret") or getattr(settings, "apm_client_secret", None)
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    async def _get_access_token(self) -> str:
        """Get OAuth2 access token using client credentials flow."""
        if self.access_token and self.token_expires_at and datetime.utcnow() < self.token_expires_at:
            return self.access_token

        if not self.client_id or not self.client_secret:
            raise PortAuthenticationError("APM Terminals credentials (client_id, client_secret) are required")

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
                    raise PortAuthenticationError("Invalid APM Terminals credentials")
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

    def _get_facility_code(self, port_code: str) -> str:
        """Get APM facility code from port code."""
        return self.TERMINAL_CODES.get(port_code.upper(), port_code.lower())

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """
        Track container using APM Terminals API.

        APM uses a unified container tracking endpoint with terminal-specific data.
        Response includes:
        - containerNumber: Container ID
        - status: Current status (INBOUND, ON_TERMINAL, OUTGATE, etc.)
        - terminalCode: Facility identifier
        - location: Yard block/bay/row/tier position
        - vesselInfo: Vessel name, voyage, ETA/ETD
        - holds: Array of hold types
        - billing: Demurrage, storage, last free day
        - appointments: Scheduled gate appointments
        """
        try:
            facility = self._get_facility_code(port_code)
            data = await self._make_request(
                f"/containers/{container_number}",
                params={"facility": facility},
            )

            if not data:
                raise PortNotFoundError(f"Container {container_number} not found at APM {facility}")

            # Map APM status to normalized status
            status = self._map_apm_status(data.get("status", "UNKNOWN"))

            # Extract terminal
            terminal = data.get("terminalCode") or data.get("facility") or facility

            # Extract location
            location_data = data.get("location", {})
            location = ContainerLocation(
                terminal=terminal,
                yard_location=self._format_yard_location(location_data),
                gate_status=data.get("gateStatus"),
                port=data.get("portName", "APM Terminal"),
                country="US",
                timestamp=self._parse_timestamp(data.get("lastEventTime")),
            )

            # Extract vessel info
            vessel = None
            vessel_data = data.get("vesselInfo", {})
            if vessel_data:
                vessel = VesselInfo(
                    name=vessel_data.get("vesselName"),
                    voyage=vessel_data.get("voyage") or vessel_data.get("voyageNumber"),
                    eta=self._parse_timestamp(vessel_data.get("eta")),
                )

            # Extract dates
            billing_data = data.get("billing", {})
            dates = ContainerDates(
                discharge_date=self._parse_timestamp(data.get("dischargeTime")),
                last_free_day=self._parse_timestamp(billing_data.get("lastFreeDay")),
                ingate_timestamp=self._parse_timestamp(data.get("ingateTime")),
                outgate_timestamp=self._parse_timestamp(data.get("outgateTime")),
            )

            # Extract container details
            container_details = ContainerDetails(
                size=data.get("containerSize") or data.get("length"),
                type=data.get("containerType") or data.get("isoCode"),
                weight=data.get("grossWeight"),
                seal_number=data.get("sealNumber"),
                shipping_line=data.get("shippingLine") or data.get("lineOperator"),
            )

            # Extract holds
            holds = data.get("holds", [])
            if isinstance(holds, list):
                holds = [h.get("holdType") if isinstance(h, dict) else h for h in holds]

            # Extract charges
            charges = None
            if billing_data:
                charges = ContainerCharges(
                    demurrage=billing_data.get("demurrage"),
                    per_diem=billing_data.get("storage"),
                    detention=billing_data.get("detention"),
                    total_charges=billing_data.get("totalOwed"),
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
                raw_data=data,
            )

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error tracking container: {str(e)}")

    def _map_apm_status(self, apm_status: str) -> str:
        """Map APM status codes to normalized status."""
        status_map = {
            "ADVISED": "ADVISED",
            "INBOUND": "IN_TRANSIT",
            "ARRIVED": "ARRIVED",
            "DISCHARGED": "DISCHARGED",
            "ON_TERMINAL": "IN_YARD",
            "AVAILABLE": "AVAILABLE",
            "RELEASED": "RELEASED",
            "TRUCK_APPOINTED": "APPOINTED",
            "OUTGATE": "OUTGATE",
            "DEPARTED": "DEPARTED",
            "LOADED": "LOADED",
        }
        return status_map.get(apm_status.upper(), apm_status or "UNKNOWN")

    def _format_yard_location(self, location_data: dict) -> Optional[str]:
        """Format yard location from APM location data."""
        if not location_data:
            return None
        block = location_data.get("block", "")
        bay = location_data.get("bay", "")
        row = location_data.get("row", "")
        tier = location_data.get("tier", "")
        parts = [p for p in [block, bay, row, tier] if p]
        return "-".join(parts) if parts else None

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse APM timestamp format to datetime."""
        if not timestamp_str:
            return None
        try:
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    async def get_container_events(
        self, container_number: str, port_code: str, since: Optional[datetime] = None
    ) -> list[dict]:
        """
        Get container event history from APM Terminals API.

        Uses the /containers/{id}/events endpoint.
        """
        try:
            facility = self._get_facility_code(port_code)
            params = {"facility": facility}
            if since:
                params["fromDate"] = since.isoformat()

            data = await self._make_request(f"/containers/{container_number}/events", params=params)
            events = data if isinstance(data, list) else data.get("events", [])

            return [
                {
                    "event_type": event.get("eventType"),
                    "timestamp": self._parse_timestamp(event.get("eventTime")),
                    "location": event.get("location"),
                    "description": event.get("description") or event.get("eventType"),
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
        Get vessel schedule from APM Terminals API.

        Uses the /vessels endpoint for vessel schedule information.
        """
        try:
            params = {}
            if vessel_name:
                params["vesselName"] = vessel_name
            if port_code:
                params["facility"] = self._get_facility_code(port_code)

            data = await self._make_request("/vessels/schedule", params=params)
            schedules = data if isinstance(data, list) else data.get("vessels", [])

            return [
                {
                    "vessel_name": schedule.get("vesselName"),
                    "voyage": schedule.get("voyage"),
                    "eta": self._parse_timestamp(schedule.get("eta")),
                    "etd": self._parse_timestamp(schedule.get("etd")),
                    "ata": self._parse_timestamp(schedule.get("ata")),
                    "atd": self._parse_timestamp(schedule.get("atd")),
                    "berth": schedule.get("berth"),
                    "terminal": schedule.get("facility"),
                    "status": schedule.get("status"),
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

    # ==================== APPOINTMENT/ePASS OPERATIONS ====================

    async def get_gate_appointments(
        self,
        container_number: Optional[str] = None,
        appointment_date: Optional[datetime] = None,
    ) -> list[dict]:
        """
        Get gate appointments from APM Terminals.

        APM uses eGate/ePass system for appointment management.
        """
        try:
            params = {}
            if container_number:
                params["containerNumber"] = container_number
            if appointment_date:
                params["date"] = appointment_date.strftime("%Y-%m-%d")

            data = await self._make_request("/appointments", params=params)
            appointments = data if isinstance(data, list) else data.get("appointments", [])

            return [
                {
                    "appointment_id": appt.get("appointmentId") or appt.get("id"),
                    "appointment_number": appt.get("confirmationNumber") or appt.get("ePassNumber"),
                    "entry_code": appt.get("entryCode") or appt.get("ePassCode"),
                    "unit_id": appt.get("containerNumber"),
                    "transaction_type": appt.get("transactionType"),
                    "appointment_time": self._parse_timestamp(appt.get("appointmentTime")),
                    "time_slot": appt.get("timeSlot"),
                    "trucking_company": appt.get("truckingCompany"),
                    "status": appt.get("status"),
                    "gate": appt.get("gate"),
                    "terminal": appt.get("facility"),
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
        Create a gate appointment (ePass) via APM Terminals API.

        Requires tenant credentials (not FreightOps credentials).

        Args:
            container_number: Container ID for the appointment
            transaction_type: Type (PUI=Pick Up Import, DOE=Drop Off Export, etc.)
            appointment_time: Requested appointment time
            trucking_company: SCAC code or trucking company ID
            driver_license: Optional driver license number
            truck_license: Optional truck license plate

        Returns:
            dict with appointment_id, appointment_number, entry_code (ePass code)
        """
        try:
            data = {
                "containerNumber": container_number,
                "transactionType": transaction_type,
                "appointmentTime": appointment_time.isoformat(),
                "truckingCompany": trucking_company,
            }
            if driver_license:
                data["driverLicense"] = driver_license
            if truck_license:
                data["truckLicense"] = truck_license

            result = await self._make_post_request("/appointments", data)
            return {
                "appointment_id": result.get("appointmentId") or result.get("id"),
                "appointment_number": result.get("confirmationNumber") or result.get("ePassNumber"),
                "entry_code": result.get("entryCode") or result.get("ePassCode"),
                "status": result.get("status"),
                "gate": result.get("gate"),
                "terminal": result.get("facility"),
                "metadata": result,
            }
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error creating gate appointment: {str(e)}")

    async def cancel_gate_appointment(self, appointment_id: str) -> dict:
        """
        Cancel a gate appointment (ePass).

        Requires tenant credentials (not FreightOps credentials).
        """
        try:
            result = await self._make_delete_request(f"/appointments/{appointment_id}")
            return {"success": True, "metadata": result}
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error canceling gate appointment: {str(e)}")

    # ==================== ACTIVE VESSEL VISITS ====================

    async def get_active_vessel_visits(self) -> list[dict]:
        """Get active vessel visits at APM terminal."""
        try:
            data = await self._make_request("/vessels/active")
            visits = data if isinstance(data, list) else data.get("vessels", [])

            return [
                {
                    "visit_id": visit.get("visitId") or visit.get("id"),
                    "vessel_name": visit.get("vesselName"),
                    "vessel_class": visit.get("vesselClass"),
                    "eta": self._parse_timestamp(visit.get("eta")),
                    "etd": self._parse_timestamp(visit.get("etd")),
                    "ata": self._parse_timestamp(visit.get("ata")),
                    "atd": self._parse_timestamp(visit.get("atd")),
                    "berth": visit.get("berth"),
                    "visit_phase": visit.get("status"),
                    "lines": visit.get("shippingLines", []),
                    "metadata": visit,
                }
                for visit in visits
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting active vessel visits: {str(e)}")

    # ==================== TRUCK/GATE OPERATIONS ====================

    async def get_truck_visits(
        self,
        truck_license: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """Get truck visit information from APM terminal."""
        try:
            params = {}
            if truck_license:
                params["truckLicense"] = truck_license
            if since:
                params["fromDate"] = since.isoformat()

            data = await self._make_request("/trucks/visits", params=params)
            visits = data if isinstance(data, list) else data.get("visits", [])

            return [
                {
                    "visit_id": visit.get("visitId") or visit.get("id"),
                    "truck_license": visit.get("truckLicense"),
                    "trucking_company": visit.get("truckingCompany"),
                    "driver_name": visit.get("driverName"),
                    "driver_license": visit.get("driverLicense"),
                    "entered_yard": self._parse_timestamp(visit.get("enteredTime")),
                    "exited_yard": self._parse_timestamp(visit.get("exitedTime")),
                    "status": visit.get("status"),
                    "facility": visit.get("facility"),
                    "metadata": visit,
                }
                for visit in visits
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting truck visits: {str(e)}")

    async def get_gate_transactions(
        self,
        container_number: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """Get gate transaction history from APM terminal."""
        try:
            params = {}
            if container_number:
                params["containerNumber"] = container_number
            if since:
                params["fromDate"] = since.isoformat()

            data = await self._make_request("/gate/transactions", params=params)
            transactions = data if isinstance(data, list) else data.get("transactions", [])

            return [
                {
                    "transaction_id": txn.get("transactionId") or txn.get("id"),
                    "unit_id": txn.get("containerNumber"),
                    "transaction_type": txn.get("transactionType"),
                    "stage": txn.get("stage"),
                    "status": txn.get("status"),
                    "trucking_company": txn.get("truckingCompany"),
                    "truck_license": txn.get("truckLicense"),
                    "driver_name": txn.get("driverName"),
                    "timestamp": self._parse_timestamp(txn.get("transactionTime")),
                    "gate": txn.get("gate"),
                    "lane": txn.get("lane"),
                    "facility": txn.get("facility"),
                    "metadata": txn,
                }
                for txn in transactions
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting gate transactions: {str(e)}")

    # ==================== BOOKING/BILLING OPERATIONS ====================

    async def get_bookings(
        self,
        booking_number: Optional[str] = None,
        vessel_visit: Optional[str] = None,
    ) -> list[dict]:
        """Get booking information from APM terminal."""
        try:
            params = {}
            if booking_number:
                params["bookingNumber"] = booking_number
            if vessel_visit:
                params["vesselVisit"] = vessel_visit

            data = await self._make_request("/bookings", params=params)
            bookings = data if isinstance(data, list) else data.get("bookings", [])

            return [
                {
                    "booking_id": booking.get("bookingId") or booking.get("id"),
                    "booking_number": booking.get("bookingNumber"),
                    "line_operator": booking.get("shippingLine"),
                    "vessel_visit": booking.get("vesselVisit"),
                    "shipper": booking.get("shipper"),
                    "quantity": booking.get("quantity"),
                    "eq_type": booking.get("equipmentType"),
                    "status": booking.get("status"),
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

    async def get_billable_events(
        self,
        container_number: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list[dict]:
        """Get billable events for containers at APM terminal."""
        try:
            params = {}
            if container_number:
                params["containerNumber"] = container_number
            if since:
                params["fromDate"] = since.isoformat()

            data = await self._make_request("/billing/events", params=params)
            events = data if isinstance(data, list) else data.get("events", [])

            return [
                {
                    "event_id": event.get("eventId") or event.get("id"),
                    "unit_id": event.get("containerNumber"),
                    "event_type": event.get("eventType"),
                    "is_billable": event.get("billable", True),
                    "freight_kind": event.get("freightKind"),
                    "timestamp": self._parse_timestamp(event.get("eventTime")),
                    "quantity": event.get("quantity"),
                    "rate": event.get("rate"),
                    "amount": event.get("amount"),
                    "currency": event.get("currency", "USD"),
                    "facility": event.get("facility"),
                    "metadata": event,
                }
                for event in events
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting billable events: {str(e)}")

    async def get_service_orders(
        self,
        container_number: Optional[str] = None,
        order_type: Optional[str] = None,
    ) -> list[dict]:
        """Get service orders from APM terminal."""
        try:
            params = {}
            if container_number:
                params["containerNumber"] = container_number
            if order_type:
                params["orderType"] = order_type

            data = await self._make_request("/orders/service", params=params)
            orders = data if isinstance(data, list) else data.get("orders", [])

            return [
                {
                    "order_id": order.get("orderId") or order.get("id"),
                    "order_number": order.get("orderNumber"),
                    "order_type": order.get("orderType"),
                    "unit_id": order.get("containerNumber"),
                    "status": order.get("status"),
                    "requested_time": self._parse_timestamp(order.get("requestedTime")),
                    "completed_time": self._parse_timestamp(order.get("completedTime")),
                    "service_type": order.get("serviceType"),
                    "notes": order.get("notes"),
                    "facility": order.get("facility"),
                    "metadata": order,
                }
                for order in orders
            ]
        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting service orders: {str(e)}")

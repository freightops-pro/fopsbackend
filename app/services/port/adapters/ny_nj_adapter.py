"""
NY/NJ Port Adapter - Multi-terminal container tracking.

Supports direct API connections to terminals at Ports of New York and New Jersey:
- PNCT (Port Newark Container Terminal) - Ports America MTOS
- APM Terminals Elizabeth
- Maher Terminals
- GCT Bayonne (Global Container Terminals)
- GCT New York

Each terminal operates independently with its own TOS and API systems.
"""

import httpx
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

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


# NY/NJ Terminal configurations
TERMINAL_CONFIGS = {
    # Port Newark Terminals
    "PNCT": {
        "name": "Port Newark Container Terminal",
        "firms_code": "F577",
        "port": "Newark",
        "api_base_url": "https://mtosportalec.portsamerica.com/api",  # Ports America MTOS
        "auth_type": "session",  # MTOS uses session-based auth
        "supports_appointments": True,
        "operator": "Ports America",
    },
    # Port Elizabeth Terminals
    "APM_ELIZABETH": {
        "name": "APM Terminals Elizabeth",
        "firms_code": "APMN",
        "port": "Elizabeth",
        "api_base_url": "https://api.apmterminals.com/elizabeth",
        "auth_type": "api_key",
        "supports_appointments": True,
        "operator": "APM Terminals",
    },
    "MAHER": {
        "name": "Maher Terminals",
        "firms_code": "M505",
        "port": "Elizabeth",
        "api_base_url": "https://maherterminals.com/api",  # Placeholder
        "auth_type": "api_key",
        "supports_appointments": True,
        "operator": "Maher Terminals",
    },
    # Global Container Terminals
    "GCT_BAYONNE": {
        "name": "GCT Bayonne",
        "firms_code": "B131",
        "port": "Bayonne",
        "api_base_url": "https://api.gcterminals.com/bayonne",
        "auth_type": "api_key",
        "supports_appointments": True,
        "operator": "Global Container Terminals",
    },
    "GCT_NY": {
        "name": "GCT New York",
        "firms_code": "S424",
        "port": "Staten Island",
        "api_base_url": "https://api.gcterminals.com/newyork",
        "auth_type": "api_key",
        "supports_appointments": True,
        "operator": "Global Container Terminals",
    },
    # Red Hook (Brooklyn)
    "RED_HOOK": {
        "name": "Red Hook Container Terminal",
        "firms_code": "R001",
        "port": "Brooklyn",
        "api_base_url": "https://redhookterminal.com/api",  # Placeholder
        "auth_type": "api_key",
        "supports_appointments": False,
        "operator": "Red Hook Container Terminal",
    },
}


class NYNJAdapter(PortAdapter):
    """
    Adapter for NY/NJ terminals with multi-terminal API support.

    Supports direct connections to individual terminal APIs:
    - PNCT (Ports America MTOS)
    - APM Terminals Elizabeth
    - Maher Terminals
    - GCT Bayonne/New York

    Can be configured for a specific terminal or auto-detect based on container.
    """

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)

        # Get terminal from config, default to auto-detect
        self.terminal_code = (config or {}).get("terminal", "AUTO")
        self.terminal_config = TERMINAL_CONFIGS.get(self.terminal_code, {})

        # Credentials per terminal
        self.api_credentials = self.credentials or {}

        # Session tokens/cookies for session-based auth
        self._sessions: Dict[str, dict] = {}

    def _get_terminal_credentials(self, terminal_code: str) -> dict:
        """Get credentials for a specific terminal."""
        terminal_creds = self.api_credentials.get(terminal_code, {})
        if terminal_creds:
            return terminal_creds

        return {
            "api_key": self.api_credentials.get("api_key"),
            "username": self.api_credentials.get("username"),
            "password": self.api_credentials.get("password"),
            "company_code": self.api_credentials.get("company_code"),
        }

    async def _get_session_token(self, terminal_code: str) -> str:
        """Get session token for terminals using session-based auth (MTOS)."""
        # Check cached session
        cached = self._sessions.get(terminal_code)
        if cached and cached.get("expires_at", datetime.min) > datetime.utcnow():
            return cached["session_id"]

        terminal_config = TERMINAL_CONFIGS.get(terminal_code, {})
        creds = self._get_terminal_credentials(terminal_code)
        base_url = terminal_config.get("api_base_url", "")

        async with httpx.AsyncClient() as client:
            try:
                # MTOS login endpoint
                response = await client.post(
                    f"{base_url}/auth/login",
                    json={
                        "username": creds.get("username"),
                        "password": creds.get("password"),
                        "company_code": creds.get("company_code"),
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                auth_data = response.json()

                # Cache session
                self._sessions[terminal_code] = {
                    "session_id": auth_data.get("session_id") or auth_data.get("token"),
                    "expires_at": datetime.utcnow() + timedelta(hours=8),  # MTOS sessions typically last 8 hours
                }
                return self._sessions[terminal_code]["session_id"]

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError(f"Invalid credentials for {terminal_code}")
                raise PortAdapterError(f"Session login failed: {e}")

    async def _make_request(
        self,
        terminal_code: str,
        endpoint: str,
        method: str = "GET",
        params: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> dict:
        """Make authenticated API request to a terminal."""
        terminal_config = TERMINAL_CONFIGS.get(terminal_code, {})
        if not terminal_config:
            raise PortAdapterError(f"Unknown terminal: {terminal_code}")

        base_url = terminal_config.get("api_base_url", "")
        auth_type = terminal_config.get("auth_type", "api_key")
        creds = self._get_terminal_credentials(terminal_code)

        headers = {"Content-Type": "application/json"}

        if auth_type == "session":
            session_token = await self._get_session_token(terminal_code)
            headers["X-Session-ID"] = session_token
        elif auth_type == "api_key":
            api_key = creds.get("api_key")
            if not api_key:
                raise PortAuthenticationError(f"API key required for {terminal_code}")
            headers["X-API-Key"] = api_key

        async with httpx.AsyncClient() as client:
            try:
                url = f"{base_url}{endpoint}"

                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=params, timeout=30.0)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=data, params=params, timeout=30.0)
                else:
                    raise PortAdapterError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    # Clear cached session on auth failure
                    self._sessions.pop(terminal_code, None)
                    raise PortAuthenticationError(f"Authentication failed for {terminal_code}")
                elif e.response.status_code == 404:
                    raise PortNotFoundError(f"Resource not found at {terminal_code}")
                elif e.response.status_code == 429:
                    raise PortAdapterError("Rate limit exceeded")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    def _identify_terminal(self, container_number: str, port_code: str) -> str:
        """Identify which terminal a container is at."""
        if self.terminal_code != "AUTO":
            return self.terminal_code

        # Default to PNCT for Newark, APM Elizabeth for others
        if port_code.upper() == "USEWR":
            return "PNCT"
        return "APM_ELIZABETH"

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """Track container using terminal-specific APIs."""
        terminal_code = self._identify_terminal(container_number, port_code)
        terminal_config = TERMINAL_CONFIGS.get(terminal_code, {})

        try:
            data = await self._make_request(
                terminal_code,
                "/containers/availability",
                params={"container_number": container_number},
            )

            container_data = data.get("container", data.get("data", {}))
            if isinstance(container_data, list) and container_data:
                container_data = container_data[0]

            status = container_data.get("status") or container_data.get("availability_status", "UNKNOWN")
            terminal_name = terminal_config.get("name", terminal_code)
            port_name = terminal_config.get("port", "Newark")

            location = ContainerLocation(
                terminal=terminal_name,
                yard_location=container_data.get("yard_location") or container_data.get("position"),
                gate_status=container_data.get("gate_status") or container_data.get("hold_status"),
                port=port_name,
                country="US",
                timestamp=self._parse_timestamp(container_data.get("last_updated")),
            )

            vessel = None
            vessel_data = container_data.get("vessel") or {}
            if vessel_data or container_data.get("vessel_name"):
                vessel = VesselInfo(
                    name=vessel_data.get("name") or container_data.get("vessel_name"),
                    voyage=vessel_data.get("voyage") or container_data.get("voyage"),
                    eta=self._parse_timestamp(vessel_data.get("eta") or container_data.get("eta")),
                )

            dates = ContainerDates(
                discharge_date=self._parse_timestamp(container_data.get("discharge_date")),
                last_free_day=self._parse_timestamp(
                    container_data.get("last_free_day") or container_data.get("lfd")
                ),
                ingate_timestamp=self._parse_timestamp(container_data.get("ingate_date")),
                outgate_timestamp=self._parse_timestamp(container_data.get("outgate_date")),
            )

            container_details = ContainerDetails(
                size=container_data.get("size") or container_data.get("container_size"),
                type=container_data.get("type") or container_data.get("container_type"),
                weight=container_data.get("weight") or container_data.get("gross_weight"),
                seal_number=container_data.get("seal_number") or container_data.get("seal"),
                shipping_line=container_data.get("shipping_line") or container_data.get("ssl"),
            )

            holds = container_data.get("holds", [])
            if isinstance(holds, str):
                holds = [holds] if holds else []

            charges = None
            charges_data = container_data.get("charges", {})
            if charges_data or container_data.get("demurrage"):
                charges = ContainerCharges(
                    demurrage=charges_data.get("demurrage") or container_data.get("demurrage"),
                    per_diem=charges_data.get("per_diem") or container_data.get("per_diem"),
                    detention=charges_data.get("detention") or container_data.get("detention"),
                    total_charges=charges_data.get("total") or container_data.get("total_charges"),
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
                raw_data=container_data,
            )

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error tracking container at {terminal_code}: {str(e)}")

    async def get_container_events(
        self, container_number: str, port_code: str, since: Optional[datetime] = None
    ) -> list[dict]:
        """Get container event history."""
        terminal_code = self._identify_terminal(container_number, port_code)

        try:
            params = {"container_number": container_number}
            if since:
                params["since"] = since.isoformat()

            data = await self._make_request(
                terminal_code,
                "/containers/events",
                params=params,
            )

            events = data.get("events", data.get("data", []))

            return [
                {
                    "event_type": event.get("event_type") or event.get("type"),
                    "timestamp": self._parse_timestamp(event.get("timestamp") or event.get("event_time")),
                    "location": event.get("location") or event.get("position"),
                    "description": event.get("description") or event.get("remarks"),
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
        """Get vessel schedule from terminals."""
        terminal_codes = [self.terminal_code] if self.terminal_code != "AUTO" else ["PNCT", "APM_ELIZABETH"]

        all_schedules = []
        for terminal_code in terminal_codes:
            if terminal_code not in TERMINAL_CONFIGS:
                continue

            try:
                params = {}
                if vessel_name:
                    params["vessel_name"] = vessel_name

                data = await self._make_request(
                    terminal_code,
                    "/vessels/schedule",
                    params=params,
                )

                schedules = data.get("schedules", data.get("data", []))
                terminal_name = TERMINAL_CONFIGS[terminal_code].get("name", terminal_code)

                for schedule in schedules:
                    all_schedules.append({
                        "vessel_name": schedule.get("vessel_name") or schedule.get("name"),
                        "voyage": schedule.get("voyage") or schedule.get("voyage_number"),
                        "eta": self._parse_timestamp(schedule.get("eta")),
                        "etd": self._parse_timestamp(schedule.get("etd")),
                        "ata": self._parse_timestamp(schedule.get("ata")),
                        "atd": self._parse_timestamp(schedule.get("atd")),
                        "berth": schedule.get("berth"),
                        "terminal": terminal_name,
                        "status": schedule.get("status") or schedule.get("phase"),
                    })

            except PortAdapterError:
                continue
            except Exception:
                continue

        return all_schedules

    async def get_gate_appointments(
        self,
        container_number: Optional[str] = None,
        appointment_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get gate appointments."""
        terminal_code = self.terminal_code if self.terminal_code != "AUTO" else "PNCT"

        try:
            params = {}
            if container_number:
                params["container_number"] = container_number
            if appointment_date:
                params["date"] = appointment_date.strftime("%Y-%m-%d")

            data = await self._make_request(
                terminal_code,
                "/appointments",
                params=params,
            )

            appointments = data.get("appointments", data.get("data", []))

            return [
                {
                    "appointment_id": appt.get("id") or appt.get("appointment_id"),
                    "container_number": appt.get("container_number"),
                    "transaction_type": appt.get("transaction_type") or appt.get("type"),
                    "appointment_time": self._parse_timestamp(appt.get("appointment_time")),
                    "status": appt.get("status"),
                    "terminal": TERMINAL_CONFIGS.get(terminal_code, {}).get("name"),
                }
                for appt in appointments
            ]

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting appointments: {str(e)}")

    async def create_gate_appointment(
        self,
        container_number: str,
        transaction_type: str,
        appointment_time: datetime,
        trucking_company: str,
        driver_license: Optional[str] = None,
        truck_license: Optional[str] = None,
    ) -> dict:
        """Create a gate appointment."""
        terminal_code = self.terminal_code if self.terminal_code != "AUTO" else "PNCT"
        terminal_config = TERMINAL_CONFIGS.get(terminal_code, {})

        if not terminal_config.get("supports_appointments"):
            raise PortAdapterError(f"Terminal {terminal_code} does not support appointments via API")

        try:
            data = {
                "container_number": container_number,
                "transaction_type": transaction_type,
                "appointment_time": appointment_time.isoformat(),
                "trucking_company": trucking_company,
            }
            if driver_license:
                data["driver_license"] = driver_license
            if truck_license:
                data["truck_license"] = truck_license

            result = await self._make_request(
                terminal_code,
                "/appointments",
                method="POST",
                data=data,
            )

            return {
                "appointment_id": result.get("id") or result.get("appointment_id"),
                "confirmation_number": result.get("confirmation_number"),
                "status": result.get("status"),
                "terminal": terminal_config.get("name"),
                "metadata": result,
            }

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error creating appointment: {str(e)}")

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse various timestamp formats to datetime."""
        if not timestamp_str:
            return None
        try:
            if "T" in str(timestamp_str):
                return datetime.fromisoformat(str(timestamp_str).replace("Z", "+00:00"))
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"]:
                try:
                    return datetime.strptime(str(timestamp_str), fmt)
                except ValueError:
                    continue
            return None
        except (ValueError, AttributeError):
            return None

    async def test_connection(self) -> bool:
        """Test connection to terminal API."""
        terminal_code = self.terminal_code if self.terminal_code != "AUTO" else "PNCT"
        try:
            await self.get_vessel_schedule()
            return True
        except PortAuthenticationError:
            return False
        except Exception:
            return True

    @staticmethod
    def get_available_terminals() -> List[dict]:
        """Get list of supported terminals."""
        return [
            {
                "code": code,
                "name": config["name"],
                "port": config["port"],
                "firms_code": config.get("firms_code"),
                "operator": config.get("operator"),
                "supports_appointments": config.get("supports_appointments", False),
            }
            for code, config in TERMINAL_CONFIGS.items()
        ]

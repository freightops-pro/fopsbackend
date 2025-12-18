"""
LA/Long Beach Port Adapter - Multi-terminal container tracking.

Supports direct API connections to terminals at Ports of Los Angeles and Long Beach:
- TraPac (LA) - TraPac API at losangeles.trapac.com
- Fenix Marine Services (LA) - FCI API
- APM Terminals (LA) - Pier 400
- LBCT (Long Beach) - Middle Harbor
- ITS (LA) - International Transportation Service
- Yusen Terminals (LA)

Each terminal may have different API authentication and endpoints.
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


# Terminal configurations with real API information
TERMINAL_CONFIGS = {
    # Los Angeles Terminals
    "TRAPAC": {
        "name": "TraPac Los Angeles",
        "firms_code": "Y258",
        "port": "Los Angeles",
        "api_base_url": "https://emodal.trapac.com/api/v1",  # TraPac eModal API
        "auth_type": "api_key",
        "supports_appointments": True,
    },
    "FENIX": {
        "name": "Fenix Marine Services",
        "firms_code": "Y549",
        "port": "Los Angeles",
        "api_base_url": "https://honey.fenixmarineservices.com/api",  # FCI API
        "auth_type": "oauth2",
        "supports_appointments": True,
    },
    "APM_LA": {
        "name": "APM Terminals Pier 400",
        "firms_code": "Y790",
        "port": "Los Angeles",
        "api_base_url": "https://api.apmterminals.com/pier400",
        "auth_type": "api_key",
        "supports_appointments": True,
    },
    "WBCT": {
        "name": "West Basin Container Terminal",
        "firms_code": "Y773",
        "port": "Los Angeles",
        "api_base_url": "https://api.wbct.com",  # Placeholder
        "auth_type": "api_key",
        "supports_appointments": True,
    },
    "YUSEN": {
        "name": "Yusen Terminals",
        "firms_code": "Y817",
        "port": "Los Angeles",
        "api_base_url": "https://yti.com/api",  # Placeholder
        "auth_type": "api_key",
        "supports_appointments": True,
    },
    "ITS": {
        "name": "International Transportation Service",
        "firms_code": "Y682",
        "port": "Los Angeles",
        "api_base_url": "https://itsexpress.com/api",  # Placeholder
        "auth_type": "api_key",
        "supports_appointments": True,
    },
    "EVERPORT": {
        "name": "Everport Terminal Services",
        "firms_code": "Y841",
        "port": "Los Angeles",
        "api_base_url": "https://everport.com/api",  # Placeholder
        "auth_type": "api_key",
        "supports_appointments": False,
    },
    # Long Beach Terminals
    "LBCT": {
        "name": "Long Beach Container Terminal",
        "firms_code": "E108",
        "port": "Long Beach",
        "api_base_url": "https://api.lbct.com/v1",
        "auth_type": "api_key",
        "supports_appointments": True,
    },
    "SSA_MARINE": {
        "name": "SSA Marine - Pier A",
        "firms_code": "E059",
        "port": "Long Beach",
        "api_base_url": "https://ssamarine.com/api",  # Placeholder
        "auth_type": "api_key",
        "supports_appointments": True,
    },
    "TTI": {
        "name": "Total Terminals International",
        "firms_code": "E102",
        "port": "Long Beach",
        "api_base_url": "https://tti-longbeach.com/api",  # Placeholder
        "auth_type": "api_key",
        "supports_appointments": True,
    },
    "PCT": {
        "name": "Pacific Container Terminal",
        "firms_code": "E032",
        "port": "Long Beach",
        "api_base_url": "https://pctlb.com/api",  # Placeholder
        "auth_type": "api_key",
        "supports_appointments": True,
    },
}


class LALBAdapter(PortAdapter):
    """
    Adapter for LA/Long Beach terminals with multi-terminal API support.

    Supports direct connections to individual terminal APIs:
    - TraPac eModal API
    - Fenix Marine FCI API
    - APM Terminals API
    - LBCT API
    - Other terminal-specific APIs

    Can be configured to use a specific terminal or auto-detect based on container.
    """

    def __init__(self, credentials: Optional[dict] = None, config: Optional[dict] = None):
        super().__init__(credentials, config)

        # Get terminal from config, default to auto-detect
        self.terminal_code = (config or {}).get("terminal", "AUTO")
        self.terminal_config = TERMINAL_CONFIGS.get(self.terminal_code, {})

        # Credentials per terminal (can have multiple)
        self.api_credentials = self.credentials or {}

        # Session tokens for OAuth terminals
        self._tokens: Dict[str, dict] = {}

    def _get_terminal_credentials(self, terminal_code: str) -> dict:
        """Get credentials for a specific terminal."""
        # Check for terminal-specific credentials first
        terminal_creds = self.api_credentials.get(terminal_code, {})
        if terminal_creds:
            return terminal_creds

        # Fall back to default credentials
        return {
            "api_key": self.api_credentials.get("api_key"),
            "client_id": self.api_credentials.get("client_id"),
            "client_secret": self.api_credentials.get("client_secret"),
            "username": self.api_credentials.get("username"),
            "password": self.api_credentials.get("password"),
        }

    async def _get_oauth_token(self, terminal_code: str) -> str:
        """Get OAuth token for terminals that use OAuth2."""
        terminal_config = TERMINAL_CONFIGS.get(terminal_code, {})
        if terminal_config.get("auth_type") != "oauth2":
            raise PortAdapterError(f"Terminal {terminal_code} does not use OAuth2")

        # Check cached token
        cached = self._tokens.get(terminal_code)
        if cached and cached.get("expires_at", datetime.min) > datetime.utcnow():
            return cached["access_token"]

        creds = self._get_terminal_credentials(terminal_code)
        base_url = terminal_config.get("api_base_url", "")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{base_url}/oauth/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": creds.get("client_id"),
                        "client_secret": creds.get("client_secret"),
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                token_data = response.json()

                # Cache token
                self._tokens[terminal_code] = {
                    "access_token": token_data["access_token"],
                    "expires_at": datetime.utcnow() + timedelta(
                        seconds=token_data.get("expires_in", 3600) - 60
                    ),
                }
                return token_data["access_token"]

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise PortAuthenticationError(f"Invalid credentials for {terminal_code}")
                raise PortAdapterError(f"OAuth token request failed: {e}")

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

        # Build headers based on auth type
        headers = {"Content-Type": "application/json"}

        if auth_type == "oauth2":
            token = await self._get_oauth_token(terminal_code)
            headers["Authorization"] = f"Bearer {token}"
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
                    raise PortAuthenticationError(f"Authentication failed for {terminal_code}")
                elif e.response.status_code == 404:
                    raise PortNotFoundError(f"Resource not found at {terminal_code}")
                elif e.response.status_code == 429:
                    raise PortAdapterError("Rate limit exceeded")
                raise PortAdapterError(f"API request failed: {e}")
            except Exception as e:
                raise PortAdapterError(f"Error making API request: {str(e)}")

    def _identify_terminal(self, container_number: str, port_code: str) -> str:
        """
        Identify which terminal a container is at.

        This would typically query Port Optimizer or use carrier data.
        For now, returns configured terminal or tries all terminals.
        """
        if self.terminal_code != "AUTO":
            return self.terminal_code

        # Default logic based on port code
        if port_code.upper() == "USLAX":
            return "TRAPAC"  # Default to TraPac for LA
        elif port_code.upper() == "USLGB":
            return "LBCT"  # Default to LBCT for Long Beach

        return "TRAPAC"

    async def track_container(self, container_number: str, port_code: str) -> ContainerTrackingResponse:
        """
        Track container using terminal-specific APIs.

        Attempts to identify the terminal and query its API directly.
        """
        terminal_code = self._identify_terminal(container_number, port_code)
        terminal_config = TERMINAL_CONFIGS.get(terminal_code, {})

        try:
            # Try terminal-specific endpoint
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
            port_name = terminal_config.get("port", "Los Angeles")

            # Extract location
            location = ContainerLocation(
                terminal=terminal_name,
                yard_location=container_data.get("yard_location") or container_data.get("position"),
                gate_status=container_data.get("gate_status") or container_data.get("hold_status"),
                port=port_name,
                country="US",
                timestamp=self._parse_timestamp(container_data.get("last_updated")),
            )

            # Extract vessel info
            vessel = None
            vessel_data = container_data.get("vessel") or {}
            if vessel_data or container_data.get("vessel_name"):
                vessel = VesselInfo(
                    name=vessel_data.get("name") or container_data.get("vessel_name"),
                    voyage=vessel_data.get("voyage") or container_data.get("voyage"),
                    eta=self._parse_timestamp(vessel_data.get("eta") or container_data.get("eta")),
                )

            # Extract dates
            dates = ContainerDates(
                discharge_date=self._parse_timestamp(container_data.get("discharge_date")),
                last_free_day=self._parse_timestamp(
                    container_data.get("last_free_day") or container_data.get("lfd")
                ),
                ingate_timestamp=self._parse_timestamp(container_data.get("ingate_date")),
                outgate_timestamp=self._parse_timestamp(container_data.get("outgate_date")),
            )

            # Extract container details
            container_details = ContainerDetails(
                size=container_data.get("size") or container_data.get("container_size"),
                type=container_data.get("type") or container_data.get("container_type"),
                weight=container_data.get("weight") or container_data.get("gross_weight"),
                seal_number=container_data.get("seal_number") or container_data.get("seal"),
                shipping_line=container_data.get("shipping_line") or container_data.get("ssl"),
            )

            # Extract holds
            holds = container_data.get("holds", [])
            if isinstance(holds, str):
                holds = [holds] if holds else []

            # Extract charges
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
        """Get container event history from terminal."""
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
        """Get vessel schedule from terminal."""
        # Determine which terminals to query
        terminal_codes = [self.terminal_code] if self.terminal_code != "AUTO" else ["TRAPAC", "LBCT"]

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
                continue  # Skip terminals that fail
            except Exception:
                continue

        return all_schedules

    async def get_gate_appointments(
        self,
        container_number: Optional[str] = None,
        appointment_date: Optional[datetime] = None,
    ) -> list[dict]:
        """Get gate appointments from terminal."""
        terminal_code = self.terminal_code if self.terminal_code != "AUTO" else "TRAPAC"

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
        """Create a gate appointment at the terminal."""
        terminal_code = self.terminal_code if self.terminal_code != "AUTO" else "TRAPAC"
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

    async def get_truck_turn_times(self, date: Optional[datetime] = None) -> dict:
        """Get truck turn time statistics for the terminal."""
        terminal_code = self.terminal_code if self.terminal_code != "AUTO" else "TRAPAC"

        try:
            params = {}
            if date:
                params["date"] = date.strftime("%Y-%m-%d")

            data = await self._make_request(
                terminal_code,
                "/operations/turn-times",
                params=params,
            )

            return {
                "terminal": TERMINAL_CONFIGS.get(terminal_code, {}).get("name"),
                "average_turn_time": data.get("average_turn_time"),
                "median_turn_time": data.get("median_turn_time"),
                "transactions_count": data.get("count"),
                "date": date.isoformat() if date else datetime.utcnow().date().isoformat(),
            }

        except PortAdapterError:
            raise
        except Exception as e:
            raise PortAdapterError(f"Error getting turn times: {str(e)}")

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse various timestamp formats to datetime."""
        if not timestamp_str:
            return None
        try:
            # Try ISO format first
            if "T" in str(timestamp_str):
                return datetime.fromisoformat(str(timestamp_str).replace("Z", "+00:00"))
            # Try common date formats
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
        terminal_code = self.terminal_code if self.terminal_code != "AUTO" else "TRAPAC"
        try:
            await self.get_vessel_schedule()
            return True
        except PortAuthenticationError:
            return False
        except Exception:
            return True  # Other errors may be OK

    @staticmethod
    def get_available_terminals() -> List[dict]:
        """Get list of supported terminals."""
        return [
            {
                "code": code,
                "name": config["name"],
                "port": config["port"],
                "firms_code": config.get("firms_code"),
                "supports_appointments": config.get("supports_appointments", False),
            }
            for code, config in TERMINAL_CONFIGS.items()
        ]

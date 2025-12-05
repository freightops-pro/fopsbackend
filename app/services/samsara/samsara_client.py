"""Samsara API client for interacting with api.samsara.com."""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Awaitable

import httpx

logger = logging.getLogger(__name__)

# Type for token update callback
TokenUpdateCallback = Callable[[Dict[str, Any]], Awaitable[None]]


class SamsaraAPIClient:
    """Client for interacting with Samsara API (api.samsara.com).

    Supports persistent OAuth with automatic token refresh:
    - Proactive refresh: Refreshes token if expiring within 5 minutes
    - Reactive refresh: Retries on 401 after refreshing token
    - Token persistence: Calls callback to save updated tokens

    Base URL: https://api.samsara.com
    EU Base URL: https://api.eu.samsara.com
    """

    BASE_URL = "https://api.samsara.com"
    EU_BASE_URL = "https://api.eu.samsara.com"
    OAUTH_TOKEN_URL = "https://api.samsara.com/oauth2/token"
    EU_OAUTH_TOKEN_URL = "https://api.eu.samsara.com/oauth2/token"

    # Refresh token if expiring within this many seconds
    TOKEN_REFRESH_BUFFER_SECONDS = 300  # 5 minutes

    def __init__(
        self,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        use_eu: bool = False,
        on_token_update: Optional[TokenUpdateCallback] = None,
    ):
        """
        Initialize Samsara API client.

        Args:
            api_key: Samsara API key (Bearer token) - for simple API key auth
            client_id: Samsara OAuth client ID - for OAuth auth
            client_secret: Samsara OAuth client secret - for OAuth auth
            access_token: Stored OAuth access token (for persistent sessions)
            refresh_token: Stored OAuth refresh token (for token refresh)
            token_expires_at: When the access token expires
            use_eu: If True, use EU data center endpoint
            on_token_update: Async callback called when tokens are refreshed
        """
        self.api_key = api_key
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._token_expires_at = token_expires_at
        self.use_eu = use_eu
        self.base_url = self.EU_BASE_URL if use_eu else self.BASE_URL
        self._on_token_update = on_token_update

        # Determine auth method
        if client_id and client_secret:
            self.auth_method = "oauth"
        elif api_key:
            self.auth_method = "api_key"
        else:
            raise ValueError("Either api_key or (client_id, client_secret) must be provided")

    def _is_token_expiring_soon(self) -> bool:
        """Check if token is expiring within the buffer period."""
        if not self._token_expires_at:
            return True  # No expiry known, assume needs refresh
        threshold = datetime.utcnow() + timedelta(seconds=self.TOKEN_REFRESH_BUFFER_SECONDS)
        return self._token_expires_at <= threshold

    async def _refresh_access_token(self) -> str:
        """Refresh OAuth access token using refresh token or client credentials."""
        token_url = self.EU_OAUTH_TOKEN_URL if self.use_eu else self.OAUTH_TOKEN_URL

        # Determine grant type - use refresh_token if available, otherwise client_credentials
        if self._refresh_token:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        else:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    token_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0,
                )
                response.raise_for_status()
                token_data = response.json()

                self._access_token = token_data.get("access_token")
                if not self._access_token:
                    raise ValueError("No access_token in OAuth response")

                # Update refresh token if provided (Samsara may return a new one)
                if token_data.get("refresh_token"):
                    self._refresh_token = token_data["refresh_token"]

                # Calculate expiry (Samsara tokens typically last 1 hour)
                expires_in = token_data.get("expires_in", 3600)
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                # Notify callback of token update for persistence
                if self._on_token_update:
                    await self._on_token_update({
                        "access_token": self._access_token,
                        "refresh_token": self._refresh_token,
                        "token_expires_at": self._token_expires_at.isoformat(),
                        "expires_in": expires_in,
                    })

                logger.info("Samsara OAuth token refreshed successfully")
                return self._access_token

            except httpx.HTTPStatusError as e:
                # If refresh fails with 400/401, the refresh token may be revoked
                if e.response.status_code in (400, 401):
                    logger.error(f"Samsara token refresh failed (revoked?): {e.response.text}")
                    # Notify callback of revocation
                    if self._on_token_update:
                        await self._on_token_update({
                            "status": "revoked",
                            "error": str(e),
                        })
                raise
            except httpx.HTTPError as e:
                logger.error(f"Samsara OAuth refresh error: {str(e)}")
                raise

    async def _ensure_valid_token(self) -> str:
        """Ensure we have a valid access token, refreshing if needed."""
        if self.auth_method != "oauth":
            return self.api_key or ""

        # Check if token needs refresh
        if not self._access_token or self._is_token_expiring_soon():
            return await self._refresh_access_token()

        return self._access_token

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retry_on_401: bool = True,
    ) -> Dict[str, Any]:
        """Make authenticated request to Samsara API with auto-refresh on 401."""
        url = f"{self.base_url}{endpoint}"
        token = await self._ensure_valid_token()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method,
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    params=params,
                    json=json_data,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                # Retry once on 401 after refreshing token
                if e.response.status_code == 401 and retry_on_401 and self.auth_method == "oauth":
                    logger.warning("Samsara API returned 401, attempting token refresh...")
                    try:
                        self._access_token = None  # Force refresh
                        new_token = await self._refresh_access_token()

                        # Retry the request
                        retry_response = await client.request(
                            method,
                            url,
                            headers={
                                "Authorization": f"Bearer {new_token}",
                                "Content-Type": "application/json",
                            },
                            params=params,
                            json=json_data,
                            timeout=30.0,
                        )
                        retry_response.raise_for_status()
                        return retry_response.json()
                    except Exception as retry_error:
                        logger.error(f"Samsara retry after 401 failed: {retry_error}")
                        raise

                logger.error(f"Samsara API error {e.response.status_code}: {e.response.text}")
                raise

            except httpx.HTTPError as e:
                logger.error(f"Samsara request error: {str(e)}")
                raise

    async def _paginate(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        max_pages: int = 10,
    ) -> List[Dict[str, Any]]:
        """Handle cursor-based pagination for Samsara API.

        Args:
            endpoint: API endpoint
            params: Query parameters
            max_pages: Maximum number of pages to fetch (safety limit)

        Returns:
            Combined list of all data from paginated responses
        """
        all_data = []
        params = params.copy() if params else {}
        pages_fetched = 0

        while pages_fetched < max_pages:
            response = await self._request("GET", endpoint, params=params)
            data = response.get("data", [])
            all_data.extend(data)
            pages_fetched += 1

            pagination = response.get("pagination", {})
            if not pagination.get("hasNextPage"):
                break

            params["after"] = pagination.get("endCursor")

        return all_data

    async def test_connection(self) -> bool:
        """Test API connection by fetching organization info."""
        try:
            response = await self._request("GET", "/me")
            return response.get("data") is not None
        except Exception as e:
            logger.error(f"Samsara connection test failed: {str(e)}")
            return False

    async def get_organization_info(self) -> Optional[Dict[str, Any]]:
        """GET /me - Get organization info for the API token."""
        try:
            response = await self._request("GET", "/me")
            return response.get("data")
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # Vehicles
    # -------------------------------------------------------------------------

    async def get_vehicles(
        self,
        tag_ids: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        GET /fleet/vehicles - List all vehicles.

        Rate limit: 25 req/sec

        Returns:
            List of vehicle objects containing:
            - id: Unique Samsara ID
            - name: Vehicle name/number
            - vin: Vehicle Identification Number
            - make, model, year: Vehicle details
            - licensePlate: License plate info
            - externalIds: External system IDs
        """
        params: Dict[str, Any] = {}
        if tag_ids:
            params["tagIds"] = ",".join(tag_ids)
        return await self._paginate("/fleet/vehicles", params)

    async def get_vehicle(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        """GET /fleet/vehicles/{id} - Retrieve a specific vehicle."""
        try:
            response = await self._request("GET", f"/fleet/vehicles/{vehicle_id}")
            return response.get("data")
        except Exception:
            return None

    async def get_trailers(self) -> List[Dict[str, Any]]:
        """GET /fleet/trailers - List all trailers."""
        return await self._paginate("/fleet/trailers")

    async def get_equipment(self) -> List[Dict[str, Any]]:
        """GET /fleet/equipment - List all equipment."""
        return await self._paginate("/fleet/equipment")

    # -------------------------------------------------------------------------
    # Vehicle Stats / Telematics
    # -------------------------------------------------------------------------

    async def get_vehicle_stats_snapshot(
        self,
        types: List[str],
        decorations: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        GET /fleet/vehicles/stats - Get last known vehicle stats.

        Types: gps, engineStates, fuelPercents, obdOdometerMeters,
               gpsOdometerMeters, faultCodes, engineRpm, batteryMilliVolts, etc.
        """
        params: Dict[str, Any] = {"types": ",".join(types)}
        if decorations:
            params["decorations"] = ",".join(decorations)
        return await self._paginate("/fleet/vehicles/stats", params)

    async def get_vehicle_locations(
        self,
        vehicle_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get current GPS locations for all vehicles."""
        stats = await self.get_vehicle_stats_snapshot(
            types=["gps"],
            decorations=["name", "vin"]
        )

        locations = []
        for vehicle in stats:
            gps = vehicle.get("gps", {})
            if gps:
                locations.append({
                    "vehicle_id": vehicle.get("id"),
                    "vehicle_name": vehicle.get("name"),
                    "latitude": gps.get("latitude"),
                    "longitude": gps.get("longitude"),
                    "speed_mph": gps.get("speedMilesPerHour"),
                    "heading": gps.get("headingDegrees"),
                    "time": gps.get("time"),
                })

        return locations

    # -------------------------------------------------------------------------
    # Drivers
    # -------------------------------------------------------------------------

    async def get_drivers(
        self,
        driver_activation_status: str = "active",
        tag_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        GET /fleet/drivers - List all drivers.

        Args:
            driver_activation_status: Filter by status (active, deactivated, all)
            tag_ids: Optional list of tag IDs to filter by

        Returns:
            List of driver objects containing:
            - id: Unique Samsara ID
            - name: Driver name
            - username: Login username
            - phone: Phone number
            - licenseNumber, licenseState: CDL info
            - externalIds: External system IDs
            - eldExempt: Whether driver is ELD exempt
        """
        params: Dict[str, Any] = {"driverActivationStatus": driver_activation_status}
        if tag_ids:
            params["tagIds"] = ",".join(tag_ids)
        return await self._paginate("/fleet/drivers", params)

    async def get_driver(self, driver_id: str) -> Optional[Dict[str, Any]]:
        """GET /fleet/drivers/{id} - Retrieve a specific driver."""
        try:
            response = await self._request("GET", f"/fleet/drivers/{driver_id}")
            return response.get("data")
        except Exception:
            return None

    async def create_driver(self, driver_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST /fleet/drivers - Create a new driver.

        Required fields: name, username, password
        Optional: phone, licenseNumber, licenseState, externalIds, tagIds,
                  eldDayStartHour, eldPcEnabled, eldYmEnabled, eldExempt
        """
        response = await self._request("POST", "/fleet/drivers", json_data=driver_data)
        return response.get("data", {})

    async def update_driver(self, driver_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH /fleet/drivers/{id} - Update driver details."""
        response = await self._request("PATCH", f"/fleet/drivers/{driver_id}", json_data=data)
        return response.get("data", {})

    # -------------------------------------------------------------------------
    # Driver-Vehicle Assignments
    # -------------------------------------------------------------------------

    async def get_driver_vehicle_assignments(
        self,
        start_time: datetime,
        end_time: datetime,
        driver_ids: Optional[List[str]] = None,
        vehicle_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        GET /fleet/driver-vehicle-assignments
        Rate limit: 5 req/sec
        """
        params: Dict[str, Any] = {
            "startTime": start_time.isoformat() + "Z",
            "endTime": end_time.isoformat() + "Z",
        }
        if driver_ids:
            params["driverIds"] = ",".join(driver_ids)
        if vehicle_ids:
            params["vehicleIds"] = ",".join(vehicle_ids)
        return await self._paginate("/fleet/driver-vehicle-assignments", params)

    # -------------------------------------------------------------------------
    # HOS / Compliance
    # -------------------------------------------------------------------------

    async def get_hos_clocks(
        self,
        driver_ids: Optional[List[str]] = None,
        tag_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        GET /fleet/hos/clocks - Get current HOS status for all drivers.

        Returns: currentDutyStatus, driveRemainingDurationMs, shiftRemainingDurationMs,
                 cycleRemainingDurationMs, timeUntilBreakMs
        """
        params: Dict[str, Any] = {}
        if driver_ids:
            params["driverIds"] = ",".join(driver_ids)
        if tag_ids:
            params["tagIds"] = ",".join(tag_ids)
        return await self._paginate("/fleet/hos/clocks", params)

    async def get_hos_logs(
        self,
        start_time: datetime,
        end_time: datetime,
        driver_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """GET /fleet/hos/logs - Historical duty status logs."""
        params: Dict[str, Any] = {
            "startTime": start_time.isoformat() + "Z",
            "endTime": end_time.isoformat() + "Z",
        }
        if driver_ids:
            params["driverIds"] = ",".join(driver_ids)
        return await self._paginate("/fleet/hos/logs", params)

    async def get_hos_daily_logs(
        self,
        start_date: str,
        end_date: str,
        driver_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        GET /fleet/hos/daily-logs - Summarized daily activity.

        Args:
            start_date: Format YYYY-MM-DD
            end_date: Format YYYY-MM-DD
        """
        params: Dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
        }
        if driver_ids:
            params["driverIds"] = ",".join(driver_ids)
        return await self._paginate("/fleet/hos/daily-logs", params)

    async def get_hos_violations(
        self,
        driver_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """GET /fleet/hos/violations - Active HOS violations."""
        params: Dict[str, Any] = {}
        if driver_ids:
            params["driverIds"] = ",".join(driver_ids)
        return await self._paginate("/fleet/hos/violations", params)

    # -------------------------------------------------------------------------
    # IFTA Reporting
    # -------------------------------------------------------------------------

    async def get_ifta_jurisdiction_reports(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        GET /fleet/reports/ifta/jurisdiction - Miles and fuel by state.

        Args:
            start_date: Format YYYY-MM-DD
            end_date: Format YYYY-MM-DD
        """
        params = {"startDate": start_date, "endDate": end_date}
        return await self._paginate("/fleet/reports/ifta/jurisdiction", params)

    async def get_ifta_vehicle_reports(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        GET /fleet/reports/ifta/vehicle - Per-vehicle IFTA breakdown.

        Args:
            start_date: Format YYYY-MM-DD
            end_date: Format YYYY-MM-DD
        """
        params = {"startDate": start_date, "endDate": end_date}
        return await self._paginate("/fleet/reports/ifta/vehicle", params)

    # -------------------------------------------------------------------------
    # DVIRs & Maintenance
    # -------------------------------------------------------------------------

    async def get_dvirs(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """GET /fleet/dvirs/history - List DVIRs within time range."""
        params = {
            "startTime": start_time.isoformat() + "Z",
            "endTime": end_time.isoformat() + "Z",
        }
        return await self._paginate("/fleet/dvirs/history", params)

    async def get_defects(
        self,
        start_time: datetime,
        end_time: datetime,
        is_resolved: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """GET /fleet/defects - List vehicle defects."""
        params: Dict[str, Any] = {
            "startTime": start_time.isoformat() + "Z",
            "endTime": end_time.isoformat() + "Z",
        }
        if is_resolved is not None:
            params["isResolved"] = str(is_resolved).lower()
        return await self._paginate("/fleet/defects", params)

    # -------------------------------------------------------------------------
    # Safety
    # -------------------------------------------------------------------------

    async def get_safety_events(
        self,
        start_time: datetime,
        end_time: datetime,
        driver_ids: Optional[List[str]] = None,
        vehicle_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """GET /fleet/safety/events - List safety events with video URLs."""
        params: Dict[str, Any] = {
            "startTime": start_time.isoformat() + "Z",
            "endTime": end_time.isoformat() + "Z",
        }
        if driver_ids:
            params["driverIds"] = ",".join(driver_ids)
        if vehicle_ids:
            params["vehicleIds"] = ",".join(vehicle_ids)
        return await self._paginate("/fleet/safety/events", params)

    # -------------------------------------------------------------------------
    # Addresses & Geofences
    # -------------------------------------------------------------------------

    async def get_addresses(self) -> List[Dict[str, Any]]:
        """GET /addresses - List all addresses."""
        return await self._paginate("/addresses")

    async def create_address(self, address_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST /addresses - Create address with geofence.

        Required: name, formattedAddress
        Geofence: circle (radiusMeters) OR polygon (vertices array)
        """
        response = await self._request("POST", "/addresses", json_data=address_data)
        return response.get("data", {})

"""Samsara service for managing Samsara ELD/GPS integration."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import CompanyIntegration
from app.services.samsara.samsara_client import SamsaraAPIClient

logger = logging.getLogger(__name__)


class SamsaraService:
    """Service for managing Samsara integration operations.

    Handles OAuth token persistence with automatic refresh:
    - Tokens stored in CompanyIntegration.credentials JSON
    - Auto-refresh on API calls when token expires
    - Status updated to 'error' on token revocation
    """

    def __init__(self, db: AsyncSession):
        """Initialize Samsara service with database session."""
        self.db = db

    def _create_client(
        self,
        credentials: Dict[str, Any],
        use_eu: bool = False,
        on_token_update: Optional[Any] = None,
    ) -> SamsaraAPIClient:
        """Create Samsara API client with stored credentials.

        Args:
            credentials: Dict containing client_id, client_secret, and optional tokens
            use_eu: Whether to use EU data center
            on_token_update: Async callback for persisting token updates
        """
        # Parse token_expires_at from ISO string if present
        token_expires_at = None
        if credentials.get("token_expires_at"):
            try:
                token_expires_at = datetime.fromisoformat(
                    credentials["token_expires_at"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        return SamsaraAPIClient(
            client_id=credentials.get("client_id"),
            client_secret=credentials.get("client_secret"),
            access_token=credentials.get("access_token"),
            refresh_token=credentials.get("refresh_token"),
            token_expires_at=token_expires_at,
            use_eu=use_eu,
            on_token_update=on_token_update,
        )

    async def _create_token_update_callback(
        self,
        integration_id: str,
    ):
        """Create a callback to persist token updates to the database."""
        async def on_token_update(token_data: Dict[str, Any]):
            """Persist updated tokens to CompanyIntegration credentials."""
            try:
                result = await self.db.execute(
                    select(CompanyIntegration).where(CompanyIntegration.id == integration_id)
                )
                integration = result.scalar_one_or_none()

                if not integration:
                    logger.error(f"Integration {integration_id} not found for token update")
                    return

                # Check for revocation
                if token_data.get("status") == "revoked":
                    integration.status = "error"
                    integration.last_error_at = datetime.utcnow()
                    integration.last_error_message = "OAuth token revoked - reconnect required"
                    await self.db.commit()
                    logger.warning(f"Samsara integration {integration_id} marked as revoked")
                    return

                # Update credentials with new tokens
                credentials = integration.credentials or {}
                credentials["access_token"] = token_data.get("access_token")
                if token_data.get("refresh_token"):
                    credentials["refresh_token"] = token_data["refresh_token"]
                if token_data.get("token_expires_at"):
                    credentials["token_expires_at"] = token_data["token_expires_at"]

                integration.credentials = credentials
                integration.last_success_at = datetime.utcnow()
                integration.consecutive_failures = 0
                await self.db.commit()

                logger.debug(f"Updated Samsara tokens for integration {integration_id}")

            except Exception as e:
                logger.error(f"Failed to persist Samsara token update: {e}")
                # Don't raise - let the API call continue

        return on_token_update

    async def create_client_for_integration(
        self,
        integration: CompanyIntegration,
    ) -> SamsaraAPIClient:
        """Create a Samsara client for an existing integration with token persistence."""
        credentials = integration.credentials or {}
        use_eu = credentials.get("use_eu", False)

        on_token_update = await self._create_token_update_callback(integration.id)

        return self._create_client(
            credentials=credentials,
            use_eu=use_eu,
            on_token_update=on_token_update,
        )

    async def test_connection(
        self,
        client_id: str,
        client_secret: str,
        use_eu: bool = False,
    ) -> Dict[str, Any]:
        """
        Test Samsara API connection using OAuth credentials.

        Args:
            client_id: Samsara OAuth client ID
            client_secret: Samsara OAuth client secret
            use_eu: Whether to use EU data center

        Returns:
            Dict with connection status and details
        """
        try:
            credentials = {
                "client_id": client_id,
                "client_secret": client_secret,
            }
            client = self._create_client(credentials=credentials, use_eu=use_eu)
            is_connected = await client.test_connection()
            if is_connected:
                org_info = await client.get_organization_info()
                return {
                    "connected": True,
                    "message": "Connection successful",
                    "organization": org_info.get("name") if org_info else None,
                }
            return {
                "connected": False,
                "message": "Connection failed",
            }
        except Exception as e:
            logger.error(f"Samsara connection test error: {str(e)}")
            return {
                "connected": False,
                "message": f"Connection error: {str(e)}",
            }

    async def get_available_devices_from_integration(
        self,
        integration: CompanyIntegration,
    ) -> List[Dict[str, Any]]:
        """Get available ELD devices using stored integration credentials."""
        client = await self.create_client_for_integration(integration)
        vehicles = await client.get_vehicles()
        return self._transform_vehicles_to_devices(vehicles)

    async def get_available_devices(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        use_eu: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get available ELD devices from Samsara.

        Returns a list of vehicles/devices from Samsara API that can be
        linked to equipment when creating new equipment.

        Args:
            company_id: Company ID
            client_id: Samsara OAuth client ID
            client_secret: Samsara OAuth client secret
            use_eu: Whether to use EU data center

        Returns:
            List of device data with id, name, vin, make, model, year
        """
        try:
            credentials = {
                "client_id": client_id,
                "client_secret": client_secret,
            }
            client = self._create_client(credentials=credentials, use_eu=use_eu)
            vehicles = await client.get_vehicles()

            devices = []
            for vehicle in vehicles:
                # Samsara returns vehicle data in a slightly different format
                devices.append({
                    "id": vehicle.get("id"),
                    "device_id": f"samsara:{vehicle.get('id')}",
                    "number": vehicle.get("name"),
                    "vin": vehicle.get("vin"),
                    "make": vehicle.get("make"),
                    "model": vehicle.get("model"),
                    "year": vehicle.get("year"),
                    "license_plate": vehicle.get("licensePlate"),
                    "external_ids": vehicle.get("externalIds", {}),
                    "display_name": self._build_display_name(vehicle),
                })

            return devices
        except Exception as e:
            logger.error(f"Samsara device fetch error: {str(e)}")
            raise

    def _build_display_name(self, vehicle: Dict[str, Any]) -> str:
        """Build a display name for the vehicle."""
        name = vehicle.get("name", "Unit")
        make = vehicle.get("make", "")
        model = vehicle.get("model", "")

        if make or model:
            return f"{name} - {make} {model}".strip()
        return name

    def _transform_vehicles_to_devices(self, vehicles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform Samsara vehicle data to device format."""
        devices = []
        for vehicle in vehicles:
            devices.append({
                "id": vehicle.get("id"),
                "device_id": f"samsara:{vehicle.get('id')}",
                "number": vehicle.get("name"),
                "vin": vehicle.get("vin"),
                "make": vehicle.get("make"),
                "model": vehicle.get("model"),
                "year": vehicle.get("year"),
                "license_plate": vehicle.get("licensePlate"),
                "external_ids": vehicle.get("externalIds", {}),
                "display_name": self._build_display_name(vehicle),
            })
        return devices

    async def get_drivers(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        use_eu: bool = False,
        status: str = "active",
    ) -> List[Dict[str, Any]]:
        """
        Get drivers from Samsara.

        Args:
            company_id: Company ID
            client_id: Samsara OAuth client ID
            client_secret: Samsara OAuth client secret
            use_eu: Whether to use EU data center
            status: Driver activation status filter

        Returns:
            List of driver data
        """
        try:
            client = self._create_client(
                client_id=client_id,
                client_secret=client_secret,
                use_eu=use_eu,
            )
            drivers = await client.get_drivers(driver_activation_status=status)

            return [
                {
                    "id": driver.get("id"),
                    "name": driver.get("name"),
                    "username": driver.get("username"),
                    "phone": driver.get("phone"),
                    "license_number": driver.get("licenseNumber"),
                    "license_state": driver.get("licenseState"),
                    "external_ids": driver.get("externalIds", {}),
                    "eld_exempt": driver.get("eldExempt", False),
                }
                for driver in drivers
            ]
        except Exception as e:
            logger.error(f"Samsara driver fetch error: {str(e)}")
            raise

    async def get_vehicle_locations(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        use_eu: bool = False,
        vehicle_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get vehicle locations from Samsara.

        Args:
            company_id: Company ID
            client_id: Samsara OAuth client ID
            client_secret: Samsara OAuth client secret
            use_eu: Whether to use EU data center
            vehicle_ids: Optional list of vehicle IDs to filter

        Returns:
            List of vehicle location data
        """
        try:
            client = self._create_client(
                client_id=client_id,
                client_secret=client_secret,
                use_eu=use_eu,
            )
            locations = await client.get_vehicle_locations(vehicle_ids=vehicle_ids)
            return locations
        except Exception as e:
            logger.error(f"Samsara location fetch error: {str(e)}")
            raise

    async def get_hos_clocks(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        use_eu: bool = False,
        driver_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get current HOS clocks for drivers.

        Args:
            company_id: Company ID
            client_id: Samsara OAuth client ID
            client_secret: Samsara OAuth client secret
            use_eu: Whether to use EU data center
            driver_ids: Optional list of driver IDs to filter

        Returns:
            List of HOS clock data with remaining drive/shift/cycle times
        """
        try:
            client = self._create_client(
                client_id=client_id,
                client_secret=client_secret,
                use_eu=use_eu,
            )
            clocks = await client.get_hos_clocks(driver_ids=driver_ids)

            # Transform to consistent format
            return [
                {
                    "driver_id": clock.get("driver", {}).get("id"),
                    "driver_name": clock.get("driver", {}).get("name"),
                    "current_duty_status": clock.get("currentDutyStatus"),
                    "drive_remaining_ms": clock.get("driveRemainingDurationMs"),
                    "shift_remaining_ms": clock.get("shiftRemainingDurationMs"),
                    "cycle_remaining_ms": clock.get("cycleRemainingDurationMs"),
                    "time_until_break_ms": clock.get("timeUntilBreakMs"),
                }
                for clock in clocks
            ]
        except Exception as e:
            logger.error(f"Samsara HOS clocks fetch error: {str(e)}")
            raise

    async def get_hos_logs(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        start_time: datetime,
        end_time: datetime,
        use_eu: bool = False,
        driver_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get HOS logs for drivers.

        Args:
            company_id: Company ID
            client_id: Samsara OAuth client ID
            client_secret: Samsara OAuth client secret
            start_time: Start of time range
            end_time: End of time range
            use_eu: Whether to use EU data center
            driver_ids: Optional list of driver IDs to filter

        Returns:
            List of HOS log entries
        """
        try:
            client = self._create_client(
                client_id=client_id,
                client_secret=client_secret,
                use_eu=use_eu,
            )
            logs = await client.get_hos_logs(
                start_time=start_time,
                end_time=end_time,
                driver_ids=driver_ids,
            )
            return logs
        except Exception as e:
            logger.error(f"Samsara HOS logs fetch error: {str(e)}")
            raise

    async def get_ifta_jurisdiction_report(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        start_date: str,
        end_date: str,
        use_eu: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get IFTA jurisdiction report.

        Args:
            company_id: Company ID
            client_id: Samsara OAuth client ID
            client_secret: Samsara OAuth client secret
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            use_eu: Whether to use EU data center

        Returns:
            List of jurisdiction mileage data
        """
        try:
            client = self._create_client(
                client_id=client_id,
                client_secret=client_secret,
                use_eu=use_eu,
            )
            report = await client.get_ifta_jurisdiction_reports(
                start_date=start_date,
                end_date=end_date,
            )

            # Transform to consistent format
            return [
                {
                    "jurisdiction": item.get("jurisdiction"),
                    "total_miles": item.get("totalDistanceMiles"),
                    "taxable_miles": item.get("taxableDistanceMiles"),
                    "fuel_gallons": item.get("fuelConsumedGallons"),
                }
                for item in report
            ]
        except Exception as e:
            logger.error(f"Samsara IFTA report fetch error: {str(e)}")
            raise

    async def get_dvirs(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        start_time: datetime,
        end_time: datetime,
        use_eu: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get DVIRs within a time range.

        Args:
            company_id: Company ID
            client_id: Samsara OAuth client ID
            client_secret: Samsara OAuth client secret
            start_time: Start of time range
            end_time: End of time range
            use_eu: Whether to use EU data center

        Returns:
            List of DVIR records
        """
        try:
            client = self._create_client(
                client_id=client_id,
                client_secret=client_secret,
                use_eu=use_eu,
            )
            dvirs = await client.get_dvirs(
                start_time=start_time,
                end_time=end_time,
            )
            return dvirs
        except Exception as e:
            logger.error(f"Samsara DVIR fetch error: {str(e)}")
            raise

    async def get_safety_events(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        start_time: datetime,
        end_time: datetime,
        use_eu: bool = False,
        driver_ids: Optional[List[str]] = None,
        vehicle_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get safety events within a time range.

        Args:
            company_id: Company ID
            client_id: Samsara OAuth client ID
            client_secret: Samsara OAuth client secret
            start_time: Start of time range
            end_time: End of time range
            use_eu: Whether to use EU data center
            driver_ids: Optional list of driver IDs to filter
            vehicle_ids: Optional list of vehicle IDs to filter

        Returns:
            List of safety events
        """
        try:
            client = self._create_client(
                client_id=client_id,
                client_secret=client_secret,
                use_eu=use_eu,
            )
            events = await client.get_safety_events(
                start_time=start_time,
                end_time=end_time,
                driver_ids=driver_ids,
                vehicle_ids=vehicle_ids,
            )
            return events
        except Exception as e:
            logger.error(f"Samsara safety events fetch error: {str(e)}")
            raise

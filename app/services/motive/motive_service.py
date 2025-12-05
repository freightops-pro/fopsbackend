"""Motive service for managing Motive ELD/GPS integration."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.services.motive.motive_client import MotiveAPIClient
from app.services.motive.sync.driver_sync import DriverSyncService
from app.services.motive.sync.fuel_sync import FuelSyncService
from app.services.motive.sync.vehicle_sync import VehicleSyncService

logger = logging.getLogger(__name__)


class MotiveService:
    """Service for managing Motive integration operations."""

    def __init__(self, db: AsyncSession):
        """Initialize Motive service with database session."""
        self.db = db

    async def test_connection(
        self, client_id: str, client_secret: str
    ) -> Dict[str, Any]:
        """
        Test Motive API connection.

        Args:
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret

        Returns:
            Dict with connection status and details
        """
        try:
            client = MotiveAPIClient(client_id, client_secret)
            is_connected = await client.test_connection()
            if is_connected:
                company_info = await client.get_company_info()
                return {
                    "connected": True,
                    "message": "Connection successful",
                    "company": company_info.get("name") if company_info else None,
                }
            return {
                "connected": False,
                "message": "Connection failed",
            }
        except Exception as e:
            logger.error(f"Motive connection test error: {str(e)}")
            return {
                "connected": False,
                "message": f"Connection error: {str(e)}",
            }

    async def sync_vehicles(
        self, company_id: str, client_id: str, client_secret: str
    ) -> Dict[str, Any]:
        """
        Sync vehicles from Motive to company equipment.

        Args:
            company_id: Company ID
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret

        Returns:
            Dict with sync results
        """
        try:
            sync_service = VehicleSyncService(self.db)
            result = await sync_service.sync_vehicles(company_id, client_id, client_secret)
            return result
        except Exception as e:
            logger.error(f"Motive vehicle sync error: {str(e)}")
            raise

    async def sync_users(
        self, company_id: str, client_id: str, client_secret: str
    ) -> Dict[str, Any]:
        """
        Sync users (drivers) from Motive to company drivers.

        Args:
            company_id: Company ID
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret

        Returns:
            Dict with sync results
        """
        try:
            sync_service = DriverSyncService(self.db)
            result = await sync_service.sync_drivers(company_id, client_id, client_secret)
            return result
        except Exception as e:
            logger.error(f"Motive user sync error: {str(e)}")
            raise

    async def get_vehicle_locations(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        vehicle_ids: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get vehicle locations from Motive.

        Args:
            company_id: Company ID
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret
            vehicle_ids: Optional list of vehicle IDs to filter
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            List of vehicle location data
        """
        try:
            client = MotiveAPIClient(client_id, client_secret)
            start_str = start_time.isoformat() if start_time else None
            end_str = end_time.isoformat() if end_time else None

            response = await client.get_locations(
                vehicle_ids=vehicle_ids,
                start_time=start_str,
                end_time=end_str,
            )
            return response.get("data", [])
        except Exception as e:
            logger.error(f"Motive location fetch error: {str(e)}")
            raise

    async def get_hos_logs(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get Hours of Service logs from Motive.

        Args:
            company_id: Company ID
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret
            user_id: Optional user ID to filter
            start_time: Optional start time
            end_time: Optional end time

        Returns:
            List of HOS logs
        """
        try:
            client = MotiveAPIClient(client_id, client_secret)
            start_str = start_time.isoformat() if start_time else None
            end_str = end_time.isoformat() if end_time else None

            response = await client.get_hos_logs(
                user_id=user_id,
                start_time=start_str,
                end_time=end_str,
            )
            return response.get("data", [])
        except Exception as e:
            logger.error(f"Motive HOS logs fetch error: {str(e)}")
            raise

    async def get_available_devices(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
    ) -> List[Dict[str, Any]]:
        """
        Get available ELD devices from Motive.

        Returns a list of vehicles/devices from Motive API that can be
        linked to equipment when creating new equipment.

        Args:
            company_id: Company ID
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret

        Returns:
            List of device data with id, number, vin, make, model, year
        """
        try:
            client = MotiveAPIClient(client_id, client_secret)
            response = await client.get_vehicles(limit=500)
            vehicles = response.get("vehicles") or response.get("data", [])

            devices = []
            for vehicle in vehicles:
                eld_device = vehicle.get("eld_device")
                eld_device_id = None
                if eld_device:
                    if isinstance(eld_device, dict):
                        eld_device_id = eld_device.get("id")
                    else:
                        eld_device_id = str(eld_device)

                devices.append({
                    "id": vehicle.get("id"),
                    "device_id": eld_device_id or f"motive:{vehicle.get('id')}",
                    "number": vehicle.get("number"),
                    "vin": vehicle.get("vin"),
                    "make": vehicle.get("make"),
                    "model": vehicle.get("model"),
                    "year": vehicle.get("year"),
                    "asset_type": vehicle.get("asset_type"),
                    "status": vehicle.get("status"),
                    "display_name": f"{vehicle.get('number', 'Unit')} - {vehicle.get('make', '')} {vehicle.get('model', '')}".strip(" -"),
                })

            return devices
        except Exception as e:
            logger.error(f"Motive device fetch error: {str(e)}")
            raise


"""Service for syncing vehicles from Motive to Equipment model."""

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipment import Equipment
from app.services.motive.motive_client import MotiveAPIClient

logger = logging.getLogger(__name__)


class VehicleSyncService:
    """Service for syncing Motive vehicles to Equipment model."""

    def __init__(self, db: AsyncSession):
        """Initialize vehicle sync service."""
        self.db = db

    async def sync_vehicles(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        """
        Sync vehicles from Motive to Equipment model.

        Args:
            company_id: Company ID
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret
            limit: Maximum number of vehicles to sync

        Returns:
            Dict with sync results
        """
        client = MotiveAPIClient(client_id, client_secret)
        synced_count = 0
        updated_count = 0
        created_count = 0
        errors: List[str] = []

        try:
            # Fetch vehicles from Motive
            offset = 0
            all_vehicles: List[Dict[str, Any]] = []

            while True:
                response = await client.get_vehicles(limit=min(limit, 100), offset=offset)
                # Motive API returns vehicles in "vehicles" or "data" field
                vehicles = response.get("vehicles") or response.get("data", [])
                if not vehicles:
                    break
                all_vehicles.extend(vehicles)
                offset += len(vehicles)
                if len(all_vehicles) >= limit or len(vehicles) < 100:
                    break

            # Sync each vehicle
            for vehicle_data in all_vehicles:
                try:
                    result = await self._sync_single_vehicle(company_id, vehicle_data)
                    if result["created"]:
                        created_count += 1
                    else:
                        updated_count += 1
                    synced_count += 1
                except Exception as e:
                    error_msg = f"Error syncing vehicle {vehicle_data.get('id', 'unknown')}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            return {
                "success": True,
                "total_vehicles": len(all_vehicles),
                "synced": synced_count,
                "created": created_count,
                "updated": updated_count,
                "errors": errors,
            }
        except Exception as e:
            logger.error(f"Vehicle sync error: {e}", exc_info=True)
            raise

    async def _sync_single_vehicle(
        self, company_id: str, vehicle_data: Dict[str, Any]
    ) -> Dict[str, bool]:
        """
        Sync a single vehicle from Motive to Equipment.

        Args:
            company_id: Company ID
            vehicle_data: Vehicle data from Motive API

        Returns:
            Dict with sync result
        """
        motive_vehicle_id = vehicle_data.get("id")
        if not motive_vehicle_id:
            raise ValueError("Vehicle ID is required")

        # Try to find existing equipment by VIN or Motive vehicle ID
        vin = vehicle_data.get("vin")
        unit_number = vehicle_data.get("number") or str(motive_vehicle_id)

        # Check for existing equipment by VIN
        equipment = None
        if vin:
            result = await self.db.execute(
                select(Equipment).where(Equipment.company_id == company_id, Equipment.vin == vin)
            )
            equipment = result.scalar_one_or_none()

        # If not found by VIN, check by external ID (Motive vehicle ID stored in gps_device_id or eld_device_id)
        if not equipment:
            # Check if we have external ID mapping - we'll use eld_device_id to store Motive vehicle ID
            result = await self.db.execute(
                select(Equipment).where(
                    Equipment.company_id == company_id,
                    Equipment.eld_device_id == f"motive:{motive_vehicle_id}",
                )
            )
            equipment = result.scalar_one_or_none()

        # Map Motive vehicle data to Equipment model
        make = vehicle_data.get("make")
        model = vehicle_data.get("model")
        year = vehicle_data.get("year")
        status = vehicle_data.get("status", "active").upper()
        operational_status = self._map_motive_status(vehicle_data.get("status"))

        # Determine equipment type (default to TRACTOR for vehicles)
        equipment_type = "TRACTOR"  # Most Motive vehicles are tractors
        if vehicle_data.get("asset_type"):
            asset_type = vehicle_data.get("asset_type").upper()
            if "TRAILER" in asset_type:
                equipment_type = "TRAILER"
            elif "TRUCK" in asset_type or "TRACTOR" in asset_type:
                equipment_type = "TRACTOR"

        # Get ELD device info
        eld_device = vehicle_data.get("eld_device")
        eld_provider = "Motive"
        eld_device_id = None
        if eld_device:
            if isinstance(eld_device, dict):
                eld_device_id = eld_device.get("id") or f"motive:{motive_vehicle_id}"
            else:
                eld_device_id = f"motive:{motive_vehicle_id}"

        # Create or update equipment
        if equipment:
            # Update existing equipment
            equipment.unit_number = unit_number
            equipment.equipment_type = equipment_type
            equipment.status = status
            equipment.operational_status = operational_status
            equipment.make = make
            equipment.model = model
            equipment.year = year
            equipment.vin = vin
            equipment.eld_provider = eld_provider
            equipment.eld_device_id = eld_device_id
            equipment.gps_provider = "Motive"
            equipment.gps_device_id = f"motive:{motive_vehicle_id}"
            return {"created": False}
        else:
            # Create new equipment
            equipment = Equipment(
                id=str(uuid.uuid4()),
                company_id=company_id,
                unit_number=unit_number,
                equipment_type=equipment_type,
                status=status,
                operational_status=operational_status,
                make=make,
                model=model,
                year=year,
                vin=vin,
                eld_provider=eld_provider,
                eld_device_id=eld_device_id,
                gps_provider="Motive",
                gps_device_id=f"motive:{motive_vehicle_id}",
            )
            self.db.add(equipment)
            await self.db.commit()
            await self.db.refresh(equipment)
            return {"created": True}

    def _map_motive_status(self, motive_status: Optional[str]) -> Optional[str]:
        """Map Motive vehicle status to operational status."""
        if not motive_status:
            return None
        status_lower = motive_status.lower()
        if status_lower == "active":
            return "IN_SERVICE"
        elif status_lower == "inactive":
            return "OUT_OF_SERVICE"
        elif status_lower == "maintenance":
            return "IN_MAINTENANCE"
        else:
            return "UNKNOWN"

    async def sync_vehicle_location(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        vehicle_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sync vehicle location from Motive.

        Args:
            company_id: Company ID
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret
            vehicle_id: Optional specific vehicle ID to sync

        Returns:
            Dict with location sync results
        """
        client = MotiveAPIClient(client_id, client_secret)

        try:
            # Get vehicle locations from Motive
            # Note: Using get_locations which is the available method
            # For v3 locations, we would need to check if that method exists
            params = {}
            if vehicle_id:
                params["vehicle_ids"] = ",".join([vehicle_id]) if isinstance(vehicle_id, str) else ",".join(vehicle_id)
            
            response = await client.get_locations(**params)
            locations = response.get("data", []) or response.get("locations", [])

            # Update equipment records with location data
            # Note: Equipment model doesn't have location fields directly,
            # but we can store this in metadata or create location events
            # For now, we'll just return the location data

            return {
                "success": True,
                "locations_synced": len(locations),
                "locations": locations,
            }
        except Exception as e:
            logger.error(f"Vehicle location sync error: {e}", exc_info=True)
            raise


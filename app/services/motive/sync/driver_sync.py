"""Service for syncing drivers/users from Motive to Driver model."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from dateutil import parser as date_parser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver import Driver
from app.services.motive.motive_client import MotiveAPIClient

logger = logging.getLogger(__name__)


class DriverSyncService:
    """Service for syncing Motive users/drivers to Driver model."""

    def __init__(self, db: AsyncSession):
        """Initialize driver sync service."""
        self.db = db

    async def sync_drivers(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        """
        Sync drivers/users from Motive to Driver model.

        Args:
            company_id: Company ID
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret
            limit: Maximum number of drivers to sync

        Returns:
            Dict with sync results
        """
        client = MotiveAPIClient(client_id, client_secret)
        synced_count = 0
        updated_count = 0
        created_count = 0
        errors: List[str] = []

        try:
            # Fetch users from Motive
            offset = 0
            all_users: List[Dict[str, Any]] = []

            while True:
                response = await client.get_users(limit=min(limit, 100), offset=offset)
                # Motive API returns users in "users" or "data" field
                users = response.get("users") or response.get("data", [])
                if not users:
                    break
                all_users.extend(users)
                offset += len(users)
                if len(all_users) >= limit or len(users) < 100:
                    break

            # Filter for drivers only (role == "driver")
            drivers = [u for u in all_users if u.get("role", "").lower() == "driver"]

            # Sync each driver
            for user_data in drivers:
                try:
                    result = await self._sync_single_driver(company_id, user_data)
                    if result["created"]:
                        created_count += 1
                    else:
                        updated_count += 1
                    synced_count += 1
                except Exception as e:
                    error_msg = f"Error syncing driver {user_data.get('id', 'unknown')}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            return {
                "success": True,
                "total_users": len(all_users),
                "total_drivers": len(drivers),
                "synced": synced_count,
                "created": created_count,
                "updated": updated_count,
                "errors": errors,
            }
        except Exception as e:
            logger.error(f"Driver sync error: {e}", exc_info=True)
            raise

    async def _sync_single_driver(
        self, company_id: str, user_data: Dict[str, Any]
    ) -> Dict[str, bool]:
        """
        Sync a single driver from Motive to Driver model.

        Args:
            company_id: Company ID
            user_data: User data from Motive API

        Returns:
            Dict with sync result
        """
        motive_user_id = user_data.get("id")
        if not motive_user_id:
            raise ValueError("User ID is required")

        # Try to find existing driver by email or Motive user ID
        email = user_data.get("email")
        driver = None

        # Check for existing driver by email
        if email:
            result = await self.db.execute(
                select(Driver).where(Driver.company_id == company_id, Driver.email == email)
            )
            driver = result.scalar_one_or_none()

        # If not found by email, check by external ID (Motive user ID stored in profile_metadata)
        if not driver:
            # Check if we have external ID mapping in profile_metadata
            # Query all drivers for this company and filter in Python (JSON queries can be complex)
            result = await self.db.execute(
                select(Driver).where(Driver.company_id == company_id)
            )
            all_drivers = result.scalars().all()
            for d in all_drivers:
                if d.profile_metadata and d.profile_metadata.get("motive_user_id") == str(motive_user_id):
                    driver = d
                    break

        # Map Motive user data to Driver model
        first_name = user_data.get("first_name", "")
        last_name = user_data.get("last_name", "")
        phone = user_data.get("phone")
        drivers_license_number = user_data.get("drivers_license_number")
        drivers_license_state = user_data.get("drivers_license_state")

        # Parse CDL expiration if available (might be in different fields)
        cdl_expiration = None
        if user_data.get("cdl_expiration"):
            try:
                cdl_expiration = date_parser.parse(user_data.get("cdl_expiration")).date()
            except Exception:
                pass

        # Store Motive-specific data in profile_metadata
        profile_metadata = {
            "motive_user_id": motive_user_id,
            "motive_username": user_data.get("username"),
            "motive_role": user_data.get("role"),
            "drivers_license_state": drivers_license_state,
            "dot_id": user_data.get("dot_id"),
            "time_zone": user_data.get("time_zone"),
        }

        # Create or update driver
        if driver:
            # Update existing driver
            driver.first_name = first_name
            driver.last_name = last_name
            driver.email = email
            driver.phone = phone
            driver.cdl_number = drivers_license_number
            driver.cdl_expiration = cdl_expiration
            # Merge profile_metadata
            if driver.profile_metadata:
                driver.profile_metadata.update(profile_metadata)
            else:
                driver.profile_metadata = profile_metadata
            return {"created": False}
        else:
            # Create new driver
            driver = Driver(
                id=str(uuid.uuid4()),
                company_id=company_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                cdl_number=drivers_license_number,
                cdl_expiration=cdl_expiration,
                profile_metadata=profile_metadata,
            )
            self.db.add(driver)
            await self.db.commit()
            await self.db.refresh(driver)
            return {"created": True}

    async def sync_driver_hos_data(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        driver_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Sync HOS (Hours of Service) data for drivers from Motive.

        Args:
            company_id: Company ID
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret
            driver_id: Optional specific driver ID to sync
            start_time: Optional start time for HOS data
            end_time: Optional end time for HOS data

        Returns:
            Dict with HOS sync results
        """
        client = MotiveAPIClient(client_id, client_secret)

        try:
            # Get HOS logs from Motive
            if driver_id:
                # Get specific driver HOS logs
                response = await client.get_hos_logs_v2(
                    user_id=driver_id,
                    start_time=start_time.isoformat() if start_time else None,
                    end_time=end_time.isoformat() if end_time else None,
                )
            else:
                # Get all drivers HOS logs
                response = await client.get_hos_logs_v2(
                    start_time=start_time.isoformat() if start_time else None,
                    end_time=end_time.isoformat() if end_time else None,
                )

            logs = response.get("hos_logs", []) or response.get("data", []) or response.get("logs", [])

            # Store HOS data in driver profile_metadata or create HOS events
            # For now, we'll return the HOS data
            # In the future, we could create a separate HOS log model

            return {
                "success": True,
                "hos_logs_synced": len(logs),
                "logs": logs,
            }
        except Exception as e:
            logger.error(f"Driver HOS sync error: {e}", exc_info=True)
            raise

    async def sync_driver_violations(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
    ) -> Dict[str, Any]:
        """
        Sync HOS violations for drivers from Motive.

        Args:
            company_id: Company ID
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret

        Returns:
            Dict with violation sync results
        """
        client = MotiveAPIClient(client_id, client_secret)

        try:
            # Get HOS violations from Motive
            response = await client.get_hos_violations()
            violations = response.get("data", []) or response.get("violations", [])

            # Map violations to DriverIncident model
            # For now, we'll return the violations
            # In the future, we could create DriverIncident records

            return {
                "success": True,
                "violations_synced": len(violations),
                "violations": violations,
            }
        except Exception as e:
            logger.error(f"Driver violation sync error: {e}", exc_info=True)
            raise


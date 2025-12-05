"""Background sync jobs for Motive integration."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionFactory
from app.models.integration import CompanyIntegration, Integration
from app.services.motive.sync.driver_sync import DriverSyncService
from app.services.motive.sync.fuel_sync import FuelSyncService
from app.services.motive.sync.vehicle_sync import VehicleSyncService

logger = logging.getLogger(__name__)


async def sync_motive_integrations():
    """Sync all active Motive integrations."""
    async with AsyncSessionFactory() as db:
        try:
            # Find all active Motive integrations
            result = await db.execute(
                select(CompanyIntegration)
                .join(Integration)
                .where(
                    Integration.integration_key == "motive",
                    CompanyIntegration.status == "active",
                    CompanyIntegration.auto_sync == True,
                )
            )
            integrations = list(result.scalars().all())

            for integration in integrations:
                try:
                    await sync_single_motive_integration(db, integration)
                except Exception as e:
                    logger.error(f"Error syncing Motive integration {integration.id}: {e}", exc_info=True)
                    integration.last_error_at = datetime.utcnow()
                    integration.last_error_message = str(e)
                    integration.consecutive_failures += 1
                    await db.commit()
        except Exception as e:
            logger.error(f"Error in Motive sync job: {e}", exc_info=True)


async def sync_single_motive_integration(db: AsyncSession, integration: CompanyIntegration):
    """Sync a single Motive integration."""
    if not integration.credentials:
        logger.warning(f"Integration {integration.id} has no credentials")
        return

    credentials = integration.credentials
    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")

    if not client_id or not client_secret:
        logger.warning(f"Integration {integration.id} has invalid credentials")
        return

    company_id = integration.company_id
    sync_interval = integration.sync_interval_minutes or 60

    # Check if it's time to sync
    if integration.last_sync_at:
        time_since_sync = (datetime.utcnow() - integration.last_sync_at).total_seconds() / 60
        if time_since_sync < sync_interval:
            return  # Not time to sync yet

    logger.info(f"Syncing Motive integration {integration.id} for company {company_id}")

    # Sync vehicles
    try:
        vehicle_sync = VehicleSyncService(db)
        vehicle_result = await vehicle_sync.sync_vehicles(company_id, client_id, client_secret)
        logger.info(f"Vehicle sync completed: {vehicle_result.get('synced', 0)} vehicles")
    except Exception as e:
        logger.error(f"Vehicle sync failed: {e}")

    # Sync drivers
    try:
        driver_sync = DriverSyncService(db)
        driver_result = await driver_sync.sync_drivers(company_id, client_id, client_secret)
        logger.info(f"Driver sync completed: {driver_result.get('synced', 0)} drivers")
    except Exception as e:
        logger.error(f"Driver sync failed: {e}")

    # Sync fuel purchases (last 30 days)
    try:
        fuel_sync = FuelSyncService(db)
        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        fuel_result = await fuel_sync.sync_fuel_purchases(
            company_id, client_id, client_secret, start_date, end_date
        )
        logger.info(f"Fuel sync completed: {fuel_result.get('synced', 0)} purchases")
    except Exception as e:
        logger.error(f"Fuel sync failed: {e}")

    # Update integration status
    integration.last_sync_at = datetime.utcnow()
    integration.last_success_at = datetime.utcnow()
    integration.consecutive_failures = 0
    integration.last_error_at = None
    integration.last_error_message = None
    await db.commit()


async def sync_motive_vehicles_job():
    """Background job to sync Motive vehicles."""
    async with AsyncSessionFactory() as db:
        try:
            result = await db.execute(
                select(CompanyIntegration)
                .join(Integration)
                .where(
                    Integration.integration_key == "motive",
                    CompanyIntegration.status == "active",
                )
            )
            integrations = list(result.scalars().all())

            for integration in integrations:
                if not integration.credentials:
                    continue
                credentials = integration.credentials
                client_id = credentials.get("client_id")
                client_secret = credentials.get("client_secret")
                if not client_id or not client_secret:
                    continue

                try:
                    vehicle_sync = VehicleSyncService(db)
                    await vehicle_sync.sync_vehicles(
                        integration.company_id, client_id, client_secret
                    )
                except Exception as e:
                    logger.error(f"Vehicle sync job error for {integration.id}: {e}")
        except Exception as e:
            logger.error(f"Vehicle sync job error: {e}", exc_info=True)


async def sync_motive_drivers_job():
    """Background job to sync Motive drivers."""
    async with AsyncSessionFactory() as db:
        try:
            result = await db.execute(
                select(CompanyIntegration)
                .join(Integration)
                .where(
                    Integration.integration_key == "motive",
                    CompanyIntegration.status == "active",
                )
            )
            integrations = list(result.scalars().all())

            for integration in integrations:
                if not integration.credentials:
                    continue
                credentials = integration.credentials
                client_id = credentials.get("client_id")
                client_secret = credentials.get("client_secret")
                if not client_id or not client_secret:
                    continue

                try:
                    driver_sync = DriverSyncService(db)
                    await driver_sync.sync_drivers(
                        integration.company_id, client_id, client_secret
                    )
                except Exception as e:
                    logger.error(f"Driver sync job error for {integration.id}: {e}")
        except Exception as e:
            logger.error(f"Driver sync job error: {e}", exc_info=True)


async def sync_motive_fuel_job():
    """Background job to sync Motive fuel purchases."""
    async with AsyncSessionFactory() as db:
        try:
            result = await db.execute(
                select(CompanyIntegration)
                .join(Integration)
                .where(
                    Integration.integration_key == "motive",
                    CompanyIntegration.status == "active",
                )
            )
            integrations = list(result.scalars().all())

            for integration in integrations:
                if not integration.credentials:
                    continue
                credentials = integration.credentials
                client_id = credentials.get("client_id")
                client_secret = credentials.get("client_secret")
                if not client_id or not client_secret:
                    continue

                try:
                    fuel_sync = FuelSyncService(db)
                    end_date = datetime.utcnow().strftime("%Y-%m-%d")
                    start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
                    await fuel_sync.sync_fuel_purchases(
                        integration.company_id, client_id, client_secret, start_date, end_date
                    )
                except Exception as e:
                    logger.error(f"Fuel sync job error for {integration.id}: {e}")
        except Exception as e:
            logger.error(f"Fuel sync job error: {e}", exc_info=True)


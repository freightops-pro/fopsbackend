from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.core.db import AsyncSessionFactory
from app.services.automation import AutomationService
from app.services.automation_evaluator import AutomationEvaluator
from app.services.company import CompanyService
from app.services.notifications import build_channel_registry
from app.services.port.port_service import PortService
from app.background.motive_sync_jobs import (
    sync_motive_integrations,
    sync_motive_vehicles_job,
    sync_motive_drivers_job,
    sync_motive_fuel_job,
)

logger = logging.getLogger(__name__)
settings = get_settings()

automation_scheduler = AsyncIOScheduler()


async def run_automation_cycle() -> None:
    async with AsyncSessionFactory() as session:
        company_service = CompanyService(session)
        companies = await company_service.list_active()
        channels = build_channel_registry()
        evaluator = AutomationEvaluator(session, channels)

        for company in companies:
            try:
                result = await evaluator.evaluate_company(company.id)
                logger.info(
                    "automation_cycle",
                    extra={
                        "company_id": company.id,
                        "company_name": company.name,
                        "sent": len(result.sent),
                        "skipped": len(result.skipped),
                    },
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Automation evaluation failed", extra={"company_id": company.id, "error": str(exc)})


async def cleanup_completed_load_tracking() -> None:
    """Clean up container tracking data for completed loads."""
    from sqlalchemy import select
    from app.models.load import Load
    
    async with AsyncSessionFactory() as session:
        try:
            # Find all completed loads
            result = await session.execute(
                select(Load).where(Load.status == "completed")
            )
            completed_loads = result.scalars().all()
            
            port_service = PortService(session)
            cleaned_count = 0
            
            for load in completed_loads:
                try:
                    await port_service.cleanup_completed_load_tracking(load.company_id, load.id)
                    cleaned_count += 1
                except Exception as exc:
                    logger.exception(
                        "Failed to cleanup tracking for load",
                        extra={"company_id": load.company_id, "load_id": load.id, "error": str(exc)}
                    )
            
            if cleaned_count > 0:
                logger.info(
                    "container_tracking_cleanup",
                    extra={"cleaned_loads": cleaned_count}
                )
        except Exception as exc:
            logger.exception("Container tracking cleanup job failed", extra={"error": str(exc)})


def start_scheduler() -> None:
    if automation_scheduler.running:
        return
    automation_scheduler.add_job(run_automation_cycle, "interval", minutes=settings.automation_interval_minutes, id="automation-cycle", max_instances=1, coalesce=True)
    # Run cleanup job daily at 2 AM
    automation_scheduler.add_job(cleanup_completed_load_tracking, "cron", hour=2, minute=0, id="container-tracking-cleanup", max_instances=1, coalesce=True)
    # Motive sync jobs
    automation_scheduler.add_job(sync_motive_integrations, "interval", minutes=15, id="motive-sync-all", max_instances=1, coalesce=True)
    automation_scheduler.add_job(sync_motive_vehicles_job, "interval", minutes=15, id="motive-sync-vehicles", max_instances=1, coalesce=True)
    automation_scheduler.add_job(sync_motive_drivers_job, "interval", minutes=30, id="motive-sync-drivers", max_instances=1, coalesce=True)
    automation_scheduler.add_job(sync_motive_fuel_job, "interval", minutes=60, id="motive-sync-fuel", max_instances=1, coalesce=True)
    automation_scheduler.start()
    logger.info("Automation scheduler started", extra={"interval_minutes": settings.automation_interval_minutes})


def shutdown_scheduler() -> None:
    if automation_scheduler.running:
        automation_scheduler.shutdown(wait=False)
        logger.info("Automation scheduler stopped")


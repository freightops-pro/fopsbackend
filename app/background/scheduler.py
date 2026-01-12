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
from app.background.hq_sync_jobs import sync_fmcsa_leads

logger = logging.getLogger(__name__)


def check_presence_idle_users() -> None:
    """Check for idle users and auto-set them to away/offline.

    Runs every minute to detect:
    - 5 min idle -> away (if not manually set)
    - 30 min idle -> offline

    NOTE: This is a sync wrapper that runs the async implementation.
    """
    import asyncio

    async def _check_presence_idle_users_async():
        from sqlalchemy import select, distinct
        from app.models.collaboration import Presence
        from app.services.presence import PresenceService
        from app.websocket.hub import channel_hub

        async with AsyncSessionFactory() as session:
            try:
                # Get all distinct channel_ids with active presence records
                result = await session.execute(
                    select(distinct(Presence.channel_id)).where(
                        Presence.status.in_(["online", "away"])
                    )
                )
                channel_ids = [row[0] for row in result.fetchall()]

                if not channel_ids:
                    return

                presence_service = PresenceService(session)

                for channel_id in channel_ids:
                    try:
                        changed = await presence_service.check_idle_users(channel_id)
                        if changed:
                            # Broadcast presence update to channel
                            await channel_hub.broadcast(
                                channel_id,
                                {
                                    "type": "presence",
                                    "data": [
                                        state.model_dump()
                                        for state in await presence_service.current_presence(channel_id)
                                    ],
                                },
                            )
                            logger.debug(
                                "presence_idle_update",
                                extra={"channel_id": channel_id, "updated_users": len(changed)},
                            )
                    except Exception as exc:
                        logger.warning(
                            "presence_idle_check_failed",
                            extra={"channel_id": channel_id, "error": str(exc)},
                        )
            except Exception as exc:
                logger.exception("presence_idle_job_failed", extra={"error": str(exc)})

    # Run the async function properly in scheduler context
    # APScheduler with AsyncIOScheduler handles async jobs natively
    try:
        loop = asyncio.get_running_loop()
        # Create task in existing loop and await it
        loop.create_task(_check_presence_idle_users_async())
    except RuntimeError:
        # Fallback: no event loop running (shouldn't happen with AsyncIOScheduler)
        asyncio.run(_check_presence_idle_users_async())


def check_hq_presence_idle() -> None:
    """Check for idle HQ employees and auto-set them to away/offline.

    Runs every minute to detect:
    - 5 min idle -> away (if not manually set)
    - 30 min idle -> offline

    NOTE: This is a sync wrapper that runs the async implementation.
    """
    import asyncio

    async def _check_hq_presence_idle_async():
        from app.services.hq_presence import HQPresenceService

        async with AsyncSessionFactory() as session:
            try:
                presence_service = HQPresenceService(session)
                changed = await presence_service.check_idle_employees()

                if changed:
                    logger.debug(
                        "hq_presence_idle_update",
                        extra={"updated_employees": len(changed)},
                    )
            except Exception as exc:
                logger.exception("hq_presence_idle_job_failed", extra={"error": str(exc)})

    # Run the async function properly in scheduler context
    # APScheduler with AsyncIOScheduler handles async jobs natively
    try:
        loop = asyncio.get_running_loop()
        # Create task in existing loop and await it
        loop.create_task(_check_hq_presence_idle_async())
    except RuntimeError:
        # Fallback: no event loop running (shouldn't happen with AsyncIOScheduler)
        asyncio.run(_check_hq_presence_idle_async())


def cleanup_orphaned_presence() -> None:
    """Clean up orphaned presence records for deleted users/channels.

    Runs daily to remove stale presence data.

    NOTE: This is a sync wrapper that runs the async implementation.
    """
    import asyncio

    async def _cleanup_orphaned_presence_async():
        from app.services.presence import PresenceService

        async with AsyncSessionFactory() as session:
            try:
                presence_service = PresenceService(session)
                removed_count = await presence_service.cleanup_orphaned_records()

                if removed_count > 0:
                    logger.info(
                        "presence_cleanup_complete",
                        extra={"removed_count": removed_count},
                    )
            except Exception as exc:
                logger.exception("presence_cleanup_failed", extra={"error": str(exc)})

    # Run the async function properly in scheduler context
    # APScheduler with AsyncIOScheduler handles async jobs natively
    try:
        loop = asyncio.get_running_loop()
        # Create task in existing loop and await it
        loop.create_task(_cleanup_orphaned_presence_async())
    except RuntimeError:
        # Fallback: no event loop running (shouldn't happen with AsyncIOScheduler)
        asyncio.run(_cleanup_orphaned_presence_async())


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


async def run_lead_import_pipeline() -> None:
    """
    Run the FMCSA lead import pipeline (no AI processing).

    AI enrichment is triggered manually by sales reps when they view a lead.
    This keeps LLM costs low and avoids rate limits.
    """
    # Wait for database to be fully initialized (migrations complete)
    from sqlalchemy import text
    import asyncio

    for attempt in range(30):  # Wait up to 30 seconds
        try:
            async with AsyncSessionFactory() as session:
                # Check if the state column exists on hq_lead (added by migration)
                result = await session.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_name = 'hq_lead' AND column_name = 'state'")
                )
                if result.scalar_one_or_none():
                    break  # Migrations are complete
        except Exception:
            pass
        await asyncio.sleep(1)
    else:
        logger.warning("lead_import_skipped", extra={"reason": "Database migrations not complete after 30s"})
        return

    logger.info("lead_import_start", extra={"details": "Starting FMCSA lead import"})

    try:
        # Import leads from FMCSA (no AI enrichment - that's done manually per lead)
        await sync_fmcsa_leads()

        logger.info("lead_import_complete", extra={"details": "FMCSA lead import completed"})
    except Exception as exc:
        logger.exception("lead_import_failed", extra={"error": str(exc)})


async def auto_send_approved_outreach() -> None:
    """
    Automatically send outreach emails that were auto-approved.

    For Level 2 autonomy:
    - Low risk actions (small fleets) = auto-send immediately
    - Medium/High risk = wait in approval queue for human review
    """
    from app.models.hq_ai_queue import HQAIAction, AIActionStatus, AIActionType
    from app.services.hq_email import HQEmailService
    from sqlalchemy import select, and_

    async with AsyncSessionFactory() as session:
        # Find auto-executed outreach actions that haven't been processed
        result = await session.execute(
            select(HQAIAction)
            .where(
                and_(
                    HQAIAction.action_type == AIActionType.LEAD_OUTREACH,
                    HQAIAction.status == AIActionStatus.AUTO_EXECUTED,
                    HQAIAction.executed_at.is_(None),  # Not yet sent
                )
            )
            .limit(20)
        )
        actions = result.scalars().all()

        if not actions:
            return

        email_service = HQEmailService(session)
        sent_count = 0

        for action in actions:
            try:
                # Get email data from entity_data
                entity_data = action.entity_data or {}
                email_to = entity_data.get("email_to")
                subject = entity_data.get("subject")

                if not email_to or not subject:
                    continue

                # Extract body from draft_content (format: "Subject: ...\n\n<body>")
                body = action.draft_content or ""
                if "\n\n" in body:
                    body = body.split("\n\n", 1)[1]

                # Send the email
                await email_service.send_outreach_email(
                    to_email=email_to,
                    subject=subject,
                    body=body,
                    lead_id=action.entity_id,
                )

                # Mark as executed
                from datetime import datetime
                action.executed_at = datetime.utcnow()
                sent_count += 1

            except Exception as exc:
                logger.warning(f"Failed to auto-send outreach for action {action.id}: {str(exc)}")

        if sent_count > 0:
            await session.commit()
            logger.info("auto_outreach_sent", extra={"sent_count": sent_count})


# Global lock to ensure only one worker runs the scheduler
_scheduler_lock_acquired = False
_scheduler_lock_file = None


def _try_acquire_scheduler_lock() -> bool:
    """Try to acquire a file lock to ensure only one worker runs the scheduler.

    Returns True if lock was acquired, False if another worker has the lock.
    """
    global _scheduler_lock_file, _scheduler_lock_acquired
    import os
    import tempfile

    if _scheduler_lock_acquired:
        return True

    lock_path = os.path.join(tempfile.gettempdir(), "fops_scheduler.lock")

    try:
        # Try to acquire an exclusive lock
        _scheduler_lock_file = open(lock_path, "w")

        # Use fcntl for Unix/Linux file locking (non-blocking)
        try:
            import fcntl
            fcntl.flock(_scheduler_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _scheduler_lock_acquired = True
            _scheduler_lock_file.write(str(os.getpid()))
            _scheduler_lock_file.flush()
            logger.info("Scheduler lock acquired", extra={"pid": os.getpid()})
            return True
        except (IOError, OSError, ImportError):
            # Lock held by another process or fcntl not available
            _scheduler_lock_file.close()
            _scheduler_lock_file = None
            return False
    except Exception as e:
        logger.warning(f"Failed to acquire scheduler lock: {e}")
        return False


def _release_scheduler_lock() -> None:
    """Release the scheduler lock."""
    global _scheduler_lock_file, _scheduler_lock_acquired
    import os

    if _scheduler_lock_file:
        try:
            import fcntl
            fcntl.flock(_scheduler_lock_file.fileno(), fcntl.LOCK_UN)
        except (ImportError, Exception):
            pass
        try:
            _scheduler_lock_file.close()
        except Exception:
            pass
        _scheduler_lock_file = None
        _scheduler_lock_acquired = False
        logger.info("Scheduler lock released", extra={"pid": os.getpid()})


def start_scheduler() -> None:
    """Start the background scheduler.

    Uses file locking to ensure only one gunicorn worker runs the scheduler.
    """
    if automation_scheduler.running:
        return

    # Only one worker should run the scheduler
    if not _try_acquire_scheduler_lock():
        logger.info("Scheduler lock held by another worker, skipping scheduler start")
        return

    automation_scheduler.add_job(run_automation_cycle, "interval", minutes=settings.automation_interval_minutes, id="run_automation_cycle", replace_existing=True, max_instances=1, coalesce=True)
    # Run cleanup job daily at 2 AM
    automation_scheduler.add_job(cleanup_completed_load_tracking, "cron", hour=2, minute=0, id="cleanup_completed_load_tracking", replace_existing=True, max_instances=1, coalesce=True)
    # Motive sync jobs
    automation_scheduler.add_job(sync_motive_integrations, "interval", minutes=15, id="sync_motive_integrations", replace_existing=True, max_instances=1, coalesce=True)
    automation_scheduler.add_job(sync_motive_vehicles_job, "interval", minutes=15, id="sync_motive_vehicles_job", replace_existing=True, max_instances=1, coalesce=True)
    automation_scheduler.add_job(sync_motive_drivers_job, "interval", minutes=30, id="sync_motive_drivers_job", replace_existing=True, max_instances=1, coalesce=True)
    automation_scheduler.add_job(sync_motive_fuel_job, "interval", minutes=60, id="sync_motive_fuel_job", replace_existing=True, max_instances=1, coalesce=True)

    # Lead Import Pipeline - runs every 30 minutes (FMCSA sync only, no AI)
    # AI enrichment is triggered manually by sales reps per lead
    automation_scheduler.add_job(run_lead_import_pipeline, "interval", minutes=30, id="run_lead_import_pipeline", replace_existing=True, max_instances=1, coalesce=True)

    # Run immediately on startup (after 10 seconds to let app initialize)
    automation_scheduler.add_job(run_lead_import_pipeline, "date", run_date=None, id="startup-lead-import", replace_existing=True)

    # Presence auto-away jobs - run every minute to check for idle users
    automation_scheduler.add_job(check_presence_idle_users, "interval", minutes=1, id="check_presence_idle_users", replace_existing=True, max_instances=1, coalesce=True)
    automation_scheduler.add_job(check_hq_presence_idle, "interval", minutes=1, id="check_hq_presence_idle", replace_existing=True, max_instances=1, coalesce=True)
    # Presence cleanup - run daily at 3 AM to remove orphaned records
    automation_scheduler.add_job(cleanup_orphaned_presence, "cron", hour=3, minute=0, id="cleanup_orphaned_presence", replace_existing=True, max_instances=1, coalesce=True)

    automation_scheduler.start()
    logger.info("Scheduler started", extra={"interval_minutes": settings.automation_interval_minutes})


def shutdown_scheduler() -> None:
    if automation_scheduler.running:
        automation_scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _release_scheduler_lock()


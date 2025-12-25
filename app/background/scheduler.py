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
from app.background.hq_sync_jobs import sync_fmcsa_leads, ai_nurture_leads

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


async def run_full_lead_pipeline() -> None:
    """
    Run the complete autonomous lead pipeline:
    1. Sync FMCSA leads
    2. AI qualification and outreach drafting
    3. Auto-send emails for low-risk leads

    This is fully autonomous - no human intervention needed for low-risk leads.
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
        logger.warning("autonomous_pipeline_skipped", extra={"reason": "Database migrations not complete after 30s"})
        return

    logger.info("autonomous_pipeline_start", extra={"message": "Starting full autonomous lead pipeline"})

    try:
        # Step 1: Sync new leads from FMCSA
        await sync_fmcsa_leads()

        # Step 2: AI qualify and draft outreach (this handles auto-execution)
        await ai_nurture_leads()

        # Step 3: Auto-send approved emails
        await auto_send_approved_outreach()

        logger.info("autonomous_pipeline_complete", extra={"message": "Full autonomous pipeline completed"})
    except Exception as exc:
        logger.exception("autonomous_pipeline_failed", extra={"error": str(exc)})


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

    # Autonomous Lead Pipeline - runs every 30 minutes (FMCSA sync + AI + auto-send)
    automation_scheduler.add_job(run_full_lead_pipeline, "interval", minutes=30, id="autonomous-lead-pipeline", max_instances=1, coalesce=True)

    # Run immediately on startup (after 10 seconds to let app initialize)
    automation_scheduler.add_job(run_full_lead_pipeline, "date", run_date=None, id="startup-lead-pipeline")

    automation_scheduler.start()
    logger.info("Automation scheduler started", extra={"interval_minutes": settings.automation_interval_minutes, "autonomous_pipeline": True})


def shutdown_scheduler() -> None:
    if automation_scheduler.running:
        automation_scheduler.shutdown(wait=False)
        logger.info("Automation scheduler stopped")


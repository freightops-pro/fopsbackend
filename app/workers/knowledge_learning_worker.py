"""
Knowledge Learning Background Worker.

This worker periodically searches the web for new knowledge
and ingests it into the knowledge base to keep AI agents up-to-date.

Features:
- Scheduled learning for HQ topics (HR, Marketing, etc.)
- Gap-driven learning (prioritize filling knowledge gaps)
- Staleness refresh (update old content)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.models.hq_knowledge_base import (
    HQKnowledgeDocument,
    HQKnowledgeGap,
    KnowledgeCategory,
    GapType,
)

logger = logging.getLogger(__name__)


class KnowledgeLearningWorker:
    """Background worker for continuous knowledge learning."""

    def __init__(
        self,
        learning_interval_hours: int = 24,
        gap_check_interval_hours: int = 6,
        staleness_days: int = 30,
    ):
        """
        Initialize the knowledge learning worker.

        Args:
            learning_interval_hours: How often to run full learning (hours)
            gap_check_interval_hours: How often to check for gaps (hours)
            staleness_days: Days before content is considered stale
        """
        self.learning_interval = learning_interval_hours * 3600
        self.gap_check_interval = gap_check_interval_hours * 3600
        self.staleness_days = staleness_days
        self.running = False
        self.last_full_learning = None
        self.last_gap_check = None

    async def start(self):
        """Start the worker loop."""
        self.running = True
        logger.info("Knowledge Learning Worker started")
        logger.info(f"  Full learning interval: {self.learning_interval / 3600} hours")
        logger.info(f"  Gap check interval: {self.gap_check_interval / 3600} hours")
        logger.info(f"  Staleness threshold: {self.staleness_days} days")

        while self.running:
            try:
                await self.check_and_learn()
            except Exception as e:
                logger.error(f"Error in learning worker loop: {e}", exc_info=True)

            # Check every hour
            await asyncio.sleep(3600)

    async def stop(self):
        """Stop the worker loop."""
        self.running = False
        logger.info("Knowledge Learning Worker stopped")

    async def check_and_learn(self):
        """Check if learning tasks need to run."""
        now = datetime.utcnow()

        # Check for gap-driven learning
        if (
            self.last_gap_check is None
            or (now - self.last_gap_check).total_seconds() > self.gap_check_interval
        ):
            logger.info("Running gap-driven learning check")
            await self.learn_from_gaps()
            self.last_gap_check = now

        # Check for full scheduled learning
        if (
            self.last_full_learning is None
            or (now - self.last_full_learning).total_seconds() > self.learning_interval
        ):
            logger.info("Running scheduled full learning")
            await self.run_full_learning()
            self.last_full_learning = now

        # Check for stale content refresh
        await self.refresh_stale_content()

    async def learn_from_gaps(self):
        """
        Learn from detected knowledge gaps.

        Prioritizes high-priority gaps and attempts to fill them.
        """
        async with async_session_maker() as db:
            # Get open gaps with high priority
            result = await db.execute(
                select(HQKnowledgeGap)
                .where(
                    and_(
                        HQKnowledgeGap.status == "open",
                        HQKnowledgeGap.priority_score >= 0.5,
                    )
                )
                .order_by(HQKnowledgeGap.priority_score.desc())
                .limit(5)
            )
            gaps = result.scalars().all()

            if not gaps:
                logger.info("No high-priority knowledge gaps to fill")
                return

            logger.info(f"Found {len(gaps)} knowledge gaps to address")

            from app.services.hq_web_learning_service import learn_specific_topic

            for gap in gaps:
                try:
                    logger.info(f"Learning to fill gap: {gap.topic[:50]}...")

                    # Determine category
                    category = gap.suggested_category or KnowledgeCategory.GENERAL

                    # Learn from web
                    result = await learn_specific_topic(
                        db=db,
                        topic=gap.topic,
                        category=category,
                    )

                    if result["status"] in ["created", "updated"]:
                        # Mark gap as resolved
                        gap.status = "resolved"
                        gap.resolution_notes = f"Auto-filled via web learning: {result.get('document_id')}"
                        gap.resolved_by_document_id = result.get("document_id")
                        gap.resolved_at = datetime.utcnow()
                        await db.commit()
                        logger.info(f"Gap resolved: {gap.topic[:50]}")
                    else:
                        logger.warning(f"Could not fill gap: {gap.topic[:50]}")

                except Exception as e:
                    logger.error(f"Error filling gap {gap.id}: {e}")

    async def run_full_learning(self):
        """Run comprehensive learning for all configured topics."""
        async with async_session_maker() as db:
            from app.services.hq_web_learning_service import learn_all_topics

            logger.info("Starting full knowledge refresh")
            result = await learn_all_topics(db)

            logger.info(f"Full learning complete:")
            logger.info(f"  Topics processed: {result['total_topics']}")
            logger.info(f"  Documents created: {result['documents_created']}")
            logger.info(f"  Documents updated: {result['documents_updated']}")
            logger.info(f"  Failed: {result['failed']}")

    async def refresh_stale_content(self):
        """Refresh content that hasn't been updated recently."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.staleness_days)

        async with async_session_maker() as db:
            # Find stale documents
            result = await db.execute(
                select(HQKnowledgeDocument)
                .where(
                    and_(
                        HQKnowledgeDocument.updated_at < cutoff_date,
                        HQKnowledgeDocument.source.ilike("%web research%"),
                    )
                )
                .limit(3)  # Only refresh a few at a time
            )
            stale_docs = result.scalars().all()

            if not stale_docs:
                return

            logger.info(f"Found {len(stale_docs)} stale documents to refresh")

            from app.services.hq_web_learning_service import learn_specific_topic

            for doc in stale_docs:
                try:
                    # Extract topic from title
                    topic = doc.title.replace("Web Research: ", "")

                    logger.info(f"Refreshing stale document: {topic}")

                    await learn_specific_topic(
                        db=db,
                        topic=topic,
                        category=doc.category,
                    )

                except Exception as e:
                    logger.error(f"Error refreshing document {doc.id}: {e}")


# =============================================================================
# Worker Control Functions
# =============================================================================

_worker_instance: Optional[KnowledgeLearningWorker] = None


async def start_learning_worker(
    learning_interval_hours: int = 24,
    gap_check_interval_hours: int = 6,
):
    """Start the knowledge learning worker."""
    global _worker_instance

    if _worker_instance is not None:
        logger.warning("Learning worker already running")
        return

    _worker_instance = KnowledgeLearningWorker(
        learning_interval_hours=learning_interval_hours,
        gap_check_interval_hours=gap_check_interval_hours,
    )

    # Start in background
    asyncio.create_task(_worker_instance.start())


async def stop_learning_worker():
    """Stop the knowledge learning worker."""
    global _worker_instance

    if _worker_instance is None:
        return

    await _worker_instance.stop()
    _worker_instance = None


def get_learning_worker() -> Optional[KnowledgeLearningWorker]:
    """Get the current learning worker instance."""
    return _worker_instance

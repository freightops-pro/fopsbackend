"""
AI Task Manager Background Worker.

This worker polls for queued AI tasks and processes them using LLM APIs.
Each agent (Oracle, Sentinel, Nexus) has specialized prompts and capabilities.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.models.hq_ai_task import (
    HQAITask,
    HQAITaskEvent,
    HQAITaskStatus,
    HQAITaskEventType,
    HQAIAgentType,
)
from app.workers.ai_agent_processor import get_processor

logger = logging.getLogger(__name__)


class AITaskWorker:
    """Background worker that processes AI tasks."""

    def __init__(self, poll_interval: int = 5):
        """
        Initialize the AI task worker.

        Args:
            poll_interval: How often to check for new tasks (seconds)
        """
        self.poll_interval = poll_interval
        self.running = False

    async def start(self):
        """Start the worker loop."""
        self.running = True
        logger.info("AI Task Worker started")

        while self.running:
            try:
                await self.process_pending_tasks()
            except Exception as e:
                logger.error(f"Error in AI task worker loop: {e}", exc_info=True)

            # Wait before next poll
            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop the worker loop."""
        self.running = False
        logger.info("AI Task Worker stopped")

    async def process_pending_tasks(self):
        """Check for queued tasks and process them."""
        async with async_session_maker() as db:
            # Get oldest queued task
            result = await db.execute(
                select(HQAITask)
                .where(HQAITask.status == HQAITaskStatus.QUEUED)
                .order_by(HQAITask.created_at.asc())
                .limit(1)
            )
            task = result.scalar_one_or_none()

            if task:
                await self.process_task(db, task)

    async def process_task(self, db: AsyncSession, task: HQAITask):
        """
        Process a single AI task.

        Args:
            db: Database session
            task: The task to process
        """
        logger.info(f"Processing task {task.id} for agent {task.agent_type.value}")

        try:
            # Update to planning status
            task.status = HQAITaskStatus.PLANNING
            task.started_at = datetime.utcnow()
            await db.commit()

            await self.add_event(
                db,
                task.id,
                HQAITaskEventType.THINKING,
                f"{task.agent_type.value.title()} agent is analyzing your request..."
            )

            # Update to in_progress
            task.status = HQAITaskStatus.IN_PROGRESS
            task.progress_percent = 25
            await db.commit()

            # Use the AI agent processor
            processor = get_processor()
            result = await processor.process(db, task, self.add_event)

            # Mark as completed
            task.status = HQAITaskStatus.COMPLETED
            task.progress_percent = 100
            task.completed_at = datetime.utcnow()
            task.result = result
            await db.commit()

            await self.add_event(
                db,
                task.id,
                HQAITaskEventType.RESULT,
                f"Task completed successfully."
            )

            logger.info(f"Task {task.id} completed successfully")

        except Exception as e:
            logger.error(f"Error processing task {task.id}: {e}", exc_info=True)

            task.status = HQAITaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.error = str(e)
            await db.commit()

            await self.add_event(
                db,
                task.id,
                HQAITaskEventType.ERROR,
                f"Task failed: {str(e)}"
            )

    async def add_event(
        self,
        db: AsyncSession,
        task_id: str,
        event_type: HQAITaskEventType,
        content: str,
    ):
        """
        Add an event to a task's activity log.

        Args:
            db: Database session
            task_id: The task ID
            event_type: The event type
            content: The event content
        """
        event = HQAITaskEvent(
            id=str(uuid.uuid4()),
            task_id=task_id,
            event_type=event_type,
            content=content,
            timestamp=datetime.utcnow(),
        )
        db.add(event)
        await db.commit()


# Singleton worker instance
_worker: Optional[AITaskWorker] = None


def get_worker() -> AITaskWorker:
    """Get the singleton worker instance."""
    global _worker
    if _worker is None:
        _worker = AITaskWorker()
    return _worker


async def start_worker():
    """Start the background worker."""
    worker = get_worker()
    await worker.start()


async def stop_worker():
    """Stop the background worker."""
    worker = get_worker()
    await worker.stop()

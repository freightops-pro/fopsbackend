#!/usr/bin/env python
"""
Script to run the AI Task Worker as a standalone process.

Usage:
    python scripts/run_ai_task_worker.py

The worker will poll for queued AI tasks and process them using LLM APIs.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.workers.ai_task_worker import start_worker, stop_worker, get_worker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)


def handle_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    worker = get_worker()
    worker.running = False


async def main():
    """Main entry point for the worker."""
    logger.info("=" * 60)
    logger.info("AI Task Worker Starting")
    logger.info("=" * 60)
    logger.info("This worker processes background AI tasks assigned to agents:")
    logger.info("  - Oracle: Strategic Insights (business metrics, forecasts)")
    logger.info("  - Sentinel: Security & Compliance (fraud, KYB/KYC)")
    logger.info("  - Nexus: Operations Hub (system health, integrations)")
    logger.info("=" * 60)

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        await start_worker()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await stop_worker()
        logger.info("Worker shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())

"""
Run Web Learning for HQ Knowledge Base.

This script triggers web learning to gather knowledge from the internet
about HR, Marketing, Business Operations, Compliance, Taxes, Accounting, and Payroll.

Usage:
    python scripts/run_web_learning.py                    # Learn all HQ topics
    python scripts/run_web_learning.py --category hr     # Learn only HR topics
    python scripts/run_web_learning.py --topic "FMLA compliance" --category hr  # Learn specific topic
    python scripts/run_web_learning.py --research "payroll tax deadlines 2026"  # One-off research
"""

import argparse
import asyncio
import logging
import sys
import os
from pathlib import Path

# Add parent directory to path (works on both Windows and Unix)
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))

# Also add to PYTHONPATH for submodules
os.environ["PYTHONPATH"] = str(backend_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.hq_knowledge_base import KnowledgeCategory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description='Run HQ Web Learning')
    parser.add_argument(
        '--category',
        choices=[cat.value for cat in KnowledgeCategory],
        help='Learn only a specific category'
    )
    parser.add_argument(
        '--topic',
        type=str,
        help='Learn about a specific topic (requires --category)'
    )
    parser.add_argument(
        '--research',
        type=str,
        help='One-off research query (does not store in knowledge base)'
    )
    parser.add_argument(
        '--list-topics',
        action='store_true',
        help='List all configured learning topics'
    )
    return parser.parse_args()


async def run_learning(args):
    """Run the web learning process."""
    # Check for Tavily API key
    if not settings.tavily_api_key:
        logger.error("TAVILY_API_KEY not configured in .env")
        logger.error("Get a free API key at: https://tavily.com")
        return

    logger.info("=" * 60)
    logger.info("HQ Web Learning")
    logger.info("=" * 60)
    logger.info(f"Tavily API key: {settings.tavily_api_key[:10]}...")

    # List topics mode
    if args.list_topics:
        from app.services.hq_web_learning_service import HQ_LEARNING_TOPICS
        logger.info("\nConfigured HQ Learning Topics:")
        for category, topics in HQ_LEARNING_TOPICS.items():
            logger.info(f"\n{category.value.upper()}:")
            for t in topics:
                logger.info(f"  - {t['topic']} ({len(t['queries'])} queries)")
        return

    # Research mode (no storage)
    if args.research:
        from app.services.hq_web_learning_service import research_topic
        logger.info(f"\nResearching: {args.research}")
        result = await research_topic(args.research, num_results=5)
        print("\n" + result)
        return

    # Database learning modes
    try:
        db_url = settings.database_url
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

        engine = create_async_engine(db_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as db:
            # Specific topic mode
            if args.topic:
                if not args.category:
                    logger.error("--topic requires --category")
                    return

                from app.services.hq_web_learning_service import learn_specific_topic

                category = KnowledgeCategory(args.category)
                logger.info(f"\nLearning topic: {args.topic}")
                logger.info(f"Category: {category.value}")

                result = await learn_specific_topic(
                    db=db,
                    topic=args.topic,
                    category=category,
                )

                logger.info(f"\nResult: {result['status']}")
                if result.get('document_id'):
                    logger.info(f"Document ID: {result['document_id']}")
                if result.get('sources_count'):
                    logger.info(f"Sources: {result['sources_count']}")

            # Category mode
            elif args.category:
                from app.services.hq_web_learning_service import learn_category

                category = KnowledgeCategory(args.category)
                logger.info(f"\nLearning category: {category.value}")

                results = await learn_category(db, category)

                logger.info("\nResults:")
                for r in results:
                    status_icon = "✓" if r['status'] in ['created', 'updated'] else "✗"
                    logger.info(f"  {status_icon} {r['topic']}: {r['status']}")

            # Full learning mode
            else:
                from app.services.hq_web_learning_service import learn_all_topics

                logger.info("\nRunning comprehensive web learning...")
                logger.info("This may take several minutes.\n")

                result = await learn_all_topics(db)

                logger.info("\n" + "=" * 60)
                logger.info("LEARNING COMPLETE")
                logger.info("=" * 60)
                logger.info(f"Total topics: {result['total_topics']}")
                logger.info(f"Documents created: {result['documents_created']}")
                logger.info(f"Documents updated: {result['documents_updated']}")
                logger.info(f"Failed: {result['failed']}")

        await engine.dispose()

    except Exception as e:
        logger.error(f"Error: {e}")
        raise


if __name__ == "__main__":
    args = parse_args()

    # Windows requires SelectorEventLoop for psycopg async compatibility
    import sys
    if sys.platform == "win32":
        import selectors
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_learning(args))

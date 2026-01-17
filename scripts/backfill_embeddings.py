"""
Backfill embeddings for HQ Knowledge chunks that are missing embeddings.

Usage:
    python scripts/backfill_embeddings.py
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))
os.environ["PYTHONPATH"] = str(backend_dir) + os.pathsep + os.environ.get("PYTHONPATH", "")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.services.hq_rag_service import generate_embedding

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


async def backfill_embeddings():
    """Backfill embeddings for chunks that don't have them."""
    logger.info("=" * 60)
    logger.info("Backfilling HQ Knowledge Embeddings")
    logger.info("=" * 60)

    # Check for API keys
    if settings.openai_api_key:
        logger.info(f"Using OpenAI API key: {settings.openai_api_key[:10]}...")
    elif settings.google_ai_api_key:
        logger.info(f"Using Google AI API key: {settings.google_ai_api_key[:10]}...")
    else:
        logger.info("No OpenAI or Google AI key - will try Jina AI free tier")

    try:
        # Use psycopg (sync driver) for simpler parameter handling
        db_url = settings.database_url
        if db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
        elif db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://")

        engine = create_async_engine(db_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as db:
            # Find chunks without embeddings
            result = await db.execute(
                text("""
                    SELECT id, content
                    FROM hq_knowledge_chunks
                    WHERE embedding IS NULL
                    ORDER BY created_at
                """)
            )
            chunks = result.fetchall()

            total = len(chunks)
            logger.info(f"Found {total} chunks without embeddings")

            if total == 0:
                logger.info("All chunks already have embeddings!")
                return

            success = 0
            failed = 0

            for i, (chunk_id, content) in enumerate(chunks, 1):
                logger.info(f"Processing chunk {i}/{total}: {chunk_id[:8]}...")

                # Generate embedding with retry logic
                embedding = None
                for attempt in range(3):
                    embedding = await generate_embedding(content)
                    if embedding:
                        break
                    # Wait longer on each retry for rate limits
                    wait_time = (attempt + 1) * 2
                    logger.info(f"  Retrying in {wait_time}s (attempt {attempt + 1}/3)...")
                    await asyncio.sleep(wait_time)

                if embedding:
                    # Update chunk with embedding using proper pgvector format
                    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
                    await db.execute(
                        text(
                            "UPDATE hq_knowledge_chunks "
                            "SET embedding = CAST(:embedding AS vector) "
                            "WHERE id = :chunk_id"
                        ),
                        {"embedding": embedding_str, "chunk_id": chunk_id}
                    )
                    await db.commit()
                    success += 1
                    logger.info(f"  ✓ Embedding generated ({len(embedding)} dimensions)")
                else:
                    failed += 1
                    logger.warning(f"  ✗ Failed to generate embedding after 3 attempts")

                # Rate limiting - pause 25s between requests for Voyage free tier (3/min)
                if i < total:
                    await asyncio.sleep(25)

            logger.info("")
            logger.info("=" * 60)
            logger.info("BACKFILL COMPLETE")
            logger.info("=" * 60)
            logger.info(f"Success: {success}")
            logger.info(f"Failed: {failed}")

        await engine.dispose()

    except Exception as e:
        logger.error(f"Error: {e}")
        raise


if __name__ == "__main__":
    # Windows requires SelectorEventLoop for psycopg async compatibility
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(backfill_embeddings())

import logging
from collections.abc import AsyncGenerator
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.models.base import Base

logger = logging.getLogger(__name__)
settings = get_settings()

def get_async_database_url(url: str) -> str:
    """Convert database URL to async-compatible format using psycopg driver."""
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    
    if "channel_binding=" in url:
        import re
        url = re.sub(r'[&?]channel_binding=[^&]*', '', url)
        url = url.replace('?&', '?').rstrip('?')
    
    return url

database_url = get_async_database_url(settings.database_url)

connect_args = {}
if "postgresql" in database_url or "postgres" in database_url:
    connect_args = {
        "connect_timeout": 10,
    }

logger.debug(f"Creating database engine")
engine: AsyncEngine = create_async_engine(
    database_url,
    future=True,
    echo=False,  # Disable SQL echo to reduce logs
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=10,
    max_overflow=10,
    connect_args=connect_args,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

# Synchronous engine for services that need sync operations
def get_sync_database_url(url: str) -> str:
    """Convert database URL to sync-compatible format for psycopg2."""
    # Handle various URL prefixes that need to be converted to postgresql://
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    elif url.startswith("postgres://"):
        # Railway and Heroku use postgres:// but SQLAlchemy requires postgresql://
        url = url.replace("postgres://", "postgresql://", 1)

    # Remove channel_binding parameter if present (not supported by all drivers)
    if "channel_binding=" in url:
        import re
        url = re.sub(r'[&?]channel_binding=[^&]*', '', url)
        url = url.replace('?&', '?').rstrip('?')

    return url

sync_database_url = get_sync_database_url(settings.database_url)
sync_engine = create_engine(
    sync_database_url,
    echo=False,  # Disable SQL echo to reduce logs
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=10,
    max_overflow=10,
)

SyncSessionFactory = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session


def get_db_sync() -> Generator[Session, None, None]:
    """Get synchronous database session for services that don't support async."""
    session = SyncSessionFactory()
    try:
        yield session
    finally:
        session.close()


def run_alembic_migrations() -> None:
    """Run Alembic migrations synchronously."""
    import subprocess
    import sys
    logger.info("Running Alembic migrations")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            logger.info("Alembic migrations completed")
        else:
            logger.warning(f"Alembic migration warning: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        logger.warning("Alembic migration timed out after 60s")
    except Exception as e:
        logger.warning(f"Alembic migration failed: {e}")


async def init_database() -> None:
    """Run migrations and create tables."""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_alembic_migrations)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass  # Expected if using Alembic migrations


async def test_database_connection() -> bool:
    """Test database connection with timeout."""
    import asyncio
    from sqlalchemy import text

    async def _test_connection():
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()

    try:
        await asyncio.wait_for(_test_connection(), timeout=10.0)
        return True
    except asyncio.TimeoutError:
        logger.error("Database connection timed out")
        return False
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

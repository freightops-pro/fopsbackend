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

print(f"[DB] Creating database engine with URL: {database_url.split('@')[0]}@***")
engine: AsyncEngine = create_async_engine(
    database_url,
    future=True,
    echo=settings.debug,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,   # Recycle connections after 1 hour
    pool_timeout=10,     # Wait up to 10 seconds for a connection from pool
    max_overflow=10,     # Allow extra connections beyond pool_size
    connect_args=connect_args,
)
print("[DB] Database engine created")

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

# Synchronous engine for services that need sync operations
sync_database_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
sync_engine = create_engine(
    sync_database_url,
    echo=settings.debug,
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


async def init_database() -> None:
    """Create all tables. In production use Alembic migrations instead.

    Note: This is a best-effort initialization. In production, Alembic
    migrations are the source of truth. If create_all fails (e.g., due to
    enum mismatches), the app can still function if tables exist via migrations.
    """
    print("[DB] Initializing database tables...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[DB] Database tables initialized successfully")
    except Exception as e:
        # Don't fail startup - migrations are the source of truth
        print(f"[DB] WARNING: create_all failed (expected if using Alembic): {e}")
        print("[DB] Continuing with existing schema from migrations...")


async def test_database_connection() -> bool:
    """Test database connection with timeout."""
    import asyncio
    from sqlalchemy import text
    print("[DB] Testing database connection...")
    
    async def _test_connection():
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()
    
    try:
        await asyncio.wait_for(_test_connection(), timeout=10.0)
        print("[DB] Database connection test successful")
        return True
    except asyncio.TimeoutError:
        print("[DB] ERROR: Database connection test timed out after 10 seconds")
        print("[DB] Check your DATABASE_URL and network connectivity")
        return False
    except Exception as e:
        print(f"[DB] ERROR: Database connection test failed: {e}")
        print(f"[DB] Error type: {type(e).__name__}")
        import traceback
        print(f"[DB] Traceback: {traceback.format_exc()}")
        return False

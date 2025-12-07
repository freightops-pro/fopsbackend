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

# Create engine with connection pool settings and timeout to prevent hanging
connect_args = {}
if "postgresql" in settings.database_url or "postgres" in settings.database_url:
    # For PostgreSQL, use psycopg connection parameters
    connect_args = {
        "connect_timeout": 10,  # 10 second connection timeout
    }

print(f"[DB] Creating database engine with URL: {settings.database_url.split('@')[0]}@***")  # Hide password
engine: AsyncEngine = create_async_engine(
    settings.database_url,
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
    """Create all tables. In production use Alembic migrations instead."""
    print("[DB] Initializing database tables...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[DB] Database tables initialized successfully")
    except Exception as e:
        print(f"[DB] ERROR initializing database: {e}")
        raise


async def test_database_connection() -> bool:
    """Test database connection with timeout."""
    import asyncio
    from sqlalchemy import text
    print("[DB] Testing database connection...")
    try:
        # Test connection with timeout
        async with asyncio.timeout(10.0):  # 10 second timeout
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                result.fetchone()  # fetchone() is not async, returns Row directly
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

# /app/app/db/session.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
from typing import AsyncGenerator

# Database URL - adjust based on your configuration
# Common patterns:
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://user:password@localhost/dbname"
)

# For SQLite (development/testing):
# DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    future=True,
    pool_pre_ping=True,  # Optional: verify connections are alive
    pool_recycle=300,    # Optional: recycle connections after 5 minutes
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Dependency to get database session
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields db sessions.
    Used in FastAPI route dependencies.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Base class for models (optional but recommended)
# If you have this in another file (like database.py), import it instead
# from .database import Base
Base = declarative_base()

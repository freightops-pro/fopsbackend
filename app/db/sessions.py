# app/db/session.py
"""
Database session configuration for FreightOps Backend.
Handles async database connections to Neon PostgreSQL.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Your Neon PostgreSQL connection URL
DATABASE_URL = "postgresql+psycopg://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=prefer&connect_timeout=10"

# Create the async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Shows SQL queries in logs (set to False in production)
    future=True,
    pool_size=10,  # Connection pool size
    max_overflow=20,  # Max overflow connections
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_async_session() -> AsyncSession:
    """
    Dependency function to get a database session.
    Used in FastAPI route dependencies.
    
    Example usage in routes:
    @router.get("/items")
    async def get_items(db: AsyncSession = Depends(get_async_session)):
        # Use db session here
        pass
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

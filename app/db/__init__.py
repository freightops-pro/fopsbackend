# Create empty __init__.py for db package
touch app/db/__init__.py

# Create session.py with basic content
echo "from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Database URL - you'll need to configure this properly
DATABASE_URL = 'postgresql+asyncpg://user:password@localhost/dbname'

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session" > app/db/session.py

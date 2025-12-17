import asyncio
from sqlalchemy import text
from app.core.database import async_engine

async def check():
    async with async_engine.connect() as conn:
        result = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"))
        tables = [row[0] for row in result]
        print("Tables in database:")
        for table in tables:
            print(f"  - {table}")

        # Check specifically for equipment table
        if 'equipment' in tables:
            print("\n✓ equipment table exists")
        else:
            print("\n✗ equipment table DOES NOT exist")

asyncio.run(check())

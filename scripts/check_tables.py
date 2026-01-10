import asyncio
import sys
if sys.platform == "win32":
    import selectors
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    asyncio.set_event_loop(loop)

from app.core.db import AsyncSessionFactory
from sqlalchemy import text

async def check_tables():
    async with AsyncSessionFactory() as db:
        result = await db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"))
        tables = [r[0] for r in result.fetchall()]
        print("Tables in database:")
        for table in tables:
            print(f"  - {table}")
        print(f"\nTotal: {len(tables)} tables")

if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(check_tables())
    else:
        asyncio.run(check_tables())

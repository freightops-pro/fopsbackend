import asyncio
from sqlalchemy import text
from app.core.db import AsyncSessionFactory

async def update_houston():
    async with AsyncSessionFactory() as db:
        # Update Port of Houston to use OAuth2 since FreightOps has API credentials
        await db.execute(text("""
            UPDATE port
            SET auth_type='oauth2',
                adapter_class='PortHoustonAdapter'
            WHERE port_code='USHOU'
        """))
        await db.commit()
        print('Port of Houston updated to use OAuth2 API')

asyncio.run(update_houston())

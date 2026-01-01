import asyncio
import sys

# Fix for Windows - use SelectorEventLoop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select
from app.core.db import AsyncSessionFactory
from app.models.user import User
from app.core.security import hash_password

async def reset_password():
    async with AsyncSessionFactory() as db:
        result = await db.execute(
            select(User).where(User.email == 'rcarbonellusa@gmail.com')
        )
        user = result.scalar_one_or_none()
        if user:
            user.hashed_password = hash_password('Catalina$2023')
            user.failed_login_attempts = 0
            user.locked_until = None
            await db.commit()
            print(f'Password reset for {user.email}')
        else:
            print('User not found!')

asyncio.run(reset_password())

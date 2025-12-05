import asyncio
from sqlalchemy import select
from app.core.db import AsyncSessionFactory
from app.models.user import User
from app.models.company import Company

async def check_user():
    async with AsyncSessionFactory() as db:
        # Check for the user
        result = await db.execute(select(User).where(User.email == 'freightopsdispatch@gmail.com'))
        user = result.scalar_one_or_none()

        if user:
            print(f'User found:')
            print(f'  ID: {user.id}')
            print(f'  Email: {user.email}')
            print(f'  First Name: {user.first_name}')
            print(f'  Last Name: {user.last_name}')
            print(f'  Active: {user.is_active}')
            print(f'  Company ID: {user.company_id}')
            print(f'  Has Password: {bool(user.hashed_password)}')

            # Check company
            company = await db.get(Company, user.company_id)
            if company:
                print(f'\nCompany found:')
                print(f'  ID: {company.id}')
                print(f'  Name: {company.name}')
                print(f'  DOT Number: {company.dotNumber}')
                print(f'  MC Number: {company.mcNumber}')
                print(f'  Active: {company.isActive}')
            else:
                print(f'\nCompany NOT found for ID: {user.company_id}')
        else:
            print('User NOT found with email: freightopsdispatch@gmail.com')

            # Check if there's a similar email
            result = await db.execute(select(User).where(User.email.like('%freight%')))
            users = result.scalars().all()
            if users:
                print(f'\nFound {len(users)} users with "freight" in email:')
                for u in users:
                    print(f'  - {u.email}')

asyncio.run(check_user())

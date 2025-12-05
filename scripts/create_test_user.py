"""
Script to create a test user for development/testing purposes.
Usage: poetry run python scripts/create_test_user.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.db import AsyncSessionFactory
from app.core.security import hash_password
from app.models.company import Company
from app.models.user import User
from sqlalchemy import select
import uuid


async def create_test_user():
    """Create a test user with company for development."""
    async with AsyncSessionFactory() as db:
        # Check if user already exists
        test_email = "test@freightops.com"
        result = await db.execute(select(User).where(User.email == test_email))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            print(f"User {test_email} already exists!")
            print(f"Company DOT: {existing_user.company.dotNumber or 'N/A'}")
            print(f"Company MC: {existing_user.company.mcNumber or 'N/A'}")
            return
        
        # Create company
        company = Company(
            id=str(uuid.uuid4()),
            name="Test Freight Company",
            email=test_email,
            phone="555-123-4567",
            subscriptionPlan="pro",
            isActive=True,
            businessType="carrier",
            dotNumber="1234567",  # Test DOT number
            mcNumber="MC123456",  # Test MC number
            primaryContactName="Test User",
        )
        db.add(company)
        await db.flush()  # Get company ID
        
        # Create user
        user = User(
            id=str(uuid.uuid4()),
            email=test_email,
            hashed_password=hash_password("test123456"),  # Password: test123456
            first_name="Test",
            last_name="User",
            company_id=company.id,
            role="TENANT_ADMIN",
            is_active=True,
        )
        db.add(user)
        
        await db.commit()
        
        print("=" * 60)
        print("Test user created successfully!")
        print("=" * 60)
        print(f"Email: {test_email}")
        print(f"Password: test123456")
        print(f"USDOT Number: 1234567")
        print(f"MC Number: MC123456")
        print("=" * 60)
        print("\nYou can use either the USDOT or MC number as the verification code.")
        print("For login, use:")
        print("  - Email: test@freightops.com")
        print("  - Password: test123456")
        print("  - Verification Code: 1234567 (or MC123456)")


if __name__ == "__main__":
    import sys
    import platform
    
    # Fix for Windows ProactorEventLoop issue with psycopg
    if platform.system() == "Windows":
        import selectors
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.set_event_loop(loop)
        loop.run_until_complete(create_test_user())
    else:
        asyncio.run(create_test_user())


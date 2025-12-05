"""
Script to create an HQ admin employee for development/testing purposes.
Usage: poetry run python scripts/create_hq_employee.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.db import AsyncSessionFactory
from app.core.security import hash_password
from app.models.hq_employee import HQEmployee, HQRole
from sqlalchemy import select
import uuid


async def create_hq_employee():
    """Create an HQ admin employee for development."""
    async with AsyncSessionFactory() as db:
        # Check if employee already exists
        test_email = "admin@freightops.com"
        result = await db.execute(select(HQEmployee).where(HQEmployee.email == test_email))
        existing_employee = result.scalar_one_or_none()

        if existing_employee:
            print(f"HQ Employee {test_email} already exists!")
            print(f"Employee Number: {existing_employee.employee_number}")
            print(f"Role: {existing_employee.role.value}")
            return

        # Create HQ employee
        employee = HQEmployee(
            id=str(uuid.uuid4()),
            employee_number="HQ001",
            email=test_email,
            hashed_password=hash_password("admin123456"),
            first_name="Admin",
            last_name="User",
            role=HQRole.SUPER_ADMIN,
            department="Administration",
            phone="555-999-0001",
            is_active=True,
            must_change_password=False,
        )
        db.add(employee)

        await db.commit()

        print("=" * 60)
        print("HQ Admin Employee created successfully!")
        print("=" * 60)
        print(f"Email: {test_email}")
        print(f"Employee Number: HQ001")
        print(f"Password: admin123456")
        print(f"Role: SUPER_ADMIN")
        print("=" * 60)
        print("\nTo login to HQ Admin Portal:")
        print("  URL: http://localhost:5174")
        print("  Email: admin@freightops.com")
        print("  Employee Number: HQ001")
        print("  Password: admin123456")


if __name__ == "__main__":
    import platform

    # Fix for Windows ProactorEventLoop issue with psycopg
    if platform.system() == "Windows":
        import selectors
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.set_event_loop(loop)
        loop.run_until_complete(create_hq_employee())
    else:
        asyncio.run(create_hq_employee())

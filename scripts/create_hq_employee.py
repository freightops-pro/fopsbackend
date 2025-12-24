"""
Script to create an HQ admin employee for development/testing purposes.
Usage: poetry run python scripts/create_hq_employee.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import all models to ensure relationships are resolved
from app.models import *  # noqa: F401, F403
from app.core.db import AsyncSessionFactory
from app.core.security import hash_password
from app.models.hq_employee import HQEmployee, HQRole
from sqlalchemy import select
import uuid


async def create_hq_employee():
    """Create HQ admin employees including the owner."""
    async with AsyncSessionFactory() as db:
        # Owner account - Rene Carbonell
        owner_email = "rcarbonell@freightopspro.com"
        owner_emp_number = "001"

        # Check by email first
        result = await db.execute(select(HQEmployee).where(HQEmployee.email == owner_email))
        existing_owner = result.scalar_one_or_none()

        if existing_owner:
            print(f"Owner {owner_email} already exists!")
            print(f"Employee Number: {existing_owner.employee_number}")
            print(f"Role: {existing_owner.role.value}")
        else:
            # Check if employee number already exists (might be different email)
            result = await db.execute(select(HQEmployee).where(HQEmployee.employee_number == owner_emp_number))
            existing_by_number = result.scalar_one_or_none()

            if existing_by_number:
                # Update existing employee to become the owner
                existing_by_number.email = owner_email
                existing_by_number.hashed_password = hash_password("Zkorpio18!")
                existing_by_number.first_name = "Rene"
                existing_by_number.last_name = "Carbonell"
                existing_by_number.role = HQRole.SUPER_ADMIN
                existing_by_number.department = "Executive"
                existing_by_number.is_active = True
                existing_by_number.must_change_password = False
                print(f"Updated existing employee #{owner_emp_number} to owner account!")
            else:
                # Create owner account
                owner = HQEmployee(
                    id=str(uuid.uuid4()),
                    employee_number=owner_emp_number,
                    email=owner_email,
                    hashed_password=hash_password("Zkorpio18!"),
                    first_name="Rene",
                    last_name="Carbonell",
                    role=HQRole.SUPER_ADMIN,
                    department="Executive",
                    phone=None,
                    is_active=True,
                    must_change_password=False,
                )
                db.add(owner)
                print("Owner account created!")

        # Also create a test admin for development
        test_email = "admin@freightops.com"
        result = await db.execute(select(HQEmployee).where(HQEmployee.email == test_email))
        existing_employee = result.scalar_one_or_none()

        if existing_employee:
            print(f"Test admin {test_email} already exists!")
        else:
            # Create test admin employee
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
            print("Test admin account created!")

        await db.commit()

        print("=" * 60)
        print("HQ Admin Employees ready!")
        print("=" * 60)
        print("\nOwner Account:")
        print(f"  Email: {owner_email}")
        print(f"  Employee Number: 001")
        print(f"  Password: Zkorpio18!")
        print(f"  Role: SUPER_ADMIN")
        print("-" * 60)
        print("\nTest Admin Account:")
        print(f"  Email: {test_email}")
        print(f"  Employee Number: HQ001")
        print(f"  Password: admin123456")
        print(f"  Role: SUPER_ADMIN")
        print("=" * 60)
        print("\nTo login to HQ Admin Portal:")
        print("  URL: http://localhost:5174")


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

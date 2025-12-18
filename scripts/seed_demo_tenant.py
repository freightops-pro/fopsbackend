"""
Demo Tenant Seed Script

Creates a complete demo company with:
- 1 Company (Demo Freight Co.)
- 5 Staff users (owner, dispatcher, fleet_manager, safety, payroll)
- 20 Drivers with compliance data
- 20 Trucks + 15 Trailers
- ~900 loads (5/day for 6 months) with complete history

Run: python -m scripts.seed_demo_tenant
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_maker
from app.models.company import Company
from app.models.user import User
from app.models.driver import Driver, DriverIncident, DriverTraining
from app.models.equipment import Equipment, EquipmentUsageEvent, EquipmentMaintenanceEvent
from app.models.load import Load, LoadStop
from app.models.worker import Worker, WorkerType, WorkerRole, WorkerStatus

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============== CONFIGURATION ==============

COMPANY_NAME = "Demo Freight Co."
COMPANY_EMAIL = "demo@freightops.com"
COMPANY_DOT = "1234567"
COMPANY_MC = "MC-123456"

# Owner credentials - IMPORTANT: Change in production!
OWNER_EMAIL = "owner@demofreight.com"
OWNER_PASSWORD = "Demo2024!"

# Staff to create
STAFF = [
    {"email": "owner@demofreight.com", "first": "Michael", "last": "Chen", "role": "owner"},
    {"email": "dispatch@demofreight.com", "first": "Sarah", "last": "Johnson", "role": "dispatcher"},
    {"email": "fleet@demofreight.com", "first": "Robert", "last": "Martinez", "role": "fleet_manager"},
    {"email": "safety@demofreight.com", "first": "Emily", "last": "Thompson", "role": "safety"},
    {"email": "payroll@demofreight.com", "first": "David", "last": "Wilson", "role": "payroll"},
]

# Driver names pool
DRIVER_FIRST_NAMES = [
    "James", "John", "Robert", "William", "David", "Richard", "Joseph", "Thomas",
    "Charles", "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Donald",
    "Steven", "Paul", "Andrew", "Joshua", "Kenneth"
]

DRIVER_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin"
]

# Customer names for loads
CUSTOMERS = [
    "Amazon Fulfillment", "Walmart Distribution", "Target Logistics", "Home Depot Supply",
    "Costco Wholesale", "Kroger Distribution", "FedEx Ground", "UPS Freight",
    "XPO Logistics", "JB Hunt", "Werner Enterprises", "Schneider National",
    "PODS Moving", "ABF Freight", "Old Dominion", "Estes Express",
    "Saia LTL", "YRC Freight", "R+L Carriers", "Averitt Express"
]

# Commodities
COMMODITIES = [
    "General Freight", "Electronics", "Furniture", "Automotive Parts", "Food Products",
    "Beverages", "Chemicals", "Paper Products", "Building Materials", "Machinery",
    "Textiles", "Plastics", "Medical Supplies", "Consumer Goods", "Industrial Equipment"
]

# Cities for routes
CITIES = [
    ("Los Angeles", "CA", 34.0522, -118.2437),
    ("Houston", "TX", 29.7604, -95.3698),
    ("Phoenix", "AZ", 33.4484, -112.0740),
    ("Dallas", "TX", 32.7767, -96.7970),
    ("San Diego", "CA", 32.7157, -117.1611),
    ("Denver", "CO", 39.7392, -104.9903),
    ("Las Vegas", "NV", 36.1699, -115.1398),
    ("Seattle", "WA", 47.6062, -122.3321),
    ("Portland", "OR", 45.5152, -122.6784),
    ("Salt Lake City", "UT", 40.7608, -111.8910),
    ("Albuquerque", "NM", 35.0844, -106.6504),
    ("Tucson", "AZ", 32.2226, -110.9747),
    ("Oklahoma City", "OK", 35.4676, -97.5164),
    ("El Paso", "TX", 31.7619, -106.4850),
    ("Sacramento", "CA", 38.5816, -121.4944),
]

# Truck makes/models
TRUCK_MAKES = [
    ("Freightliner", "Cascadia"),
    ("Kenworth", "T680"),
    ("Peterbilt", "579"),
    ("Volvo", "VNL 860"),
    ("International", "LT"),
    ("Mack", "Anthem"),
]

TRAILER_TYPES = ["Dry Van", "Reefer", "Flatbed"]

# Load statuses for historical data
COMPLETED_STATUSES = ["delivered", "invoiced", "paid"]


# ============== HELPER FUNCTIONS ==============

def generate_id() -> str:
    return str(uuid.uuid4())


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def random_date_between(start: datetime, end: datetime) -> datetime:
    delta = end - start
    random_days = random.randint(0, delta.days)
    random_seconds = random.randint(0, 86400)
    return start + timedelta(days=random_days, seconds=random_seconds)


def generate_cdl_number(state: str) -> str:
    return f"{state}{random.randint(10000000, 99999999)}"


def generate_vin() -> str:
    chars = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    return "".join(random.choice(chars) for _ in range(17))


def generate_unit_number(prefix: str, num: int) -> str:
    return f"{prefix}{num:03d}"


# ============== SEED FUNCTIONS ==============

async def create_company(db: AsyncSession) -> Company:
    """Create the demo company."""
    company = Company(
        id=generate_id(),
        name=COMPANY_NAME,
        email=COMPANY_EMAIL,
        phone="(555) 123-4567",
        subscription_plan="enterprise",
        is_active=True,
        business_type="Trucking",
        dot_number=COMPANY_DOT,
        mc_number=COMPANY_MC,
        primary_contact_name="Michael Chen",
    )
    db.add(company)
    await db.flush()
    print(f"Created company: {company.name} (ID: {company.id})")
    return company


async def create_users(db: AsyncSession, company_id: str) -> List[User]:
    """Create staff users."""
    users = []
    for staff in STAFF:
        user = User(
            id=generate_id(),
            email=staff["email"],
            hashed_password=hash_password(OWNER_PASSWORD),
            first_name=staff["first"],
            last_name=staff["last"],
            role=staff["role"],
            company_id=company_id,
            is_active=True,
            must_change_password=False,
        )
        db.add(user)
        users.append(user)
        print(f"Created user: {staff['email']} ({staff['role']})")

    await db.flush()
    return users


async def create_drivers(db: AsyncSession, company_id: str) -> List[Driver]:
    """Create 20 drivers with compliance data."""
    drivers = []
    today = date.today()

    for i in range(20):
        first_name = DRIVER_FIRST_NAMES[i]
        last_name = DRIVER_LAST_NAMES[i]

        # Random CDL expiration 6-24 months from now
        cdl_exp = today + timedelta(days=random.randint(180, 730))
        # Random medical card expiration 3-24 months from now
        med_exp = today + timedelta(days=random.randint(90, 730))

        driver = Driver(
            id=generate_id(),
            company_id=company_id,
            first_name=first_name,
            last_name=last_name,
            email=f"{first_name.lower()}.{last_name.lower()}@demofreight.com",
            phone=f"(555) {random.randint(100, 999)}-{random.randint(1000, 9999)}",
            cdl_number=generate_cdl_number("CA"),
            cdl_expiration=cdl_exp,
            medical_card_expiration=med_exp,
            compliance_score=round(random.uniform(85, 100), 1),
            average_rating=round(random.uniform(4.0, 5.0), 2),
            total_completed_loads=random.randint(50, 300),
        )
        db.add(driver)
        drivers.append(driver)

    await db.flush()
    print(f"Created {len(drivers)} drivers")

    # Add some training records
    training_courses = [
        "Defensive Driving", "HazMat Certification", "Smith System",
        "Hours of Service", "Load Securement", "Pre-Trip Inspection"
    ]

    for driver in drivers:
        # Each driver has 2-4 training records
        for _ in range(random.randint(2, 4)):
            completed = today - timedelta(days=random.randint(30, 365))
            expires = completed + timedelta(days=random.randint(365, 730))

            training = DriverTraining(
                id=generate_id(),
                driver_id=driver.id,
                course_name=random.choice(training_courses),
                completed_at=completed,
                expires_at=expires,
                instructor="Safety Department",
                notes="Annual certification",
            )
            db.add(training)

    await db.flush()
    print("Added driver training records")

    # Add a few incidents (not too many)
    incident_types = ["Minor Accident", "HOS Violation", "Inspection Finding", "Customer Complaint"]
    severities = ["low", "medium"]

    for driver in random.sample(drivers, 5):  # Only 5 drivers have incidents
        incident = DriverIncident(
            id=generate_id(),
            driver_id=driver.id,
            incident_type=random.choice(incident_types),
            severity=random.choice(severities),
            occurred_at=today - timedelta(days=random.randint(30, 180)),
            description="Incident documented and resolved.",
        )
        db.add(incident)

    await db.flush()
    print("Added driver incidents")

    return drivers


async def create_equipment(db: AsyncSession, company_id: str) -> tuple[List[Equipment], List[Equipment]]:
    """Create 20 trucks and 15 trailers."""
    trucks = []
    trailers = []
    today = date.today()

    # Create 20 trucks
    for i in range(1, 21):
        make, model = random.choice(TRUCK_MAKES)
        year = random.randint(2019, 2024)

        truck = Equipment(
            id=generate_id(),
            company_id=company_id,
            unit_number=generate_unit_number("T", i),
            equipment_type="TRACTOR",
            status="ACTIVE",
            operational_status="IN_SERVICE",
            make=make,
            model=model,
            year=year,
            vin=generate_vin(),
            current_mileage=random.randint(50000, 500000),
            current_engine_hours=random.randint(2000, 15000),
            gps_provider="samsara",
            gps_device_id=f"SAMSARA-{generate_id()[:8].upper()}",
            eld_provider="samsara",
            eld_device_id=f"ELD-{generate_id()[:8].upper()}",
        )
        db.add(truck)
        trucks.append(truck)

    # Create 15 trailers
    for i in range(1, 16):
        trailer_type = random.choice(TRAILER_TYPES)
        year = random.randint(2018, 2024)

        trailer = Equipment(
            id=generate_id(),
            company_id=company_id,
            unit_number=generate_unit_number("TR", i),
            equipment_type="TRAILER",
            status="ACTIVE",
            operational_status="IN_SERVICE",
            make="Great Dane" if trailer_type != "Flatbed" else "Fontaine",
            model=trailer_type,
            year=year,
            vin=generate_vin(),
        )
        db.add(trailer)
        trailers.append(trailer)

    await db.flush()
    print(f"Created {len(trucks)} trucks and {len(trailers)} trailers")

    # Add maintenance records for trucks
    service_types = ["Oil Change", "Tire Rotation", "Brake Inspection", "DOT Inspection", "PM Service"]

    for truck in trucks:
        # 3-6 maintenance events per truck
        for _ in range(random.randint(3, 6)):
            service_date = today - timedelta(days=random.randint(30, 365))

            maint = EquipmentMaintenanceEvent(
                id=generate_id(),
                equipment_id=truck.id,
                service_type=random.choice(service_types),
                service_date=service_date,
                vendor="Fleet Maintenance Inc.",
                cost=Decimal(str(random.randint(100, 2000))),
                odometer_at_service=truck.current_mileage - random.randint(10000, 50000),
                notes="Routine maintenance completed",
                next_due_date=service_date + timedelta(days=random.randint(90, 180)),
                next_due_mileage=truck.current_mileage + random.randint(15000, 30000),
            )
            db.add(maint)

    await db.flush()
    print("Added maintenance records")

    return trucks, trailers


async def create_loads(
    db: AsyncSession,
    company_id: str,
    drivers: List[Driver],
    trucks: List[Equipment],
    trailers: List[Equipment]
) -> List[Load]:
    """Create ~900 loads (5/day for 6 months)."""
    loads = []
    today = datetime.now()
    start_date = today - timedelta(days=180)  # 6 months ago

    # Generate 5 loads per day
    current_date = start_date
    load_count = 0

    while current_date <= today:
        for _ in range(5):  # 5 loads per day
            # Pick random origin and destination
            origin = random.choice(CITIES)
            destination = random.choice([c for c in CITIES if c != origin])

            # Random times
            pickup_time = current_date + timedelta(hours=random.randint(6, 18))
            delivery_time = pickup_time + timedelta(hours=random.randint(4, 48))

            # Assign driver and equipment
            driver = random.choice(drivers)
            truck = random.choice(trucks)
            trailer = random.choice(trailers)

            # Calculate rate based on distance (rough estimate)
            distance = random.randint(100, 1500)
            rate_per_mile = random.uniform(2.50, 4.00)
            base_rate = Decimal(str(round(distance * rate_per_mile, 2)))

            # Determine status based on date
            if current_date < today - timedelta(days=7):
                status = random.choice(COMPLETED_STATUSES)
            elif current_date < today:
                status = random.choice(["delivered", "in_transit"])
            else:
                status = "confirmed"

            load = Load(
                id=generate_id(),
                company_id=company_id,
                customer_name=random.choice(CUSTOMERS),
                load_type=random.choice(["ftl", "ltl"]),
                commodity=random.choice(COMMODITIES),
                base_rate=base_rate,
                status=status,
                driver_id=driver.id,
                truck_id=truck.id,
                notes=f"Load #{load_count + 1}",
                created_at=current_date,
                updated_at=delivery_time if status in COMPLETED_STATUSES else current_date,
            )

            # Add tracking data for completed loads
            if status in COMPLETED_STATUSES:
                load.pickup_arrival_time = pickup_time
                load.pickup_arrival_lat = origin[2]
                load.pickup_arrival_lng = origin[3]
                load.pickup_departure_time = pickup_time + timedelta(hours=random.randint(1, 3))
                load.pickup_departure_lat = origin[2]
                load.pickup_departure_lng = origin[3]

                load.delivery_arrival_time = delivery_time
                load.delivery_arrival_lat = destination[2]
                load.delivery_arrival_lng = destination[3]
                load.delivery_departure_time = delivery_time + timedelta(hours=random.randint(1, 2))
                load.delivery_departure_lat = destination[2]
                load.delivery_departure_lng = destination[3]

            db.add(load)

            # Add stops
            pickup_stop = LoadStop(
                id=generate_id(),
                load_id=load.id,
                sequence=1,
                stop_type="pickup",
                location_name=f"{origin[0]} Warehouse",
                city=origin[0],
                state=origin[1],
                scheduled_at=pickup_time,
                distance_miles=0,
            )
            db.add(pickup_stop)

            delivery_stop = LoadStop(
                id=generate_id(),
                load_id=load.id,
                sequence=2,
                stop_type="delivery",
                location_name=f"{destination[0]} Distribution Center",
                city=destination[0],
                state=destination[1],
                scheduled_at=delivery_time,
                distance_miles=distance,
            )
            db.add(delivery_stop)

            loads.append(load)
            load_count += 1

        current_date += timedelta(days=1)

        # Flush periodically to avoid memory issues
        if load_count % 100 == 0:
            await db.flush()
            print(f"Created {load_count} loads...")

    await db.flush()
    print(f"Created {len(loads)} total loads")
    return loads


async def create_workers(db: AsyncSession, company_id: str, drivers: List[Driver]) -> List[Worker]:
    """Create worker records for payroll."""
    workers = []

    # Create workers for drivers
    for driver in drivers:
        worker = Worker(
            id=generate_id(),
            company_id=company_id,
            type=WorkerType.CONTRACTOR if random.random() < 0.3 else WorkerType.EMPLOYEE,
            role=WorkerRole.DRIVER,
            first_name=driver.first_name,
            last_name=driver.last_name,
            email=driver.email,
            phone=driver.phone,
            status=WorkerStatus.ACTIVE,
            hire_date=date.today() - timedelta(days=random.randint(90, 730)),
        )
        db.add(worker)
        workers.append(worker)

        # Link driver to worker
        driver.worker_id = worker.id

    # Create office workers
    office_staff = [
        ("Jennifer", "Adams", WorkerRole.DISPATCHER),
        ("Michael", "Brown", WorkerRole.DISPATCHER),
        ("Lisa", "Clark", WorkerRole.OTHER),  # Accounting
    ]

    for first, last, role in office_staff:
        worker = Worker(
            id=generate_id(),
            company_id=company_id,
            type=WorkerType.EMPLOYEE,
            role=role,
            first_name=first,
            last_name=last,
            email=f"{first.lower()}.{last.lower()}@demofreight.com",
            status=WorkerStatus.ACTIVE,
            hire_date=date.today() - timedelta(days=random.randint(180, 1000)),
        )
        db.add(worker)
        workers.append(worker)

    await db.flush()
    print(f"Created {len(workers)} workers")
    return workers


# ============== MAIN ==============

async def seed_demo_tenant():
    """Main function to seed demo tenant."""
    print("\n" + "=" * 60)
    print("DEMO TENANT SEED SCRIPT")
    print("=" * 60 + "\n")

    async with async_session_maker() as db:
        try:
            # Check if company already exists
            result = await db.execute(
                select(Company).where(Company.email == COMPANY_EMAIL)
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"Company '{COMPANY_NAME}' already exists!")
                print("Delete existing data first if you want to re-seed.")
                return

            # Create everything
            company = await create_company(db)
            users = await create_users(db, company.id)
            drivers = await create_drivers(db, company.id)
            trucks, trailers = await create_equipment(db, company.id)
            loads = await create_loads(db, company.id, drivers, trucks, trailers)
            workers = await create_workers(db, company.id, drivers)

            # Commit all changes
            await db.commit()

            print("\n" + "=" * 60)
            print("SEED COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            print(f"\nCompany: {COMPANY_NAME}")
            print(f"Users: {len(users)}")
            print(f"Drivers: {len(drivers)}")
            print(f"Trucks: {len(trucks)}")
            print(f"Trailers: {len(trailers)}")
            print(f"Loads: {len(loads)}")
            print(f"Workers: {len(workers)}")
            print("\n" + "-" * 60)
            print("OWNER LOGIN CREDENTIALS:")
            print("-" * 60)
            print(f"Email:    {OWNER_EMAIL}")
            print(f"Password: {OWNER_PASSWORD}")
            print("-" * 60 + "\n")

        except Exception as e:
            await db.rollback()
            print(f"\nERROR: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(seed_demo_tenant())

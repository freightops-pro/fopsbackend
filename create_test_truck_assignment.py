import sqlite3
import uuid
from datetime import datetime, timedelta

# Connect to the database
conn = sqlite3.connect('freightops.db')
cursor = conn.cursor()

# Get the first company
cursor.execute("SELECT id, name FROM companies LIMIT 1")
company = cursor.fetchone()

if not company:
    print("No companies found. Please create a company first.")
    exit(1)

company_id, company_name = company
print(f"Found company: {company_name} (ID: {company_id})")

# Get the test driver
cursor.execute("SELECT id, firstName, lastName, email FROM drivers WHERE email = 'driver@test.com'")
driver = cursor.fetchone()

if not driver:
    print("Test driver not found. Please create a test driver first.")
    exit(1)

driver_id, first_name, last_name, email = driver
print(f"Found driver: {first_name} {last_name} (ID: {driver_id})")

# Check if truck already exists
cursor.execute("SELECT id FROM equipment WHERE assignedDriverId = ?", (driver_id,))
existing_truck = cursor.fetchone()

if existing_truck:
    print(f"Driver already has an assigned truck: {existing_truck[0]}")
else:
    # Create a test truck in the equipment table
    truck_id = str(uuid.uuid4())
    truck_data = {
        'id': truck_id,
        'companyId': company_id,
        'equipmentNumber': 'TRK001',
        'equipmentType': 'Tractor',
        'make': 'Freightliner',
        'model': 'Cascadia',
        'year': '2022',
        'vinNumber': '1FUJGHDV8NLAA1234',
        'plateNumber': 'TX123ABC',
        'currentMileage': 125000,
        'engineType': 'DD15',
        'fuelType': 'Diesel',
        'eldProvider': 'Samsara',
        'eldDeviceId': 'SAM123456',
        'registrationState': 'TX',
        'registrationExpiry': (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d'),
        'insuranceProvider': 'Progressive Commercial',
        'insurancePolicyNumber': 'PC123456789',
        'insuranceExpiry': (datetime.now() + timedelta(days=180)).strftime('%Y-%m-%d'),
        'homeTerminal': 'Dallas, TX',
        'operationalStatus': 'active',
        'status': 'available',
        'assignedDriverId': driver_id,
        'isActive': 1,
        'createdAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # Insert truck
    columns = ', '.join(truck_data.keys())
    placeholders = ', '.join(['?' for _ in truck_data])
    query = f"INSERT INTO equipment ({columns}) VALUES ({placeholders})"
    
    cursor.execute(query, list(truck_data.values()))
    conn.commit()
    
    print(f"Created test truck:")
    print(f"  Truck Number: {truck_data['equipmentNumber']}")
    print(f"  Make/Model: {truck_data['year']} {truck_data['make']} {truck_data['model']}")
    print(f"  VIN: {truck_data['vinNumber']}")
    print(f"  Assigned to: {first_name} {last_name}")
    print(f"  Status: {truck_data['status']}")

# Close connection
conn.close()
print("\nTruck assignment complete! Driver can now see their assigned truck in the mobile app.")


import sqlite3
from datetime import datetime, timedelta
import uuid

# Connect to the database
conn = sqlite3.connect('freightops.db')
cursor = conn.cursor()

# Get the first company ID
cursor.execute("SELECT id, name FROM companies LIMIT 1")
company = cursor.fetchone()

if not company:
    print("No companies found in database. Please create a company first.")
    exit(1)

company_id, company_name = company
print(f"Found company: {company_name} (ID: {company_id})")

# Create a test driver
driver_id = str(uuid.uuid4())
driver_data = {
    'id': driver_id,
    'companyId': company_id,
    'firstName': 'Test',
    'lastName': 'Driver',
    'email': 'driver@test.com',
    'phone': '555-123-4567',
    'licenseNumber': 'CDL123456789',
    'licenseClass': 'A',
    'licenseExpiry': (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d'),
    'dateOfBirth': '1985-01-15',
    'address': '123 Test Street',
    'city': 'Test City',
    'state': 'TX',
    'zipCode': '12345',
    'emergencyContact': 'Emergency Contact',
    'emergencyPhone': '555-987-6543',
    'hireDate': datetime.now().strftime('%Y-%m-%d'),
    'status': 'available',
    'payRate': 0.50,
    'payType': 'per_mile',
    'hoursRemaining': 11.0,
    'currentLocation': 'Dallas, TX',
    'isActive': 1,
    'createdAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'updatedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
}

# Check if driver already exists
cursor.execute("SELECT id FROM drivers WHERE email = ?", (driver_data['email'],))
existing = cursor.fetchone()

if existing:
    print(f"Driver with email {driver_data['email']} already exists")
    cursor.execute("UPDATE drivers SET passwordHash = NULL WHERE email = ?", (driver_data['email'],))
    conn.commit()
    print("Cleared password so driver can sign up again")
else:
    # Insert new driver
    columns = ', '.join(driver_data.keys())
    placeholders = ', '.join(['?' for _ in driver_data])
    query = f"INSERT INTO drivers ({columns}) VALUES ({placeholders})"
    
    cursor.execute(query, list(driver_data.values()))
    conn.commit()
    print(f"Created test driver:")
    print(f"  Email: {driver_data['email']}")
    print(f"  Name: {driver_data['firstName']} {driver_data['lastName']}")
    print(f"  Company: {company_name}")
    print(f"  Status: {driver_data['status']}")
    print("\nDriver can now sign up with this email and set their password.")

# Close connection
conn.close()

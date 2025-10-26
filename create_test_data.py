#!/usr/bin/env python3
"""
Script to create test data for ELD compliance testing
"""

import psycopg2
import uuid
from datetime import datetime, date
from app.config.settings import settings

def create_test_data():
    # Connect to the database using PostgreSQL
    conn = psycopg2.connect(settings.DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # Get the first company ID
        cursor.execute("SELECT id FROM companies WHERE \"isActive\" = true LIMIT 1")
        company_result = cursor.fetchone()
        
        if not company_result:
            print("No active company found. Creating a default company...")
            company_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO companies (id, name, email, phone, address, city, state, "zipCode", 
                                     "dotNumber", "mcNumber", ein, "businessType", "yearsInBusiness", 
                                     "numberOfTrucks", "walletBalance", "subscriptionStatus", 
                                     "subscriptionPlan", "createdAt", "updatedAt", "isActive")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                company_id, "Test FreightOps Company", "admin@testfreightops.com", "+1-555-0123",
                "123 Test Street", "Test City", "TX", "12345", "DOT1234567", "MC-123456",
                "12-3456789", "LLC", 5, 10, 0.0, "trial", "starter",
                datetime.utcnow(), datetime.utcnow(), True
            ))
        else:
            company_id = company_result[0]
        
        # Check if test drivers already exist
        cursor.execute("SELECT COUNT(*) FROM drivers WHERE \"companyId\" = %s", (company_id,))
        driver_count = cursor.fetchone()[0]
        
        if driver_count == 0:
            print("Creating test drivers...")
            
            # Create test drivers
            test_drivers = [
                {
                    'id': str(uuid.uuid4()),
                    'firstName': 'John',
                    'lastName': 'Smith',
                    'email': 'john.smith@testfreightops.com',
                    'phone': '+1-555-1111',
                    'licenseNumber': 'CDL123456',
                    'licenseClass': 'CDL-A',
                    'licenseExpiry': date(2026, 12, 31),
                    'dateOfBirth': date(1985, 5, 15),
                    'address': '123 Driver St',
                    'city': 'Test City',
                    'state': 'TX',
                    'zipCode': '12345',
                    'emergencyContact': 'Jane Smith',
                    'emergencyPhone': '+1-555-1112',
                    'hireDate': date(2023, 1, 15),
                    'status': 'active',
                    'payRate': 0.60,
                    'payType': 'percentage',
                    'hoursRemaining': 11.0,
                    'currentLocation': 'Test City, TX',
                    'isActive': True,
                    'createdAt': datetime.utcnow(),
                    'updatedAt': datetime.utcnow()
                },
                {
                    'id': str(uuid.uuid4()),
                    'firstName': 'Sarah',
                    'lastName': 'Johnson',
                    'email': 'sarah.johnson@testfreightops.com',
                    'phone': '+1-555-2222',
                    'licenseNumber': 'CDL789012',
                    'licenseClass': 'CDL-A',
                    'licenseExpiry': date(2026, 6, 30),
                    'dateOfBirth': date(1990, 8, 22),
                    'address': '456 Driver Ave',
                    'city': 'Test City',
                    'state': 'TX',
                    'zipCode': '12345',
                    'emergencyContact': 'Mike Johnson',
                    'emergencyPhone': '+1-555-2223',
                    'hireDate': date(2023, 3, 10),
                    'status': 'active',
                    'payRate': 0.58,
                    'payType': 'percentage',
                    'hoursRemaining': 9.5,
                    'currentLocation': 'Test City, TX',
                    'isActive': True,
                    'createdAt': datetime.utcnow(),
                    'updatedAt': datetime.utcnow()
                },
                {
                    'id': str(uuid.uuid4()),
                    'firstName': 'Mike',
                    'lastName': 'Davis',
                    'email': 'mike.davis@testfreightops.com',
                    'phone': '+1-555-3333',
                    'licenseNumber': 'CDL345678',
                    'licenseClass': 'CDL-A',
                    'licenseExpiry': date(2027, 3, 15),
                    'dateOfBirth': date(1988, 12, 5),
                    'address': '789 Driver Blvd',
                    'city': 'Test City',
                    'state': 'TX',
                    'zipCode': '12345',
                    'emergencyContact': 'Lisa Davis',
                    'emergencyPhone': '+1-555-3334',
                    'hireDate': date(2023, 6, 20),
                    'status': 'active',
                    'payRate': 0.55,
                    'payType': 'percentage',
                    'hoursRemaining': 10.0,
                    'currentLocation': 'Test City, TX',
                    'isActive': True,
                    'createdAt': datetime.utcnow(),
                    'updatedAt': datetime.utcnow()
                }
            ]
            
            for driver in test_drivers:
                cursor.execute("""
                    INSERT INTO drivers (id, "companyId", "firstName", "lastName", email, phone, 
                                       "licenseNumber", "licenseClass", "licenseExpiry", "dateOfBirth",
                                       address, city, state, "zipCode", "emergencyContact", "emergencyPhone",
                                       "hireDate", status, "payRate", "payType", "hoursRemaining", "currentLocation",
                                       "isActive", "createdAt", "updatedAt")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    driver['id'], company_id, driver['firstName'], driver['lastName'], driver['email'],
                    driver['phone'], driver['licenseNumber'], driver['licenseClass'], driver['licenseExpiry'],
                    driver['dateOfBirth'], driver['address'], driver['city'], driver['state'], driver['zipCode'],
                    driver['emergencyContact'], driver['emergencyPhone'], driver['hireDate'], driver['status'],
                    driver['payRate'], driver['payType'], driver['hoursRemaining'], driver['currentLocation'],
                    driver['isActive'], driver['createdAt'], driver['updatedAt']
                ))
            
            print(f"Created {len(test_drivers)} test drivers")
        else:
            print(f"Found {driver_count} existing drivers")
        
        # Check if test equipment already exists
        cursor.execute("SELECT COUNT(*) FROM equipment WHERE \"companyId\" = %s", (company_id,))
        equipment_count = cursor.fetchone()[0]
        
        if equipment_count == 0:
            print("Creating test equipment...")
            
            # Create test equipment
            test_equipment = [
                {
                    'id': str(uuid.uuid4()),
                    'equipmentNumber': 'T001',
                    'equipmentType': 'Day Cab',
                    'make': 'Peterbilt',
                    'model': '579',
                    'year': '2022',
                    'vinNumber': '1XP5DB9X1MD123456',
                    'plateNumber': 'TX-T001',
                    'currentMileage': 125000,
                    'engineType': 'Cummins X15',
                    'transmission': 'Eaton Fuller 18-speed',
                    'fuelType': 'Diesel',
                    'fuelCapacity': 150,
                    'status': 'available',
                    'isActive': True,
                    'createdAt': datetime.utcnow(),
                    'updatedAt': datetime.utcnow()
                },
                {
                    'id': str(uuid.uuid4()),
                    'equipmentNumber': 'T002',
                    'equipmentType': 'Sleeper',
                    'make': 'Freightliner',
                    'model': 'Cascadia',
                    'year': '2023',
                    'vinNumber': '1FUJGHDV8NLAA1234',
                    'plateNumber': 'TX-T002',
                    'currentMileage': 85000,
                    'engineType': 'Detroit DD15',
                    'transmission': 'Detroit DT12',
                    'fuelType': 'Diesel',
                    'fuelCapacity': 120,
                    'status': 'available',
                    'isActive': True,
                    'createdAt': datetime.utcnow(),
                    'updatedAt': datetime.utcnow()
                },
                {
                    'id': str(uuid.uuid4()),
                    'equipmentNumber': 'T003',
                    'equipmentType': 'Day Cab',
                    'make': 'Kenworth',
                    'model': 'T680',
                    'year': '2021',
                    'vinNumber': '1XKWDB0X2PJ789012',
                    'plateNumber': 'TX-T003',
                    'currentMileage': 180000,
                    'engineType': 'PACCAR MX-13',
                    'transmission': 'Eaton Fuller 10-speed',
                    'fuelType': 'Diesel',
                    'fuelCapacity': 130,
                    'status': 'available',
                    'isActive': True,
                    'createdAt': datetime.utcnow(),
                    'updatedAt': datetime.utcnow()
                }
            ]
            
            for equipment in test_equipment:
                cursor.execute("""
                    INSERT INTO equipment (id, "companyId", "equipmentNumber", "equipmentType", make, model, year,
                                         "vinNumber", "plateNumber", "currentMileage", "engineType", transmission,
                                         "fuelType", "fuelCapacity", status, "isActive", "createdAt", "updatedAt")
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    equipment['id'], company_id, equipment['equipmentNumber'], equipment['equipmentType'],
                    equipment['make'], equipment['model'], equipment['year'], equipment['vinNumber'],
                    equipment['plateNumber'], equipment['currentMileage'], equipment['engineType'],
                    equipment['transmission'], equipment['fuelType'], equipment['fuelCapacity'],
                    equipment['status'], equipment['isActive'], equipment['createdAt'], equipment['updatedAt']
                ))
            
            print(f"Created {len(test_equipment)} test equipment")
        else:
            print(f"Found {equipment_count} existing equipment")
        
        conn.commit()
        print("Test data created successfully!")
        
    except Exception as e:
        print(f"Error creating test data: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_test_data()

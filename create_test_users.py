#!/usr/bin/env python3
"""
Create test users for chat functionality testing
"""

import os
import sys
from datetime import datetime
import uuid

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.config.db import get_db
from app.models.userModels import Users, Companies
from sqlalchemy.orm import Session
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_test_users():
    """Create test users and company for chat testing"""
    print("🚀 Creating test users for chat functionality...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Create a test company first
        print("\n📊 Creating test company...")
        company_id = str(uuid.uuid4())
        test_company = Companies(
            id=company_id,
            name="Test Chat Company",
            email="admin@testchat.com",
            phone="+1234567890",
            address="123 Test Street",
            city="Test City",
            state="TS",
            zipCode="12345",
            dotNumber="123456",
            mcNumber="MC123456",
            ein="12-3456789",
            businessType="Freight",
            yearsInBusiness=5,
            numberOfTrucks=10,
            walletBalance=10000.0,
            subscriptionStatus="active",
            subscriptionPlan="premium",
            isActive=True,
            createdat=datetime.utcnow(),
            updatedat=datetime.utcnow()
        )
        
        db.add(test_company)
        db.commit()
        print(f"✅ Company created: {test_company.name} (ID: {company_id})")
        
        # Create test users
        test_users = [
            {
                "email": "alice@test.com",
                "password": "password123",
                "firstname": "Alice",
                "lastname": "Johnson",
                "phone": "+1234567890",
                "role": "admin"
            },
            {
                "email": "bob@test.com",
                "password": "password123",
                "firstname": "Bob",
                "lastname": "Smith",
                "phone": "+1234567891",
                "role": "user"
            },
            {
                "email": "charlie@test.com",
                "password": "password123",
                "firstname": "Charlie",
                "lastname": "Brown",
                "phone": "+1234567892",
                "role": "driver"
            }
        ]
        
        print("\n👥 Creating test users...")
        created_users = []
        
        for user_data in test_users:
            user_id = str(uuid.uuid4())
            
            # Hash the password
            hashed_password = pwd_context.hash(user_data["password"])
            
            user = Users(
                id=user_id,
                email=user_data["email"],
                password=hashed_password,
                firstname=user_data["firstname"],
                lastname=user_data["lastname"],
                phone=user_data["phone"],
                role=user_data["role"],
                companyid=company_id,
                isactive=True,
                createdat=datetime.utcnow(),
                updatedat=datetime.utcnow()
            )
            
            db.add(user)
            created_users.append({
                "id": user_id,
                "email": user_data["email"],
                "name": f"{user_data['firstname']} {user_data['lastname']}",
                "role": user_data["role"]
            })
        
        db.commit()
        
        print("✅ Test users created successfully!")
        print("\n📋 Created users:")
        for user in created_users:
            print(f"  - {user['name']} ({user['email']}) - Role: {user['role']} - ID: {user['id']}")
        
        print(f"\n🏢 Company: {test_company.name} (ID: {company_id})")
        
        print("\n🔐 Login credentials:")
        print("  Alice (Admin): alice@test.com / password123")
        print("  Bob (User): bob@test.com / password123")
        print("  Charlie (Driver): charlie@test.com / password123")
        
        print("\n🧪 Ready for chat testing!")
        print("You can now:")
        print("1. Go to http://localhost:8000/docs")
        print("2. Login with any of the test users")
        print("3. Test the chat functionality")
        
        return created_users, company_id
        
    except Exception as e:
        print(f"❌ Error creating test users: {e}")
        db.rollback()
        return None, None
    finally:
        db.close()

def check_existing_users():
    """Check if users already exist"""
    print("🔍 Checking existing users...")
    
    db = next(get_db())
    try:
        users = db.query(Users).limit(5).all()
        if users:
            print(f"Found {len(users)} existing users:")
            for user in users:
                print(f"  - {user.firstname} {user.lastname} ({user.email}) - Role: {user.role}")
            return True
        else:
            print("No existing users found.")
            return False
    except Exception as e:
        print(f"Error checking users: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🧪 CHAT TEST USER SETUP")
    print("=" * 40)
    
    # Check if users already exist
    if check_existing_users():
        print("\n❓ Users already exist. Do you want to create additional test users?")
        choice = input("Enter 'y' to create more users, or 'n' to skip: ").strip().lower()
        if choice != 'y':
            print("Skipping user creation.")
            exit(0)
    
    # Create test users
    users, company_id = create_test_users()
    
    if users:
        print("\n🎉 Setup complete! You can now test the chat functionality.")
    else:
        print("\n❌ Setup failed. Please check the error messages above.")

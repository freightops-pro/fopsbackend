#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.config.db import get_db
from app.models.userModels import Users, Companies
from app.routes.user import verify_password
import traceback

def test_database_connection():
    """Test database connection and basic queries"""
    try:
        db = next(get_db())
        print("Database connection successful")
        
        # Test Users table
        users_count = db.query(Users).count()
        print(f"Total users in database: {users_count}")
        
        if users_count > 0:
            # Get first user
            first_user = db.query(Users).first()
            print(f"First user: {first_user.email}")
            print(f"   - ID: {first_user.id}")
            print(f"   - Email verified: {first_user.emailverified}")
            print(f"   - Active: {first_user.isactive}")
            print(f"   - Company ID: {first_user.companyid}")
            
            # Check if user has company
            if first_user.companyid:
                company = db.query(Companies).filter(Companies.id == first_user.companyid).first()
                if company:
                    print(f"Company: {company.name}")
                    print(f"   - DOT Number: {company.dotNumber}")
                    print(f"   - MC Number: {company.mcNumber}")
                else:
                    print("Company not found for user")
            else:
                print("User has no company ID")
        
        # Test Companies table
        companies_count = db.query(Companies).count()
        print(f"Total companies in database: {companies_count}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"Database connection failed: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return False

def test_password_verification():
    """Test password verification function"""
    try:
        # Test with a dummy password
        test_password = "test123"
        test_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj8/4XvZ9X8K"  # Example bcrypt hash
        
        result = verify_password(test_password, test_hash)
        print(f"Password verification test: {result}")
        return True
        
    except Exception as e:
        print(f"Password verification failed: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("Testing FreightOps Backend Database Connection...")
    print("=" * 50)
    
    # Test database connection
    db_success = test_database_connection()
    print()
    
    # Test password verification
    pwd_success = test_password_verification()
    print()
    
    if db_success and pwd_success:
        print("All tests passed!")
    else:
        print("Some tests failed!")

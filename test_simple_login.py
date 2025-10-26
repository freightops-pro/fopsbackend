#!/usr/bin/env python3
"""
Simple test to see what breaks during login
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.config.db import get_db
from app.models.userModels import Users, Companies
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

try:
    print("Step 1: Connecting to database...")
    db = next(get_db())
    
    print("Step 2: Querying for user by email...")
    user = db.query(Users).filter(Users.email == "newuser@example.com").first()
    
    if not user:
        print("ERROR: No user found with that email")
        sys.exit(1)
    
    print(f"SUCCESS: Found user: {user.email}")
    
    print("Step 3: Verifying password...")
    # Test password verification
    test_password = "password123"
    if pwd_context.verify(test_password, user.password):
        print("SUCCESS: Password verified")
    else:
        print("ERROR: Password verification failed")
    
    print("Step 4: Querying company...")
    company = db.query(Companies).filter(Companies.id == user.companyid).first()
    
    if not company:
        print("ERROR: No company found")
        sys.exit(1)
    
    print(f"SUCCESS: Found company: {company.name}")
    
    print("Step 5: Checking company DOT/MC numbers...")
    print(f"  DOT Number: {company.dotNumber}")
    print(f"  MC Number: {company.mcNumber}")
    
    print("\nALL STEPS SUCCESSFUL!")
    print("\nUser Details:")
    print(f"  ID: {user.id}")
    print(f"  Email: {user.email}")
    print(f"  Role: {user.role}")
    print(f"  Active: {user.isactive}")
    
    print("\nCompany Details:")
    print(f"  ID: {company.id}")
    print(f"  Name: {company.name}")
    print(f"  DOT: {company.dotNumber}")
    print(f"  MC: {company.mcNumber}")
    
except Exception as e:
    print(f"\nERROR at some step:")
    print(f"Type: {type(e).__name__}")
    print(f"Message: {str(e)}")
    import traceback
    traceback.print_exc()


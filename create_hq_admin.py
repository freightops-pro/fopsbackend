#!/usr/bin/env python3
"""
Create initial HQ admin user
Run this script to create the first HQ admin user
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from sqlalchemy.orm import Session
from app.config.db import engine, Base, create_tables
from app.models.hqModels import HQAdmin
from passlib.context import CryptContext
import uuid

# Password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_initial_hq_admin():
    """Create initial HQ admin user"""
    # Create tables if they don't exist
    create_tables()
    
    with Session(engine) as db:
        # Check if any HQ admins exist
        existing_admin = db.query(HQAdmin).first()
        if existing_admin:
            print("HQ admin already exists. Skipping creation.")
            return
        
        # Create initial platform owner
        admin = HQAdmin(
            id=str(uuid.uuid4()),
            email="admin@freightops.com",
            password_hash=pwd_context.hash("FreightOps2024!"),
            first_name="Platform",
            last_name="Owner",
            role="platform_owner",
            is_active=True,
            notes="Initial platform owner account"
        )
        
        db.add(admin)
        db.commit()
        
        print("✅ Initial HQ admin created successfully!")
        print("Email: admin@freightops.com")
        print("Password: FreightOps2024!")
        print("Role: platform_owner")
        print("\n⚠️  IMPORTANT: Change this password immediately after first login!")

if __name__ == "__main__":
    create_initial_hq_admin()

#!/usr/bin/env python3
"""
Script to create a default company for testing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.config.settings import settings
import uuid
from datetime import datetime

def create_default_company():
    """Create a default company if none exists"""
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Check if companies table exists
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'companies'
            """))
            
            if result.fetchone() is None:
                print("Companies table does not exist.")
                return
            
            # Check if any companies exist
            result = conn.execute(text("SELECT COUNT(*) FROM companies"))
            count = result.fetchone()[0]
            
            if count == 0:
                # Create default company
                company_id = str(uuid.uuid4())
                now = datetime.utcnow()
                
                conn.execute(text("""
                    INSERT INTO companies (
                        id, name, email, phone, address, city, state, "zipCode", 
                        "dotNumber", "mcNumber", ein, "businessType", "yearsInBusiness", 
                        "numberOfTrucks", "walletBalance", "subscriptionStatus", 
                        "subscriptionPlan", "createdAt", "updatedAt", "isActive", 
                        "handlesContainers", "containerTrackingEnabled"
                    ) VALUES (
                        :id, :name, :email, :phone, :address, :city, :state, :zipCode,
                        :dotNumber, :mcNumber, :ein, :businessType, :yearsInBusiness,
                        :numberOfTrucks, :walletBalance, :subscriptionStatus,
                        :subscriptionPlan, :createdAt, :updatedAt, :isActive,
                        :handlesContainers, :containerTrackingEnabled
                    )
                """), {
                    'id': company_id,
                    'name': 'Default FreightOps Company',
                    'email': 'admin@freightops.com',
                    'phone': '+1-555-0123',
                    'address': '123 Main Street',
                    'city': 'Chicago',
                    'state': 'IL',
                    'zipCode': '60601',
                    'dotNumber': 'DOT1234567',
                    'mcNumber': 'MC-123456',
                    'ein': '12-3456789',
                    'businessType': 'LLC',
                    'yearsInBusiness': 5,
                    'numberOfTrucks': 10,
                    'walletBalance': 0.0,
                    'subscriptionStatus': 'trial',
                    'subscriptionPlan': 'starter',
                    'createdAt': now,
                    'updatedAt': now,
                    'isActive': True,
                    'handlesContainers': False,
                    'containerTrackingEnabled': False
                })
                
                conn.commit()
                print(f"Default company created with ID: {company_id}")
                return company_id
            else:
                # Get the first company
                result = conn.execute(text("SELECT id FROM companies LIMIT 1"))
                company_id = result.fetchone()[0]
                print(f"Using existing company with ID: {company_id}")
                return company_id
                
    except Exception as e:
        print(f"Error creating default company: {e}")
        return None

if __name__ == "__main__":
    create_default_company()

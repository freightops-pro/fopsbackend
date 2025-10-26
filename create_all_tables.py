#!/usr/bin/env python3
"""
Script to create all tables for FreightOps including banking tables.
This script creates tables in the correct order to avoid foreign key issues.
"""

import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from sqlalchemy import create_engine, text
from app.config.db import Base, engine
from app import models  # This imports all models including banking

def create_all_tables():
    """Create all tables in the database"""
    try:
        print("Creating all FreightOps tables...")
        
        # Create all tables (SQLAlchemy will handle the order based on dependencies)
        Base.metadata.create_all(bind=engine)
        
        print("✅ All tables created successfully!")
        
        # Verify tables exist
        with engine.connect() as conn:
            # Check for base tables
            base_tables = [
                "companies",
                "users", 
                "drivers",
                "trucks",
                "simple_loads"
            ]
            
            # Check for banking tables
            banking_tables = [
                "banking_customers",
                "banking_accounts", 
                "banking_cards",
                "banking_transactions",
                "banking_transfers"
            ]
            
            all_tables = base_tables + banking_tables
            
            print("\n📋 Checking table creation status:")
            for table in all_tables:
                try:
                    result = conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                    print(f"✅ Table '{table}' exists and is accessible")
                except Exception as e:
                    print(f"❌ Table '{table}' not found or not accessible: {str(e)}")
        
        print("\n🎉 All tables setup complete!")
        print("\n📊 Available tables:")
        print("\nBase Tables:")
        for table in base_tables:
            print(f"  - {table}")
        
        print("\nBanking Tables:")
        for table in banking_tables:
            print(f"  - {table}")
        
        print("\n🚀 You can now start the FreightOps API!")
        
    except Exception as e:
        print(f"❌ Error creating tables: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    create_all_tables()


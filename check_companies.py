#!/usr/bin/env python3
"""
Script to check what companies exist in the database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.config.settings import settings

def check_companies():
    """Check what companies exist in the database"""
    
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
            
            # Get all companies
            result = conn.execute(text("SELECT id, name, email FROM companies"))
            companies = result.fetchall()
            
            if companies:
                print("Existing companies:")
                for company in companies:
                    print(f"ID: {company[0]}, Name: {company[1]}, Email: {company[2]}")
            else:
                print("No companies found in the database.")
                
    except Exception as e:
        print(f"Error checking companies: {e}")

if __name__ == "__main__":
    check_companies()

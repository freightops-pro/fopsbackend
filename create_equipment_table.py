#!/usr/bin/env python3
"""
Script to create the Equipment table in the existing database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.config.settings import settings
from app.models.userModels import Equipment, Base

def create_equipment_table():
    """Create the Equipment table if it doesn't exist"""
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        # Check if equipment table exists
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='equipment'
            """))
            
            if result.fetchone() is None:
                print("Creating equipment table...")
                # Create the table
                Base.metadata.create_all(bind=engine, tables=[Equipment.__table__])
                print("Equipment table created successfully!")
            else:
                print("Equipment table already exists.")
                
    except Exception as e:
        print(f"Error creating equipment table: {e}")
        return False
    
    return True

if __name__ == "__main__":
    create_equipment_table()

#!/usr/bin/env python3
import os
import sys

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.config.db import engine, Base
from app.models.vendor import Vendor
from app.models.bill import Bill

def create_vendor_tables():
    try:
        print("Creating vendor and bill tables...")
        
        # This will create all tables that are defined in the models
        Base.metadata.create_all(bind=engine)
        
        print("Successfully created vendor and bill tables!")
        
    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == "__main__":
    create_vendor_tables()

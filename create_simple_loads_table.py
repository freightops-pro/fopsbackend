#!/usr/bin/env python3
import sqlite3
from sqlalchemy import create_engine, text
from app.config.db import Base
from app.models.simple_load import SimpleLoad

def create_simple_loads_table():
    try:
        # Create engine
        engine = create_engine('sqlite:///freightops.db')
        
        # Create the simple_loads table specifically
        SimpleLoad.__table__.create(engine, checkfirst=True)
        
        print("✅ simple_loads table created successfully!")
        
        # Verify it was created
        conn = sqlite3.connect('freightops.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='simple_loads'")
        result = cursor.fetchone()
        
        if result:
            print("✅ simple_loads table verified!")
        else:
            print("❌ simple_loads table not found!")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Error creating simple_loads table: {e}")

if __name__ == "__main__":
    create_simple_loads_table()

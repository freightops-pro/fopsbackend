#!/usr/bin/env python3
"""
Script to add priority column to simple_loads table
"""

import sqlite3
import os

def add_priority_column():
    """Add priority column to simple_loads table if it doesn't exist"""
    
    # Get the database path
    db_path = "freightops.db"
    
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found!")
        return
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if priority column already exists
        cursor.execute("PRAGMA table_info(simple_loads)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'priority' not in columns:
            print("Adding priority column to simple_loads table...")
            cursor.execute("ALTER TABLE simple_loads ADD COLUMN priority VARCHAR DEFAULT 'normal'")
            conn.commit()
            print("✅ Priority column added successfully!")
        else:
            print("✅ Priority column already exists!")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(simple_loads)")
        columns = cursor.fetchall()
        print("\nCurrent simple_loads table structure:")
        for column in columns:
            print(f"  - {column[1]} ({column[2]})")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if conn:
            conn.close()

if __name__ == "__main__":
    add_priority_column()

#!/usr/bin/env python3
import sqlite3

def verify_table():
    try:
        conn = sqlite3.connect('freightops.db')
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(simple_loads)")
        columns = cursor.fetchall()
        
        print("simple_loads table structure:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_table()

#!/usr/bin/env python3
import sqlite3

def check_tables():
    try:
        conn = sqlite3.connect('freightops.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("Existing tables:")
        for table in tables:
            print(f"  - {table[0]}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_tables()

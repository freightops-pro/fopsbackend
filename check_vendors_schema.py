#!/usr/bin/env python3
import psycopg2
from psycopg2.extras import RealDictCursor

def check_vendors_schema():
    try:
        # Connect to PostgreSQL database
        conn = psycopg2.connect(
            host="localhost",
            database="freightops",
            user="postgres",
            password="password"
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if vendors table exists
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'vendors'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        
        if not columns:
            print("vendors table does not exist")
        else:
            print("Current vendors table schema:")
            for col in columns:
                print(f"  {col['column_name']}: {col['data_type']} {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")
        
        conn.close()
        
    except Exception as e:
        print(f"Error checking schema: {e}")

if __name__ == "__main__":
    check_vendors_schema()

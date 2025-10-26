#!/usr/bin/env python3
"""
Test script to check Neon database connection
"""
import psycopg2
from app.config.settings import settings

def test_neon_connection():
    try:
        print("Testing Neon database connection...")
        print(f"Database URL: {settings.DATABASE_URL}")
        
        # Try to connect to the database
        conn = psycopg2.connect(settings.DATABASE_URL)
        cursor = conn.cursor()
        
        # Test a simple query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Connection successful!")
        print(f"PostgreSQL version: {version[0]}")
        
        # Test creating a simple table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_connection (
                id SERIAL PRIMARY KEY,
                test_field VARCHAR(50)
            );
        """)
        conn.commit()
        print("✅ Table creation test successful!")
        
        # Clean up test table
        cursor.execute("DROP TABLE IF EXISTS test_connection;")
        conn.commit()
        print("✅ Table cleanup successful!")
        
        cursor.close()
        conn.close()
        print("✅ All database tests passed!")
        
    except psycopg2.OperationalError as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting suggestions:")
        print("1. Check if your Neon database is active (not suspended)")
        print("2. Verify the connection string is correct")
        print("3. Check if your IP is whitelisted (if applicable)")
        print("4. Try connecting with a simpler connection string")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_neon_connection()

#!/usr/bin/env python3
"""
Check the actual schema of the users table in the database
"""
import psycopg2

DATABASE_URL = "postgresql://neondb_owner:npg_JVQsDGh9lM6S@ep-quiet-moon-adsx2dey-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

try:
    print("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Query to get column information for users table
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'users'
        ORDER BY ordinal_position;
    """)
    
    columns = cursor.fetchall()
    
    print("\nColumns in 'users' table:")
    print("-" * 60)
    for col_name, data_type, is_nullable in columns:
        print(f"{col_name:30} {data_type:20} {is_nullable}")
    print("-" * 60)
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")


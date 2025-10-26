#!/usr/bin/env python3
"""
Check companies table schema to see what columns actually exist
"""
import psycopg2

conn_string = "postgresql://neondb_owner:npg_JVQsDGh9lM6S@54.156.15.30:5432/neondb?sslmode=require&options=endpoint%3Dep-quiet-moon-adsx2dey"

try:
    conn = psycopg2.connect(conn_string)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'companies'
        ORDER BY ordinal_position;
    """)
    
    print("Companies table columns:")
    print("-" * 80)
    for row in cur.fetchall():
        print(f"  {row[0]:<40} {row[1]:<20} {row[2]}")
    
    cur.close()
    conn.close()
    print("\nSuccess!")
    
except Exception as e:
    print(f"Error: {e}")


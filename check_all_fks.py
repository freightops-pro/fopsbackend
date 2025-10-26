#!/usr/bin/env python3
"""
Check all foreign keys in the database to understand actual relationships
"""
import psycopg2

conn_string = "postgresql://neondb_owner:npg_JVQsDGh9lM6S@54.156.15.30:5432/neondb?sslmode=require&options=endpoint%3Dep-quiet-moon-adsx2dey"

try:
    conn = psycopg2.connect(conn_string)
    cur = conn.cursor()
    
    # Get all tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    
    tables = [row[0] for row in cur.fetchall()]
    print(f"Found {len(tables)} tables\n")
    
    # For each table, get its foreign keys
    for table in tables:
        cur.execute("""
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND tc.table_name = %s
            ORDER BY kcu.ordinal_position;
        """, (table,))
        
        fks = cur.fetchall()
        if fks:
            print(f"{table}:")
            for fk in fks:
                print(f"  {fk[0]} -> {fk[1]}.{fk[2]}")
            print()
    
    cur.close()
    conn.close()
    print("Done!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()


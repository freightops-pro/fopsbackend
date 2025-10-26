#!/usr/bin/env python3
"""
Add missing foreign keys to fix relationships properly
"""
import psycopg2

conn_string = "postgresql://neondb_owner:npg_JVQsDGh9lM6S@54.156.15.30:5432/neondb?sslmode=require&options=endpoint%3Dep-quiet-moon-adsx2dey"

try:
    conn = psycopg2.connect(conn_string)
    cur = conn.cursor()
    
    print("Adding missing foreign keys to fix relationships...")
    
    # 1. Add home_location_id to drivers table
    print("1. Adding home_location_id to drivers table...")
    try:
        cur.execute("ALTER TABLE drivers ADD COLUMN home_location_id INTEGER REFERENCES locations(id);")
        print("   SUCCESS: Added home_location_id to drivers")
    except psycopg2.errors.DuplicateColumn:
        print("   home_location_id already exists in drivers")
    
    # 2. Add home_location_id to trucks table  
    print("2. Adding home_location_id to trucks table...")
    try:
        cur.execute("ALTER TABLE trucks ADD COLUMN home_location_id INTEGER REFERENCES locations(id);")
        print("   SUCCESS: Added home_location_id to trucks")
    except psycopg2.errors.DuplicateColumn:
        print("   home_location_id already exists in trucks")
    
    # 3. Add pickup_location_id and delivery_location_id to loads table
    print("3. Adding location foreign keys to loads table...")
    try:
        cur.execute("ALTER TABLE loads ADD COLUMN pickup_location_id INTEGER REFERENCES locations(id);")
        print("   SUCCESS: Added pickup_location_id to loads")
    except psycopg2.errors.DuplicateColumn:
        print("   pickup_location_id already exists in loads")
    
    try:
        cur.execute("ALTER TABLE loads ADD COLUMN delivery_location_id INTEGER REFERENCES locations(id);")
        print("   SUCCESS: Added delivery_location_id to loads")
    except psycopg2.errors.DuplicateColumn:
        print("   delivery_location_id already exists in loads")
    
    # 4. Fix loads.truck_id to reference trucks.id instead of vehicles.id
    print("4. Fixing loads.truck_id foreign key...")
    try:
        # Drop the old foreign key constraint
        cur.execute("""
            ALTER TABLE loads DROP CONSTRAINT IF EXISTS loads_truck_id_fkey;
        """)
        
        # Add the correct foreign key constraint
        cur.execute("""
            ALTER TABLE loads ADD CONSTRAINT loads_truck_id_fkey 
            FOREIGN KEY (truck_id) REFERENCES trucks(id);
        """)
        print("   SUCCESS: Fixed loads.truck_id to reference trucks.id")
    except Exception as e:
        print(f"   WARNING: Could not fix loads.truck_id: {e}")
    
    conn.commit()
    print("\nSUCCESS: All foreign keys added successfully!")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

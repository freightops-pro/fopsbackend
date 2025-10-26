#!/usr/bin/env python3
"""
Add location tracking fields to SimpleLoad model for dual location system.
This script adds the new columns to the simple_loads table.
"""

import os
import sys
from sqlalchemy import create_engine, text
from app.config.settings import settings

def add_location_tracking_fields():
    """Add location tracking fields to simple_loads table"""
    
    # Create database connection
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            print("Adding location tracking fields to simple_loads table...")
            
            # Check if we're using PostgreSQL or SQLite
            dialect = engine.dialect.name
            print(f"Database dialect: {dialect}")
            
            if dialect == "postgresql":
                # PostgreSQL - add columns with proper types
                columns_to_add = [
                    ("current_driver_latitude", "FLOAT"),
                    ("current_driver_longitude", "FLOAT"),
                    ("last_location_update", "TIMESTAMP WITH TIME ZONE"),
                    ("actual_pickup_latitude", "FLOAT"),
                    ("actual_pickup_longitude", "FLOAT"),
                    ("actual_pickup_time", "TIMESTAMP WITH TIME ZONE"),
                    ("actual_delivery_latitude", "FLOAT"),
                    ("actual_delivery_longitude", "FLOAT"),
                    ("actual_delivery_time", "TIMESTAMP WITH TIME ZONE"),
                    ("route_history", "JSONB")
                ]
                
                for column_name, column_type in columns_to_add:
                    # Check if column already exists
                    check_query = text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='simple_loads' AND column_name=:column_name
                    """)
                    
                    result = conn.execute(check_query, {"column_name": column_name}).fetchone()
                    
                    if not result:
                        # Column doesn't exist, add it
                        alter_query = text(f"""
                            ALTER TABLE simple_loads 
                            ADD COLUMN {column_name} {column_type}
                        """)
                        conn.execute(alter_query)
                        print(f"[OK] Added column: {column_name}")
                    else:
                        print(f"[EXISTS] Column already exists: {column_name}")
                        
            elif dialect == "sqlite":
                # SQLite - add columns with TEXT type for JSON
                columns_to_add = [
                    ("current_driver_latitude", "REAL"),
                    ("current_driver_longitude", "REAL"),
                    ("last_location_update", "TEXT"),
                    ("actual_pickup_latitude", "REAL"),
                    ("actual_pickup_longitude", "REAL"),
                    ("actual_pickup_time", "TEXT"),
                    ("actual_delivery_latitude", "REAL"),
                    ("actual_delivery_longitude", "REAL"),
                    ("actual_delivery_time", "TEXT"),
                    ("route_history", "TEXT")
                ]
                
                for column_name, column_type in columns_to_add:
                    # Check if column already exists
                    check_query = text("PRAGMA table_info(simple_loads)")
                    result = conn.execute(check_query).fetchall()
                    
                    column_exists = any(row[1] == column_name for row in result)
                    
                    if not column_exists:
                        # Column doesn't exist, add it
                        alter_query = text(f"""
                            ALTER TABLE simple_loads 
                            ADD COLUMN {column_name} {column_type}
                        """)
                        conn.execute(alter_query)
                        print(f"[OK] Added column: {column_name}")
                    else:
                        print(f"[EXISTS] Column already exists: {column_name}")
            
            # Commit the changes
            conn.commit()
            print("\n[SUCCESS] Location tracking fields added successfully!")
            
            # Create indexes for better performance
            print("\nCreating indexes for location tracking fields...")
            
            if dialect == "postgresql":
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_simple_loads_current_location ON simple_loads(current_driver_latitude, current_driver_longitude)",
                    "CREATE INDEX IF NOT EXISTS idx_simple_loads_pickup_location ON simple_loads(actual_pickup_latitude, actual_pickup_longitude)",
                    "CREATE INDEX IF NOT EXISTS idx_simple_loads_delivery_location ON simple_loads(actual_delivery_latitude, actual_delivery_longitude)",
                    "CREATE INDEX IF NOT EXISTS idx_simple_loads_last_update ON simple_loads(last_location_update)"
                ]
                
                for index_query in indexes:
                    try:
                        conn.execute(text(index_query))
                        print(f"[OK] Created index: {index_query.split('idx_')[1].split(' ')[0]}")
                    except Exception as e:
                        print(f"[EXISTS] Index may already exist: {e}")
                        
            elif dialect == "sqlite":
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_simple_loads_current_location ON simple_loads(current_driver_latitude, current_driver_longitude)",
                    "CREATE INDEX IF NOT EXISTS idx_simple_loads_pickup_location ON simple_loads(actual_pickup_latitude, actual_pickup_longitude)",
                    "CREATE INDEX IF NOT EXISTS idx_simple_loads_delivery_location ON simple_loads(actual_delivery_latitude, actual_delivery_longitude)",
                    "CREATE INDEX IF NOT EXISTS idx_simple_loads_last_update ON simple_loads(last_location_update)"
                ]
                
                for index_query in indexes:
                    try:
                        conn.execute(text(index_query))
                        print(f"[OK] Created index: {index_query.split('idx_')[1].split(' ')[0]}")
                    except Exception as e:
                        print(f"[EXISTS] Index may already exist: {e}")
            
            conn.commit()
            print("\n[SUCCESS] Indexes created successfully!")
            
    except Exception as e:
        print(f"Error adding location tracking fields: {e}")
        return False
        
    finally:
        engine.dispose()
    
    return True

def verify_migration():
    """Verify that the migration was successful"""
    
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            print("\nVerifying migration...")
            
            # Check if all columns exist
            dialect = engine.dialect.name
            
            if dialect == "postgresql":
                query = text("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name='simple_loads' 
                    AND column_name IN (
                        'current_driver_latitude', 'current_driver_longitude', 'last_location_update',
                        'actual_pickup_latitude', 'actual_pickup_longitude', 'actual_pickup_time',
                        'actual_delivery_latitude', 'actual_delivery_longitude', 'actual_delivery_time',
                        'route_history'
                    )
                    ORDER BY column_name
                """)
                
                result = conn.execute(query).fetchall()
                
                expected_columns = [
                    'actual_delivery_latitude', 'actual_delivery_longitude', 'actual_delivery_time',
                    'actual_pickup_latitude', 'actual_pickup_longitude', 'actual_pickup_time',
                    'current_driver_latitude', 'current_driver_longitude', 'last_location_update',
                    'route_history'
                ]
                
                found_columns = [row[0] for row in result]
                
                print(f"Expected columns: {len(expected_columns)}")
                print(f"Found columns: {len(found_columns)}")
                
                for column in expected_columns:
                    if column in found_columns:
                        print(f"[OK] {column}")
                    else:
                        print(f"[MISSING] {column}")
                        
                if len(found_columns) == len(expected_columns):
                    print("\n[SUCCESS] Migration verification successful!")
                    return True
                else:
                    print("\n[FAILED] Migration verification failed!")
                    return False
                    
            elif dialect == "sqlite":
                query = text("PRAGMA table_info(simple_loads)")
                result = conn.execute(query).fetchall()
                
                found_columns = [row[1] for row in result]
                
                expected_columns = [
                    'actual_delivery_latitude', 'actual_delivery_longitude', 'actual_delivery_time',
                    'actual_pickup_latitude', 'actual_pickup_longitude', 'actual_pickup_time',
                    'current_driver_latitude', 'current_driver_longitude', 'last_location_update',
                    'route_history'
                ]
                
                print(f"Expected columns: {len(expected_columns)}")
                print(f"Found columns: {len([col for col in found_columns if col in expected_columns])}")
                
                for column in expected_columns:
                    if column in found_columns:
                        print(f"[OK] {column}")
                    else:
                        print(f"[MISSING] {column}")
                        
                if all(col in found_columns for col in expected_columns):
                    print("\n[SUCCESS] Migration verification successful!")
                    return True
                else:
                    print("\n[FAILED] Migration verification failed!")
                    return False
                    
    except Exception as e:
        print(f"Error verifying migration: {e}")
        return False
        
    finally:
        engine.dispose()

if __name__ == "__main__":
    print("FreightOps Pro - Location Tracking Migration")
    print("=" * 50)
    
    # Add the location tracking fields
    success = add_location_tracking_fields()
    
    if success:
        # Verify the migration
        verify_migration()
        print("\n[SUCCESS] Migration completed successfully!")
        print("\nThe dual location tracking system is now ready to use.")
        print("\nFeatures added:")
        print("- Driver mobile GPS location tracking")
        print("- Pickup location verification with timestamps")
        print("- Delivery location verification (Proof of Delivery)")
        print("- Route history tracking")
        print("- Dual location display on dispatch map")
    else:
        print("\n[FAILED] Migration failed!")
        sys.exit(1)

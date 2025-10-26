#!/usr/bin/env python3
from sqlalchemy import create_engine, text
from app.config.db import get_db

def add_priority_column_postgres():
    try:
        # Get database connection
        db = next(get_db())
        
        # Add priority column if it doesn't exist
        db.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='simple_loads' AND column_name='priority'
                ) THEN
                    ALTER TABLE simple_loads ADD COLUMN priority VARCHAR DEFAULT 'normal';
                END IF;
            END$$;
        """))
        
        db.commit()
        print("✅ Priority column added successfully!")
        
        # Verify the column was added
        result = db.execute(text("""
            SELECT column_name, data_type, column_default 
            FROM information_schema.columns 
            WHERE table_name='simple_loads' AND column_name='priority'
        """))
        
        column_info = result.fetchone()
        if column_info:
            print(f"✅ Priority column verified: {column_info}")
        else:
            print("❌ Priority column not found!")
            
        db.close()
        
    except Exception as e:
        print(f"❌ Error adding priority column: {e}")

if __name__ == "__main__":
    add_priority_column_postgres()

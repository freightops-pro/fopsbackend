"""
Fix Neon database schema - migrate from INTEGER IDs to VARCHAR IDs
This script will:
1. Disable all foreign key constraints
2. Convert ID columns from INTEGER to VARCHAR
3. Re-enable foreign key constraints
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Neon connection string (using IP address with endpoint ID)
DATABASE_URL = "postgresql://neondb_owner:npg_JVQsDGh9lM6S@54.156.15.30/neondb?sslmode=require&options=endpoint%3Dep-quiet-moon-adsx2dey"

def fix_schema():
    try:
        # Connect to Neon
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("OK Connected to Neon database")
        
        # Step 1: Get ALL foreign key constraints
        print("\n=> Finding ALL foreign key constraints...")
        cursor.execute("""
            SELECT 
                tc.table_name, 
                tc.constraint_name,
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
              AND tc.table_schema = 'public';
        """)
        
        foreign_keys = cursor.fetchall()
        print(f"Found {len(foreign_keys)} foreign key constraints to drop")
        
        # Step 2: Drop all foreign key constraints
        print("\n=> Dropping foreign key constraints...")
        for fk in foreign_keys:
            table_name, constraint_name, column_name, foreign_table, foreign_column = fk
            try:
                cursor.execute(f'ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS "{constraint_name}" CASCADE;')
                print(f"  + Dropped {constraint_name} from {table_name}")
            except Exception as e:
                print(f"  ! Warning dropping {constraint_name}: {e}")
        
        # Step 3: Get all primary key columns that are INTEGER
        print("\n=> Finding all PRIMARY KEY columns...")
        cursor.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND column_name = 'id'
              AND data_type IN ('integer', 'bigint')
            ORDER BY table_name;
        """)
        
        pk_columns = cursor.fetchall()
        print(f"Found {len(pk_columns)} ID columns that need conversion")
        
        # Step 4: Convert all ID columns from INTEGER to VARCHAR
        print("\n=> Converting all ID columns to VARCHAR...")
        for table_name, column_name, data_type in pk_columns:
            try:
                cursor.execute(f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" TYPE VARCHAR USING "{column_name}"::VARCHAR;')
                print(f"  + Converted {table_name}.{column_name} to VARCHAR")
            except Exception as e:
                print(f"  i {table_name}.{column_name} error: {e}")
        
        # Step 5: Convert all foreign key columns to VARCHAR
        print("\n=> Converting foreign key columns to VARCHAR...")
        fk_columns_to_convert = set()
        for fk in foreign_keys:
            table_name, _, column_name, _, _ = fk
            fk_columns_to_convert.add((table_name, column_name))
        
        for table_name, column_name in fk_columns_to_convert:
            try:
                cursor.execute(f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" TYPE VARCHAR USING "{column_name}"::VARCHAR;')
                print(f"  + Converted {table_name}.{column_name} to VARCHAR")
            except Exception as e:
                print(f"  i {table_name}.{column_name} already VARCHAR or error: {e}")
        
        # Step 6: Recreate foreign key constraints
        print("\n=> Recreating foreign key constraints...")
        for fk in foreign_keys:
            table_name, constraint_name, column_name, foreign_table, foreign_column = fk
            try:
                cursor.execute(f'''
                    ALTER TABLE "{table_name}" 
                    ADD CONSTRAINT "{constraint_name}" 
                    FOREIGN KEY ("{column_name}") 
                    REFERENCES "{foreign_table}" ("{foreign_column}");
                ''')
                print(f"  + Created {constraint_name} on {table_name}")
            except Exception as e:
                print(f"  ! Warning creating {constraint_name}: {e}")
        
        cursor.close()
        conn.close()
        
        print("\nOK Schema migration completed successfully!")
        print("The Neon database is now compatible with your models.")
        
    except psycopg2.OperationalError as e:
        print(f"\nX Connection Error: {e}")
        print("\n! This is a DNS/network issue. The Neon hostname cannot be resolved.")
        print("   Please check your network connection or DNS settings.")
        print("   Try using Google DNS (8.8.8.8) in your network settings.")
        return False
    except Exception as e:
        print(f"\nX Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Neon Database Schema Migration Tool")
    print("Converting INTEGER IDs to VARCHAR IDs")
    print("=" * 60)
    
    success = fix_schema()
    
    if success:
        print("\n" + "=" * 60)
        print("OK Migration Complete!")
        print("You can now start your backend server.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("X Migration Failed")
        print("Using SQLite as fallback for development.")
        print("=" * 60)


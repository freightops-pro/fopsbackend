#!/usr/bin/env python3
import psycopg2

def fix_vendors_schema():
    try:
        # Connect to PostgreSQL database
        conn = psycopg2.connect(
            host="localhost",
            database="freightops",
            user="postgres",
            password="password"
        )
        cursor = conn.cursor()
        
        # Add missing columns to vendors table
        alter_queries = [
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS title TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS firstName TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS middleName TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS lastName TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS suffix TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS company TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS displayName TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS printOnCheck TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS address TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS city TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS state TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS zipCode TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS country TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS email TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS phone TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS mobile TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS fax TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS other TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS website TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS billingRate TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS terms TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS openingBalance TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS balanceAsOf TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS accountNumber TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS taxId TEXT",
            "ALTER TABLE vendors ADD COLUMN IF NOT EXISTS trackPaymentsFor1099 BOOLEAN DEFAULT FALSE"
        ]
        
        for query in alter_queries:
            try:
                cursor.execute(query)
                print(f"Executed: {query}")
            except Exception as e:
                print(f"Error executing {query}: {e}")
        
        # Add missing columns to bills table
        bills_alter_queries = [
            "ALTER TABLE bills ADD COLUMN IF NOT EXISTS vendorId TEXT",
            "ALTER TABLE bills ADD COLUMN IF NOT EXISTS vendorName TEXT",
            "ALTER TABLE bills ADD COLUMN IF NOT EXISTS amount DECIMAL(10,2)",
            "ALTER TABLE bills ADD COLUMN IF NOT EXISTS billDate DATE",
            "ALTER TABLE bills ADD COLUMN IF NOT EXISTS dueDate DATE",
            "ALTER TABLE bills ADD COLUMN IF NOT EXISTS category TEXT",
            "ALTER TABLE bills ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending'",
            "ALTER TABLE bills ADD COLUMN IF NOT EXISTS notes TEXT"
        ]
        
        for query in bills_alter_queries:
            try:
                cursor.execute(query)
                print(f"Executed: {query}")
            except Exception as e:
                print(f"Error executing {query}: {e}")
        
        conn.commit()
        conn.close()
        
        print("Successfully updated vendors and bills tables!")
        
    except Exception as e:
        print(f"Error fixing schema: {e}")

if __name__ == "__main__":
    fix_vendors_schema()

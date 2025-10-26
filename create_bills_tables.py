#!/usr/bin/env python3
import sqlite3
from datetime import datetime

def create_bills_tables():
    try:
        conn = sqlite3.connect('freightops.db')
        cursor = conn.cursor()
        
        # Create vendors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vendors (
                id TEXT PRIMARY KEY NOT NULL,
                companyId TEXT NOT NULL,
                
                -- Personal Details
                title TEXT,
                firstName TEXT,
                middleName TEXT,
                lastName TEXT,
                suffix TEXT,
                
                -- Company Details
                company TEXT,
                displayName TEXT NOT NULL,
                printOnCheck TEXT,
                
                -- Address Information
                address TEXT,
                city TEXT,
                state TEXT,
                zipCode TEXT,
                country TEXT,
                
                -- Contact Information
                email TEXT,
                phone TEXT,
                mobile TEXT,
                fax TEXT,
                other TEXT,
                website TEXT,
                
                -- Financial Information
                billingRate TEXT,
                terms TEXT,
                openingBalance TEXT,
                balanceAsOf TEXT,
                accountNumber TEXT,
                
                -- 1099 Tracking
                taxId TEXT,
                trackPaymentsFor1099 BOOLEAN DEFAULT FALSE,
                
                -- Timestamps
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create bills table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bills (
                id TEXT PRIMARY KEY NOT NULL,
                companyId TEXT NOT NULL,
                vendorId TEXT,
                vendorName TEXT NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                billDate DATE,
                dueDate DATE,
                category TEXT,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (vendorId) REFERENCES vendors (id)
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_vendors_companyId ON vendors(companyId)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bills_companyId ON bills(companyId)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bills_vendorId ON bills(vendorId)')
        
        conn.commit()
        conn.close()
        
        print("Successfully created bills and vendors tables!")
        
    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == "__main__":
    create_bills_tables()

#!/usr/bin/env python3
"""
Script to create the documents table in the existing database
"""

import sqlite3
import os

def create_documents_table():
    # Connect to the database
    db_path = "freightops.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create Documents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            "companyId" TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            "fileName" TEXT NOT NULL,
            "fileSize" INTEGER,
            "fileType" TEXT,
            "filePath" TEXT,
            "employeeId" TEXT,
            "employeeName" TEXT,
            status TEXT DEFAULT 'Active',
            "uploadDate" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "expiryDate" TIMESTAMP,
            details TEXT,
            "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY ("companyId") REFERENCES companies(id)
        )
    ''')
    
    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_company_id ON documents("companyId")')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_employee_id ON documents("employeeId")')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category)')
    
    conn.commit()
    conn.close()
    
    print("Documents table created successfully!")

if __name__ == "__main__":
    create_documents_table()

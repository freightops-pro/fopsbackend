#!/usr/bin/env python3
"""
Script to create the compliance-related tables in the existing database
"""

import psycopg2
import os
from app.config.settings import settings

def create_compliance_tables():
    # Connect to the database using PostgreSQL
    conn = psycopg2.connect(settings.DATABASE_URL)
    cursor = conn.cursor()
    
    # Check if ELD Compliance table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'eld_compliance'
        )
    """)
    
    if not cursor.fetchone()[0]:
        # Create ELD Compliance table
        cursor.execute('''
            CREATE TABLE eld_compliance (
                id TEXT PRIMARY KEY,
                "companyId" TEXT NOT NULL,
                "driverId" TEXT NOT NULL,
                "equipmentId" TEXT NOT NULL,
                date DATE NOT NULL,
                "totalDrivingTime" INTEGER,
                "totalOnDutyTime" INTEGER,
                "totalOffDutyTime" INTEGER,
                "totalSleeperTime" INTEGER,
                "hasViolations" BOOLEAN DEFAULT FALSE,
                violations JSONB,
                "violationTypes" JSONB,
                "isCompliant" BOOLEAN DEFAULT TRUE,
                "complianceScore" INTEGER,
                "auditStatus" TEXT DEFAULT 'pending',
                "aiAuditResults" JSONB,
                "aiRecommendations" TEXT,
                "aiConfidence" REAL,
                "exportedAt" TIMESTAMP,
                "exportFormat" TEXT,
                "exportUrl" TEXT,
                "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                "isActive" BOOLEAN DEFAULT TRUE
            )
        ''')
        print("ELD Compliance table created successfully!")
    else:
        print("ELD Compliance table already exists!")
    
    # Create SAFER Data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS safer_data (
            id TEXT PRIMARY KEY,
            "companyId" TEXT NOT NULL,
            "dotNumber" TEXT NOT NULL,
            "legalName" TEXT NOT NULL,
            "dbaName" TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            "zipCode" TEXT,
            country TEXT DEFAULT 'US',
            "safetyRating" TEXT,
            "safetyRatingDate" DATE,
            "previousSafetyRating" TEXT,
            "totalInspections" INTEGER DEFAULT 0,
            "totalInspectionsWithViolations" INTEGER DEFAULT 0,
            "totalViolations" INTEGER DEFAULT 0,
            "totalOutOfServiceViolations" INTEGER DEFAULT 0,
            "totalOutOfServiceViolationsPercentage" REAL,
            "totalCrashes" INTEGER DEFAULT 0,
            "fatalCrashes" INTEGER DEFAULT 0,
            "injuryCrashes" INTEGER DEFAULT 0,
            "towAwayCrashes" INTEGER DEFAULT 0,
            "totalVehicles" INTEGER DEFAULT 0,
            "totalDrivers" INTEGER DEFAULT 0,
            "reportUrl" TEXT,
            "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "isActive" BOOLEAN DEFAULT TRUE,
            FOREIGN KEY ("companyId") REFERENCES companies(id)
        )
    ''')
    
    # Create Insurance Policies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS insurance_policies (
            id TEXT PRIMARY KEY,
            "companyId" TEXT NOT NULL,
            "policyNumber" TEXT NOT NULL,
            "policyType" TEXT NOT NULL,
            "insuranceProvider" TEXT NOT NULL,
            "agentName" TEXT,
            "agentPhone" TEXT,
            "agentEmail" TEXT,
            "coverageAmount" REAL NOT NULL,
            deductible REAL,
            premium REAL NOT NULL,
            "paymentFrequency" TEXT,
            "effectiveDate" DATE NOT NULL,
            "expirationDate" DATE NOT NULL,
            "renewalDate" DATE,
            status TEXT DEFAULT 'active',
            "isRenewed" BOOLEAN DEFAULT FALSE,
            "policyDocument" TEXT,
            "certificateOfInsurance" TEXT,
            notes TEXT,
            "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "isActive" BOOLEAN DEFAULT TRUE,
            FOREIGN KEY ("companyId") REFERENCES companies(id)
        )
    ''')
    
    # Create Permit Books table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS permit_books (
            id TEXT PRIMARY KEY,
            "companyId" TEXT NOT NULL,
            "permitNumber" TEXT NOT NULL,
            "permitType" TEXT NOT NULL,
            "issuingAuthority" TEXT NOT NULL,
            state TEXT NOT NULL,
            description TEXT,
            route TEXT,
            restrictions TEXT,
            "specialConditions" TEXT,
            "issueDate" DATE NOT NULL,
            "expirationDate" DATE NOT NULL,
            "renewalDate" DATE,
            "permitFee" REAL,
            "processingFee" REAL,
            "totalFee" REAL,
            status TEXT DEFAULT 'active',
            "isRenewed" BOOLEAN DEFAULT FALSE,
            "permitDocument" TEXT,
            "applicationDocument" TEXT,
            notes TEXT,
            "equipmentId" TEXT,
            "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "isActive" BOOLEAN DEFAULT TRUE,
            FOREIGN KEY ("companyId") REFERENCES companies(id)
        )
    ''')
    
    # Create Driver HOS Logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS driver_hos_logs (
            id TEXT PRIMARY KEY,
            "companyId" TEXT NOT NULL,
            "driverId" TEXT NOT NULL,
            "equipmentId" TEXT NOT NULL,
            "logDate" DATE NOT NULL,
            "drivingTime" INTEGER DEFAULT 0,
            "onDutyTime" INTEGER DEFAULT 0,
            "offDutyTime" INTEGER DEFAULT 0,
            "sleeperTime" INTEGER DEFAULT 0,
            "hasRequiredBreaks" BOOLEAN DEFAULT TRUE,
            "breakViolations" TEXT,
            "elevenHourCompliant" BOOLEAN DEFAULT TRUE,
            "elevenHourViolations" TEXT,
            "fourteenHourCompliant" BOOLEAN DEFAULT TRUE,
            "fourteenHourViolations" TEXT,
            "seventyHourCompliant" BOOLEAN DEFAULT TRUE,
            "seventyHourViolations" TEXT,
            "thirtyFourHourCompliant" BOOLEAN DEFAULT TRUE,
            "thirtyFourHourViolations" TEXT,
            "eldDeviceId" TEXT,
            "eldProvider" TEXT,
            "dataTransferStatus" TEXT,
            "isCompliant" BOOLEAN DEFAULT TRUE,
            violations TEXT,
            "violationCount" INTEGER DEFAULT 0,
            notes TEXT,
            "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "isActive" BOOLEAN DEFAULT TRUE,
            FOREIGN KEY ("companyId") REFERENCES companies(id)
        )
    ''')
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    
    print("Compliance tables created successfully!")

if __name__ == "__main__":
    create_compliance_tables()

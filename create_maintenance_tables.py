#!/usr/bin/env python3
"""
Script to create the maintenance-related tables in the existing database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.config.settings import settings

def create_maintenance_tables():
    """Create the maintenance-related tables if they don't exist"""
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Check if maintenance_schedule table exists (PostgreSQL syntax)
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'maintenance_schedule'
                )
            """))
            
            if not result.fetchone()[0]:
                print("Creating maintenance_schedule table...")
                conn.execute(text("""
                    CREATE TABLE maintenance_schedule (
                        id VARCHAR PRIMARY KEY NOT NULL,
                        "companyId" VARCHAR NOT NULL,
                        "equipmentId" VARCHAR NOT NULL,
                        title VARCHAR NOT NULL,
                        description TEXT,
                        "maintenanceType" VARCHAR NOT NULL,
                        priority VARCHAR DEFAULT 'medium',
                        "scheduledDate" TIMESTAMP NOT NULL,
                        "estimatedDuration" INTEGER,
                        "estimatedCost" NUMERIC,
                        "isRecurring" BOOLEAN DEFAULT FALSE,
                        "recurrenceType" VARCHAR,
                        "recurrenceInterval" INTEGER,
                        "nextOccurrence" TIMESTAMP,
                        status VARCHAR DEFAULT 'scheduled',
                        "actualStartDate" TIMESTAMP,
                        "actualEndDate" TIMESTAMP,
                        "actualCost" NUMERIC,
                        "assignedTechnician" VARCHAR,
                        "assignedVendor" VARCHAR,
                        "vendorContact" VARCHAR,
                        "vendorPhone" VARCHAR,
                        location VARCHAR,
                        notes TEXT,
                        attachments JSONB,
                        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        "createdBy" VARCHAR,
                        "isActive" BOOLEAN DEFAULT TRUE
                    )
                """))
                print("✓ maintenance_schedule table created successfully")
            else:
                print("✓ maintenance_schedule table already exists")
            
            # Check if eld_alerts table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'eld_alerts'
                )
            """))
            
            if not result.fetchone()[0]:
                print("Creating eld_alerts table...")
                conn.execute(text("""
                    CREATE TABLE eld_alerts (
                        id VARCHAR PRIMARY KEY NOT NULL,
                        "companyId" VARCHAR NOT NULL,
                        "equipmentId" VARCHAR NOT NULL,
                        "driverId" VARCHAR,
                        "alertType" VARCHAR NOT NULL,
                        severity VARCHAR DEFAULT 'medium',
                        title VARCHAR NOT NULL,
                        description TEXT,
                        "alertData" JSONB,
                        location VARCHAR,
                        status VARCHAR DEFAULT 'active',
                        "acknowledgedBy" VARCHAR,
                        "acknowledgedAt" TIMESTAMP,
                        "resolvedBy" VARCHAR,
                        "resolvedAt" TIMESTAMP,
                        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        "isActive" BOOLEAN DEFAULT TRUE
                    )
                """))
                print("✓ eld_alerts table created successfully")
            else:
                print("✓ eld_alerts table already exists")
            
            # Check if road_services table exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'road_services'
                )
            """))
            
            if not result.fetchone()[0]:
                print("Creating road_services table...")
                conn.execute(text("""
                    CREATE TABLE road_services (
                        id VARCHAR PRIMARY KEY NOT NULL,
                        "companyId" VARCHAR NOT NULL,
                        "equipmentId" VARCHAR NOT NULL,
                        "driverId" VARCHAR,
                        "serviceType" VARCHAR NOT NULL,
                        priority VARCHAR DEFAULT 'medium',
                        title VARCHAR NOT NULL,
                        description TEXT,
                        location VARCHAR NOT NULL,
                        latitude NUMERIC,
                        longitude NUMERIC,
                        "contactName" VARCHAR,
                        "contactPhone" VARCHAR,
                        "serviceProvider" VARCHAR,
                        "providerPhone" VARCHAR,
                        "estimatedArrival" TIMESTAMP,
                        "estimatedCost" NUMERIC,
                        status VARCHAR DEFAULT 'requested',
                        "requestedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        "dispatchedAt" TIMESTAMP,
                        "arrivedAt" TIMESTAMP,
                        "completedAt" TIMESTAMP,
                        "actualCost" NUMERIC,
                        notes TEXT,
                        photos JSONB,
                        documents JSONB,
                        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        "createdBy" VARCHAR,
                        "isActive" BOOLEAN DEFAULT TRUE
                    )
                """))
                print("✓ road_services table created successfully")
            else:
                print("✓ road_services table already exists")
            
            conn.commit()
            print("\n🎉 All maintenance tables created successfully!")
            
    except Exception as e:
        print(f"❌ Error creating maintenance tables: {e}")
        return False
    
    return True

if __name__ == "__main__":
    create_maintenance_tables()

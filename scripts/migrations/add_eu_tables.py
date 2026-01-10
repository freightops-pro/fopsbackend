"""
Migration: Add EU (European Union) Regional Tables

Creates tables for EU-specific freight compliance:
- eu_ecmr_documents - Electronic Consignment Notes
- eu_cabotage_operations - Cabotage tracking (3-in-7 rule)
- eu_posted_worker_declarations - Posted worker compliance
- eu_tachograph_data - Digital tachograph downloads
- eu_company_data - EU-specific company registrations
"""

import asyncio
import sys

if sys.platform == "win32":
    import selectors

    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    asyncio.set_event_loop(loop)

from app.core.db import AsyncSessionFactory
from sqlalchemy import text


async def add_eu_tables():
    """Add EU regional tables to database"""
    async with AsyncSessionFactory() as db:
        try:
            # Check if tables already exist
            check_sql = """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name LIKE 'eu_%'
            ORDER BY table_name
            """
            result = await db.execute(text(check_sql))
            existing_tables = [r[0] for r in result.fetchall()]

            if existing_tables:
                print("Existing EU tables found:")
                for table in existing_tables:
                    print(f"  - {table}")
                print("\nSkipping tables that already exist...")

            # 1. EU e-CMR Documents
            if "eu_ecmr_documents" not in existing_tables:
                print("\nCreating eu_ecmr_documents table...")
                await db.execute(
                    text(
                        """
                    CREATE TABLE eu_ecmr_documents (
                        id VARCHAR PRIMARY KEY,
                        company_id VARCHAR NOT NULL,
                        load_id VARCHAR NOT NULL,

                        -- Document Details
                        consignment_note_number VARCHAR NOT NULL UNIQUE,
                        issue_date TIMESTAMP NOT NULL DEFAULT NOW(),
                        document_type VARCHAR NOT NULL DEFAULT 'e-CMR',

                        -- Parties
                        sender_name VARCHAR NOT NULL,
                        sender_address TEXT NOT NULL,
                        sender_country_code VARCHAR(2) NOT NULL,

                        carrier_name VARCHAR NOT NULL,
                        carrier_license_number VARCHAR,
                        carrier_country_code VARCHAR(2) NOT NULL,

                        consignee_name VARCHAR NOT NULL,
                        consignee_address TEXT NOT NULL,
                        consignee_country_code VARCHAR(2) NOT NULL,

                        -- Goods Description
                        goods_description TEXT NOT NULL,
                        weight_kg FLOAT NOT NULL,
                        package_count INTEGER NOT NULL,
                        package_type VARCHAR,

                        -- Dangerous Goods
                        is_dangerous_goods BOOLEAN NOT NULL DEFAULT FALSE,
                        un_number VARCHAR,
                        adr_class VARCHAR,

                        -- Temperature Control
                        requires_temperature_control BOOLEAN NOT NULL DEFAULT FALSE,
                        temperature_range VARCHAR,
                        atp_certificate_number VARCHAR,

                        -- Transport Details
                        vehicle_registration VARCHAR,
                        trailer_registration VARCHAR,
                        driver_name VARCHAR,
                        tachograph_card_number VARCHAR,

                        -- Route
                        place_of_loading TEXT NOT NULL,
                        place_of_delivery TEXT NOT NULL,
                        loading_date TIMESTAMP,
                        delivery_date TIMESTAMP,

                        -- Instructions
                        special_instructions TEXT,
                        payment_instructions TEXT,

                        -- Digital Signatures
                        sender_signature TEXT,
                        sender_signature_timestamp TIMESTAMP,
                        carrier_signature TEXT,
                        carrier_signature_timestamp TIMESTAMP,
                        consignee_signature TEXT,
                        consignee_signature_timestamp TIMESTAMP,

                        -- Status
                        status VARCHAR NOT NULL DEFAULT 'draft',

                        -- Platform Integration
                        ecmr_platform VARCHAR,
                        platform_document_id VARCHAR,

                        -- Additional Data
                        additional_data JSONB,

                        -- Timestamps
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    );

                    CREATE INDEX idx_eu_ecmr_company ON eu_ecmr_documents(company_id);
                    CREATE INDEX idx_eu_ecmr_load ON eu_ecmr_documents(load_id);
                    CREATE INDEX idx_eu_ecmr_number ON eu_ecmr_documents(consignment_note_number);
                """
                    )
                )
                await db.commit()
                print("  Created eu_ecmr_documents table")

            # 2. EU Cabotage Operations
            if "eu_cabotage_operations" not in existing_tables:
                print("\nCreating eu_cabotage_operations table...")
                await db.execute(
                    text(
                        """
                    CREATE TABLE eu_cabotage_operations (
                        id VARCHAR PRIMARY KEY,
                        company_id VARCHAR NOT NULL,
                        vehicle_id VARCHAR NOT NULL,
                        load_id VARCHAR NOT NULL,

                        -- Country and Dates
                        country_code VARCHAR(2) NOT NULL,
                        operation_date TIMESTAMP NOT NULL,
                        operation_number INTEGER NOT NULL,

                        -- Preceding International Transport
                        preceding_international_load_id VARCHAR,
                        international_unloading_date TIMESTAMP,

                        -- Route Details
                        origin_city VARCHAR NOT NULL,
                        destination_city VARCHAR NOT NULL,
                        distance_km FLOAT NOT NULL,

                        -- Validation
                        is_compliant BOOLEAN NOT NULL DEFAULT TRUE,
                        violation_reason TEXT,

                        -- Enforcement
                        checked_by_authority BOOLEAN NOT NULL DEFAULT FALSE,
                        check_date TIMESTAMP,
                        check_location VARCHAR,
                        fine_amount FLOAT,

                        -- Timestamps
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    );

                    CREATE INDEX idx_eu_cabotage_company ON eu_cabotage_operations(company_id);
                    CREATE INDEX idx_eu_cabotage_vehicle ON eu_cabotage_operations(vehicle_id);
                    CREATE INDEX idx_eu_cabotage_country ON eu_cabotage_operations(country_code);
                    CREATE INDEX idx_eu_cabotage_date ON eu_cabotage_operations(operation_date);
                """
                    )
                )
                await db.commit()
                print("  Created eu_cabotage_operations table")

            # 3. EU Posted Worker Declarations
            if "eu_posted_worker_declarations" not in existing_tables:
                print("\nCreating eu_posted_worker_declarations table...")
                await db.execute(
                    text(
                        """
                    CREATE TABLE eu_posted_worker_declarations (
                        id VARCHAR PRIMARY KEY,
                        company_id VARCHAR NOT NULL,
                        driver_id VARCHAR NOT NULL,

                        -- Posting Details
                        host_country_code VARCHAR(2) NOT NULL,
                        posting_start_date TIMESTAMP NOT NULL,
                        posting_end_date TIMESTAMP,
                        days_in_country INTEGER NOT NULL DEFAULT 0,

                        -- Driver Information
                        driver_name VARCHAR NOT NULL,
                        driver_nationality VARCHAR(2) NOT NULL,
                        driver_residence_country VARCHAR(2) NOT NULL,

                        -- Employment Details
                        employment_contract_country VARCHAR(2) NOT NULL,
                        applicable_social_security_system VARCHAR(2) NOT NULL,

                        -- Accommodation
                        accommodation_address TEXT NOT NULL,
                        accommodation_type VARCHAR NOT NULL,

                        -- Transport Operations
                        loads_during_posting JSON,

                        -- Submission to Authority
                        submitted_to_authority BOOLEAN NOT NULL DEFAULT FALSE,
                        submission_date TIMESTAMP,
                        submission_reference VARCHAR,
                        authority_response TEXT,

                        -- Status
                        status VARCHAR NOT NULL DEFAULT 'draft',

                        -- Timestamps
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    );

                    CREATE INDEX idx_eu_posted_company ON eu_posted_worker_declarations(company_id);
                    CREATE INDEX idx_eu_posted_driver ON eu_posted_worker_declarations(driver_id);
                    CREATE INDEX idx_eu_posted_country ON eu_posted_worker_declarations(host_country_code);
                """
                    )
                )
                await db.commit()
                print("  Created eu_posted_worker_declarations table")

            # 4. EU Tachograph Data
            if "eu_tachograph_data" not in existing_tables:
                print("\nCreating eu_tachograph_data table...")
                await db.execute(
                    text(
                        """
                    CREATE TABLE eu_tachograph_data (
                        id VARCHAR PRIMARY KEY,
                        company_id VARCHAR NOT NULL,

                        -- Download Type
                        download_type VARCHAR NOT NULL,

                        -- Vehicle or Driver
                        vehicle_id VARCHAR,
                        driver_id VARCHAR,

                        -- Tachograph Details
                        tachograph_serial_number VARCHAR NOT NULL,
                        driver_card_number VARCHAR,

                        -- Download Information
                        download_date TIMESTAMP NOT NULL DEFAULT NOW(),
                        data_period_start TIMESTAMP NOT NULL,
                        data_period_end TIMESTAMP NOT NULL,
                        days_of_data INTEGER NOT NULL,

                        -- File Information
                        file_name VARCHAR NOT NULL,
                        file_format VARCHAR NOT NULL DEFAULT 'DDD',
                        file_size_bytes INTEGER NOT NULL,
                        file_storage_path VARCHAR NOT NULL,

                        -- Analysis Results
                        violations_detected INTEGER NOT NULL DEFAULT 0,
                        violation_types JSON,
                        total_driving_time_hours FLOAT,
                        total_rest_time_hours FLOAT,

                        -- Compliance Status
                        is_compliant BOOLEAN NOT NULL DEFAULT TRUE,
                        requires_review BOOLEAN NOT NULL DEFAULT FALSE,
                        reviewed_by VARCHAR,
                        review_date TIMESTAMP,
                        review_notes TEXT,

                        -- Timestamps
                        created_at TIMESTAMP NOT NULL DEFAULT NOW()
                    );

                    CREATE INDEX idx_eu_tacho_company ON eu_tachograph_data(company_id);
                    CREATE INDEX idx_eu_tacho_vehicle ON eu_tachograph_data(vehicle_id);
                    CREATE INDEX idx_eu_tacho_driver ON eu_tachograph_data(driver_id);
                """
                    )
                )
                await db.commit()
                print("  Created eu_tachograph_data table")

            # 5. EU Company Data
            if "eu_company_data" not in existing_tables:
                print("\nCreating eu_company_data table...")
                await db.execute(
                    text(
                        """
                    CREATE TABLE eu_company_data (
                        id VARCHAR PRIMARY KEY,
                        company_id VARCHAR NOT NULL UNIQUE,

                        -- EU Community License
                        eu_license_number VARCHAR NOT NULL UNIQUE,
                        eu_license_issuing_country VARCHAR(2) NOT NULL,
                        eu_license_valid_until TIMESTAMP NOT NULL,
                        eu_license_type VARCHAR NOT NULL DEFAULT 'community',

                        -- Company Registration
                        company_registration_number VARCHAR NOT NULL,
                        vat_number VARCHAR,
                        eori_number VARCHAR,

                        -- Operating Countries
                        operating_countries JSON NOT NULL,

                        -- e-CMR Configuration
                        ecmr_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                        ecmr_platform VARCHAR,
                        ecmr_platform_credentials TEXT,

                        -- Insurance
                        liability_insurance_policy VARCHAR,
                        liability_insurance_valid_until TIMESTAMP,
                        insurance_coverage_amount FLOAT,

                        -- Fleet Information
                        total_vehicles INTEGER NOT NULL DEFAULT 0,
                        total_drivers INTEGER NOT NULL DEFAULT 0,

                        -- Compliance Features
                        tachograph_download_frequency_days INTEGER NOT NULL DEFAULT 28,
                        automatic_posted_worker_declarations BOOLEAN NOT NULL DEFAULT TRUE,
                        cabotage_tracking_enabled BOOLEAN NOT NULL DEFAULT TRUE,

                        -- Contact Information
                        compliance_officer_name VARCHAR,
                        compliance_officer_email VARCHAR,
                        compliance_officer_phone VARCHAR,

                        -- Additional Data
                        additional_data JSONB,

                        -- Timestamps
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    );

                    CREATE INDEX idx_eu_company_id ON eu_company_data(company_id);
                    CREATE INDEX idx_eu_license ON eu_company_data(eu_license_number);
                """
                    )
                )
                await db.commit()
                print("  Created eu_company_data table")

            print("\n" + "=" * 60)
            print("EU REGIONAL TABLES MIGRATION COMPLETED")
            print("=" * 60)

            # Verify all tables were created
            result = await db.execute(text(check_sql))
            final_tables = [r[0] for r in result.fetchall()]

            if final_tables:
                print("\nEU tables in database:")
                for table in sorted(final_tables):
                    print(f"  - {table}")
                print(f"\nTotal EU tables: {len(final_tables)}")
            else:
                print("\nNo EU tables found - migration may have failed")

        except Exception as e:
            print(f"\nERROR during migration: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(add_eu_tables())
    else:
        asyncio.run(add_eu_tables())

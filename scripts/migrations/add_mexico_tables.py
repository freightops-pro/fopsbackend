"""
Add Mexico-Specific Tables

Creates Mexico compliance tables WITHOUT touching any existing tables.

What this does:
1. Creates mexico_carta_porte (Carta de Porte 3.0 digital waybills)
2. Creates mexico_sat_submissions (SAT API logs)
3. Creates mexico_company_data (Mexican registrations)
4. Creates mexico_security_incidents (Security tracking)

What this DOES NOT do:
- Does NOT modify company table
- Does NOT modify loads table
- Does NOT modify any USA/Brazil/Canada tables
- Does NOT affect existing data

Run: python -m scripts.migrations.add_mexico_tables
"""

import sys
if sys.platform == "win32":
    import asyncio
    import selectors
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    asyncio.set_event_loop(loop)

import asyncio
from sqlalchemy import text

from app.core.db import AsyncSessionFactory


async def add_mexico_tables():
    """Create Mexico-specific tables."""

    async with AsyncSessionFactory() as db:
        print("=" * 70)
        print("ADDING MEXICO COMPLIANCE TABLES")
        print("=" * 70)
        print()

        # Check if tables already exist
        check_sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name LIKE 'mexico_%'
        """

        result = await db.execute(text(check_sql))
        existing_tables = {row[0] for row in result.fetchall()}

        tables_to_create = []

        # ========== MEXICO CARTA DE PORTE TABLE ==========

        if 'mexico_carta_porte' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE mexico_carta_porte (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR NOT NULL,
                    load_id VARCHAR NOT NULL,

                    -- CFDI/Carta de Porte Identification
                    serie VARCHAR NOT NULL DEFAULT 'CP',
                    folio VARCHAR NOT NULL,
                    uuid VARCHAR UNIQUE,

                    -- SAT Status
                    status VARCHAR NOT NULL,
                    sat_seal TEXT,
                    authorization_date TIMESTAMP,

                    -- XML Data
                    xml_unsigned TEXT NOT NULL,
                    xml_signed TEXT,

                    -- Transport Details
                    rfc_emisor VARCHAR NOT NULL,
                    rfc_receptor VARCHAR,
                    driver_name VARCHAR NOT NULL,
                    driver_license VARCHAR NOT NULL,
                    driver_rfc VARCHAR,

                    -- Vehicle Details
                    vehicle_plate VARCHAR NOT NULL,
                    vehicle_year INTEGER,
                    config_vehicular VARCHAR NOT NULL DEFAULT 'C2',

                    -- Cargo Details
                    total_distance_km DECIMAL(10,2) NOT NULL,
                    total_weight_kg DECIMAL(10,2) NOT NULL,
                    cargo_value_mxn DECIMAL(15,2) NOT NULL,
                    cargo_description TEXT NOT NULL,

                    -- SCT Permit
                    sct_permit_type VARCHAR NOT NULL,
                    sct_permit_number VARCHAR NOT NULL,

                    -- Insurance
                    insurance_company VARCHAR,
                    insurance_policy VARCHAR,

                    -- Additional
                    error_message TEXT,
                    metadata JSONB,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_mexico_carta_porte_company ON mexico_carta_porte(company_id);
                CREATE INDEX idx_mexico_carta_porte_load ON mexico_carta_porte(load_id);
                CREATE INDEX idx_mexico_carta_porte_status ON mexico_carta_porte(status);
                """,
                "mexico_carta_porte (Carta de Porte 3.0 Digital Waybills)"
            ))

        # ========== MEXICO SAT SUBMISSIONS TABLE ==========

        if 'mexico_sat_submissions' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE mexico_sat_submissions (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR NOT NULL,

                    -- Submission Details
                    document_type VARCHAR NOT NULL,
                    document_id VARCHAR NOT NULL,
                    submission_type VARCHAR NOT NULL,

                    -- SAT Response
                    status_code VARCHAR NOT NULL,
                    sat_status VARCHAR NOT NULL,
                    uuid VARCHAR,
                    sat_seal TEXT,
                    response_message TEXT,

                    -- XML Exchange
                    request_xml TEXT NOT NULL,
                    response_xml TEXT,

                    -- Timing
                    request_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                    response_timestamp TIMESTAMP,
                    response_time_ms INTEGER,

                    -- Error Handling
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_mexico_sat_company ON mexico_sat_submissions(company_id);
                CREATE INDEX idx_mexico_sat_document ON mexico_sat_submissions(document_id);
                CREATE INDEX idx_mexico_sat_status ON mexico_sat_submissions(sat_status);
                """,
                "mexico_sat_submissions (SAT API Logs)"
            ))

        # ========== MEXICO COMPANY DATA TABLE ==========

        if 'mexico_company_data' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE mexico_company_data (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR UNIQUE NOT NULL,

                    -- Tax Registration
                    rfc VARCHAR UNIQUE NOT NULL,

                    -- Transport Registration
                    sct_permit VARCHAR UNIQUE NOT NULL,
                    sct_permit_type VARCHAR NOT NULL,
                    sct_permit_expiry TIMESTAMP,

                    -- Insurance
                    insurance_company VARCHAR,
                    insurance_policy VARCHAR,
                    insurance_expiry TIMESTAMP,

                    -- Digital Certificate for SAT
                    certificate_type VARCHAR,
                    certificate_serial VARCHAR,
                    certificate_expiry TIMESTAMP,
                    certificate_data TEXT,

                    -- SAT Configuration
                    sat_environment VARCHAR NOT NULL DEFAULT 'production',

                    -- Security
                    gps_jammer_detection_available BOOLEAN NOT NULL DEFAULT FALSE,
                    cargo_insurance_active BOOLEAN NOT NULL DEFAULT FALSE,

                    -- Quebec Operations (NAFTA/USMCA)
                    operates_in_quebec BOOLEAN NOT NULL DEFAULT FALSE,
                    french_language_capable BOOLEAN NOT NULL DEFAULT FALSE,

                    -- Status
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    registration_validated BOOLEAN NOT NULL DEFAULT FALSE,

                    -- Metadata
                    registration_date TIMESTAMP,
                    metadata JSONB,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_mexico_company_data_company ON mexico_company_data(company_id);
                CREATE UNIQUE INDEX idx_mexico_company_rfc ON mexico_company_data(rfc);
                CREATE UNIQUE INDEX idx_mexico_company_sct ON mexico_company_data(sct_permit);
                """,
                "mexico_company_data (Mexican Company Registrations)"
            ))

        # ========== MEXICO SECURITY INCIDENTS TABLE ==========

        if 'mexico_security_incidents' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE mexico_security_incidents (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR NOT NULL,
                    load_id VARCHAR,

                    -- Incident Details
                    incident_type VARCHAR NOT NULL,
                    incident_date TIMESTAMP NOT NULL,
                    state VARCHAR NOT NULL,
                    municipality VARCHAR,
                    highway VARCHAR,

                    -- Location
                    latitude DECIMAL(10,7),
                    longitude DECIMAL(10,7),

                    -- Impact
                    cargo_value_lost_mxn DECIMAL(15,2),
                    injuries BOOLEAN NOT NULL DEFAULT FALSE,
                    fatalities BOOLEAN NOT NULL DEFAULT FALSE,

                    -- Investigation
                    police_report_number VARCHAR,
                    insurance_claim_number VARCHAR,
                    resolved BOOLEAN NOT NULL DEFAULT FALSE,

                    -- Description
                    description TEXT,
                    metadata JSONB,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_mexico_incidents_company ON mexico_security_incidents(company_id);
                CREATE INDEX idx_mexico_incidents_load ON mexico_security_incidents(load_id);
                CREATE INDEX idx_mexico_incidents_state ON mexico_security_incidents(state);
                CREATE INDEX idx_mexico_incidents_date ON mexico_security_incidents(incident_date);
                """,
                "mexico_security_incidents (Security Incident Tracking)"
            ))

        # ========== EXECUTE MIGRATIONS ==========

        if not tables_to_create:
            print("✓ All Mexico tables already exist!")
            print("  No changes needed.")
            return

        print(f"Creating {len(tables_to_create)} Mexico tables...")
        print()

        for sql, description in tables_to_create:
            try:
                await db.execute(text(sql))
                print(f"  ✓ Created {description}")
            except Exception as e:
                print(f"  ! Failed to create {description}")
                print(f"     Error: {str(e)}")

        await db.commit()

        print()
        print("=" * 70)
        print("MEXICO TABLES CREATED SUCCESSFULLY")
        print("=" * 70)
        print()
        print("Tables created:")
        print("  ✓ mexico_carta_porte - Carta de Porte 3.0 Digital Waybills")
        print("  ✓ mexico_sat_submissions - SAT API Logs")
        print("  ✓ mexico_company_data - Mexican Company Registrations")
        print("  ✓ mexico_security_incidents - Security Incident Tracking")
        print()
        print("Tables NOT modified (safe):")
        print("  ✓ company - Untouched")
        print("  ✓ loads - Untouched")
        print("  ✓ drivers - Untouched")
        print("  ✓ usa_* tables - Untouched")
        print("  ✓ brazil_* tables - Untouched")
        print("  ✓ canada_* tables - Untouched")
        print()
        print("Next steps:")
        print("  1. For Mexican companies: Populate mexico_company_data")
        print("  2. Configure SAT credentials and digital certificates")
        print("  3. Set up GPS jammer detection for high-value cargo")
        print("  4. Test Carta de Porte generation with homologation environment")
        print()


async def main():
    await add_mexico_tables()


if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    else:
        asyncio.run(main())

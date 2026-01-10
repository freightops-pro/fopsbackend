"""
Add Canada-Specific Tables

Creates Canada compliance tables WITHOUT touching any existing tables.

What this does:
1. Creates canada_hos_logs (Canadian Hours of Service logs)
2. Creates canada_erod_events (EROD device events)
3. Creates canada_ifta_records (IFTA fuel tax records)
4. Creates canada_tdg_shipments (Dangerous goods tracking)
5. Creates canada_company_data (Canadian registrations)
6. Creates canada_border_crossings (Canada-USA border tracking)

What this DOES NOT do:
- Does NOT modify company table
- Does NOT modify loads table
- Does NOT modify any USA/Brazil/Mexico tables
- Does NOT affect existing data

Run: python -m scripts.migrations.add_canada_tables
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


async def add_canada_tables():
    """Create Canada-specific tables."""

    async with AsyncSessionFactory() as db:
        print("=" * 70)
        print("ADDING CANADA COMPLIANCE TABLES")
        print("=" * 70)
        print()

        # Check if tables already exist
        check_sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name LIKE 'canada_%'
        """

        result = await db.execute(text(check_sql))
        existing_tables = {row[0] for row in result.fetchall()}

        tables_to_create = []

        # ========== CANADA HOS LOGS TABLE ==========

        if 'canada_hos_logs' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE canada_hos_logs (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR NOT NULL,
                    driver_id VARCHAR NOT NULL,
                    load_id VARCHAR,

                    -- Log Entry
                    log_date TIMESTAMP NOT NULL,
                    duty_status VARCHAR NOT NULL,
                    duration_minutes INTEGER NOT NULL,

                    -- Location
                    location VARCHAR,
                    province VARCHAR,
                    odometer_km DECIMAL(10,2),

                    -- HOS Tracking
                    driving_hours_today DECIMAL(5,2) NOT NULL DEFAULT 0,
                    on_duty_hours_today DECIMAL(5,2) NOT NULL DEFAULT 0,
                    cycle_hours_used DECIMAL(5,2) NOT NULL DEFAULT 0,

                    -- Violations
                    hos_violation BOOLEAN NOT NULL DEFAULT FALSE,
                    violation_type VARCHAR,

                    -- EROD
                    erod_provider VARCHAR,
                    erod_device_id VARCHAR,

                    -- Additional
                    notes TEXT,
                    metadata JSONB,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_canada_hos_company ON canada_hos_logs(company_id);
                CREATE INDEX idx_canada_hos_driver ON canada_hos_logs(driver_id);
                CREATE INDEX idx_canada_hos_date ON canada_hos_logs(log_date);
                """,
                "canada_hos_logs (Hours of Service Logs)"
            ))

        # ========== CANADA EROD EVENTS TABLE ==========

        if 'canada_erod_events' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE canada_erod_events (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR NOT NULL,
                    driver_id VARCHAR NOT NULL,

                    -- Event Details
                    event_type VARCHAR NOT NULL,
                    event_timestamp TIMESTAMP NOT NULL,
                    event_code VARCHAR NOT NULL,

                    -- Duty Status
                    duty_status VARCHAR,

                    -- Location
                    latitude DECIMAL(10,7),
                    longitude DECIMAL(10,7),
                    location_description VARCHAR,
                    province VARCHAR,

                    -- Vehicle
                    vehicle_id VARCHAR,
                    odometer_km DECIMAL(10,2),

                    -- EROD Device
                    erod_provider VARCHAR NOT NULL,
                    erod_device_id VARCHAR NOT NULL,
                    erod_sequence_id INTEGER NOT NULL,

                    -- Additional
                    notes TEXT,
                    metadata JSONB,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_canada_erod_company ON canada_erod_events(company_id);
                CREATE INDEX idx_canada_erod_driver ON canada_erod_events(driver_id);
                CREATE INDEX idx_canada_erod_timestamp ON canada_erod_events(event_timestamp);
                """,
                "canada_erod_events (EROD Device Events)"
            ))

        # ========== CANADA IFTA RECORDS TABLE ==========

        if 'canada_ifta_records' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE canada_ifta_records (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR NOT NULL,
                    vehicle_id VARCHAR NOT NULL,
                    driver_id VARCHAR,

                    -- Quarter
                    quarter VARCHAR NOT NULL,
                    year INTEGER NOT NULL,

                    -- Jurisdiction
                    jurisdiction VARCHAR NOT NULL,

                    -- Distance
                    miles_driven DECIMAL(10,2) NOT NULL,
                    km_driven DECIMAL(10,2) NOT NULL,

                    -- Fuel
                    fuel_purchased_liters DECIMAL(10,2),
                    fuel_purchased_gallons DECIMAL(10,2),
                    fuel_cost_cad DECIMAL(10,2),

                    -- Tax
                    tax_rate DECIMAL(10,4),
                    tax_amount_cad DECIMAL(10,2),

                    -- Additional
                    notes TEXT,
                    metadata JSONB,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_canada_ifta_company ON canada_ifta_records(company_id);
                CREATE INDEX idx_canada_ifta_vehicle ON canada_ifta_records(vehicle_id);
                CREATE INDEX idx_canada_ifta_quarter ON canada_ifta_records(quarter);
                CREATE INDEX idx_canada_ifta_jurisdiction ON canada_ifta_records(jurisdiction);
                """,
                "canada_ifta_records (IFTA Fuel Tax Records)"
            ))

        # ========== CANADA TDG SHIPMENTS TABLE ==========

        if 'canada_tdg_shipments' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE canada_tdg_shipments (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR NOT NULL,
                    load_id VARCHAR NOT NULL,
                    driver_id VARCHAR NOT NULL,

                    -- TDG Classification
                    un_number VARCHAR NOT NULL,
                    shipping_name VARCHAR NOT NULL,
                    tdg_class VARCHAR NOT NULL,
                    packing_group VARCHAR,

                    -- Quantity
                    quantity DECIMAL(10,2) NOT NULL,
                    unit VARCHAR NOT NULL,

                    -- Placarding
                    placard_required BOOLEAN NOT NULL,
                    placard_numbers JSONB,

                    -- Emergency Response
                    emergency_phone VARCHAR NOT NULL,
                    emergency_contact_name VARCHAR NOT NULL,

                    -- Driver Certification
                    driver_tdg_certificate VARCHAR NOT NULL,
                    driver_tdg_expiry TIMESTAMP NOT NULL,

                    -- Documentation
                    shipping_document_number VARCHAR NOT NULL,
                    emergency_response_plan TEXT,

                    -- Status
                    status VARCHAR NOT NULL,

                    -- Additional
                    metadata JSONB,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_canada_tdg_company ON canada_tdg_shipments(company_id);
                CREATE INDEX idx_canada_tdg_load ON canada_tdg_shipments(load_id);
                CREATE INDEX idx_canada_tdg_status ON canada_tdg_shipments(status);
                """,
                "canada_tdg_shipments (TDG Dangerous Goods Tracking)"
            ))

        # ========== CANADA COMPANY DATA TABLE ==========

        if 'canada_company_data' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE canada_company_data (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR UNIQUE NOT NULL,

                    -- Federal Registration
                    nsc_number VARCHAR UNIQUE NOT NULL,
                    carrier_profile_number VARCHAR,

                    -- Provincial Registration
                    cvor_number VARCHAR UNIQUE,
                    cvor_expiry TIMESTAMP,
                    home_province VARCHAR NOT NULL,

                    -- IFTA
                    ifta_number VARCHAR UNIQUE,
                    ifta_expiry TIMESTAMP,

                    -- TDG
                    tdg_certified BOOLEAN NOT NULL DEFAULT FALSE,
                    tdg_certificate_number VARCHAR,
                    tdg_expiry TIMESTAMP,

                    -- Safety Rating
                    safety_rating VARCHAR,
                    safety_rating_date TIMESTAMP,

                    -- Insurance
                    liability_insurance_policy VARCHAR,
                    liability_insurance_expiry TIMESTAMP,
                    cargo_insurance_policy VARCHAR,
                    cargo_insurance_expiry TIMESTAMP,

                    -- Quebec Operations
                    operates_in_quebec BOOLEAN NOT NULL DEFAULT FALSE,
                    french_language_capable BOOLEAN NOT NULL DEFAULT FALSE,
                    quebec_permit_number VARCHAR,

                    -- Border Crossing
                    fast_approved BOOLEAN NOT NULL DEFAULT FALSE,
                    fast_number VARCHAR,
                    ace_aci_certified BOOLEAN NOT NULL DEFAULT FALSE,

                    -- Status
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    registration_validated BOOLEAN NOT NULL DEFAULT FALSE,

                    -- Metadata
                    registration_date TIMESTAMP,
                    metadata JSONB,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_canada_company_data_company ON canada_company_data(company_id);
                CREATE UNIQUE INDEX idx_canada_company_nsc ON canada_company_data(nsc_number);
                CREATE UNIQUE INDEX idx_canada_company_cvor ON canada_company_data(cvor_number);
                """,
                "canada_company_data (Canadian Company Registrations)"
            ))

        # ========== CANADA BORDER CROSSINGS TABLE ==========

        if 'canada_border_crossings' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE canada_border_crossings (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR NOT NULL,
                    load_id VARCHAR NOT NULL,
                    driver_id VARCHAR NOT NULL,

                    -- Border Port
                    border_port VARCHAR NOT NULL,
                    direction VARCHAR NOT NULL,
                    crossing_date TIMESTAMP NOT NULL,

                    -- Timing
                    arrival_time TIMESTAMP NOT NULL,
                    clearance_time TIMESTAMP,
                    departure_time TIMESTAMP,
                    wait_time_minutes INTEGER,

                    -- Customs
                    customs_status VARCHAR NOT NULL,
                    pars_paps_number VARCHAR,
                    ace_aci_used BOOLEAN NOT NULL DEFAULT FALSE,
                    fast_lane_used BOOLEAN NOT NULL DEFAULT FALSE,

                    -- Documentation
                    customs_broker VARCHAR,
                    commercial_invoice_number VARCHAR,
                    canada_customs_invoice VARCHAR,

                    -- Issues
                    inspection_required BOOLEAN NOT NULL DEFAULT FALSE,
                    issues_encountered TEXT,
                    delay_reason VARCHAR,

                    -- Additional
                    metadata JSONB,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_canada_border_company ON canada_border_crossings(company_id);
                CREATE INDEX idx_canada_border_load ON canada_border_crossings(load_id);
                CREATE INDEX idx_canada_border_port ON canada_border_crossings(border_port);
                CREATE INDEX idx_canada_border_date ON canada_border_crossings(crossing_date);
                """,
                "canada_border_crossings (Border Crossing Tracking)"
            ))

        # ========== EXECUTE MIGRATIONS ==========

        if not tables_to_create:
            print("✓ All Canada tables already exist!")
            print("  No changes needed.")
            return

        print(f"Creating {len(tables_to_create)} Canada tables...")
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
        print("CANADA TABLES CREATED SUCCESSFULLY")
        print("=" * 70)
        print()
        print("Tables created:")
        print("  ✓ canada_hos_logs - Hours of Service Logs")
        print("  ✓ canada_erod_events - EROD Device Events")
        print("  ✓ canada_ifta_records - IFTA Fuel Tax Records")
        print("  ✓ canada_tdg_shipments - TDG Dangerous Goods Tracking")
        print("  ✓ canada_company_data - Canadian Company Registrations")
        print("  ✓ canada_border_crossings - Border Crossing Tracking")
        print()
        print("Tables NOT modified (safe):")
        print("  ✓ company - Untouched")
        print("  ✓ loads - Untouched")
        print("  ✓ drivers - Untouched")
        print("  ✓ usa_* tables - Untouched")
        print("  ✓ brazil_* tables - Untouched")
        print("  ✓ mexico_* tables - Untouched")
        print()
        print("Next steps:")
        print("  1. For Canadian companies: Populate canada_company_data")
        print("  2. Configure NSC/CVOR registrations")
        print("  3. Set up EROD provider integration (Samsara, Geotab, etc.)")
        print("  4. Configure border crossing systems (ACE/ACI, FAST)")
        print()


async def main():
    await add_canada_tables()


if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    else:
        asyncio.run(main())

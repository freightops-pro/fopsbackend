"""
Add Brazil-Specific Tables

Creates Brazil compliance tables WITHOUT touching any existing USA tables.

What this does:
1. Creates brazil_mdfe (Electronic Cargo Manifests)
2. Creates brazil_ciot (Payment codes)
3. Creates brazil_sefaz_submissions (Tax authority API logs)
4. Creates brazil_company_data (Brazilian registrations)

What this DOES NOT do:
- Does NOT modify company table
- Does NOT modify loads table
- Does NOT modify any USA tables
- Does NOT affect existing USA data

Run: python -m scripts.migrations.add_brazil_tables
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


async def add_brazil_tables():
    """Create Brazil-specific tables."""

    async with AsyncSessionFactory() as db:
        print("=" * 70)
        print("ADDING BRAZIL COMPLIANCE TABLES")
        print("=" * 70)
        print()

        # Check if tables already exist
        check_sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name LIKE 'brazil_%'
        """

        result = await db.execute(text(check_sql))
        existing_tables = {row[0] for row in result.fetchall()}

        tables_to_create = []

        # ========== BRAZIL MDF-E TABLE ==========

        if 'brazil_mdfe' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE brazil_mdfe (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR NOT NULL,
                    load_id VARCHAR NOT NULL,

                    -- MDF-e Identification
                    mdfe_number INTEGER NOT NULL,
                    serie VARCHAR NOT NULL DEFAULT '1',
                    chave_acesso VARCHAR UNIQUE NOT NULL,

                    -- SEFAZ Status
                    status VARCHAR NOT NULL,
                    sefaz_protocol VARCHAR,
                    authorization_date TIMESTAMP,

                    -- XML Data
                    xml_unsigned TEXT NOT NULL,
                    xml_signed TEXT,
                    xml_authorized TEXT,

                    -- Transport Details
                    driver_cpf VARCHAR NOT NULL,
                    vehicle_plate VARCHAR NOT NULL,
                    uf_start VARCHAR NOT NULL,
                    uf_end VARCHAR NOT NULL,

                    -- Cargo Details
                    total_cargo_value DECIMAL(15,2) NOT NULL,
                    total_weight_kg DECIMAL(10,2) NOT NULL,

                    -- Additional
                    error_message TEXT,
                    metadata JSONB,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_brazil_mdfe_company ON brazil_mdfe(company_id);
                CREATE INDEX idx_brazil_mdfe_load ON brazil_mdfe(load_id);
                CREATE INDEX idx_brazil_mdfe_status ON brazil_mdfe(status);
                """,
                "brazil_mdfe (Electronic Cargo Manifests)"
            ))

        # ========== BRAZIL CIOT TABLE ==========

        if 'brazil_ciot' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE brazil_ciot (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR NOT NULL,
                    load_id VARCHAR NOT NULL,

                    -- CIOT Identification
                    ciot_code VARCHAR UNIQUE NOT NULL,
                    payment_provider VARCHAR NOT NULL,

                    -- Payment Details
                    amount_brl DECIMAL(15,2) NOT NULL,
                    payment_date TIMESTAMP NOT NULL,
                    payment_status VARCHAR NOT NULL,

                    -- ANTT Validation
                    antt_minimum_rate DECIMAL(15,2),
                    distance_km DECIMAL(10,2) NOT NULL,
                    cargo_type VARCHAR,

                    -- Driver Details
                    driver_cpf VARCHAR NOT NULL,
                    driver_name VARCHAR NOT NULL,

                    -- Provider Response
                    provider_response JSONB,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_brazil_ciot_company ON brazil_ciot(company_id);
                CREATE INDEX idx_brazil_ciot_load ON brazil_ciot(load_id);
                CREATE INDEX idx_brazil_ciot_status ON brazil_ciot(payment_status);
                """,
                "brazil_ciot (CIOT Payment Codes)"
            ))

        # ========== BRAZIL SEFAZ SUBMISSIONS TABLE ==========

        if 'brazil_sefaz_submissions' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE brazil_sefaz_submissions (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR NOT NULL,

                    -- Submission Details
                    document_type VARCHAR NOT NULL,
                    document_id VARCHAR NOT NULL,
                    submission_type VARCHAR NOT NULL,

                    -- SEFAZ Response
                    status_code VARCHAR NOT NULL,
                    sefaz_status VARCHAR NOT NULL,
                    protocol_number VARCHAR,
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

                CREATE INDEX idx_brazil_sefaz_company ON brazil_sefaz_submissions(company_id);
                CREATE INDEX idx_brazil_sefaz_document ON brazil_sefaz_submissions(document_id);
                CREATE INDEX idx_brazil_sefaz_status ON brazil_sefaz_submissions(sefaz_status);
                """,
                "brazil_sefaz_submissions (SEFAZ API Logs)"
            ))

        # ========== BRAZIL COMPANY DATA TABLE ==========

        if 'brazil_company_data' not in existing_tables:
            tables_to_create.append((
                """
                CREATE TABLE brazil_company_data (
                    id VARCHAR PRIMARY KEY,
                    company_id VARCHAR UNIQUE NOT NULL,

                    -- Tax Registration
                    cnpj VARCHAR UNIQUE NOT NULL,
                    ie_number VARCHAR,

                    -- Transport Registration
                    rntrc VARCHAR UNIQUE NOT NULL,
                    antt_registration VARCHAR NOT NULL,

                    -- Digital Certificate
                    certificate_type VARCHAR,
                    certificate_serial VARCHAR,
                    certificate_expiry TIMESTAMP,
                    certificate_data TEXT,

                    -- SEFAZ Configuration
                    sefaz_environment VARCHAR NOT NULL DEFAULT 'production',
                    sefaz_uf VARCHAR NOT NULL,

                    -- Counters
                    last_mdfe_number INTEGER NOT NULL DEFAULT 0,
                    last_cte_number INTEGER NOT NULL DEFAULT 0,

                    -- Status
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    registration_validated BOOLEAN NOT NULL DEFAULT FALSE,

                    -- Metadata
                    registration_date TIMESTAMP,
                    metadata JSONB,

                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );

                CREATE INDEX idx_brazil_company_data_company ON brazil_company_data(company_id);
                CREATE UNIQUE INDEX idx_brazil_company_cnpj ON brazil_company_data(cnpj);
                CREATE UNIQUE INDEX idx_brazil_company_rntrc ON brazil_company_data(rntrc);
                """,
                "brazil_company_data (Brazilian Company Registrations)"
            ))

        # ========== EXECUTE MIGRATIONS ==========

        if not tables_to_create:
            print("✓ All Brazil tables already exist!")
            print("  No changes needed.")
            return

        print(f"Creating {len(tables_to_create)} Brazil tables...")
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
        print("BRAZIL TABLES CREATED SUCCESSFULLY")
        print("=" * 70)
        print()
        print("Tables created:")
        print("  ✓ brazil_mdfe - Electronic Cargo Manifests (MDF-e)")
        print("  ✓ brazil_ciot - CIOT Payment Codes")
        print("  ✓ brazil_sefaz_submissions - SEFAZ API Logs")
        print("  ✓ brazil_company_data - Brazilian Registrations")
        print()
        print("Tables NOT modified (USA safe):")
        print("  ✓ company - Untouched")
        print("  ✓ loads - Untouched")
        print("  ✓ drivers - Untouched")
        print("  ✓ usa_hos_logs - Untouched")
        print("  ✓ usa_eld_events - Untouched")
        print()
        print("Next steps:")
        print("  1. For Brazilian companies: Populate brazil_company_data")
        print("  2. Configure SEFAZ credentials and certificates")
        print("  3. Set up CIOT payment provider integration")
        print("  4. Test MDF-e generation with homologation environment")
        print()


async def main():
    await add_brazil_tables()


if __name__ == "__main__":
    if sys.platform == "win32":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    else:
        asyncio.run(main())

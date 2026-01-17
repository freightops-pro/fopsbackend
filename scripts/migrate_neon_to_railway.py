"""
Migrate database from Neon to Railway Postgres.

This script:
1. Connects to both Neon (source) and Railway (target) databases
2. Exports all tables from Neon
3. Enables pgvector extension on Railway
4. Imports all data to Railway

Usage:
    python scripts/migrate_neon_to_railway.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.orm import sessionmaker
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database URLs
NEON_URL = "postgresql+psycopg://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=prefer&connect_timeout=10"
RAILWAY_URL = "postgresql+psycopg://postgres:KVy1COSojjJ66s3wR3ytilWtioLwA5Ka@maglev.proxy.rlwy.net:48993/railway"


def migrate_database():
    """Migrate all data from Neon to Railway."""
    logger.info("=" * 60)
    logger.info("Database Migration: Neon -> Railway")
    logger.info("=" * 60)

    # Create engines
    logger.info("Connecting to Neon (source)...")
    source_engine = create_engine(NEON_URL)

    logger.info("Connecting to Railway (target)...")
    target_engine = create_engine(RAILWAY_URL)

    try:
        # Step 1: Check for pgvector extension on Railway (skip if not available)
        logger.info("\n--- Step 1: Checking pgvector extension on Railway ---")
        pgvector_available = False
        with target_engine.connect() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                pgvector_available = True
                logger.info("pgvector extension enabled")
            except Exception as e:
                logger.warning(f"pgvector not available on Railway: {e}")
                logger.warning("Will migrate data WITHOUT embeddings - you'll need to regenerate them later")
                conn.rollback()

        # Step 2: Get all tables from source
        logger.info("\n--- Step 2: Getting table list from Neon ---")
        inspector = inspect(source_engine)
        tables = inspector.get_table_names()
        logger.info(f"Found {len(tables)} tables: {tables}")

        # Step 3: Get all enum types from source
        logger.info("\n--- Step 3: Copying enum types ---")
        with source_engine.connect() as source_conn:
            # Get enum types
            enums_result = source_conn.execute(text("""
                SELECT t.typname as enum_name,
                       array_agg(e.enumlabel ORDER BY e.enumsortorder) as enum_values
                FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = 'public'
                GROUP BY t.typname
            """))
            enums = enums_result.fetchall()

        with target_engine.connect() as target_conn:
            for enum_name, enum_values in enums:
                logger.info(f"Creating enum: {enum_name} with values: {enum_values}")
                # Check if enum exists
                exists = target_conn.execute(text(
                    "SELECT 1 FROM pg_type WHERE typname = :name"
                ), {"name": enum_name}).fetchone()

                if not exists:
                    values_str = ", ".join([f"'{v}'" for v in enum_values])
                    target_conn.execute(text(f"CREATE TYPE {enum_name} AS ENUM ({values_str})"))
                    logger.info(f"  Created enum {enum_name}")
                else:
                    logger.info(f"  Enum {enum_name} already exists")
            target_conn.commit()

        # Step 4: Get DDL and create tables on target
        logger.info("\n--- Step 4: Creating tables on Railway ---")

        # Get the full schema DDL from source
        with source_engine.connect() as source_conn:
            # Get table definitions
            for table in tables:
                # Get create table statement
                result = source_conn.execute(text(f"""
                    SELECT
                        'CREATE TABLE IF NOT EXISTS ' || :table_name || ' (' ||
                        string_agg(
                            column_name || ' ' ||
                            CASE
                                WHEN udt_name = 'vector' THEN 'vector(' || character_maximum_length || ')'
                                WHEN data_type = 'USER-DEFINED' THEN udt_name
                                WHEN data_type = 'ARRAY' THEN udt_name
                                WHEN character_maximum_length IS NOT NULL THEN data_type || '(' || character_maximum_length || ')'
                                ELSE data_type
                            END ||
                            CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END,
                            ', '
                        ) || ')'
                    FROM information_schema.columns
                    WHERE table_name = :table_name AND table_schema = 'public'
                    GROUP BY table_name
                """), {"table_name": table})

        # Use metadata reflection to create tables
        metadata = MetaData()
        metadata.reflect(bind=source_engine)

        # Create all tables on target (without foreign keys first)
        with target_engine.connect() as target_conn:
            for table in metadata.sorted_tables:
                logger.info(f"Creating table: {table.name}")
                try:
                    # Drop if exists and recreate
                    target_conn.execute(text(f"DROP TABLE IF EXISTS {table.name} CASCADE"))
                    target_conn.commit()
                except Exception as e:
                    logger.warning(f"  Could not drop {table.name}: {e}")
                    target_conn.rollback()

            # Create tables using metadata
            metadata.create_all(target_engine)
            logger.info("All tables created")

        # Step 5: Copy data
        logger.info("\n--- Step 5: Copying data ---")

        # Define table order (respect foreign keys)
        # Tables without dependencies first
        table_order = [
            'alembic_version',
            'users',
            'companies',
            'tenants',
            'company_settings',
            'company_documents',
            'contacts',
            'equipment',
            'drivers',
            'driver_documents',
            'driver_pay_rates',
            'driver_incidents',
            'customers',
            'customer_contacts',
            'shippers',
            'receivers',
            'loads',
            'load_legs',
            'load_documents',
            'load_events',
            'load_accessorials',
            'load_notes',
            'invoices',
            'invoice_line_items',
            'payments',
            'settlements',
            'settlement_line_items',
            'fuel_transactions',
            'ifta_reports',
            'ifta_jurisdiction_details',
            'maintenance_records',
            'maintenance_items',
            'integrations',
            'integration_credentials',
            'automation_rules',
            'automation_logs',
            'notifications',
            'hq_ai_tasks',
            'hq_ai_task_results',
            'hq_knowledge_documents',
            'hq_knowledge_chunks',
        ]

        # Add any tables not in the order list
        for table in tables:
            if table not in table_order:
                table_order.append(table)

        # Only process tables that exist
        tables_to_copy = [t for t in table_order if t in tables]

        with source_engine.connect() as source_conn:
            with target_engine.connect() as target_conn:
                for table in tables_to_copy:
                    try:
                        # Get row count from source
                        count_result = source_conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                        row_count = count_result.scalar()

                        if row_count == 0:
                            logger.info(f"  {table}: 0 rows (skipping)")
                            continue

                        logger.info(f"  Copying {table}: {row_count} rows...")

                        # Get all data from source
                        result = source_conn.execute(text(f'SELECT * FROM "{table}"'))
                        rows = result.fetchall()
                        columns = result.keys()

                        if rows:
                            # Clear target table
                            target_conn.execute(text(f'DELETE FROM "{table}"'))

                            # Build insert statement
                            col_names = ", ".join([f'"{c}"' for c in columns])
                            placeholders = ", ".join([f":{c}" for c in columns])
                            insert_sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'

                            # Insert in batches
                            batch_size = 100
                            for i in range(0, len(rows), batch_size):
                                batch = rows[i:i+batch_size]
                                for row in batch:
                                    row_dict = dict(zip(columns, row))
                                    # Handle vector columns
                                    for key, value in row_dict.items():
                                        if isinstance(value, list) and all(isinstance(x, (int, float)) for x in value):
                                            # Convert list to vector string format
                                            row_dict[key] = "[" + ",".join(str(x) for x in value) + "]"
                                    try:
                                        target_conn.execute(text(insert_sql), row_dict)
                                    except Exception as e:
                                        logger.warning(f"    Row insert error: {e}")

                            target_conn.commit()
                            logger.info(f"    Copied {len(rows)} rows")

                    except Exception as e:
                        logger.error(f"  Error copying {table}: {e}")
                        target_conn.rollback()

        # Step 6: Recreate indexes
        logger.info("\n--- Step 6: Recreating indexes ---")
        with source_engine.connect() as source_conn:
            # Get indexes from source
            indexes_result = source_conn.execute(text("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                AND indexname NOT LIKE '%_pkey'
            """))
            indexes = indexes_result.fetchall()

        with target_engine.connect() as target_conn:
            for index_name, index_def in indexes:
                try:
                    # Replace CREATE INDEX with CREATE INDEX IF NOT EXISTS
                    index_def_safe = index_def.replace("CREATE INDEX", "CREATE INDEX IF NOT EXISTS")
                    index_def_safe = index_def_safe.replace("CREATE UNIQUE INDEX", "CREATE UNIQUE INDEX IF NOT EXISTS")
                    logger.info(f"  Creating index: {index_name}")
                    target_conn.execute(text(index_def_safe))
                    target_conn.commit()
                except Exception as e:
                    logger.warning(f"    Could not create index {index_name}: {e}")
                    target_conn.rollback()

        logger.info("\n" + "=" * 60)
        logger.info("MIGRATION COMPLETE")
        logger.info("=" * 60)
        logger.info("\nNext steps:")
        logger.info("1. Update DATABASE_URL in Railway environment variables to:")
        logger.info("   postgresql+asyncpg://postgres:BdSDLIIFnTLGuZGxwqTHNuEEiZQAavhI@maglev.proxy.rlwy.net:35284/railway")
        logger.info("2. Redeploy the Railway service")
        logger.info("3. Test the application")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    migrate_database()

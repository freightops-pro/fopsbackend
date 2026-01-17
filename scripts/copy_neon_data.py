"""
Copy data from Neon to Railway (schema already exists on Railway).

This script only copies data, not schema.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, inspect
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database URLs
NEON_URL = "postgresql+psycopg://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"
RAILWAY_URL = "postgresql+psycopg://postgres:KVy1COSojjJ66s3wR3ytilWtioLwA5Ka@maglev.proxy.rlwy.net:48993/railway"


def copy_data():
    """Copy all data from Neon to Railway."""
    logger.info("=" * 60)
    logger.info("Copying Data: Neon -> Railway")
    logger.info("=" * 60)

    source_engine = create_engine(NEON_URL)
    target_engine = create_engine(RAILWAY_URL)

    try:
        # Get tables from source
        inspector = inspect(source_engine)
        source_tables = set(inspector.get_table_names())

        # Get tables from target
        target_inspector = inspect(target_engine)
        target_tables = set(target_inspector.get_table_names())

        # Only copy tables that exist in both
        tables_to_copy = source_tables & target_tables
        logger.info(f"Found {len(tables_to_copy)} tables to copy")

        # Skip alembic_version as we already stamped it
        tables_to_copy.discard('alembic_version')

        copied = 0
        skipped = 0
        errors = 0

        with source_engine.connect() as source_conn:
            with target_engine.connect() as target_conn:
                for table in sorted(tables_to_copy):
                    try:
                        # Get row count from source
                        result = source_conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                        source_count = result.scalar()

                        if source_count == 0:
                            skipped += 1
                            continue

                        # Check if target already has data
                        result = target_conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                        target_count = result.scalar()

                        if target_count > 0:
                            logger.info(f"  {table}: already has {target_count} rows, skipping")
                            skipped += 1
                            continue

                        logger.info(f"  Copying {table}: {source_count} rows...")

                        # Get column names
                        cols_result = source_conn.execute(text(f"""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_name = '{table}' AND table_schema = 'public'
                            ORDER BY ordinal_position
                        """))
                        columns = [row[0] for row in cols_result]

                        # Get all data
                        result = source_conn.execute(text(f'SELECT * FROM "{table}"'))
                        rows = result.fetchall()

                        if rows:
                            # Build insert statement
                            col_names = ", ".join([f'"{c}"' for c in columns])
                            placeholders = ", ".join([f":{c}" for c in columns])
                            insert_sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'

                            # Insert rows
                            for row in rows:
                                row_dict = {}
                                for i, col in enumerate(columns):
                                    val = row[i]
                                    # Handle vector columns - convert list to string
                                    if isinstance(val, list):
                                        val = "[" + ",".join(str(x) for x in val) + "]"
                                    row_dict[col] = val

                                try:
                                    target_conn.execute(text(insert_sql), row_dict)
                                except Exception as e:
                                    if "duplicate key" not in str(e).lower():
                                        logger.warning(f"    Row error in {table}: {str(e)[:100]}")

                            target_conn.commit()
                            copied += 1
                            logger.info(f"    Copied {len(rows)} rows")

                    except Exception as e:
                        errors += 1
                        logger.error(f"  Error copying {table}: {str(e)[:200]}")
                        target_conn.rollback()

        logger.info("\n" + "=" * 60)
        logger.info("DATA COPY COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Copied: {copied} tables")
        logger.info(f"Skipped: {skipped} tables (empty or already has data)")
        logger.info(f"Errors: {errors} tables")

    except Exception as e:
        logger.error(f"Copy failed: {e}")
        raise
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    copy_data()

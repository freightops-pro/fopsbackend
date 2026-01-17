"""
Copy data from Neon to Railway with FK constraints disabled.
"""

import sys
import os
import json
from pathlib import Path

script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, inspect
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NEON_URL = "postgresql+psycopg://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"
RAILWAY_URL = "postgresql+psycopg://postgres:KVy1COSojjJ66s3wR3ytilWtioLwA5Ka@maglev.proxy.rlwy.net:48993/railway"


def copy_data():
    """Copy all data from Neon to Railway with FK disabled."""
    logger.info("=" * 60)
    logger.info("Copying Data: Neon -> Railway (FK disabled)")
    logger.info("=" * 60)

    source_engine = create_engine(NEON_URL)
    target_engine = create_engine(RAILWAY_URL)

    try:
        # Get common tables
        source_inspector = inspect(source_engine)
        target_inspector = inspect(target_engine)
        source_tables = set(source_inspector.get_table_names())
        target_tables = set(target_inspector.get_table_names())
        tables_to_copy = sorted(source_tables & target_tables)
        tables_to_copy = [t for t in tables_to_copy if t != 'alembic_version']

        logger.info(f"Found {len(tables_to_copy)} tables to copy")

        with target_engine.connect() as target_conn:
            # Disable FK constraints
            logger.info("Disabling FK constraints...")
            target_conn.execute(text("SET session_replication_role = 'replica'"))

            with source_engine.connect() as source_conn:
                copied = 0
                skipped = 0

                for table in tables_to_copy:
                    try:
                        # Get counts
                        source_count = source_conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                        target_count = target_conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()

                        if source_count == 0:
                            skipped += 1
                            continue

                        if target_count > 0:
                            logger.info(f"  {table}: clearing {target_count} existing rows")
                            target_conn.execute(text(f'DELETE FROM "{table}"'))

                        logger.info(f"  Copying {table}: {source_count} rows...")

                        # Get column info
                        cols_result = source_conn.execute(text(f"""
                            SELECT column_name, data_type, udt_name
                            FROM information_schema.columns
                            WHERE table_name = '{table}' AND table_schema = 'public'
                            ORDER BY ordinal_position
                        """))
                        columns_info = [(row[0], row[1], row[2]) for row in cols_result]
                        columns = [c[0] for c in columns_info]

                        # Get data
                        result = source_conn.execute(text(f'SELECT * FROM "{table}"'))
                        rows = result.fetchall()

                        if rows:
                            # Get target table columns to handle schema differences
                            target_cols_result = target_conn.execute(text(f"""
                                SELECT column_name
                                FROM information_schema.columns
                                WHERE table_name = '{table}' AND table_schema = 'public'
                            """))
                            target_columns = set(row[0] for row in target_cols_result)

                            # Only use columns that exist in both source and target
                            common_columns = [c for c in columns if c in target_columns]

                            if not common_columns:
                                logger.warning(f"    No common columns found, skipping")
                                skipped += 1
                                continue

                            col_names = ", ".join([f'"{c}"' for c in common_columns])
                            placeholders = ", ".join([f":{c}" for c in common_columns])
                            insert_sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'

                            batch_size = 100
                            for i in range(0, len(rows), batch_size):
                                batch = rows[i:i+batch_size]
                                for row in batch:
                                    row_dict = {}
                                    for j, col in enumerate(columns):
                                        if col not in target_columns:
                                            continue  # Skip columns not in target
                                        val = row[j]
                                        # Convert dict to JSON string
                                        if isinstance(val, dict):
                                            val = json.dumps(val)
                                        # Convert list - check if it's a vector (numbers) or JSON array
                                        elif isinstance(val, list):
                                            if val and all(isinstance(x, (int, float)) for x in val):
                                                # Vector column - use bracket format
                                                val = "[" + ",".join(str(x) for x in val) + "]"
                                            else:
                                                # JSON array
                                                val = json.dumps(val)
                                        row_dict[col] = val
                                    target_conn.execute(text(insert_sql), row_dict)

                            target_conn.commit()
                            copied += 1
                            logger.info(f"    Done ({len(rows)} rows)")

                    except Exception as e:
                        logger.error(f"  Error copying {table}: {str(e)[:150]}")
                        target_conn.rollback()
                        skipped += 1

            # Re-enable FK constraints
            logger.info("Re-enabling FK constraints...")
            target_conn.execute(text("SET session_replication_role = 'origin'"))
            target_conn.commit()

        logger.info("\n" + "=" * 60)
        logger.info("DATA COPY COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Copied: {copied} tables")
        logger.info(f"Skipped: {skipped} tables")

    except Exception as e:
        logger.error(f"Copy failed: {e}")
        raise
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    copy_data()

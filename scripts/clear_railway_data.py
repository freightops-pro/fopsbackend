"""
Clear all data from Railway database (keep schema).
"""

import sys
from pathlib import Path

script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, inspect
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RAILWAY_URL = "postgresql+psycopg://postgres:KVy1COSojjJ66s3wR3ytilWtioLwA5Ka@maglev.proxy.rlwy.net:48993/railway"


def clear_data():
    """Clear all data from Railway (FK disabled)."""
    logger.info("=" * 60)
    logger.info("Clearing Railway Data (keeping schema)")
    logger.info("=" * 60)

    engine = create_engine(RAILWAY_URL)

    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        tables = [t for t in tables if t != 'alembic_version']

        logger.info(f"Found {len(tables)} tables to clear")

        with engine.connect() as conn:
            # Disable FK constraints
            conn.execute(text("SET session_replication_role = 'replica'"))

            for table in sorted(tables):
                try:
                    result = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                    count = result.scalar()
                    if count > 0:
                        conn.execute(text(f'DELETE FROM "{table}"'))
                        logger.info(f"  Cleared {table}: {count} rows")
                except Exception as e:
                    logger.error(f"  Error clearing {table}: {e}")

            # Re-enable FK constraints
            conn.execute(text("SET session_replication_role = 'origin'"))
            conn.commit()

        logger.info("Data cleared successfully")

    except Exception as e:
        logger.error(f"Clear failed: {e}")
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    clear_data()

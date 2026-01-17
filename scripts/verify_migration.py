"""
Verify data migration from Neon to Railway.
"""

import sys
from pathlib import Path

script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NEON_URL = "postgresql+psycopg://neondb_owner:npg_5uN2QZBeqpKo@ep-purple-moon-ahj5tx9w-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require"
RAILWAY_URL = "postgresql+psycopg://postgres:KVy1COSojjJ66s3wR3ytilWtioLwA5Ka@maglev.proxy.rlwy.net:48993/railway"


def verify():
    """Compare row counts between Neon and Railway."""
    logger.info("=" * 60)
    logger.info("Migration Verification")
    logger.info("=" * 60)

    source_engine = create_engine(NEON_URL)
    target_engine = create_engine(RAILWAY_URL)

    key_tables = [
        'company', 'driver', 'freight_load', 'freight_load_stop',
        'user', 'accounting_invoice', 'accounting_customer',
        'fleet_equipment', 'fueltransaction', 'hq_lead', 'hq_deal',
        'hq_ai_actions', 'hq_employee', 'worker', 'role', 'permission'
    ]

    try:
        with source_engine.connect() as source_conn:
            with target_engine.connect() as target_conn:
                match = 0
                mismatch = 0

                for table in key_tables:
                    try:
                        source_count = source_conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                        target_count = target_conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()

                        status = "✓" if source_count == target_count else "✗"
                        if source_count == target_count:
                            match += 1
                        else:
                            mismatch += 1

                        logger.info(f"  {status} {table}: Neon={source_count}, Railway={target_count}")
                    except Exception as e:
                        logger.error(f"  Error checking {table}: {e}")
                        mismatch += 1

                logger.info("")
                logger.info(f"Match: {match}/{len(key_tables)}")
                if mismatch > 0:
                    logger.warning(f"Mismatch: {mismatch} tables")

    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    verify()

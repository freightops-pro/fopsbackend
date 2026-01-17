"""
Setup Railway database directly using SQLAlchemy models.

This bypasses Alembic migrations and creates all tables directly.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))
os.environ["PYTHONPATH"] = str(backend_dir)

from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Railway database URL
RAILWAY_URL = "postgresql+psycopg://postgres:KVy1COSojjJ66s3wR3ytilWtioLwA5Ka@maglev.proxy.rlwy.net:48993/railway"


def setup_database():
    """Set up the database using SQLAlchemy models."""
    logger.info("=" * 60)
    logger.info("Setting up Railway PostgreSQL Database")
    logger.info("=" * 60)

    engine = create_engine(RAILWAY_URL)

    try:
        with engine.connect() as conn:
            # Step 1: Reset schema
            logger.info("\n--- Step 1: Resetting schema ---")
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
            conn.commit()
            logger.info("Schema reset complete")

            # Step 2: Enable pgvector
            logger.info("\n--- Step 2: Enabling pgvector ---")
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            logger.info("pgvector enabled")

        # Step 3: Import all models to register them with Base
        logger.info("\n--- Step 3: Importing models ---")
        from app.models.base import Base
        import app.models  # This imports all models
        logger.info(f"Registered {len(Base.metadata.tables)} tables")

        # Step 3.5: Create all enum types first (before tables)
        logger.info("\n--- Step 3.5: Creating enum types ---")
        created_enums = set()
        with engine.connect() as conn:
            for table in Base.metadata.sorted_tables:
                for column in table.columns:
                    col_type = column.type
                    if hasattr(col_type, 'enums') and hasattr(col_type, 'name'):
                        enum_name = col_type.name
                        if enum_name and enum_name not in created_enums:
                            enum_values = col_type.enums
                            values_str = ", ".join([f"'{v}'" for v in enum_values])
                            sql = f"""
                                DO $$
                                BEGIN
                                    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{enum_name}') THEN
                                        CREATE TYPE {enum_name} AS ENUM ({values_str});
                                    END IF;
                                END $$;
                            """
                            try:
                                conn.execute(text(sql))
                                created_enums.add(enum_name)
                                logger.info(f"  Created enum: {enum_name}")
                            except Exception as e:
                                logger.warning(f"  Error creating {enum_name}: {e}")
            conn.commit()
        logger.info(f"Created {len(created_enums)} enum types")

        # Step 4: Create all tables
        logger.info("\n--- Step 4: Creating tables ---")
        Base.metadata.create_all(engine)
        logger.info("All tables created successfully")

        # Step 5: Stamp alembic version
        logger.info("\n--- Step 5: Stamping Alembic version ---")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(32) PRIMARY KEY
                )
            """))
            conn.execute(text("DELETE FROM alembic_version"))
            conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20260116_hq_learning')"))
            conn.commit()
        logger.info("Alembic stamped at head: 20260116_hq_learning")

        # Step 6: Verify
        logger.info("\n--- Step 6: Verification ---")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """))
            count = result.scalar()
            logger.info(f"Total tables created: {count}")

            # List some key tables
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
                LIMIT 20
            """))
            logger.info("Sample tables:")
            for row in result:
                logger.info(f"  - {row[0]}")

        logger.info("\n" + "=" * 60)
        logger.info("DATABASE SETUP COMPLETE!")
        logger.info("=" * 60)
        logger.info("\nNext steps:")
        logger.info("1. Update DATABASE_URL in Railway environment variables to:")
        logger.info("   postgresql+asyncpg://postgres:KVy1COSojjJ66s3wR3ytilWtioLwA5Ka@maglev.proxy.rlwy.net:48993/railway")
        logger.info("2. Redeploy the Railway service")

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    setup_database()

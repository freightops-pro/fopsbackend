import sqlite3
from sqlalchemy import text
from app.config.db import engine

def add_password_column():
    """Add passwordHash column to drivers table if it doesn't exist"""
    try:
        with engine.connect() as conn:
            dialect = engine.dialect.name
            
            if dialect == "sqlite":
                # SQLite approach
                conn.execute(text("PRAGMA table_info(drivers)"))
                cols = conn.execute(text("PRAGMA table_info(drivers)")).fetchall()
                has_password_hash = any(row[1] == "passwordHash" for row in cols)
                
                if not has_password_hash:
                    conn.execute(text("ALTER TABLE drivers ADD COLUMN passwordHash TEXT"))
                    conn.commit()
                    print("Successfully added passwordHash column to drivers table")
                else:
                    print("passwordHash column already exists in drivers table")
            else:
                # PostgreSQL approach
                conn.execute(text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='drivers' AND lower(column_name)='passwordhash'
                        ) THEN
                            ALTER TABLE drivers ADD COLUMN passwordHash VARCHAR;
                        END IF;
                    END$$;
                    """
                ))
                conn.commit()
                print("Successfully added passwordHash column to drivers table")
                
    except Exception as e:
        print(f"Error adding passwordHash column: {e}")

if __name__ == "__main__":
    add_password_column()

#!/usr/bin/env python3
from app.config.db import create_tables
from app.models.simple_load import SimpleLoad

def create_simple_loads_table():
    try:
        create_tables()
        print("✅ Tables created successfully!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")

if __name__ == "__main__":
    create_simple_loads_table()

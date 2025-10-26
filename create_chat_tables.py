#!/usr/bin/env python3
"""
Create chat tables migration script
This script creates the necessary tables for the chat functionality
"""

import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.config.settings import settings
from app.config.db import Base
from app.models.chat import Conversation, ConversationReadStatus, Message

def create_chat_tables():
    """Create chat tables"""
    print("Creating chat tables...")
    
    # Create database engine
    if settings.DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False}
        )
    else:
        engine = create_engine(settings.DATABASE_URL)
    
    # Create tables
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Chat tables created successfully!")
        
        # Verify tables were created
        with engine.connect() as conn:
            if settings.DATABASE_URL.startswith("sqlite"):
                # SQLite verification
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%conversation%' OR name LIKE '%message%'"))
                tables = result.fetchall()
                print(f"Created tables: {[table[0] for table in tables]}")
            else:
                # PostgreSQL verification
                result = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND (table_name LIKE '%conversation%' OR table_name LIKE '%message%')
                """))
                tables = result.fetchall()
                print(f"Created tables: {[table[0] for table in tables]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating chat tables: {str(e)}")
        return False

def verify_chat_tables():
    """Verify chat tables exist and have correct structure"""
    print("Verifying chat tables...")
    
    # Create database engine
    if settings.DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False}
        )
    else:
        engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            if settings.DATABASE_URL.startswith("sqlite"):
                # SQLite verification
                tables_to_check = ['conversations', 'conversation_read_status', 'messages']
                for table in tables_to_check:
                    result = conn.execute(text(f"PRAGMA table_info({table})"))
                    columns = result.fetchall()
                    if columns:
                        print(f"✅ Table '{table}' exists with {len(columns)} columns")
                    else:
                        print(f"❌ Table '{table}' not found")
            else:
                # PostgreSQL verification
                tables_to_check = ['conversations', 'conversation_read_status', 'messages']
                for table in tables_to_check:
                    result = conn.execute(text(f"""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = '{table}' 
                        ORDER BY ordinal_position
                    """))
                    columns = result.fetchall()
                    if columns:
                        print(f"✅ Table '{table}' exists with {len(columns)} columns")
                        print(f"   Columns: {[col[0] for col in columns]}")
                    else:
                        print(f"❌ Table '{table}' not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verifying chat tables: {str(e)}")
        return False

def main():
    """Main function"""
    print("=" * 50)
    print("FreightOps Chat Tables Migration")
    print("=" * 50)
    
    # Create tables
    success = create_chat_tables()
    
    if success:
        print("\n" + "=" * 50)
        print("Verification")
        print("=" * 50)
        verify_chat_tables()
        
        print("\n" + "=" * 50)
        print("Migration completed successfully!")
        print("Chat functionality is now available.")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("Migration failed!")
        print("Please check the error messages above.")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    main()

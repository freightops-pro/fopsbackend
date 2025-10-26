#!/usr/bin/env python3
"""
Script to create banking tables for Synctera integration.
Run this script to create the banking-related database tables.
"""

import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from sqlalchemy import create_engine, text
from app.config.db import Base, engine
from app.models.banking import (
    BankingCustomer, BankingAccount, BankingCard, 
    BankingTransaction, BankingTransfer
)

def create_banking_tables():
    """Create banking tables in the database"""
    try:
        print("Creating banking tables...")
        
        # Create all tables
        Base.metadata.create_all(bind=engine, tables=[
            BankingCustomer.__table__,
            BankingAccount.__table__,
            BankingCard.__table__,
            BankingTransaction.__table__,
            BankingTransfer.__table__
        ])
        
        print("✅ Banking tables created successfully!")
        
        # Verify tables exist
        with engine.connect() as conn:
            tables = [
                "banking_customers",
                "banking_accounts", 
                "banking_cards",
                "banking_transactions",
                "banking_transfers"
            ]
            
            for table in tables:
                result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"))
                if result.fetchone():
                    print(f"✅ Table '{table}' exists")
                else:
                    print(f"❌ Table '{table}' not found")
        
        print("\n🎉 Banking tables setup complete!")
        print("\nAvailable tables:")
        print("- banking_customers: Store customer information and KYB status")
        print("- banking_accounts: Store bank account details")
        print("- banking_cards: Store card information and limits")
        print("- banking_transactions: Store transaction history")
        print("- banking_transfers: Store transfer records")
        
    except Exception as e:
        print(f"❌ Error creating banking tables: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    create_banking_tables()


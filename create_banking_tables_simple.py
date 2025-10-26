#!/usr/bin/env python3
"""
Script to create banking tables for Synctera integration.
This creates tables without foreign keys to avoid dependency issues.
"""

import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from sqlalchemy import create_engine, text
from app.config.db import engine

def create_banking_tables():
    """Create banking tables using raw SQL"""
    try:
        print("Creating banking tables...")
        
        with engine.connect() as conn:
            # Create banking_customers table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS banking_customers (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    company_id VARCHAR NOT NULL,
                    synctera_person_id VARCHAR(255) UNIQUE,
                    synctera_business_id VARCHAR(255) UNIQUE,
                    legal_name VARCHAR(255) NOT NULL,
                    ein VARCHAR(20) NOT NULL,
                    business_address TEXT NOT NULL,
                    business_city VARCHAR(100) NOT NULL,
                    business_state VARCHAR(50) NOT NULL,
                    business_zip_code VARCHAR(20) NOT NULL,
                    naics_code VARCHAR(10) NOT NULL,
                    website VARCHAR(255),
                    control_person_name VARCHAR(255) NOT NULL,
                    kyb_status VARCHAR(50) DEFAULT 'pending',
                    kyb_submitted_at TIMESTAMP WITH TIME ZONE,
                    kyb_approved_at TIMESTAMP WITH TIME ZONE,
                    kyb_rejection_reason TEXT,
                    status VARCHAR(50) DEFAULT 'active',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            
            # Create banking_accounts table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS banking_accounts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    customer_id UUID NOT NULL,
                    synctera_account_id VARCHAR(255) UNIQUE,
                    account_type VARCHAR(50) NOT NULL,
                    account_number VARCHAR(255),
                    routing_number VARCHAR(255),
                    account_name VARCHAR(255) NOT NULL,
                    available_balance FLOAT DEFAULT 0.0,
                    current_balance FLOAT DEFAULT 0.0,
                    pending_balance FLOAT DEFAULT 0.0,
                    status VARCHAR(50) DEFAULT 'active',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            
            # Create banking_cards table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS banking_cards (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id UUID NOT NULL,
                    synctera_card_id VARCHAR(255) UNIQUE,
                    card_type VARCHAR(50) NOT NULL,
                    card_number VARCHAR(255),
                    last_four VARCHAR(4),
                    expiry_date VARCHAR(7),
                    cvv VARCHAR(255),
                    card_name VARCHAR(255) NOT NULL,
                    assigned_to VARCHAR(255),
                    daily_limit FLOAT,
                    monthly_limit FLOAT,
                    restrictions JSONB,
                    status VARCHAR(50) DEFAULT 'active',
                    is_enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            
            # Create banking_transactions table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS banking_transactions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    account_id UUID NOT NULL,
                    card_id UUID,
                    synctera_transaction_id VARCHAR(255) UNIQUE,
                    amount FLOAT NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    category VARCHAR(100),
                    description TEXT,
                    merchant_name VARCHAR(255),
                    merchant_category VARCHAR(100),
                    reference_id VARCHAR(255),
                    transaction_date TIMESTAMP WITH TIME ZONE NOT NULL,
                    posted_date TIMESTAMP WITH TIME ZONE,
                    status VARCHAR(50) DEFAULT 'pending',
                    transaction_metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            
            # Create banking_transfers table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS banking_transfers (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    from_account_id UUID NOT NULL,
                    to_account_id UUID,
                    synctera_transfer_id VARCHAR(255) UNIQUE,
                    amount FLOAT NOT NULL,
                    transfer_type VARCHAR(50) NOT NULL,
                    description TEXT,
                    recipient_name VARCHAR(255),
                    recipient_account VARCHAR(255),
                    recipient_routing VARCHAR(255),
                    status VARCHAR(50) DEFAULT 'pending',
                    scheduled_date TIMESTAMP WITH TIME ZONE,
                    completed_date TIMESTAMP WITH TIME ZONE,
                    transfer_metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            
            conn.commit()
        
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
                result = conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
                print(f"✅ Table '{table}' exists and is accessible")
        
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


"""
Script to create necessary tables in Neon database for FreightOps Pro
"""
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text

# Neon database URL
DATABASE_URL = "postgresql://neondb_owner:npg_JVQsDGh9lM6S@ep-quiet-moon-adsx2dey-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def create_tables():
    """Create essential tables for FreightOps Pro"""
    
    # SQL commands to create tables
    create_tables_sql = """
    -- Create companies table
    CREATE TABLE IF NOT EXISTS companies (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        phone VARCHAR(50),
        address TEXT,
        city VARCHAR(100),
        state VARCHAR(50),
        zip_code VARCHAR(20),
        dot_number VARCHAR(20),
        mc_number VARCHAR(20),
        ein VARCHAR(20),
        business_type VARCHAR(100),
        years_in_business INTEGER,
        number_of_trucks INTEGER,
        wallet_balance DECIMAL(15,2) DEFAULT 0.00,
        subscription_status VARCHAR(50) DEFAULT 'trial',
        subscription_plan VARCHAR(50) DEFAULT 'starter',
        subscription_tier VARCHAR(50) DEFAULT 'starter',
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Create users table
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        first_name VARCHAR(100),
        last_name VARCHAR(100),
        phone VARCHAR(50),
        role VARCHAR(50) DEFAULT 'user',
        company_id INTEGER REFERENCES companies(id),
        is_active BOOLEAN DEFAULT true,
        last_login TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Create drivers table
    CREATE TABLE IF NOT EXISTS drivers (
        id SERIAL PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255),
        first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100) NOT NULL,
        phone VARCHAR(50),
        license_number VARCHAR(50),
        license_state VARCHAR(10),
        license_expiry DATE,
        company_id INTEGER REFERENCES companies(id),
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Create vehicles table
    CREATE TABLE IF NOT EXISTS vehicles (
        id SERIAL PRIMARY KEY,
        vin VARCHAR(17) UNIQUE NOT NULL,
        make VARCHAR(50) NOT NULL,
        model VARCHAR(50) NOT NULL,
        year INTEGER NOT NULL,
        license_plate VARCHAR(20),
        company_id INTEGER REFERENCES companies(id),
        status VARCHAR(20) DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Create loads table
    CREATE TABLE IF NOT EXISTS loads (
        id SERIAL PRIMARY KEY,
        load_number VARCHAR(100) UNIQUE NOT NULL,
        origin VARCHAR(255),
        destination VARCHAR(255),
        pickup_date TIMESTAMP,
        delivery_date TIMESTAMP,
        status VARCHAR(50) DEFAULT 'pending',
        rate DECIMAL(15,2),
        customer_id VARCHAR(100),
        driver_id INTEGER REFERENCES drivers(id),
        truck_id INTEGER REFERENCES vehicles(id),
        company_id INTEGER REFERENCES companies(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Create audit_logs table for security
    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id VARCHAR(100),
        company_id VARCHAR(100),
        action VARCHAR(100),
        entity_type VARCHAR(100),
        entity_id VARCHAR(100),
        details JSONB,
        ip_address VARCHAR(45),
        user_agent TEXT,
        status VARCHAR(50) DEFAULT 'success',
        metadata_json JSONB
    );

    -- Create security_events table
    CREATE TABLE IF NOT EXISTS security_events (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        event_type VARCHAR(100) NOT NULL,
        severity VARCHAR(50) NOT NULL,
        description TEXT NOT NULL,
        company_id VARCHAR(100),
        user_id VARCHAR(100),
        ip_address VARCHAR(45),
        user_agent TEXT,
        details_json JSONB,
        action_taken VARCHAR(100),
        resolved BOOLEAN DEFAULT false,
        resolved_at TIMESTAMP,
        resolved_by VARCHAR(100)
    );

    -- Create api_keys table
    CREATE TABLE IF NOT EXISTS api_keys (
        id SERIAL PRIMARY KEY,
        key_name VARCHAR(255) NOT NULL,
        key_hash VARCHAR(255) NOT NULL,
        company_id INTEGER REFERENCES companies(id),
        permissions JSONB,
        is_active BOOLEAN DEFAULT true,
        last_used TIMESTAMP,
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Create indexes for better performance
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    CREATE INDEX IF NOT EXISTS idx_users_company_id ON users(company_id);
    CREATE INDEX IF NOT EXISTS idx_drivers_email ON drivers(email);
    CREATE INDEX IF NOT EXISTS idx_drivers_company_id ON drivers(company_id);
    CREATE INDEX IF NOT EXISTS idx_vehicles_company_id ON vehicles(company_id);
    CREATE INDEX IF NOT EXISTS idx_loads_company_id ON loads(company_id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_company_id ON audit_logs(company_id);
    CREATE INDEX IF NOT EXISTS idx_security_events_timestamp ON security_events(timestamp);
    CREATE INDEX IF NOT EXISTS idx_api_keys_company_id ON api_keys(company_id);
    """

    try:
        # Connect to Neon database
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Execute the SQL commands
            conn.execute(text(create_tables_sql))
            conn.commit()
            
        print("Successfully created all tables in Neon database!")
        return True
        
    except Exception as e:
        print(f"Error creating tables: {e}")
        return False

def create_test_data():
    """Create test data for development"""
    
    test_data_sql = """
    -- Insert test company
    INSERT INTO companies (name, email, phone, city, state, subscription_plan, subscription_tier) 
    VALUES ('Test Freight Company', 'test@freightops.com', '555-1234', 'Los Angeles', 'CA', 'professional', 'professional')
    ON CONFLICT (email) DO NOTHING;

    -- Insert test user (password is 'password123')
    INSERT INTO users (email, password, first_name, last_name, role, company_id) 
    VALUES ('test@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4ZqIhQK8nG', 'Test', 'User', 'admin', 1)
    ON CONFLICT (email) DO NOTHING;

    -- Insert test driver
    INSERT INTO drivers (email, password_hash, first_name, last_name, phone, license_number, company_id) 
    VALUES ('driver@test.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4ZqIhQK8nG', 'John', 'Driver', '555-5678', 'D123456789', 1)
    ON CONFLICT (email) DO NOTHING;

    -- Insert test vehicle
    INSERT INTO vehicles (vin, make, model, year, license_plate, company_id) 
    VALUES ('1HGBH41JXMN109186', 'Freightliner', 'Cascadia', 2023, 'ABC123', 1)
    ON CONFLICT (vin) DO NOTHING;
    """
    
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            conn.execute(text(test_data_sql))
            conn.commit()
            
        print("Successfully created test data!")
        return True
        
    except Exception as e:
        print(f"Error creating test data: {e}")
        return False

if __name__ == "__main__":
    print("Setting up Neon database for FreightOps Pro...")
    
    if create_tables():
        print("Creating test data...")
        create_test_data()
        print("Database setup complete!")
    else:
        print("Database setup failed!")

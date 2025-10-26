-- Create vendors table
CREATE TABLE IF NOT EXISTS vendors (
    id TEXT PRIMARY KEY NOT NULL,
    companyId TEXT NOT NULL,
    
    -- Personal Details
    title TEXT,
    firstName TEXT,
    middleName TEXT,
    lastName TEXT,
    suffix TEXT,
    
    -- Company Details
    company TEXT,
    displayName TEXT NOT NULL,
    printOnCheck TEXT,
    
    -- Address Information
    address TEXT,
    city TEXT,
    state TEXT,
    zipCode TEXT,
    country TEXT,
    
    -- Contact Information
    email TEXT,
    phone TEXT,
    mobile TEXT,
    fax TEXT,
    other TEXT,
    website TEXT,
    
    -- Financial Information
    billingRate TEXT,
    terms TEXT,
    openingBalance TEXT,
    balanceAsOf TEXT,
    accountNumber TEXT,
    
    -- 1099 Tracking
    taxId TEXT,
    trackPaymentsFor1099 BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create bills table
CREATE TABLE IF NOT EXISTS bills (
    id TEXT PRIMARY KEY NOT NULL,
    companyId TEXT NOT NULL,
    vendorId TEXT,
    vendorName TEXT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    billDate DATE,
    dueDate DATE,
    category TEXT,
    status TEXT DEFAULT 'pending',
    notes TEXT,
    createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (vendorId) REFERENCES vendors (id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_vendors_companyId ON vendors(companyId);
CREATE INDEX IF NOT EXISTS idx_bills_companyId ON bills(companyId);
CREATE INDEX IF NOT EXISTS idx_bills_vendorId ON bills(vendorId);

-- Verify tables were created
SELECT name FROM sqlite_master WHERE type='table' AND name IN ('vendors', 'bills');

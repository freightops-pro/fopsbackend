from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.config.db import Base


class Authority(Base):
    """Model for managing multiple operating authorities within a company"""
    __tablename__ = "authorities"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Company relationship
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    company = relationship("Companies", back_populates="authorities")
    
    # Authority details
    name = Column(String(100), nullable=False)  # e.g., "Main Carrier Operations", "Brokerage Division"
    authority_type = Column(String(50), nullable=False)  # carrier, brokerage, nvocc, forwarder
    dot_mc_number = Column(String(20), nullable=True)  # DOT/MC number for carrier authority
    fmc_number = Column(String(20), nullable=True)  # FMC number for NVOCC
    license_number = Column(String(50), nullable=True)  # Other license numbers
    
    # Status and configuration
    is_active = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)  # Primary authority for company
    effective_date = Column(DateTime(timezone=True), nullable=True)
    expiration_date = Column(DateTime(timezone=True), nullable=True)
    
    # Contact and address information
    contact_name = Column(String(100), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    contact_email = Column(String(100), nullable=True)
    business_address = Column(Text, nullable=True)
    
    # Authority-specific settings
    settings = Column(JSON, nullable=True)  # Authority-specific configuration
    insurance_requirements = Column(JSON, nullable=True)  # Insurance details
    compliance_requirements = Column(JSON, nullable=True)  # Compliance settings
    
    # Financial settings
    default_payment_terms = Column(String(20), default="net_30")  # net_15, net_30, cod, etc.
    default_currency = Column(String(3), default="USD")
    tax_id = Column(String(20), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    # Note: Load model doesn't exist, so commenting out
    # loads = relationship("Loads", back_populates="authority")
    # Note: Invoice and Customer relationships commented out to avoid circular dependencies
    # These can be added back if needed with proper lazy loading
    # invoices = relationship("Invoice", back_populates="authority")
    # customers = relationship("Customer", back_populates="primary_authority")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_company_authorities', 'company_id', 'is_active'),
        Index('idx_company_primary_authority', 'company_id', 'is_primary'),
        Index('idx_authority_type', 'authority_type', 'is_active'),
    )


class AuthorityUser(Base):
    """Model for managing user access to specific authorities"""
    __tablename__ = "authority_users"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Relationships
    authority_id = Column(String, ForeignKey("authorities.id"), nullable=False)
    authority = relationship("Authority")
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    user = relationship("Users", foreign_keys=[user_id])
    
    # Access permissions
    can_view = Column(Boolean, default=True)
    can_edit = Column(Boolean, default=False)
    can_manage = Column(Boolean, default=False)  # Full management access
    can_create_loads = Column(Boolean, default=False)  # Create loads for this authority
    can_view_financials = Column(Boolean, default=False)  # View authority P&L
    can_manage_customers = Column(Boolean, default=False)  # Manage customers for this authority
    
    # Assignment details
    is_primary_authority = Column(Boolean, default=False)  # User's primary authority
    assigned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    assigned_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    assigned_by = relationship("Users", foreign_keys=[assigned_by_id])
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Unique constraint
    __table_args__ = (
        Index('idx_authority_user_unique', 'authority_id', 'user_id', unique=True),
        Index('idx_user_authorities', 'user_id', 'is_primary_authority'),
    )


class AuthorityFinancials(Base):
    """Model for tracking financial metrics per authority"""
    __tablename__ = "authority_financials"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Relationships
    authority_id = Column(String, ForeignKey("authorities.id"), nullable=False)
    authority = relationship("Authority")
    
    # Financial period
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    period_type = Column(String(20), default="monthly")  # daily, weekly, monthly, yearly
    
    # Revenue metrics
    total_revenue = Column(Integer, default=0)  # Revenue in cents
    load_count = Column(Integer, default=0)
    average_rate = Column(Integer, default=0)  # Average rate per load in cents
    
    # Authority-specific revenue (for brokerage/NVOCC)
    gross_revenue = Column(Integer, default=0)  # Total customer revenue
    carrier_payments = Column(Integer, default=0)  # Payments to carriers (brokerage)
    ocean_freight_costs = Column(Integer, default=0)  # Ocean freight costs (NVOCC)
    port_charges = Column(Integer, default=0)  # Port and terminal charges
    
    # Expense metrics
    fuel_cost = Column(Integer, default=0)
    maintenance_cost = Column(Integer, default=0)
    driver_pay = Column(Integer, default=0)
    overhead_cost = Column(Integer, default=0)
    total_expenses = Column(Integer, default=0)
    
    # Profitability
    gross_profit = Column(Integer, default=0)
    net_profit = Column(Integer, default=0)
    profit_margin = Column(Integer, default=0)  # Percentage * 100 (e.g., 1500 = 15%)
    
    # Authority-specific metrics (will be stored in JSON settings)
    carrier_count = Column(Integer, default=0)
    average_margin_percent = Column(Integer, default=0)  # Brokerage margin percentage
    container_count = Column(Integer, default=0)
    teu_count = Column(Integer, default=0)  # Twenty-foot equivalent units
    
    # Operational metrics
    loads_managed = Column(Integer, default=0)
    customer_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Indexes
    __table_args__ = (
        Index('idx_authority_period', 'authority_id', 'period_start', 'period_end'),
        Index('idx_authority_period_type', 'authority_id', 'period_type'),
    )


class AuthorityCustomer(Base):
    """Model for managing customer relationships per authority"""
    __tablename__ = "authority_customers"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Relationships
    authority_id = Column(String, ForeignKey("authorities.id"), nullable=False)
    authority = relationship("Authority")
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    customer = relationship("Customer")
    
    # Relationship details
    is_primary = Column(Boolean, default=False)  # Primary authority for this customer
    relationship_type = Column(String(50), default="direct")  # direct, broker, forwarder, nvocc
    
    # Authority-specific settings
    payment_terms = Column(String(20), nullable=True)  # Override default terms
    credit_limit = Column(Integer, nullable=True)  # Credit limit in cents
    special_instructions = Column(Text, nullable=True)
    
    # Contract details
    contract_start_date = Column(DateTime(timezone=True), nullable=True)
    contract_end_date = Column(DateTime(timezone=True), nullable=True)
    contract_terms = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Unique constraint
    __table_args__ = (
        Index('idx_authority_customer_unique', 'authority_id', 'customer_id', unique=True),
        Index('idx_customer_authorities', 'customer_id', 'is_primary'),
    )


class AuthorityIntegration(Base):
    """Model for managing authority-specific integrations"""
    __tablename__ = "authority_integrations"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Relationships
    authority_id = Column(String, ForeignKey("authorities.id"), nullable=False)
    authority = relationship("Authority")
    
    # Integration details
    integration_type = Column(String(50), nullable=False)  # eld, loadboard, factoring, accounting, etc.
    provider_name = Column(String(100), nullable=False)  # DAT, Truckstop, Apex, QuickBooks, etc.
    provider_id = Column(String(100), nullable=True)  # External provider ID
    
    # Configuration
    is_active = Column(Boolean, default=True)
    configuration = Column(JSON, nullable=True)  # Integration-specific settings
    credentials = Column(JSON, nullable=True)  # Encrypted credentials
    
    # Usage tracking
    last_sync = Column(DateTime(timezone=True), nullable=True)
    sync_frequency = Column(String(20), default="daily")  # real-time, hourly, daily, weekly
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Indexes
    __table_args__ = (
        Index('idx_authority_integrations', 'authority_id', 'integration_type'),
        Index('idx_authority_active_integrations', 'authority_id', 'is_active'),
    )


class AuthorityAuditLog(Base):
    """Model for tracking authority-related changes and activities"""
    __tablename__ = "authority_audit_logs"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Relationships
    authority_id = Column(String, ForeignKey("authorities.id"), nullable=False)
    authority = relationship("Authority")
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    user = relationship("Users")
    
    # Audit details
    action = Column(String(50), nullable=False)  # create, update, delete, view, etc.
    entity_type = Column(String(50), nullable=True)  # load, invoice, customer, etc.
    entity_id = Column(String(50), nullable=True)  # ID of the affected entity
    
    # Change details
    old_values = Column(JSON, nullable=True)  # Previous values
    new_values = Column(JSON, nullable=True)  # New values
    change_summary = Column(Text, nullable=True)  # Human-readable summary
    
    # Context
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Indexes
    __table_args__ = (
        Index('idx_authority_audit', 'authority_id', 'created_at'),
        Index('idx_authority_user_audit', 'authority_id', 'user_id', 'created_at'),
        Index('idx_authority_entity_audit', 'authority_id', 'entity_type', 'entity_id'),
    )

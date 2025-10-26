from sqlalchemy import Column, String, DateTime, Float, Boolean, Text, JSON, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.config.db import Base
import uuid

class BankingCustomer(Base):
    __tablename__ = "banking_customers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    synctera_person_id = Column(String(255), unique=True, nullable=True)
    synctera_business_id = Column(String(255), unique=True, nullable=True)
    
    # Business Information
    legal_name = Column(String(255), nullable=False)
    ein = Column(String(20), nullable=False)
    business_address = Column(Text, nullable=False)
    business_city = Column(String(100), nullable=False)
    business_state = Column(String(50), nullable=False)
    business_zip_code = Column(String(20), nullable=False)
    naics_code = Column(String(10), nullable=False)
    website = Column(String(255), nullable=True)
    control_person_name = Column(String(255), nullable=False)
    
    # KYB Status
    kyb_status = Column(String(50), default="pending")  # pending, approved, rejected, needs_info
    kyb_submitted_at = Column(DateTime(timezone=True), nullable=True)
    kyb_approved_at = Column(DateTime(timezone=True), nullable=True)
    kyb_rejection_reason = Column(Text, nullable=True)
    
    # Customer Status
    status = Column(String(50), default="active")  # active, suspended, closed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    accounts = relationship("BankingAccount", back_populates="customer", cascade="all, delete-orphan")
    company = relationship("Companies")

class BankingAccount(Base):
    __tablename__ = "banking_accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("banking_customers.id", ondelete="CASCADE"), nullable=False)
    synctera_account_id = Column(String(255), unique=True, nullable=True)
    
    # Account Information
    account_type = Column(String(50), nullable=False)  # checking, savings, escrow
    account_number = Column(String(255), nullable=True)
    routing_number = Column(String(255), nullable=True)
    account_name = Column(String(255), nullable=False)
    
    # Balance Information
    available_balance = Column(Float, default=0.0)
    current_balance = Column(Float, default=0.0)
    pending_balance = Column(Float, default=0.0)
    
    # Account Status
    status = Column(String(50), default="active")  # active, suspended, closed, pending
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    customer = relationship("BankingCustomer", back_populates="accounts")
    cards = relationship("BankingCard", back_populates="account", cascade="all, delete-orphan")
    transactions = relationship("BankingTransaction", back_populates="account", cascade="all, delete-orphan")

class BankingCard(Base):
    __tablename__ = "banking_cards"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("banking_accounts.id", ondelete="CASCADE"), nullable=False)
    synctera_card_id = Column(String(255), unique=True, nullable=True)
    
    # Card Information
    card_type = Column(String(50), nullable=False)  # virtual, physical
    card_number = Column(String(255), nullable=True)  # Masked for security
    last_four = Column(String(4), nullable=True)
    expiry_date = Column(String(7), nullable=True)  # MM/YYYY format
    cvv = Column(String(255), nullable=True)  # Encrypted
    
    # Card Details
    card_name = Column(String(255), nullable=False)
    assigned_to = Column(String(255), nullable=True)  # Driver name or "All Drivers"
    
    # Limits and Restrictions
    daily_limit = Column(Float, nullable=True)
    monthly_limit = Column(Float, nullable=True)
    restrictions = Column(JSON, nullable=True)  # Merchant categories, etc.
    
    # Card Status
    status = Column(String(50), default="active")  # active, locked, expired, cancelled
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    account = relationship("BankingAccount", back_populates="cards")
    transactions = relationship("BankingTransaction", back_populates="card", cascade="all, delete-orphan")

class BankingTransaction(Base):
    __tablename__ = "banking_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("banking_accounts.id", ondelete="CASCADE"), nullable=False)
    card_id = Column(UUID(as_uuid=True), ForeignKey("banking_cards.id", ondelete="SET NULL"), nullable=True)
    synctera_transaction_id = Column(String(255), unique=True, nullable=True)
    
    # Transaction Information
    amount = Column(Float, nullable=False)
    type = Column(String(50), nullable=False)  # credit, debit
    category = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    merchant_name = Column(String(255), nullable=True)
    merchant_category = Column(String(100), nullable=True)
    
    # Transaction Details
    reference_id = Column(String(255), nullable=True)
    transaction_date = Column(DateTime(timezone=True), nullable=False)
    posted_date = Column(DateTime(timezone=True), nullable=True)
    
    # Status and Metadata
    status = Column(String(50), default="pending")  # pending, completed, failed, cancelled
    transaction_metadata = Column(JSON, nullable=True)  # Additional transaction data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    account = relationship("BankingAccount", back_populates="transactions")
    card = relationship("BankingCard", back_populates="transactions")

class BankingTransfer(Base):
    __tablename__ = "banking_transfers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_account_id = Column(UUID(as_uuid=True), ForeignKey("banking_accounts.id", ondelete="CASCADE"), nullable=False)
    to_account_id = Column(UUID(as_uuid=True), ForeignKey("banking_accounts.id", ondelete="SET NULL"), nullable=True)
    synctera_transfer_id = Column(String(255), unique=True, nullable=True)
    
    # Transfer Information
    amount = Column(Float, nullable=False)
    transfer_type = Column(String(50), nullable=False)  # ach, wire, internal
    description = Column(Text, nullable=True)
    
    # External Transfer Details
    recipient_name = Column(String(255), nullable=True)
    recipient_account = Column(String(255), nullable=True)
    recipient_routing = Column(String(255), nullable=True)
    
    # Status and Timing
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    scheduled_date = Column(DateTime(timezone=True), nullable=True)
    completed_date = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    transfer_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, JSON, Numeric, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class Invoice(Base):
    __tablename__ = "accounting_invoice"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    load_id = Column(String, ForeignKey("freight_load.id"), nullable=True, index=True)

    invoice_number = Column(String, nullable=False, unique=True)
    invoice_date = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="draft")
    subtotal = Column(Numeric(12, 2), nullable=False)
    tax = Column(Numeric(12, 2), nullable=False, default=0)
    total = Column(Numeric(12, 2), nullable=False)
    line_items = Column(JSON, nullable=False, default=list)
    metadata_json = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company")
    load = relationship("Load")


class LedgerEntry(Base):
    __tablename__ = "accounting_ledger_entry"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    load_id = Column(String, ForeignKey("freight_load.id"), nullable=True, index=True)
    source = Column(String, nullable=False)  # dispatch, fuel, detention, adjustment
    category = Column(String, nullable=False)  # revenue, expense, deduction
    quantity = Column(Numeric(12, 3), nullable=False)
    unit = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())


class Settlement(Base):
    __tablename__ = "accounting_settlement"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    driver_id = Column(String, ForeignKey("driver.id"), nullable=False, index=True)
    load_id = Column(String, ForeignKey("freight_load.id"), nullable=True, index=True)

    settlement_date = Column(Date, nullable=False)
    total_earnings = Column(Numeric(12, 2), nullable=False)
    total_deductions = Column(Numeric(12, 2), nullable=False)
    net_pay = Column(Numeric(12, 2), nullable=False)
    breakdown = Column(JSON, nullable=False, default=dict)
    metadata_json = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())


class Customer(Base):
    __tablename__ = "accounting_customer"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Basic Info
    name = Column(String, nullable=False)
    legal_name = Column(String, nullable=True)
    tax_id = Column(String, nullable=True)  # EIN, SSN, etc.

    # Contact Info
    primary_contact_name = Column(String, nullable=True)
    primary_contact_email = Column(String, nullable=True)
    primary_contact_phone = Column(String, nullable=True)

    # Addresses (stored as JSON)
    billing_address = Column(JSON, nullable=True)  # {street, city, state, zip, country}
    shipping_address = Column(JSON, nullable=True)

    # Payment Terms
    payment_terms = Column(String, nullable=True)  # "NET_30", "NET_15", "DUE_ON_RECEIPT", etc.
    credit_limit = Column(Numeric(12, 2), nullable=True)
    credit_limit_used = Column(Numeric(12, 2), nullable=False, default=0)

    # Banking Integration
    synctera_account_id = Column(String, nullable=True)  # Link to Synctera account

    # Status
    status = Column(String, nullable=False, default="active")  # active, inactive, suspended
    is_active = Column(Boolean, nullable=False, default=True)

    # Metadata
    metadata_json = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company")


class Vendor(Base):
    __tablename__ = "accounting_vendor"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Basic Info
    name = Column(String, nullable=False)
    legal_name = Column(String, nullable=True)
    tax_id = Column(String, nullable=True)  # EIN, SSN, etc.

    # Category: equipment_maintenance, finance_insurance, integrations, facilities_partners
    category = Column(String, nullable=False, default="equipment_maintenance")

    # Contact Info
    primary_contact_name = Column(String, nullable=True)
    primary_contact_email = Column(String, nullable=True)
    primary_contact_phone = Column(String, nullable=True)

    # Address (stored as JSON)
    address = Column(JSON, nullable=True)  # {street, city, state, zip, country}

    # Payment Terms
    payment_terms = Column(String, nullable=True)  # "NET_30", "NET_15", "DUE_ON_RECEIPT", etc.

    # Contract Info
    contract_start_date = Column(Date, nullable=True)
    contract_end_date = Column(Date, nullable=True)
    contract_value = Column(Numeric(12, 2), nullable=True)

    # Outstanding Balance
    outstanding_balance = Column(Numeric(12, 2), nullable=False, default=0)

    # Status
    status = Column(String, nullable=False, default="active")  # active, inactive, suspended
    is_active = Column(Boolean, nullable=False, default=True)

    # Notes
    notes = Column(String, nullable=True)

    # Metadata
    metadata_json = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company")



"""HQ Accounting models for A/R and A/P."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    JSON,
    func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base


# ============================================================================
# Enums
# ============================================================================

class CustomerStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class CustomerType(enum.Enum):
    TENANT = "tenant"
    PARTNER = "partner"
    ENTERPRISE = "enterprise"
    OTHER = "other"


class InvoiceStatus(enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    PAID = "paid"
    PARTIAL = "partial"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    VOID = "void"


class InvoiceType(enum.Enum):
    SUBSCRIPTION = "subscription"
    SERVICE = "service"
    SETUP_FEE = "setup_fee"
    CREDIT_NOTE = "credit_note"
    OTHER = "other"


class VendorStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING_APPROVAL = "pending_approval"


class VendorType(enum.Enum):
    SERVICE = "service"
    SUPPLIER = "supplier"
    CONTRACTOR = "contractor"
    UTILITY = "utility"
    OTHER = "other"


class BillStatus(enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PAID = "paid"
    PARTIAL = "partial"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    VOID = "void"


class BillType(enum.Enum):
    EXPENSE = "expense"
    SERVICE = "service"
    UTILITY = "utility"
    SUBSCRIPTION = "subscription"
    OTHER = "other"


class PaymentType(enum.Enum):
    CHECK = "check"
    ACH = "ach"
    WIRE = "wire"
    CREDIT_CARD = "credit_card"
    OTHER = "other"


class PaymentDirection(enum.Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


# ============================================================================
# Customer Model (A/R)
# ============================================================================

class HQCustomer(Base):
    """Customer for accounts receivable."""

    __tablename__ = "hq_customer"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), ForeignKey("hq_tenant.id"), nullable=True)
    customer_number = Column(String(20), unique=True, nullable=False)

    name = Column(String(255), nullable=False)
    customer_type = Column(Enum(CustomerType), default=CustomerType.TENANT, nullable=False)
    status = Column(Enum(CustomerStatus), default=CustomerStatus.ACTIVE, nullable=False)

    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)

    # Billing address
    billing_address = Column(String(255), nullable=True)
    billing_city = Column(String(100), nullable=True)
    billing_state = Column(String(50), nullable=True)
    billing_zip = Column(String(20), nullable=True)
    billing_country = Column(String(2), default="US", nullable=False)

    tax_id = Column(String(50), nullable=True)
    payment_terms_days = Column(Integer, default=30, nullable=False)
    credit_limit = Column(Numeric(12, 2), nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("HQTenant", back_populates="customer", uselist=False)
    invoices = relationship("HQInvoice", back_populates="customer")


# ============================================================================
# Invoice Model (A/R)
# ============================================================================

class HQInvoice(Base):
    """Invoice for accounts receivable."""

    __tablename__ = "hq_invoice"

    id = Column(String(36), primary_key=True)
    customer_id = Column(String(36), ForeignKey("hq_customer.id"), nullable=False)
    tenant_id = Column(String(36), ForeignKey("hq_tenant.id"), nullable=True)
    contract_id = Column(String(36), ForeignKey("hq_contract.id"), nullable=True)

    invoice_number = Column(String(20), unique=True, nullable=False)
    invoice_type = Column(Enum(InvoiceType), default=InvoiceType.SUBSCRIPTION, nullable=False)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT, nullable=False)

    description = Column(Text, nullable=True)
    line_items = Column(JSON, default=list, nullable=False)

    subtotal = Column(Numeric(12, 2), default=0, nullable=False)
    tax_total = Column(Numeric(12, 2), default=0, nullable=False)
    total = Column(Numeric(12, 2), default=0, nullable=False)
    paid_amount = Column(Numeric(12, 2), default=0, nullable=False)
    balance_due = Column(Numeric(12, 2), default=0, nullable=False)

    issued_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    paid_date = Column(DateTime, nullable=True)

    notes = Column(Text, nullable=True)
    terms = Column(Text, nullable=True)

    stripe_invoice_id = Column(String(100), nullable=True)
    created_by_id = Column(String(36), ForeignKey("hq_employee.id"), nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    customer = relationship("HQCustomer", back_populates="invoices")
    tenant = relationship("HQTenant")
    contract = relationship("HQContract")
    created_by = relationship("HQEmployee")
    payments = relationship("HQPayment", back_populates="invoice")


# ============================================================================
# Vendor Model (A/P)
# ============================================================================

class HQVendor(Base):
    """Vendor for accounts payable."""

    __tablename__ = "hq_vendor"

    id = Column(String(36), primary_key=True)
    vendor_number = Column(String(20), unique=True, nullable=False)

    name = Column(String(255), nullable=False)
    vendor_type = Column(Enum(VendorType), default=VendorType.SERVICE, nullable=False)
    status = Column(Enum(VendorStatus), default=VendorStatus.ACTIVE, nullable=False)

    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)

    # Address
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    country = Column(String(2), default="US", nullable=False)

    tax_id = Column(String(50), nullable=True)
    payment_terms_days = Column(Integer, default=30, nullable=False)
    default_expense_account = Column(String(50), nullable=True)
    bank_account_info = Column(Text, nullable=True)  # Encrypted in production

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    bills = relationship("HQBill", back_populates="vendor")


# ============================================================================
# Bill Model (A/P)
# ============================================================================

class HQBill(Base):
    """Bill for accounts payable."""

    __tablename__ = "hq_bill"

    id = Column(String(36), primary_key=True)
    vendor_id = Column(String(36), ForeignKey("hq_vendor.id"), nullable=False)

    bill_number = Column(String(20), unique=True, nullable=False)
    vendor_invoice_number = Column(String(100), nullable=True)
    bill_type = Column(Enum(BillType), default=BillType.EXPENSE, nullable=False)
    status = Column(Enum(BillStatus), default=BillStatus.DRAFT, nullable=False)

    description = Column(Text, nullable=True)
    line_items = Column(JSON, default=list, nullable=False)

    subtotal = Column(Numeric(12, 2), default=0, nullable=False)
    tax_total = Column(Numeric(12, 2), default=0, nullable=False)
    total = Column(Numeric(12, 2), default=0, nullable=False)
    paid_amount = Column(Numeric(12, 2), default=0, nullable=False)
    balance_due = Column(Numeric(12, 2), default=0, nullable=False)

    bill_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=True)
    paid_date = Column(DateTime, nullable=True)

    notes = Column(Text, nullable=True)

    approved_by_id = Column(String(36), ForeignKey("hq_employee.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_by_id = Column(String(36), ForeignKey("hq_employee.id"), nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    vendor = relationship("HQVendor", back_populates="bills")
    approved_by = relationship("HQEmployee", foreign_keys=[approved_by_id])
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])
    payments = relationship("HQPayment", back_populates="bill")


# ============================================================================
# Payment Model
# ============================================================================

class HQPayment(Base):
    """Payment record for A/R and A/P."""

    __tablename__ = "hq_payment"

    id = Column(String(36), primary_key=True)
    payment_number = Column(String(20), unique=True, nullable=False)

    invoice_id = Column(String(36), ForeignKey("hq_invoice.id"), nullable=True)
    bill_id = Column(String(36), ForeignKey("hq_bill.id"), nullable=True)

    payment_type = Column(Enum(PaymentType), nullable=False)
    direction = Column(Enum(PaymentDirection), nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)
    payment_date = Column(DateTime, nullable=False)
    reference_number = Column(String(100), nullable=True)

    stripe_payment_id = Column(String(100), nullable=True)
    synctera_transaction_id = Column(String(100), nullable=True)

    notes = Column(Text, nullable=True)
    recorded_by_id = Column(String(36), ForeignKey("hq_employee.id"), nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    invoice = relationship("HQInvoice", back_populates="payments")
    bill = relationship("HQBill", back_populates="payments")
    recorded_by = relationship("HQEmployee")

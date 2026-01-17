"""HQ General Ledger models for double-entry accounting.

This is the accounting core that tracks every penny in the system.
Follows GAAP double-entry bookkeeping: Debits always equal Credits.
"""

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
    Boolean,
    JSON,
    Index,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base


# ============================================================================
# Account Types (Standard Chart of Accounts)
# ============================================================================

class AccountType(enum.Enum):
    """Standard accounting account types."""
    # Balance Sheet Accounts
    ASSET = "asset"                    # 1000-1999: Cash, AR, Equipment
    LIABILITY = "liability"            # 2000-2999: AP, Loans, Deferred Revenue
    EQUITY = "equity"                  # 3000-3999: Retained Earnings, Capital

    # Income Statement Accounts
    REVENUE = "revenue"                # 4000-4999: SaaS Revenue, Services
    COST_OF_REVENUE = "cost_of_revenue"  # 5000-5999: AI Compute, Hosting
    EXPENSE = "expense"                # 6000-6999: Salaries, Marketing, Rent


class AccountSubtype(enum.Enum):
    """Account subtypes for detailed categorization."""
    # Assets
    CASH = "cash"
    ACCOUNTS_RECEIVABLE = "accounts_receivable"
    PREPAID_EXPENSE = "prepaid_expense"
    FIXED_ASSET = "fixed_asset"

    # Liabilities
    ACCOUNTS_PAYABLE = "accounts_payable"
    CREDIT_CARD = "credit_card"
    DEFERRED_REVENUE = "deferred_revenue"
    PAYROLL_LIABILITY = "payroll_liability"

    # Equity
    RETAINED_EARNINGS = "retained_earnings"
    OWNER_EQUITY = "owner_equity"

    # Revenue
    SAAS_REVENUE = "saas_revenue"
    SERVICE_REVENUE = "service_revenue"
    OTHER_INCOME = "other_income"

    # COGS
    AI_COMPUTE = "ai_compute"
    HOSTING = "hosting"
    PAYMENT_PROCESSING = "payment_processing"

    # Expenses
    PAYROLL = "payroll"
    MARKETING = "marketing"
    SOFTWARE = "software"
    PROFESSIONAL_SERVICES = "professional_services"
    OFFICE = "office"
    OTHER_EXPENSE = "other_expense"


class JournalEntryStatus(enum.Enum):
    """Status of a journal entry."""
    DRAFT = "draft"
    POSTED = "posted"
    VOID = "void"


# ============================================================================
# Chart of Accounts
# ============================================================================

class HQChartOfAccounts(Base):
    """Chart of Accounts - The master list of all accounts."""

    __tablename__ = "hq_chart_of_accounts"

    id = Column(String(36), primary_key=True)

    # Account identification
    account_number = Column(String(10), unique=True, nullable=False)  # e.g., "1000", "4010"
    account_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Classification
    account_type = Column(Enum(AccountType), nullable=False)
    account_subtype = Column(Enum(AccountSubtype), nullable=True)

    # Hierarchy (for sub-accounts)
    parent_account_id = Column(String(36), ForeignKey("hq_chart_of_accounts.id"), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)  # System accounts can't be deleted

    # Balance tracking
    current_balance = Column(Numeric(14, 2), default=0, nullable=False)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    parent_account = relationship("HQChartOfAccounts", remote_side=[id], backref="sub_accounts")
    debit_entries = relationship("HQGeneralLedgerEntry", foreign_keys="HQGeneralLedgerEntry.debit_account_id", back_populates="debit_account")
    credit_entries = relationship("HQGeneralLedgerEntry", foreign_keys="HQGeneralLedgerEntry.credit_account_id", back_populates="credit_account")

    __table_args__ = (
        Index("ix_hq_coa_account_type", "account_type"),
        Index("ix_hq_coa_account_number", "account_number"),
    )


# ============================================================================
# Journal Entry (Transaction Header)
# ============================================================================

class HQJournalEntry(Base):
    """Journal Entry header - Groups related GL entries into a single transaction."""

    __tablename__ = "hq_journal_entry"

    id = Column(String(36), primary_key=True)

    # Identification
    entry_number = Column(String(20), unique=True, nullable=False)  # JE-2024-00001
    reference = Column(String(100), nullable=True)  # External reference (Invoice #, etc.)

    # Transaction details
    transaction_date = Column(DateTime, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(JournalEntryStatus), default=JournalEntryStatus.DRAFT, nullable=False)

    # Source tracking
    source_type = Column(String(50), nullable=True)  # "invoice", "bill", "payroll", "bank_transaction"
    source_id = Column(String(36), nullable=True)  # ID of the source document

    # Tenant attribution (for per-customer P&L)
    tenant_id = Column(String(36), ForeignKey("hq_tenant.id"), nullable=True)

    # Totals (for validation)
    total_debits = Column(Numeric(14, 2), default=0, nullable=False)
    total_credits = Column(Numeric(14, 2), default=0, nullable=False)

    # Audit
    created_by_id = Column(String(36), ForeignKey("hq_employee.id"), nullable=True)
    posted_by_id = Column(String(36), ForeignKey("hq_employee.id"), nullable=True)
    posted_at = Column(DateTime, nullable=True)
    voided_at = Column(DateTime, nullable=True)
    voided_by_id = Column(String(36), ForeignKey("hq_employee.id"), nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("HQTenant")
    created_by = relationship("HQEmployee", foreign_keys=[created_by_id])
    posted_by = relationship("HQEmployee", foreign_keys=[posted_by_id])
    voided_by = relationship("HQEmployee", foreign_keys=[voided_by_id])
    entries = relationship("HQGeneralLedgerEntry", back_populates="journal_entry", cascade="all, delete-orphan")

    __table_args__ = (
        # NOTE: Balance check (total_debits = total_credits for posted entries)
        # is enforced at the application level in the posting logic
        Index("ix_hq_je_transaction_date", "transaction_date"),
        Index("ix_hq_je_tenant_id", "tenant_id"),
        Index("ix_hq_je_source", "source_type", "source_id"),
    )


# ============================================================================
# General Ledger Entry (The immutable record)
# ============================================================================

class HQGeneralLedgerEntry(Base):
    """
    General Ledger Entry - The immutable record of every penny.

    Each entry represents one side of a double-entry transaction.
    Every journal entry must have balanced debit and credit entries.
    """

    __tablename__ = "hq_general_ledger_entry"

    id = Column(String(36), primary_key=True)

    # Link to journal entry
    journal_entry_id = Column(String(36), ForeignKey("hq_journal_entry.id"), nullable=False)

    # Account affected
    debit_account_id = Column(String(36), ForeignKey("hq_chart_of_accounts.id"), nullable=True)
    credit_account_id = Column(String(36), ForeignKey("hq_chart_of_accounts.id"), nullable=True)

    # Amount (always positive)
    amount = Column(Numeric(14, 2), nullable=False)

    # Optional memo for this specific line
    memo = Column(Text, nullable=True)

    # For tenant attribution (cost allocation)
    tenant_id = Column(String(36), ForeignKey("hq_tenant.id"), nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    journal_entry = relationship("HQJournalEntry", back_populates="entries")
    debit_account = relationship("HQChartOfAccounts", foreign_keys=[debit_account_id], back_populates="debit_entries")
    credit_account = relationship("HQChartOfAccounts", foreign_keys=[credit_account_id], back_populates="credit_entries")
    tenant = relationship("HQTenant")

    __table_args__ = (
        # Either debit or credit, not both or neither
        CheckConstraint(
            "(debit_account_id IS NOT NULL AND credit_account_id IS NULL) OR "
            "(debit_account_id IS NULL AND credit_account_id IS NOT NULL)",
            name="ck_gle_debit_or_credit"
        ),
        # Amount must be positive
        CheckConstraint("amount > 0", name="ck_gle_positive_amount"),
        Index("ix_hq_gle_journal_entry_id", "journal_entry_id"),
        Index("ix_hq_gle_debit_account", "debit_account_id"),
        Index("ix_hq_gle_credit_account", "credit_account_id"),
        Index("ix_hq_gle_tenant_id", "tenant_id"),
    )


# ============================================================================
# Usage Logs (The "Meter" for dynamic billing)
# ============================================================================

class UsageMetricType(enum.Enum):
    """Types of billable usage metrics."""
    ACTIVE_TRUCKS = "active_trucks"
    ACTIVE_DRIVERS = "active_drivers"
    PAYROLL_EMPLOYEES = "payroll_employees"
    AI_TOKENS_USED = "ai_tokens_used"
    AI_REQUESTS = "ai_requests"
    STORAGE_GB = "storage_gb"
    API_CALLS = "api_calls"


class HQUsageLog(Base):
    """
    Usage Logs - Tracks dynamic billing metrics and AI COGS.

    This is the "meter" that enables:
    1. Dynamic billing (e.g., $78/truck)
    2. AI cost attribution per tenant (for true gross margins)
    """

    __tablename__ = "hq_usage_log"

    id = Column(String(36), primary_key=True)

    # What tenant
    tenant_id = Column(String(36), ForeignKey("hq_tenant.id"), nullable=False)

    # What metric
    metric_type = Column(Enum(UsageMetricType), nullable=False)
    metric_value = Column(Numeric(14, 4), nullable=False)  # 4 decimal places for tokens

    # When (for time-series analysis)
    recorded_at = Column(DateTime, default=func.now(), nullable=False)
    period_start = Column(DateTime, nullable=True)  # For aggregated metrics
    period_end = Column(DateTime, nullable=True)

    # Cost attribution (for AI COGS)
    unit_cost = Column(Numeric(10, 6), nullable=True)  # Cost per unit (e.g., per 1K tokens)
    total_cost = Column(Numeric(12, 4), nullable=True)  # metric_value * unit_cost

    # AI-specific metadata
    ai_metadata = Column(JSON, nullable=True)  # model, input_tokens, output_tokens, etc.

    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    tenant = relationship("HQTenant")

    __table_args__ = (
        Index("ix_hq_usage_tenant_metric", "tenant_id", "metric_type"),
        Index("ix_hq_usage_recorded_at", "recorded_at"),
        Index("ix_hq_usage_period", "period_start", "period_end"),
    )


# ============================================================================
# Recurring Billing Schedule
# ============================================================================

class BillingFrequency(enum.Enum):
    """Billing frequency options."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class HQRecurringBilling(Base):
    """
    Recurring Billing Schedule for subscription invoices.

    This drives the automated invoice generation.
    """

    __tablename__ = "hq_recurring_billing"

    id = Column(String(36), primary_key=True)

    # Who
    tenant_id = Column(String(36), ForeignKey("hq_tenant.id"), nullable=False)
    customer_id = Column(String(36), ForeignKey("hq_customer.id"), nullable=False)

    # Billing schedule
    frequency = Column(Enum(BillingFrequency), default=BillingFrequency.MONTHLY, nullable=False)
    billing_anchor_day = Column(Integer, default=1, nullable=False)  # Day of month (1-28)

    # Base pricing
    base_amount = Column(Numeric(10, 2), nullable=False)  # e.g., $78 per truck
    pricing_model = Column(String(50), default="per_unit", nullable=False)  # per_unit, flat, tiered

    # What to bill for
    metric_type = Column(Enum(UsageMetricType), nullable=True)  # e.g., ACTIVE_TRUCKS
    unit_price = Column(Numeric(10, 2), nullable=True)  # Price per unit

    # Add-ons (JSON array of {name, price, quantity})
    add_ons = Column(JSON, default=list, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    next_billing_date = Column(DateTime, nullable=True)
    last_billed_date = Column(DateTime, nullable=True)

    # Contract reference
    contract_id = Column(String(36), ForeignKey("hq_contract.id"), nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tenant = relationship("HQTenant")
    customer = relationship("HQCustomer")
    contract = relationship("HQContract")

    __table_args__ = (
        Index("ix_hq_recurring_tenant", "tenant_id"),
        Index("ix_hq_recurring_next_billing", "next_billing_date"),
    )

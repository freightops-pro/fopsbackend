from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class LedgerEntryCreate(BaseModel):
    """Schema for creating a manual ledger entry from the accounting module."""
    date: str  # ISO date string
    transaction_date: Optional[str] = None  # ISO date string
    description: str
    account_id: str  # Account name/identifier
    type: str  # "debit" or "credit"
    category: str  # "revenue", "expense", "asset", "liability", "equity"
    amount: float
    reference: Optional[str] = None
    debit: Optional[float] = None  # For backwards compatibility
    credit: Optional[float] = None  # For backwards compatibility


class LedgerEntryResponse(BaseModel):
    id: str
    source: str
    category: str
    quantity: float
    unit: str
    amount: float
    recorded_at: datetime

    model_config = {"from_attributes": True}


class LedgerSummaryResponse(BaseModel):
    total_revenue: float
    total_expense: float
    total_deductions: float
    net_total: float
    entries: List[LedgerEntryResponse]


class InvoiceLineItem(BaseModel):
    description: str
    amount: float
    quantity: Optional[float] = None
    unit: Optional[str] = None


class InvoiceCreate(BaseModel):
    load_id: Optional[str] = None
    invoice_number: Optional[str] = None  # Auto-generated if not provided
    invoice_date: date
    line_items: List[InvoiceLineItem] = Field(..., min_length=1)
    tax_rate: float = 0.0


class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str
    invoice_date: date
    status: str
    subtotal: float
    tax: float
    total: float
    line_items: List[InvoiceLineItem]
    created_at: datetime

    model_config = {"from_attributes": True}


class SettlementCreate(BaseModel):
    driver_id: str
    load_id: Optional[str] = None
    settlement_date: date


class SettlementResponse(BaseModel):
    id: str
    driver_id: str
    load_id: Optional[str]
    settlement_date: date
    total_earnings: float
    total_deductions: float
    net_pay: float
    breakdown: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class AccountingBasicReport(BaseModel):
    period: str
    dateRange: dict
    revenue: dict
    expenses: dict
    profit: dict
    outstanding: dict
    cashFlow: dict
    fuel: Optional[dict] = None


class PayrollSummary(BaseModel):
    totalPayroll: float
    totalEmployees: int
    taxesWithheld: float
    benefitsCost: float
    w2sGenerated: int
    quarterlyTaxes: float
    upcomingPayroll: Optional[str] = None
    lastProcessed: Optional[str] = None


# Customer Schemas
class Address(BaseModel):
    street: str
    city: str
    state: str
    zip: str
    country: str = "US"


class CustomerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    legal_name: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    primary_contact_name: Optional[str] = Field(None, max_length=255)
    primary_contact_email: Optional[str] = Field(None, max_length=255)
    primary_contact_phone: Optional[str] = Field(None, max_length=50)
    billing_address: Optional[Address] = None
    shipping_address: Optional[Address] = None
    payment_terms: Optional[str] = Field(None, max_length=50)  # NET_30, NET_15, DUE_ON_RECEIPT, etc.
    credit_limit: Optional[Decimal] = Field(None, ge=0)
    synctera_account_id: Optional[str] = Field(None, max_length=255)
    status: str = Field(default="active", max_length=50)  # active, inactive, suspended


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    legal_name: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    primary_contact_name: Optional[str] = Field(None, max_length=255)
    primary_contact_email: Optional[str] = Field(None, max_length=255)
    primary_contact_phone: Optional[str] = Field(None, max_length=50)
    billing_address: Optional[Address] = None
    shipping_address: Optional[Address] = None
    payment_terms: Optional[str] = Field(None, max_length=50)
    credit_limit: Optional[Decimal] = Field(None, ge=0)
    synctera_account_id: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None


class CustomerResponse(CustomerBase):
    id: str
    company_id: str
    credit_limit_used: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerSummary(BaseModel):
    id: str
    name: str
    total_outstanding: Decimal
    overdue_amount: Decimal
    credit_limit: Optional[Decimal]
    credit_limit_used: Decimal
    status: str

    model_config = {"from_attributes": True}


class CustomersSummaryResponse(BaseModel):
    active_customers: int
    total_ar: Decimal
    overdue_accounts: int
    overdue_amount: Decimal
    credit_limit_usage_percent: float
    total_credit_limit: Decimal
    used_credit_limit: Decimal
    customers: List[CustomerSummary]


# Vendor Schemas
class VendorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    legal_name: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    category: str = Field(default="equipment_maintenance", max_length=50)  # equipment_maintenance, finance_insurance, integrations, facilities_partners
    primary_contact_name: Optional[str] = Field(None, max_length=255)
    primary_contact_email: Optional[str] = Field(None, max_length=255)
    primary_contact_phone: Optional[str] = Field(None, max_length=50)
    address: Optional[Address] = None
    payment_terms: Optional[str] = Field(None, max_length=50)  # NET_30, NET_15, DUE_ON_RECEIPT, etc.
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    contract_value: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    status: str = Field(default="active", max_length=50)  # active, inactive, suspended


class VendorCreate(VendorBase):
    pass


class VendorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    legal_name: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, max_length=50)
    primary_contact_name: Optional[str] = Field(None, max_length=255)
    primary_contact_email: Optional[str] = Field(None, max_length=255)
    primary_contact_phone: Optional[str] = Field(None, max_length=50)
    address: Optional[Address] = None
    payment_terms: Optional[str] = Field(None, max_length=50)
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    contract_value: Optional[Decimal] = Field(None, ge=0)
    outstanding_balance: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None
    status: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None


class VendorResponse(VendorBase):
    id: str
    company_id: str
    outstanding_balance: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VendorsSummaryResponse(BaseModel):
    active_vendors: int
    total_vendors: int
    by_category: Dict[str, int]  # {equipment_maintenance: 5, finance_insurance: 3, ...}
    contracts_expiring_soon: int  # Contracts expiring in 30 days
    total_outstanding: Decimal
    total_contract_value: Decimal


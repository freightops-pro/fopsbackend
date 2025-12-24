"""HQ Admin Portal schemas."""

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


# ============================================================================
# Auth Schemas
# ============================================================================

class HQLoginRequest(BaseModel):
    email: EmailStr
    employee_number: str = Field(..., min_length=1, max_length=10)
    password: str


class HQTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HQSessionUser(BaseModel):
    id: str
    email: EmailStr
    employee_number: str
    first_name: str
    last_name: str
    role: str
    department: Optional[str] = None

    model_config = {"from_attributes": True}


class HQAuthSessionResponse(BaseModel):
    user: HQSessionUser
    access_token: Optional[str] = None


# ============================================================================
# Employee Schemas
# ============================================================================

HQRoleType = Literal["SUPER_ADMIN", "ADMIN", "HR_MANAGER", "SALES_MANAGER", "ACCOUNTANT", "SUPPORT"]


class HQEmployeeBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: HQRoleType = "SUPPORT"
    department: Optional[str] = None
    phone: Optional[str] = None


class HQEmployeeCreate(HQEmployeeBase):
    employee_number: str = Field(..., min_length=1, max_length=10)
    password: str = Field(..., min_length=8)


class HQEmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[HQRoleType] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class HQEmployeeResponse(HQEmployeeBase):
    id: str
    employee_number: str
    is_active: bool
    must_change_password: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Tenant Schemas
# ============================================================================

TenantStatusType = Literal["active", "trial", "suspended", "cancelled"]
SubscriptionTierType = Literal["starter", "professional", "enterprise", "custom"]


class HQTenantBase(BaseModel):
    billing_email: Optional[str] = None
    subscription_tier: SubscriptionTierType = "starter"
    monthly_rate: Optional[Decimal] = None
    notes: Optional[str] = None


class HQTenantCreate(HQTenantBase):
    company_id: str


class HQTenantUpdate(BaseModel):
    status: Optional[TenantStatusType] = None
    subscription_tier: Optional[SubscriptionTierType] = None
    monthly_rate: Optional[Decimal] = None
    billing_email: Optional[str] = None
    notes: Optional[str] = None
    assigned_sales_rep_id: Optional[str] = None


class HQTenantResponse(HQTenantBase):
    id: str
    company_id: str
    status: TenantStatusType
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    subscription_started_at: Optional[datetime] = None
    current_period_ends_at: Optional[datetime] = None
    assigned_sales_rep_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Joined from Company
    company_name: Optional[str] = None
    company_email: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================================
# Contract Schemas
# ============================================================================

ContractStatusType = Literal["draft", "pending_approval", "active", "expired", "terminated", "renewed"]
ContractTypeType = Literal["standard", "enterprise", "custom", "pilot"]


class HQContractBase(BaseModel):
    title: str
    contract_type: ContractTypeType = "standard"
    description: Optional[str] = None
    monthly_value: Decimal
    annual_value: Optional[Decimal] = None
    setup_fee: Decimal = Decimal("0")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    auto_renew: str = "false"
    notice_period_days: str = "30"
    custom_terms: Optional[str] = None


class HQContractCreate(HQContractBase):
    tenant_id: str


class HQContractUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[ContractStatusType] = None
    description: Optional[str] = None
    monthly_value: Optional[Decimal] = None
    annual_value: Optional[Decimal] = None
    setup_fee: Optional[Decimal] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    custom_terms: Optional[str] = None


class HQContractResponse(HQContractBase):
    id: str
    tenant_id: str
    contract_number: str
    status: ContractStatusType
    signed_by_customer: Optional[str] = None
    signed_by_hq: Optional[str] = None
    signed_at: Optional[datetime] = None
    created_by_id: Optional[str] = None
    approved_by_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Quote Schemas
# ============================================================================

QuoteStatusType = Literal["draft", "sent", "viewed", "accepted", "rejected", "expired"]


class HQQuoteBase(BaseModel):
    title: str
    description: Optional[str] = None
    tier: str = "professional"
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_company: Optional[str] = None
    contact_phone: Optional[str] = None
    base_monthly_rate: Decimal
    discount_percent: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    final_monthly_rate: Decimal
    setup_fee: Decimal = Decimal("0")
    addons: Optional[str] = None
    valid_until: Optional[datetime] = None


class HQQuoteCreate(HQQuoteBase):
    tenant_id: Optional[str] = None


class HQQuoteUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[QuoteStatusType] = None
    description: Optional[str] = None
    tier: Optional[str] = None
    base_monthly_rate: Optional[Decimal] = None
    discount_percent: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    final_monthly_rate: Optional[Decimal] = None
    setup_fee: Optional[Decimal] = None
    addons: Optional[str] = None
    valid_until: Optional[datetime] = None


class HQQuoteSend(BaseModel):
    email: EmailStr


class HQQuoteResponse(HQQuoteBase):
    id: str
    tenant_id: Optional[str] = None
    quote_number: str
    status: QuoteStatusType
    sent_at: Optional[datetime] = None
    viewed_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_by_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Credit Schemas
# ============================================================================

CreditTypeType = Literal["promotional", "service_issue", "billing_adjustment", "goodwill", "referral"]
CreditStatusType = Literal["pending", "approved", "rejected", "applied", "expired"]


class HQCreditBase(BaseModel):
    credit_type: CreditTypeType
    amount: Decimal
    reason: str
    internal_notes: Optional[str] = None
    expires_at: Optional[datetime] = None


class HQCreditCreate(HQCreditBase):
    tenant_id: str


class HQCreditApprove(BaseModel):
    pass


class HQCreditReject(BaseModel):
    rejection_reason: str


class HQCreditApply(BaseModel):
    invoice_id: Optional[str] = None


class HQCreditResponse(HQCreditBase):
    id: str
    tenant_id: str
    status: CreditStatusType
    remaining_amount: Decimal
    requested_by_id: str
    approved_by_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_by_id: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    applied_at: Optional[datetime] = None
    applied_to_invoice_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Payout Schemas
# ============================================================================

PayoutStatusType = Literal["pending", "processing", "completed", "failed", "cancelled"]


class HQPayoutBase(BaseModel):
    amount: Decimal
    currency: str = "USD"
    description: Optional[str] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class HQPayoutCreate(HQPayoutBase):
    tenant_id: str


class HQPayoutCancel(BaseModel):
    pass


class HQPayoutResponse(HQPayoutBase):
    id: str
    tenant_id: str
    status: PayoutStatusType
    stripe_payout_id: Optional[str] = None
    stripe_transfer_id: Optional[str] = None
    stripe_destination_account: Optional[str] = None
    initiated_by_id: Optional[str] = None
    initiated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# System Module Schemas
# ============================================================================

ModuleStatusType = Literal["active", "maintenance", "disabled"]


class HQSystemModuleBase(BaseModel):
    key: str
    name: str
    description: Optional[str] = None


class HQSystemModuleUpdate(BaseModel):
    status: Optional[ModuleStatusType] = None
    maintenance_message: Optional[str] = None
    maintenance_end_time: Optional[datetime] = None


class HQSystemModuleResponse(HQSystemModuleBase):
    id: str
    status: ModuleStatusType
    maintenance_message: Optional[str] = None
    maintenance_end_time: Optional[datetime] = None
    last_updated_by_id: Optional[str] = None
    last_updated_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Dashboard Schemas
# ============================================================================

class HQDashboardMetrics(BaseModel):
    active_tenants: int
    trial_tenants: int
    mrr: Decimal
    arr: Decimal
    churn_rate: Decimal
    ltv: Decimal
    pending_payouts_amount: Decimal
    pending_payouts_count: int
    pending_credits_count: int
    expiring_contracts_count: int


class HQRecentTenant(BaseModel):
    id: str
    company_name: str
    status: str
    subscription_tier: str
    created_at: datetime


class HQExpiringContract(BaseModel):
    id: str
    tenant_name: str
    contract_number: str
    end_date: datetime
    monthly_value: Decimal


# ============================================================================
# Banking Admin Schemas (Synctera Integration)
# ============================================================================

BankingCompanyStatusType = Literal["active", "under_review", "frozen", "closed"]
KYBStatusType = Literal["not_started", "pending_review", "approved", "rejected", "requires_info"]
FraudAlertSeverityType = Literal["low", "medium", "high", "critical"]
FraudAlertStatusType = Literal["pending", "investigating", "approved", "blocked", "resolved"]
BankingAuditActionType = Literal[
    "account_frozen", "account_unfrozen", "kyb_approved", "kyb_rejected",
    "fraud_approved", "fraud_blocked", "card_suspended", "card_terminated",
    "payout_initiated", "transfer_approved"
]


class HQBankingCompanyResponse(BaseModel):
    """Company with banking status for HQ admin view."""
    id: str
    tenant_id: str
    company_name: str
    status: BankingCompanyStatusType
    kyb_status: KYBStatusType
    synctera_business_id: Optional[str] = None
    synctera_customer_id: Optional[str] = None
    account_count: int = 0
    card_count: int = 0
    total_balance: Decimal = Decimal("0")
    available_balance: Decimal = Decimal("0")
    fraud_alert_count: int = 0
    last_activity_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class HQFraudAlertResponse(BaseModel):
    """Fraud alert from Synctera for HQ review."""
    id: str
    company_id: str
    company_name: str
    alert_type: str
    amount: Decimal
    description: Optional[str] = None
    severity: FraudAlertSeverityType
    status: FraudAlertStatusType
    transaction_id: Optional[str] = None
    card_id: Optional[str] = None
    account_id: Optional[str] = None
    synctera_alert_id: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HQBankingAuditLogResponse(BaseModel):
    """Audit log entry for banking admin actions."""
    id: str
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    action: BankingAuditActionType
    description: str
    performed_by: str
    performed_by_name: str
    ip_address: Optional[str] = None
    action_metadata: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class HQBankingOverviewStats(BaseModel):
    """Banking overview statistics for HQ dashboard."""
    total_companies: int
    active_companies: int
    frozen_companies: int
    pending_kyb: int
    total_balance: Decimal
    pending_fraud_alerts: int
    fraud_alerts_today: int


class HQFraudAlertResolve(BaseModel):
    """Request to resolve a fraud alert."""
    resolution_notes: Optional[str] = None


# ============================================================================
# Accounting - Customer (A/R) Schemas
# ============================================================================

CustomerStatusType = Literal["active", "inactive", "suspended"]
CustomerTypeType = Literal["tenant", "partner", "enterprise", "other"]


class HQCustomerBase(BaseModel):
    """HQ customer for accounts receivable."""
    name: str
    customer_type: CustomerTypeType = "tenant"
    email: Optional[str] = None
    phone: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_zip: Optional[str] = None
    billing_country: str = "US"
    tax_id: Optional[str] = None
    payment_terms_days: int = 30
    credit_limit: Optional[Decimal] = None
    notes: Optional[str] = None


class HQCustomerCreate(HQCustomerBase):
    tenant_id: Optional[str] = None  # Link to HQTenant if applicable


class HQCustomerUpdate(BaseModel):
    name: Optional[str] = None
    customer_type: Optional[CustomerTypeType] = None
    status: Optional[CustomerStatusType] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_zip: Optional[str] = None
    payment_terms_days: Optional[int] = None
    credit_limit: Optional[Decimal] = None
    notes: Optional[str] = None


class HQCustomerResponse(HQCustomerBase):
    id: str
    tenant_id: Optional[str] = None
    customer_number: str
    status: CustomerStatusType
    outstanding_balance: Decimal = Decimal("0")
    total_invoiced: Decimal = Decimal("0")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Accounting - Invoice (A/R) Schemas
# ============================================================================

InvoiceStatusType = Literal["draft", "sent", "viewed", "paid", "partial", "overdue", "cancelled", "void"]
InvoiceTypeType = Literal["subscription", "service", "setup_fee", "credit_note", "other"]


class HQInvoiceLineItem(BaseModel):
    """Line item for an invoice."""
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal
    amount: Decimal
    tax_rate: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")


class HQInvoiceBase(BaseModel):
    """HQ invoice for accounts receivable."""
    customer_id: str
    invoice_type: InvoiceTypeType = "subscription"
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    line_items: List[HQInvoiceLineItem] = []
    subtotal: Decimal
    tax_total: Decimal = Decimal("0")
    total: Decimal
    notes: Optional[str] = None
    terms: Optional[str] = None


class HQInvoiceCreate(HQInvoiceBase):
    tenant_id: Optional[str] = None
    contract_id: Optional[str] = None


class HQInvoiceUpdate(BaseModel):
    status: Optional[InvoiceStatusType] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None


class HQInvoiceResponse(HQInvoiceBase):
    id: str
    tenant_id: Optional[str] = None
    contract_id: Optional[str] = None
    invoice_number: str
    status: InvoiceStatusType
    issued_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    paid_amount: Decimal = Decimal("0")
    balance_due: Decimal
    stripe_invoice_id: Optional[str] = None
    created_by_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Joined fields
    customer_name: Optional[str] = None
    tenant_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================================
# Accounting - Vendor (A/P) Schemas
# ============================================================================

VendorStatusType = Literal["active", "inactive", "pending_approval"]
VendorTypeType = Literal["service", "supplier", "contractor", "utility", "other"]


class HQVendorBase(BaseModel):
    """HQ vendor for accounts payable."""
    name: str
    vendor_type: VendorTypeType = "service"
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: str = "US"
    tax_id: Optional[str] = None
    payment_terms_days: int = 30
    default_expense_account: Optional[str] = None
    bank_account_info: Optional[str] = None
    notes: Optional[str] = None


class HQVendorCreate(HQVendorBase):
    pass


class HQVendorUpdate(BaseModel):
    name: Optional[str] = None
    vendor_type: Optional[VendorTypeType] = None
    status: Optional[VendorStatusType] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    payment_terms_days: Optional[int] = None
    default_expense_account: Optional[str] = None
    notes: Optional[str] = None


class HQVendorResponse(HQVendorBase):
    id: str
    vendor_number: str
    status: VendorStatusType
    outstanding_balance: Decimal = Decimal("0")
    total_paid: Decimal = Decimal("0")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================================
# Accounting - Bill (A/P) Schemas
# ============================================================================

BillStatusType = Literal["draft", "pending_approval", "approved", "paid", "partial", "overdue", "cancelled", "void"]
BillTypeType = Literal["expense", "service", "utility", "subscription", "other"]


class HQBillLineItem(BaseModel):
    """Line item for a bill."""
    description: str
    quantity: Decimal = Decimal("1")
    unit_price: Decimal
    amount: Decimal
    expense_account: Optional[str] = None


class HQBillBase(BaseModel):
    """HQ bill for accounts payable."""
    vendor_id: str
    bill_type: BillTypeType = "expense"
    vendor_invoice_number: Optional[str] = None
    description: Optional[str] = None
    bill_date: datetime
    due_date: Optional[datetime] = None
    line_items: List[HQBillLineItem] = []
    subtotal: Decimal
    tax_total: Decimal = Decimal("0")
    total: Decimal
    notes: Optional[str] = None


class HQBillCreate(HQBillBase):
    pass


class HQBillUpdate(BaseModel):
    status: Optional[BillStatusType] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None


class HQBillApprove(BaseModel):
    pass


class HQBillResponse(HQBillBase):
    id: str
    bill_number: str
    status: BillStatusType
    approved_by_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    paid_amount: Decimal = Decimal("0")
    balance_due: Decimal
    created_by_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Joined fields
    vendor_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================================
# Accounting - Payment Schemas
# ============================================================================

PaymentTypeType = Literal["check", "ach", "wire", "credit_card", "other"]
PaymentDirectionType = Literal["incoming", "outgoing"]


class HQPaymentBase(BaseModel):
    """Payment record for tracking A/R and A/P payments."""
    payment_type: PaymentTypeType
    direction: PaymentDirectionType
    amount: Decimal
    payment_date: datetime
    reference_number: Optional[str] = None
    notes: Optional[str] = None


class HQPaymentCreate(HQPaymentBase):
    invoice_id: Optional[str] = None  # For incoming payments
    bill_id: Optional[str] = None  # For outgoing payments


class HQPaymentResponse(HQPaymentBase):
    id: str
    invoice_id: Optional[str] = None
    bill_id: Optional[str] = None
    payment_number: str
    stripe_payment_id: Optional[str] = None
    synctera_transaction_id: Optional[str] = None
    recorded_by_id: Optional[str] = None
    created_at: datetime
    # Joined fields
    customer_name: Optional[str] = None
    vendor_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================================
# Accounting Dashboard Schemas
# ============================================================================

class HQAccountingDashboard(BaseModel):
    """Accounting dashboard metrics."""
    # A/R Metrics
    total_outstanding_ar: Decimal
    ar_current: Decimal
    ar_30_days: Decimal
    ar_60_days: Decimal
    ar_90_plus_days: Decimal
    pending_invoices_count: int
    overdue_invoices_count: int
    # A/P Metrics
    total_outstanding_ap: Decimal
    ap_current: Decimal
    ap_30_days: Decimal
    ap_60_days: Decimal
    ap_90_plus_days: Decimal
    pending_bills_count: int
    overdue_bills_count: int
    # Cash Flow
    expected_collections_30_days: Decimal
    expected_payments_30_days: Decimal


# ============================================================================
# HR & Payroll Schemas (Check Integration)
# ============================================================================

EmploymentType = Literal["full_time", "part_time", "contractor", "intern"]
EmployeeStatusType = Literal["active", "terminated", "on_leave", "onboarding"]
PayFrequency = Literal["weekly", "biweekly", "semimonthly", "monthly"]


class HQHREmployeeBase(BaseModel):
    """HQ employee for HR/Payroll (different from HQEmployee admin users)."""
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    employment_type: EmploymentType = "full_time"
    department: Optional[str] = None
    job_title: Optional[str] = None
    manager_id: Optional[str] = None
    hire_date: Optional[datetime] = None
    pay_frequency: PayFrequency = "biweekly"
    annual_salary: Optional[Decimal] = None
    hourly_rate: Optional[Decimal] = None
    # Address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


class HQHREmployeeCreate(HQHREmployeeBase):
    ssn_last_four: Optional[str] = None  # Last 4 for verification only
    date_of_birth: Optional[datetime] = None


class HQHREmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    employment_type: Optional[EmploymentType] = None
    status: Optional[EmployeeStatusType] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    manager_id: Optional[str] = None
    pay_frequency: Optional[PayFrequency] = None
    annual_salary: Optional[Decimal] = None
    hourly_rate: Optional[Decimal] = None


class HQHREmployeeResponse(HQHREmployeeBase):
    id: str
    employee_number: str
    status: EmployeeStatusType
    check_employee_id: Optional[str] = None  # Check payroll ID
    termination_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Joined fields
    manager_name: Optional[str] = None

    model_config = {"from_attributes": True}


class HQPayrollRunBase(BaseModel):
    """Payroll run for processing employee payments."""
    pay_period_start: datetime
    pay_period_end: datetime
    pay_date: datetime
    description: Optional[str] = None


PayrollStatusType = Literal["draft", "pending_approval", "approved", "processing", "completed", "failed", "cancelled"]


class HQPayrollRunCreate(HQPayrollRunBase):
    employee_ids: Optional[List[str]] = None  # If None, all active employees


class HQPayrollRunResponse(HQPayrollRunBase):
    id: str
    payroll_number: str
    status: PayrollStatusType
    check_payroll_id: Optional[str] = None  # Check payroll ID
    total_gross: Decimal = Decimal("0")
    total_taxes: Decimal = Decimal("0")
    total_deductions: Decimal = Decimal("0")
    total_net: Decimal = Decimal("0")
    employee_count: int = 0
    approved_by_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    created_by_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HQPayrollItemResponse(BaseModel):
    """Individual employee payroll item within a payroll run."""
    id: str
    payroll_run_id: str
    employee_id: str
    employee_name: str
    gross_pay: Decimal
    federal_tax: Decimal = Decimal("0")
    state_tax: Decimal = Decimal("0")
    social_security: Decimal = Decimal("0")
    medicare: Decimal = Decimal("0")
    other_deductions: Decimal = Decimal("0")
    net_pay: Decimal
    hours_worked: Optional[Decimal] = None
    overtime_hours: Optional[Decimal] = None
    check_paystub_id: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================================
# HQ Colab AI Schemas
# ============================================================================

HQAgentType = Literal["oracle", "sentinel", "nexus"]


class HQColabChatRequest(BaseModel):
    """Request to chat with HQ AI agents."""
    session_id: str
    agent: HQAgentType
    message: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None


class HQColabChatResponse(BaseModel):
    """Response from HQ AI agent."""
    response: str
    agent: HQAgentType
    reasoning: Optional[str] = None
    tools_used: Optional[List[str]] = None
    confidence: Optional[float] = None
    task_id: Optional[str] = None


class HQColabInitRequest(BaseModel):
    """Initialize an HQ Colab chat session."""
    session_id: str
    agent: HQAgentType
    user_id: Optional[str] = None
    user_name: Optional[str] = None


class HQColabInitResponse(BaseModel):
    """Response from initializing HQ Colab chat."""
    message: str
    agent: HQAgentType


# ============================================================================
# General Ledger Schemas
# ============================================================================

AccountTypeType = Literal["asset", "liability", "equity", "revenue", "cost_of_revenue", "expense"]
AccountSubtypeType = Literal[
    "cash", "accounts_receivable", "prepaid_expense", "fixed_asset",
    "accounts_payable", "credit_card", "deferred_revenue", "payroll_liability",
    "retained_earnings", "owner_equity",
    "saas_revenue", "service_revenue", "other_income",
    "ai_compute", "hosting", "payment_processing",
    "payroll", "marketing", "software", "professional_services", "office", "other_expense"
]
JournalEntryStatusType = Literal["draft", "posted", "void"]


class HQChartOfAccountsBase(BaseModel):
    """Chart of Accounts entry."""
    account_number: str
    account_name: str
    account_type: AccountTypeType
    account_subtype: Optional[AccountSubtypeType] = None
    description: Optional[str] = None
    parent_account_id: Optional[str] = None


class HQChartOfAccountsCreate(HQChartOfAccountsBase):
    is_system: bool = False


class HQChartOfAccountsUpdate(BaseModel):
    account_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class HQChartOfAccountsResponse(HQChartOfAccountsBase):
    id: str
    is_active: bool
    is_system: bool
    current_balance: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HQJournalEntryLineCreate(BaseModel):
    """Single line in a journal entry."""
    account_number: str
    amount: Decimal
    is_debit: bool
    memo: Optional[str] = None
    tenant_id: Optional[str] = None


class HQJournalEntryCreate(BaseModel):
    """Create a journal entry with lines."""
    description: str
    lines: List[HQJournalEntryLineCreate]
    transaction_date: Optional[datetime] = None
    reference: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    tenant_id: Optional[str] = None
    auto_post: bool = False


class HQJournalEntryResponse(BaseModel):
    """Journal entry with lines."""
    id: str
    entry_number: str
    reference: Optional[str] = None
    transaction_date: datetime
    description: str
    status: JournalEntryStatusType
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    tenant_id: Optional[str] = None
    total_debits: Decimal
    total_credits: Decimal
    created_by_id: Optional[str] = None
    posted_by_id: Optional[str] = None
    posted_at: Optional[datetime] = None
    voided_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HQGLEntryResponse(BaseModel):
    """General Ledger entry line."""
    id: str
    journal_entry_id: str
    debit_account_id: Optional[str] = None
    credit_account_id: Optional[str] = None
    amount: Decimal
    memo: Optional[str] = None
    tenant_id: Optional[str] = None
    created_at: datetime
    # Joined fields
    account_number: Optional[str] = None
    account_name: Optional[str] = None

    model_config = {"from_attributes": True}


class HQAccountBalance(BaseModel):
    """Account balance summary."""
    account_id: str
    account_number: str
    account_name: str
    account_type: AccountTypeType
    debit_total: Decimal
    credit_total: Decimal
    balance: Decimal


# ============================================================================
# Financial Reports Schemas
# ============================================================================

class HQProfitLossReport(BaseModel):
    """Monthly P&L report."""
    period_start: datetime
    period_end: datetime
    revenue: dict  # account_name: amount
    cost_of_revenue: dict
    expenses: dict
    total_revenue: Decimal
    total_cogs: Decimal
    gross_profit: Decimal
    gross_margin_percent: Decimal
    total_expenses: Decimal
    net_income: Decimal
    tenant_breakdown: Optional[dict] = None


class HQBalanceSheetReport(BaseModel):
    """Balance sheet report."""
    as_of_date: datetime
    assets: dict
    liabilities: dict
    equity: dict
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal


class HQTenantProfitMargin(BaseModel):
    """Per-tenant profit margin analysis."""
    tenant_id: str
    tenant_name: Optional[str] = None
    revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    gross_margin_percent: Decimal


# ============================================================================
# Usage Metering Schemas (AI COGS)
# ============================================================================

UsageMetricTypeType = Literal[
    "active_trucks", "active_drivers", "payroll_employees",
    "ai_tokens_used", "ai_requests", "storage_gb", "api_calls"
]


class HQUsageLogCreate(BaseModel):
    """Log AI or resource usage."""
    tenant_id: str
    metric_type: UsageMetricTypeType
    metric_value: Decimal
    unit_cost: Optional[Decimal] = None
    ai_metadata: Optional[dict] = None


class HQUsageLogResponse(BaseModel):
    """Usage log entry."""
    id: str
    tenant_id: str
    metric_type: UsageMetricTypeType
    metric_value: Decimal
    unit_cost: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None
    ai_metadata: Optional[dict] = None
    recorded_at: datetime
    created_at: datetime
    # Joined
    tenant_name: Optional[str] = None

    model_config = {"from_attributes": True}


class HQAIUsageLogRequest(BaseModel):
    """Request to log AI usage."""
    tenant_id: str
    model: str
    input_tokens: int
    output_tokens: int


class HQAICostsByTenant(BaseModel):
    """AI costs aggregated by tenant."""
    tenant_id: str
    tenant_name: Optional[str] = None
    request_count: int
    total_tokens: int
    total_cost: Decimal


class HQGLDashboard(BaseModel):
    """General Ledger dashboard metrics."""
    # Balance Sheet Summary
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    cash_balance: Decimal
    accounts_receivable: Decimal
    accounts_payable: Decimal
    # P&L Summary (current month)
    current_month_revenue: Decimal
    current_month_cogs: Decimal
    current_month_gross_profit: Decimal
    current_month_expenses: Decimal
    current_month_net_income: Decimal
    # AI COGS breakdown
    ai_costs_mtd: Decimal
    ai_costs_by_model: dict
    # Metrics
    gross_margin_percent: Decimal
    accounts_count: int
    posted_entries_count: int

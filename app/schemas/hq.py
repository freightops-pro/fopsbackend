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

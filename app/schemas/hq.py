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
    first_name: str = Field(alias="firstName", serialization_alias="firstName")
    last_name: str = Field(alias="lastName", serialization_alias="lastName")
    role: HQRoleType = "SUPPORT"
    department: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    hire_date: Optional[datetime] = Field(None, alias="hireDate", serialization_alias="hireDate")
    salary: Optional[int] = None
    emergency_contact: Optional[str] = Field(None, alias="emergencyContact", serialization_alias="emergencyContact")
    emergency_phone: Optional[str] = Field(None, alias="emergencyPhone", serialization_alias="emergencyPhone")

    model_config = {"populate_by_name": True}


class HQEmployeeCreate(HQEmployeeBase):
    employee_number: str = Field(..., min_length=1, max_length=10, alias="employeeNumber", serialization_alias="employeeNumber")
    password: str = Field(..., min_length=8)


class HQEmployeeUpdate(BaseModel):
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    role: Optional[HQRoleType] = None
    department: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    hire_date: Optional[datetime] = Field(None, alias="hireDate")
    salary: Optional[int] = None
    emergency_contact: Optional[str] = Field(None, alias="emergencyContact")
    emergency_phone: Optional[str] = Field(None, alias="emergencyPhone")
    is_active: Optional[bool] = Field(None, alias="isActive")

    model_config = {"populate_by_name": True}


class HQEmployeeResponse(BaseModel):
    id: str
    employee_number: str = Field(alias="employeeNumber", serialization_alias="employeeNumber")
    email: EmailStr
    first_name: str = Field(alias="firstName", serialization_alias="firstName")
    last_name: str = Field(alias="lastName", serialization_alias="lastName")
    role: HQRoleType
    department: Optional[str] = None
    title: Optional[str] = None
    phone: Optional[str] = None
    hire_date: Optional[datetime] = Field(None, alias="hireDate", serialization_alias="hireDate")
    salary: Optional[int] = None
    emergency_contact: Optional[str] = Field(None, alias="emergencyContact", serialization_alias="emergencyContact")
    emergency_phone: Optional[str] = Field(None, alias="emergencyPhone", serialization_alias="emergencyPhone")
    is_active: bool = Field(alias="isActive", serialization_alias="isActive")
    must_change_password: bool = Field(alias="mustChangePassword", serialization_alias="mustChangePassword")
    last_login_at: Optional[datetime] = Field(None, alias="lastLoginAt", serialization_alias="lastLoginAt")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


# ============================================================================
# Tenant Schemas
# ============================================================================

TenantStatusType = Literal["active", "trial", "suspended", "cancelled", "churned", "pending_setup"]
SubscriptionTierType = Literal["starter", "professional", "enterprise", "custom"]


class AddressResponse(BaseModel):
    """Address nested in tenant response."""
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None


class HQTenantBase(BaseModel):
    billing_email: Optional[str] = Field(None, alias="billingEmail", serialization_alias="billingEmail")
    subscription_tier: SubscriptionTierType = Field("starter", alias="subscriptionTier", serialization_alias="subscriptionTier")
    monthly_fee: Optional[Decimal] = Field(None, alias="monthlyFee", serialization_alias="monthlyFee")
    setup_fee: Optional[Decimal] = Field(Decimal("0"), alias="setupFee", serialization_alias="setupFee")
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQTenantCreate(BaseModel):
    """Schema for creating a tenant with company - matches frontend form."""
    company_name: str = Field(..., alias="companyName")
    legal_name: Optional[str] = Field(None, alias="legalName")
    tax_id: Optional[str] = Field(None, alias="taxId")
    dot_number: Optional[str] = Field(None, alias="dotNumber")
    mc_number: Optional[str] = Field(None, alias="mcNumber")
    subscription_tier: SubscriptionTierType = Field("starter", alias="subscriptionTier")
    monthly_fee: Decimal = Field(..., alias="monthlyFee")
    setup_fee: Optional[Decimal] = Field(Decimal("0"), alias="setupFee")
    subscription_start_date: Optional[str] = Field(None, alias="subscriptionStartDate")
    primary_contact_name: Optional[str] = Field(None, alias="primaryContactName")
    primary_contact_email: Optional[str] = Field(None, alias="primaryContactEmail")
    primary_contact_phone: Optional[str] = Field(None, alias="primaryContactPhone")
    billing_email: Optional[str] = Field(None, alias="billingEmail")
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQTenantUpdate(BaseModel):
    status: Optional[TenantStatusType] = None
    subscription_tier: Optional[SubscriptionTierType] = Field(None, alias="subscriptionTier")
    monthly_fee: Optional[Decimal] = Field(None, alias="monthlyFee")
    setup_fee: Optional[Decimal] = Field(None, alias="setupFee")
    billing_email: Optional[str] = Field(None, alias="billingEmail")
    notes: Optional[str] = None
    assigned_sales_rep_id: Optional[str] = Field(None, alias="assignedSalesRepId")

    model_config = {"populate_by_name": True}


class HQTenantResponse(BaseModel):
    """Full tenant response with company data - matches frontend Tenant type."""
    id: str
    company_name: str = Field(alias="companyName", serialization_alias="companyName")
    legal_name: Optional[str] = Field(None, alias="legalName", serialization_alias="legalName")
    tax_id: Optional[str] = Field(None, alias="taxId", serialization_alias="taxId")
    dot_number: Optional[str] = Field(None, alias="dotNumber", serialization_alias="dotNumber")
    mc_number: Optional[str] = Field(None, alias="mcNumber", serialization_alias="mcNumber")
    status: TenantStatusType
    subscription_tier: SubscriptionTierType = Field(alias="subscriptionTier", serialization_alias="subscriptionTier")
    subscription_start_date: Optional[datetime] = Field(None, alias="subscriptionStartDate", serialization_alias="subscriptionStartDate")
    subscription_end_date: Optional[datetime] = Field(None, alias="subscriptionEndDate", serialization_alias="subscriptionEndDate")
    monthly_fee: Decimal = Field(Decimal("0"), alias="monthlyFee", serialization_alias="monthlyFee")
    setup_fee: Decimal = Field(Decimal("0"), alias="setupFee", serialization_alias="setupFee")
    primary_contact_name: Optional[str] = Field(None, alias="primaryContactName", serialization_alias="primaryContactName")
    primary_contact_email: Optional[str] = Field(None, alias="primaryContactEmail", serialization_alias="primaryContactEmail")
    primary_contact_phone: Optional[str] = Field(None, alias="primaryContactPhone", serialization_alias="primaryContactPhone")
    billing_email: Optional[str] = Field(None, alias="billingEmail", serialization_alias="billingEmail")
    address: Optional[AddressResponse] = None
    total_users: int = Field(0, alias="totalUsers", serialization_alias="totalUsers")
    active_users: int = Field(0, alias="activeUsers", serialization_alias="activeUsers")
    stripe_customer_id: Optional[str] = Field(None, alias="stripeCustomerId", serialization_alias="stripeCustomerId")
    stripe_subscription_id: Optional[str] = Field(None, alias="stripeSubscriptionId", serialization_alias="stripeSubscriptionId")
    notes: Optional[str] = None
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class TenantUsageMetrics(BaseModel):
    """Usage metrics for a tenant."""
    ocr_calls: int = Field(0, alias="ocrCalls", serialization_alias="ocrCalls")
    chat_calls: int = Field(0, alias="chatCalls", serialization_alias="chatCalls")
    audit_calls: int = Field(0, alias="auditCalls", serialization_alias="auditCalls")
    total_api_calls: int = Field(0, alias="totalApiCalls", serialization_alias="totalApiCalls")
    tokens_used: int = Field(0, alias="tokensUsed", serialization_alias="tokensUsed")
    estimated_cost: Decimal = Field(Decimal("0"), alias="estimatedCost", serialization_alias="estimatedCost")

    model_config = {"populate_by_name": True}


class TenantFleetMetrics(BaseModel):
    """Fleet metrics for a tenant."""
    total_trucks: int = Field(0, alias="totalTrucks", serialization_alias="totalTrucks")
    active_trucks: int = Field(0, alias="activeTrucks", serialization_alias="activeTrucks")
    total_trailers: int = Field(0, alias="totalTrailers", serialization_alias="totalTrailers")
    active_trailers: int = Field(0, alias="activeTrailers", serialization_alias="activeTrailers")
    total_drivers: int = Field(0, alias="totalDrivers", serialization_alias="totalDrivers")
    active_drivers: int = Field(0, alias="activeDrivers", serialization_alias="activeDrivers")

    model_config = {"populate_by_name": True}


class TenantDispatchMetrics(BaseModel):
    """Dispatch metrics for a tenant."""
    total_loads: int = Field(0, alias="totalLoads", serialization_alias="totalLoads")
    completed_loads: int = Field(0, alias="completedLoads", serialization_alias="completedLoads")
    in_transit_loads: int = Field(0, alias="inTransitLoads", serialization_alias="inTransitLoads")
    pending_loads: int = Field(0, alias="pendingLoads", serialization_alias="pendingLoads")
    total_revenue: Decimal = Field(Decimal("0"), alias="totalRevenue", serialization_alias="totalRevenue")
    avg_load_value: Decimal = Field(Decimal("0"), alias="avgLoadValue", serialization_alias="avgLoadValue")

    model_config = {"populate_by_name": True}


class TenantCostBreakdown(BaseModel):
    """Cost breakdown for a tenant."""
    base_subscription: Decimal = Field(Decimal("0"), alias="baseSubscription", serialization_alias="baseSubscription")
    per_truck_cost: Decimal = Field(Decimal("0"), alias="perTruckCost", serialization_alias="perTruckCost")
    per_driver_cost: Decimal = Field(Decimal("0"), alias="perDriverCost", serialization_alias="perDriverCost")
    api_usage_cost: Decimal = Field(Decimal("0"), alias="apiUsageCost", serialization_alias="apiUsageCost")
    total_monthly_cost: Decimal = Field(Decimal("0"), alias="totalMonthlyCost", serialization_alias="totalMonthlyCost")

    model_config = {"populate_by_name": True}


class HQTenantDetailResponse(HQTenantResponse):
    """Detailed tenant response with full metrics."""
    fleet: TenantFleetMetrics = Field(default_factory=TenantFleetMetrics)
    dispatch: TenantDispatchMetrics = Field(default_factory=TenantDispatchMetrics)
    usage: TenantUsageMetrics = Field(default_factory=TenantUsageMetrics)
    cost_breakdown: TenantCostBreakdown = Field(default_factory=TenantCostBreakdown, alias="costBreakdown", serialization_alias="costBreakdown")

    model_config = {"from_attributes": True, "populate_by_name": True}


# ============================================================================
# Contract Schemas
# ============================================================================

ContractStatusType = Literal["draft", "pending_approval", "active", "expired", "terminated", "renewed"]
ContractTypeType = Literal["standard", "enterprise", "custom", "pilot"]


class HQContractBase(BaseModel):
    title: str
    contract_type: ContractTypeType = Field("standard", alias="type", serialization_alias="type")
    description: Optional[str] = None
    monthly_value: Decimal = Field(alias="monthlyFee", serialization_alias="monthlyFee")
    annual_value: Optional[Decimal] = Field(None, alias="annualValue", serialization_alias="annualValue")
    setup_fee: Decimal = Field(Decimal("0"), alias="setupFee", serialization_alias="setupFee")
    start_date: Optional[datetime] = Field(None, alias="startDate", serialization_alias="startDate")
    end_date: Optional[datetime] = Field(None, alias="endDate", serialization_alias="endDate")
    auto_renew: str = Field("false", alias="autoRenew", serialization_alias="autoRenew")
    notice_period_days: str = Field("30", alias="noticePeriodDays", serialization_alias="noticePeriodDays")
    custom_terms: Optional[str] = Field(None, alias="customTerms", serialization_alias="customTerms")

    model_config = {"populate_by_name": True}


class HQContractCreate(HQContractBase):
    tenant_id: str = Field(alias="tenantId")


class HQContractUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[ContractStatusType] = None
    description: Optional[str] = None
    monthly_value: Optional[Decimal] = Field(None, alias="monthlyFee")
    annual_value: Optional[Decimal] = Field(None, alias="annualValue")
    setup_fee: Optional[Decimal] = Field(None, alias="setupFee")
    start_date: Optional[datetime] = Field(None, alias="startDate")
    end_date: Optional[datetime] = Field(None, alias="endDate")
    custom_terms: Optional[str] = Field(None, alias="customTerms")

    model_config = {"populate_by_name": True}


class HQContractResponse(HQContractBase):
    id: str
    tenant_id: str = Field(alias="tenantId", serialization_alias="tenantId")
    tenant_name: Optional[str] = Field(None, alias="tenantName", serialization_alias="tenantName")
    contract_number: str = Field(alias="contractNumber", serialization_alias="contractNumber")
    status: ContractStatusType
    signed_by_customer: Optional[str] = Field(None, alias="signedByCustomer", serialization_alias="signedByCustomer")
    signed_by_hq: Optional[str] = Field(None, alias="signedByHQ", serialization_alias="signedByHQ")
    signed_at: Optional[datetime] = Field(None, alias="signedAt", serialization_alias="signedAt")
    created_by_id: Optional[str] = Field(None, alias="createdBy", serialization_alias="createdBy")
    approved_by_id: Optional[str] = Field(None, alias="approvedBy", serialization_alias="approvedBy")
    approved_at: Optional[datetime] = Field(None, alias="approvedAt", serialization_alias="approvedAt")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


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


class HQCreditCreateForTenant(HQCreditBase):
    """Schema for creating credit via /tenants/{tenant_id}/credits endpoint.

    tenant_id is not required in body since it comes from URL path parameter.
    """
    pass


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
    """Dashboard metrics matching frontend HQDashboardMetrics type."""
    total_tenants: int = Field(0, alias="totalTenants", serialization_alias="totalTenants")
    active_tenants: int = Field(0, alias="activeTenants", serialization_alias="activeTenants")
    trial_tenants: int = Field(0, alias="trialTenants", serialization_alias="trialTenants")
    churned_tenants: int = Field(0, alias="churnedTenants", serialization_alias="churnedTenants")
    mrr: Decimal = Field(Decimal("0"), serialization_alias="mrr")
    arr: Decimal = Field(Decimal("0"), serialization_alias="arr")
    mrr_growth: Decimal = Field(Decimal("0"), alias="mrrGrowth", serialization_alias="mrrGrowth")
    pending_payouts: int = Field(0, alias="pendingPayouts", serialization_alias="pendingPayouts")
    pending_payout_amount: Decimal = Field(Decimal("0"), alias="pendingPayoutAmount", serialization_alias="pendingPayoutAmount")
    open_contracts: int = Field(0, alias="openContracts", serialization_alias="openContracts")
    expiring_contracts: int = Field(0, alias="expiringContracts", serialization_alias="expiringContracts")
    pending_quotes: int = Field(0, alias="pendingQuotes", serialization_alias="pendingQuotes")
    total_credits_outstanding: Decimal = Field(Decimal("0"), alias="totalCreditsOutstanding", serialization_alias="totalCreditsOutstanding")
    hq_employee_count: int = Field(0, alias="hqEmployeeCount", serialization_alias="hqEmployeeCount")

    model_config = {"populate_by_name": True}


class HQRecentTenant(BaseModel):
    id: str
    company_name: str = Field(alias="companyName", serialization_alias="companyName")
    status: str
    subscription_tier: str = Field(alias="subscriptionTier", serialization_alias="subscriptionTier")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")

    model_config = {"populate_by_name": True}


class HQExpiringContract(BaseModel):
    id: str
    tenant_name: str = Field(alias="tenantName", serialization_alias="tenantName")
    contract_number: str = Field(alias="contractNumber", serialization_alias="contractNumber")
    end_date: datetime = Field(alias="endDate", serialization_alias="endDate")
    monthly_value: Decimal = Field(alias="monthlyValue", serialization_alias="monthlyValue")

    model_config = {"populate_by_name": True}


# ============================================================================
# CRM Lead Schemas
# ============================================================================

LeadStatusType = Literal["new", "contacted", "qualified", "unqualified", "converted"]
LeadSourceType = Literal["referral", "website", "cold_call", "partner", "trade_show", "linkedin", "fmcsa", "other"]


class HQLeadBase(BaseModel):
    company_name: str = Field(alias="companyName", serialization_alias="companyName")
    contact_name: Optional[str] = Field(None, alias="contactName", serialization_alias="contactName")
    contact_email: Optional[str] = Field(None, alias="contactEmail", serialization_alias="contactEmail")
    contact_phone: Optional[str] = Field(None, alias="contactPhone", serialization_alias="contactPhone")
    contact_title: Optional[str] = Field(None, alias="contactTitle", serialization_alias="contactTitle")
    source: LeadSourceType = "other"
    estimated_mrr: Optional[Decimal] = Field(None, alias="estimatedMrr", serialization_alias="estimatedMrr")
    estimated_trucks: Optional[str] = Field(None, alias="estimatedTrucks", serialization_alias="estimatedTrucks")
    estimated_drivers: Optional[str] = Field(None, alias="estimatedDrivers", serialization_alias="estimatedDrivers")
    next_follow_up_date: Optional[datetime] = Field(None, alias="nextFollowUpDate", serialization_alias="nextFollowUpDate")
    notes: Optional[str] = None
    # FMCSA data
    state: Optional[str] = None
    dot_number: Optional[str] = Field(None, alias="dotNumber", serialization_alias="dotNumber")
    mc_number: Optional[str] = Field(None, alias="mcNumber", serialization_alias="mcNumber")
    carrier_type: Optional[str] = Field(None, alias="carrierType", serialization_alias="carrierType")
    cargo_types: Optional[str] = Field(None, alias="cargoTypes", serialization_alias="cargoTypes")

    model_config = {"populate_by_name": True}


class HQLeadCreate(HQLeadBase):
    assigned_sales_rep_id: Optional[str] = Field(None, alias="assignedSalesRepId", serialization_alias="assignedSalesRepId")


class HQLeadUpdate(BaseModel):
    company_name: Optional[str] = Field(None, alias="companyName")
    contact_name: Optional[str] = Field(None, alias="contactName")
    contact_email: Optional[str] = Field(None, alias="contactEmail")
    contact_phone: Optional[str] = Field(None, alias="contactPhone")
    contact_title: Optional[str] = Field(None, alias="contactTitle")
    source: Optional[LeadSourceType] = None
    status: Optional[LeadStatusType] = None
    estimated_mrr: Optional[Decimal] = Field(None, alias="estimatedMrr")
    estimated_trucks: Optional[str] = Field(None, alias="estimatedTrucks")
    estimated_drivers: Optional[str] = Field(None, alias="estimatedDrivers")
    assigned_sales_rep_id: Optional[str] = Field(None, alias="assignedSalesRepId")
    next_follow_up_date: Optional[datetime] = Field(None, alias="nextFollowUpDate")
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQLeadResponse(HQLeadBase):
    id: str
    lead_number: str = Field(alias="leadNumber", serialization_alias="leadNumber")
    status: LeadStatusType
    assigned_sales_rep_id: Optional[str] = Field(None, alias="assignedSalesRepId", serialization_alias="assignedSalesRepId")
    assigned_sales_rep_name: Optional[str] = Field(None, alias="assignedSalesRepName", serialization_alias="assignedSalesRepName")
    last_contacted_at: Optional[datetime] = Field(None, alias="lastContactedAt", serialization_alias="lastContactedAt")
    converted_to_opportunity_id: Optional[str] = Field(None, alias="convertedToOpportunityId", serialization_alias="convertedToOpportunityId")
    converted_at: Optional[datetime] = Field(None, alias="convertedAt", serialization_alias="convertedAt")
    created_by_id: Optional[str] = Field(None, alias="createdById", serialization_alias="createdById")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class HQLeadConvert(BaseModel):
    """Convert lead to opportunity."""
    title: str
    estimated_mrr: Decimal = Field(alias="estimatedMrr")
    estimated_close_date: Optional[datetime] = Field(None, alias="estimatedCloseDate")

    model_config = {"populate_by_name": True}


class HQLeadImportRequest(BaseModel):
    """Request to import leads from AI-parsed content."""
    content: str = Field(..., min_length=10, max_length=100000)
    content_type: Literal["csv", "email", "spreadsheet", "text"] = Field("text", alias="contentType")
    assign_to_sales_rep_id: Optional[str] = Field(None, alias="assignToSalesRepId")
    auto_assign_round_robin: bool = Field(False, alias="autoAssignRoundRobin")

    model_config = {"populate_by_name": True}


class HQLeadImportResponse(BaseModel):
    """Response from AI lead import."""
    leads_created: List["HQLeadResponse"] = Field(alias="leadsCreated", serialization_alias="leadsCreated")
    errors: List[dict] = []
    total_parsed: int = Field(alias="totalParsed", serialization_alias="totalParsed")
    total_created: int = Field(alias="totalCreated", serialization_alias="totalCreated")

    model_config = {"populate_by_name": True}


class HQLeadFMCSAImportRequest(BaseModel):
    """Request to import leads from FMCSA Census data."""
    state: Optional[str] = Field(None, min_length=2, max_length=2)
    min_trucks: int = Field(5, ge=1, alias="minTrucks")
    max_trucks: int = Field(500, ge=1, alias="maxTrucks")
    limit: int = Field(50, ge=1, le=200)
    authority_days: Optional[int] = Field(None, ge=1, le=365, alias="authorityDays")
    assign_to_sales_rep_id: Optional[str] = Field(None, alias="assignToSalesRepId")
    auto_assign_round_robin: bool = Field(False, alias="autoAssignRoundRobin")

    model_config = {"populate_by_name": True}


class HQLeadEnrichRequest(BaseModel):
    """Request to enrich leads with AI-found contact info."""
    lead_ids: List[str] = Field(..., alias="leadIds", min_length=1, max_length=50)

    model_config = {"populate_by_name": True}


class HQLeadEnrichResponse(BaseModel):
    """Response from AI lead enrichment."""
    enriched_leads: List["HQLeadResponse"] = Field(alias="enrichedLeads", serialization_alias="enrichedLeads")
    errors: List[dict] = []
    total_enriched: int = Field(alias="totalEnriched", serialization_alias="totalEnriched")

    model_config = {"populate_by_name": True}


# ============================================================================
# CRM Opportunity Schemas
# ============================================================================

OpportunityStageType = Literal["discovery", "proposal", "negotiation", "closed_won", "closed_lost"]


class HQOpportunityBase(BaseModel):
    company_name: str = Field(alias="companyName", serialization_alias="companyName")
    contact_name: Optional[str] = Field(None, alias="contactName", serialization_alias="contactName")
    contact_email: Optional[str] = Field(None, alias="contactEmail", serialization_alias="contactEmail")
    contact_phone: Optional[str] = Field(None, alias="contactPhone", serialization_alias="contactPhone")
    title: str
    description: Optional[str] = None
    estimated_mrr: Decimal = Field(alias="estimatedMrr", serialization_alias="estimatedMrr")
    estimated_setup_fee: Optional[Decimal] = Field(Decimal("0"), alias="estimatedSetupFee", serialization_alias="estimatedSetupFee")
    estimated_trucks: Optional[str] = Field(None, alias="estimatedTrucks", serialization_alias="estimatedTrucks")
    estimated_close_date: Optional[datetime] = Field(None, alias="estimatedCloseDate", serialization_alias="estimatedCloseDate")
    probability: Optional[Decimal] = Field(Decimal("20"), serialization_alias="probability")
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQOpportunityCreate(HQOpportunityBase):
    lead_id: Optional[str] = Field(None, alias="leadId", serialization_alias="leadId")
    tenant_id: Optional[str] = Field(None, alias="tenantId", serialization_alias="tenantId")
    assigned_sales_rep_id: Optional[str] = Field(None, alias="assignedSalesRepId", serialization_alias="assignedSalesRepId")


class HQOpportunityUpdate(BaseModel):
    company_name: Optional[str] = Field(None, alias="companyName")
    contact_name: Optional[str] = Field(None, alias="contactName")
    contact_email: Optional[str] = Field(None, alias="contactEmail")
    contact_phone: Optional[str] = Field(None, alias="contactPhone")
    title: Optional[str] = None
    description: Optional[str] = None
    stage: Optional[OpportunityStageType] = None
    probability: Optional[Decimal] = None
    estimated_mrr: Optional[Decimal] = Field(None, alias="estimatedMrr")
    estimated_setup_fee: Optional[Decimal] = Field(None, alias="estimatedSetupFee")
    estimated_trucks: Optional[str] = Field(None, alias="estimatedTrucks")
    estimated_close_date: Optional[datetime] = Field(None, alias="estimatedCloseDate")
    assigned_sales_rep_id: Optional[str] = Field(None, alias="assignedSalesRepId")
    lost_reason: Optional[str] = Field(None, alias="lostReason")
    competitor: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQOpportunityResponse(HQOpportunityBase):
    id: str
    opportunity_number: str = Field(alias="opportunityNumber", serialization_alias="opportunityNumber")
    lead_id: Optional[str] = Field(None, alias="leadId", serialization_alias="leadId")
    tenant_id: Optional[str] = Field(None, alias="tenantId", serialization_alias="tenantId")
    stage: OpportunityStageType
    actual_close_date: Optional[datetime] = Field(None, alias="actualCloseDate", serialization_alias="actualCloseDate")
    assigned_sales_rep_id: Optional[str] = Field(None, alias="assignedSalesRepId", serialization_alias="assignedSalesRepId")
    assigned_sales_rep_name: Optional[str] = Field(None, alias="assignedSalesRepName", serialization_alias="assignedSalesRepName")
    converted_to_quote_id: Optional[str] = Field(None, alias="convertedToQuoteId", serialization_alias="convertedToQuoteId")
    converted_at: Optional[datetime] = Field(None, alias="convertedAt", serialization_alias="convertedAt")
    lost_reason: Optional[str] = Field(None, alias="lostReason", serialization_alias="lostReason")
    competitor: Optional[str] = None
    created_by_id: Optional[str] = Field(None, alias="createdById", serialization_alias="createdById")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class HQOpportunityConvert(BaseModel):
    """Convert opportunity to quote."""
    title: str
    tier: str = "professional"
    base_monthly_rate: Decimal = Field(alias="baseMonthlyRate")
    setup_fee: Optional[Decimal] = Field(Decimal("0"), alias="setupFee")
    valid_days: int = Field(30, alias="validDays")

    model_config = {"populate_by_name": True}


class HQPipelineSummary(BaseModel):
    """Pipeline stage summary for dashboard."""
    stage: OpportunityStageType
    count: int
    total_value: Decimal = Field(alias="totalValue", serialization_alias="totalValue")
    weighted_value: Decimal = Field(alias="weightedValue", serialization_alias="weightedValue")

    model_config = {"populate_by_name": True}


# ============================================================================
# Commission Configuration Schemas
# ============================================================================

CommissionTierType = Literal["junior", "mid", "senior", "enterprise"]


class HQSalesRepCommissionBase(BaseModel):
    commission_rate: Decimal = Field(alias="commissionRate", serialization_alias="commissionRate")
    tier_level: CommissionTierType = Field("junior", alias="tierLevel", serialization_alias="tierLevel")
    effective_from: Optional[datetime] = Field(None, alias="effectiveFrom", serialization_alias="effectiveFrom")
    effective_until: Optional[datetime] = Field(None, alias="effectiveUntil", serialization_alias="effectiveUntil")
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQSalesRepCommissionCreate(HQSalesRepCommissionBase):
    sales_rep_id: str = Field(alias="salesRepId", serialization_alias="salesRepId")


class HQSalesRepCommissionUpdate(BaseModel):
    commission_rate: Optional[Decimal] = Field(None, alias="commissionRate")
    tier_level: Optional[CommissionTierType] = Field(None, alias="tierLevel")
    effective_until: Optional[datetime] = Field(None, alias="effectiveUntil")
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQSalesRepCommissionResponse(HQSalesRepCommissionBase):
    id: str
    sales_rep_id: str = Field(alias="salesRepId", serialization_alias="salesRepId")
    sales_rep_name: Optional[str] = Field(None, alias="salesRepName", serialization_alias="salesRepName")
    sales_rep_email: Optional[str] = Field(None, alias="salesRepEmail", serialization_alias="salesRepEmail")
    created_by_id: Optional[str] = Field(None, alias="createdById", serialization_alias="createdById")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


# ============================================================================
# Commission Record & Payment Schemas
# ============================================================================

CommissionRecordStatusType = Literal["pending", "eligible", "active", "cancelled"]
CommissionPaymentStatusType = Literal["pending", "approved", "paid", "cancelled"]


class HQCommissionRecordResponse(BaseModel):
    id: str
    sales_rep_id: str = Field(alias="salesRepId", serialization_alias="salesRepId")
    sales_rep_name: Optional[str] = Field(None, alias="salesRepName", serialization_alias="salesRepName")
    contract_id: str = Field(alias="contractId", serialization_alias="contractId")
    tenant_id: str = Field(alias="tenantId", serialization_alias="tenantId")
    tenant_name: Optional[str] = Field(None, alias="tenantName", serialization_alias="tenantName")
    commission_rate: Decimal = Field(alias="commissionRate", serialization_alias="commissionRate")
    base_mrr: Decimal = Field(alias="baseMrr", serialization_alias="baseMrr")
    status: CommissionRecordStatusType
    deal_closed_at: datetime = Field(alias="dealClosedAt", serialization_alias="dealClosedAt")
    eligible_at: datetime = Field(alias="eligibleAt", serialization_alias="eligibleAt")
    total_paid_amount: Decimal = Field(alias="totalPaidAmount", serialization_alias="totalPaidAmount")
    is_active: bool = Field(alias="isActive", serialization_alias="isActive")
    deactivated_at: Optional[datetime] = Field(None, alias="deactivatedAt", serialization_alias="deactivatedAt")
    deactivated_reason: Optional[str] = Field(None, alias="deactivatedReason", serialization_alias="deactivatedReason")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class HQCommissionPaymentResponse(BaseModel):
    id: str
    commission_record_id: str = Field(alias="commissionRecordId", serialization_alias="commissionRecordId")
    sales_rep_id: str = Field(alias="salesRepId", serialization_alias="salesRepId")
    sales_rep_name: Optional[str] = Field(None, alias="salesRepName", serialization_alias="salesRepName")
    tenant_name: Optional[str] = Field(None, alias="tenantName", serialization_alias="tenantName")
    period_start: datetime = Field(alias="periodStart", serialization_alias="periodStart")
    period_end: datetime = Field(alias="periodEnd", serialization_alias="periodEnd")
    mrr_amount: Decimal = Field(alias="mrrAmount", serialization_alias="mrrAmount")
    commission_rate: Decimal = Field(alias="commissionRate", serialization_alias="commissionRate")
    commission_amount: Decimal = Field(alias="commissionAmount", serialization_alias="commissionAmount")
    status: CommissionPaymentStatusType
    payment_date: Optional[datetime] = Field(None, alias="paymentDate", serialization_alias="paymentDate")
    payment_reference: Optional[str] = Field(None, alias="paymentReference", serialization_alias="paymentReference")
    payment_method: Optional[str] = Field(None, alias="paymentMethod", serialization_alias="paymentMethod")
    approved_by_id: Optional[str] = Field(None, alias="approvedById", serialization_alias="approvedById")
    approved_at: Optional[datetime] = Field(None, alias="approvedAt", serialization_alias="approvedAt")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class HQCommissionPaymentApprove(BaseModel):
    """Approve a commission payment."""
    payment_method: Optional[str] = Field(None, alias="paymentMethod")
    payment_reference: Optional[str] = Field(None, alias="paymentReference")
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


# ============================================================================
# Sales Rep Earnings Dashboard Schemas
# ============================================================================

class HQSalesRepEarnings(BaseModel):
    """Sales rep earnings dashboard data."""
    sales_rep_id: str = Field(alias="salesRepId", serialization_alias="salesRepId")
    sales_rep_name: str = Field(alias="salesRepName", serialization_alias="salesRepName")
    commission_rate: Decimal = Field(alias="commissionRate", serialization_alias="commissionRate")
    tier_level: CommissionTierType = Field(alias="tierLevel", serialization_alias="tierLevel")
    # Earnings
    lifetime_earnings: Decimal = Field(alias="lifetimeEarnings", serialization_alias="lifetimeEarnings")
    ytd_earnings: Decimal = Field(alias="ytdEarnings", serialization_alias="ytdEarnings")
    mtd_earnings: Decimal = Field(alias="mtdEarnings", serialization_alias="mtdEarnings")
    pending_amount: Decimal = Field(alias="pendingAmount", serialization_alias="pendingAmount")
    eligible_unpaid: Decimal = Field(alias="eligibleUnpaid", serialization_alias="eligibleUnpaid")
    # Activity
    active_accounts: int = Field(alias="activeAccounts", serialization_alias="activeAccounts")
    active_mrr: Decimal = Field(alias="activeMrr", serialization_alias="activeMrr")
    pipeline_value: Decimal = Field(alias="pipelineValue", serialization_alias="pipelineValue")
    pipeline_count: int = Field(alias="pipelineCount", serialization_alias="pipelineCount")
    leads_count: int = Field(alias="leadsCount", serialization_alias="leadsCount")

    model_config = {"populate_by_name": True}


class HQSalesRepAccountSummary(BaseModel):
    """Sales rep's account summary with MRR breakdown."""
    tenant_id: str = Field(alias="tenantId", serialization_alias="tenantId")
    tenant_name: str = Field(alias="tenantName", serialization_alias="tenantName")
    mrr: Decimal
    contract_start_date: Optional[datetime] = Field(None, alias="contractStartDate", serialization_alias="contractStartDate")
    commission_earned: Decimal = Field(alias="commissionEarned", serialization_alias="commissionEarned")
    status: str

    model_config = {"populate_by_name": True}


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


class HQHREmployeeResponse(BaseModel):
    """Response model for HR employee with camelCase fields for frontend."""
    id: str
    employeeNumber: str
    firstName: str
    lastName: str
    email: str
    phone: Optional[str] = None
    employmentType: str
    status: str
    department: Optional[str] = None
    jobTitle: Optional[str] = None
    managerId: Optional[str] = None
    managerName: Optional[str] = None
    hireDate: Optional[str] = None
    terminationDate: Optional[str] = None
    payFrequency: str
    annualSalary: Optional[float] = None
    hourlyRate: Optional[float] = None
    addressLine1: Optional[str] = None
    addressLine2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zipCode: Optional[str] = None
    checkEmployeeId: Optional[str] = None
    createdAt: str
    updatedAt: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, emp) -> "HQHREmployeeResponse":
        """Convert ORM model to response with camelCase."""
        return cls(
            id=emp.id,
            employeeNumber=emp.employee_number,
            firstName=emp.first_name,
            lastName=emp.last_name,
            email=emp.email,
            phone=emp.phone,
            employmentType=emp.employment_type.value if hasattr(emp.employment_type, 'value') else str(emp.employment_type),
            status=emp.status.value if hasattr(emp.status, 'value') else str(emp.status),
            department=emp.department,
            jobTitle=emp.job_title,
            managerId=emp.manager_id,
            managerName=None,  # TODO: Join manager name
            hireDate=emp.hire_date.isoformat() if emp.hire_date else None,
            terminationDate=emp.termination_date.isoformat() if emp.termination_date else None,
            payFrequency=emp.pay_frequency.value if hasattr(emp.pay_frequency, 'value') else str(emp.pay_frequency),
            annualSalary=float(emp.annual_salary) if emp.annual_salary else None,
            hourlyRate=float(emp.hourly_rate) if emp.hourly_rate else None,
            addressLine1=emp.address_line1,
            addressLine2=emp.address_line2,
            city=emp.city,
            state=emp.state,
            zipCode=emp.zip_code,
            checkEmployeeId=emp.check_employee_id,
            createdAt=emp.created_at.isoformat() if emp.created_at else "",
            updatedAt=emp.updated_at.isoformat() if emp.updated_at else "",
        )


class HQPayrollRunBase(BaseModel):
    """Payroll run for processing employee payments."""
    pay_period_start: datetime
    pay_period_end: datetime
    pay_date: datetime
    description: Optional[str] = None


PayrollStatusType = Literal["draft", "pending_approval", "approved", "processing", "completed", "failed", "cancelled"]


class HQPayrollRunCreate(HQPayrollRunBase):
    employee_ids: Optional[List[str]] = None  # If None, all active employees


class HQPayrollRunResponse(BaseModel):
    """Payroll run response with camelCase fields for frontend."""
    id: str
    payrollNumber: str
    status: str
    payPeriodStart: str
    payPeriodEnd: str
    payDate: str
    description: Optional[str] = None
    checkPayrollId: Optional[str] = None
    totalGross: float = 0
    totalTaxes: float = 0
    totalDeductions: float = 0
    totalNet: float = 0
    employeeCount: int = 0
    approvedById: Optional[str] = None
    approvedAt: Optional[str] = None
    processedAt: Optional[str] = None
    createdById: Optional[str] = None
    createdAt: str
    updatedAt: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, pr) -> "HQPayrollRunResponse":
        """Convert ORM model to response with camelCase."""
        return cls(
            id=pr.id,
            payrollNumber=pr.payroll_number,
            status=pr.status.value if hasattr(pr.status, 'value') else str(pr.status),
            payPeriodStart=pr.pay_period_start.isoformat() if pr.pay_period_start else "",
            payPeriodEnd=pr.pay_period_end.isoformat() if pr.pay_period_end else "",
            payDate=pr.pay_date.isoformat() if pr.pay_date else "",
            description=pr.description,
            checkPayrollId=pr.check_payroll_id,
            totalGross=float(pr.total_gross) if pr.total_gross else 0,
            totalTaxes=float(pr.total_taxes) if pr.total_taxes else 0,
            totalDeductions=float(pr.total_deductions) if pr.total_deductions else 0,
            totalNet=float(pr.total_net) if pr.total_net else 0,
            employeeCount=pr.employee_count or 0,
            approvedById=pr.approved_by_id,
            approvedAt=pr.approved_at.isoformat() if pr.approved_at else None,
            processedAt=pr.processed_at.isoformat() if pr.processed_at else None,
            createdById=pr.created_by_id,
            createdAt=pr.created_at.isoformat() if pr.created_at else "",
            updatedAt=pr.updated_at.isoformat() if pr.updated_at else "",
        )


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
# HQ Chat Schemas (Unified Team + AI Chat)
# ============================================================================

HQChannelType = Literal["team", "ai", "direct", "announcement"]


class HQChatParticipant(BaseModel):
    """Participant in an HQ chat channel."""
    id: str
    employee_id: str = Field(alias="employeeId", serialization_alias="employeeId")
    display_name: str = Field(alias="displayName", serialization_alias="displayName")
    role: Optional[str] = None
    is_ai: bool = Field(False, alias="isAi", serialization_alias="isAi")
    added_at: datetime = Field(alias="addedAt", serialization_alias="addedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class HQChatChannelCreate(BaseModel):
    """Create a new HQ chat channel."""
    name: str
    channel_type: HQChannelType = Field("team", alias="channelType")
    description: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQChatChannelResponse(BaseModel):
    """Response for an HQ chat channel."""
    id: str
    name: str
    channel_type: HQChannelType = Field(alias="channelType", serialization_alias="channelType")
    description: Optional[str] = None
    last_message: Optional[str] = Field(None, alias="lastMessage", serialization_alias="lastMessage")
    last_message_at: Optional[datetime] = Field(None, alias="lastMessageAt", serialization_alias="lastMessageAt")
    unread_count: int = Field(0, alias="unreadCount", serialization_alias="unreadCount")
    is_pinned: bool = Field(False, alias="isPinned", serialization_alias="isPinned")
    participants: List[HQChatParticipant] = []
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class HQChatAttachment(BaseModel):
    """File attachment in a chat message."""
    id: str
    filename: str
    file_type: str  # image/png, application/pdf, etc.
    file_size: int  # bytes
    url: str
    thumbnail_url: Optional[str] = Field(None, alias="thumbnailUrl", serialization_alias="thumbnailUrl")

    model_config = {"populate_by_name": True}


class HQChatMessageCreate(BaseModel):
    """Create a new chat message."""
    content: str
    mentions: Optional[List[str]] = None  # Employee IDs mentioned
    attachments: Optional[List[HQChatAttachment]] = None  # File attachments


class HQChatMessageResponse(BaseModel):
    """Response for a chat message."""
    id: str
    channel_id: str = Field(alias="channelId", serialization_alias="channelId")
    author_id: str = Field(alias="authorId", serialization_alias="authorId")
    author_name: str = Field(alias="authorName", serialization_alias="authorName")
    content: str
    is_ai_response: bool = Field(False, alias="isAiResponse", serialization_alias="isAiResponse")
    ai_agent: Optional[HQAgentType] = Field(None, alias="aiAgent", serialization_alias="aiAgent")
    ai_reasoning: Optional[str] = Field(None, alias="aiReasoning", serialization_alias="aiReasoning")
    ai_confidence: Optional[float] = Field(None, alias="aiConfidence", serialization_alias="aiConfidence")
    attachments: Optional[List[HQChatAttachment]] = None
    mentions: Optional[List[str]] = None
    is_read: bool = Field(False, alias="isRead", serialization_alias="isRead")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class HQChatAIRoutingResult(BaseModel):
    """Result of AI routing decision."""
    agent: HQAgentType
    confidence: float
    reasoning: str


class HQDirectMessageCreate(BaseModel):
    """Create a direct message channel with another employee."""
    employee_id: str = Field(alias="employeeId")  # Employee ID to start DM with

    model_config = {"populate_by_name": True}


class HQGroupChatCreate(BaseModel):
    """Create a group chat with multiple employees."""
    name: str
    description: Optional[str] = None
    participant_ids: List[str] = Field(alias="participantIds")  # Employee IDs to add

    model_config = {"populate_by_name": True}


class HQAddParticipant(BaseModel):
    """Add a participant to a channel."""
    employee_id: str = Field(alias="employeeId")

    model_config = {"populate_by_name": True}


class HQChatFileUpload(BaseModel):
    """Response after uploading a file for chat."""
    id: str
    filename: str
    file_type: str = Field(alias="fileType", serialization_alias="fileType")
    file_size: int = Field(alias="fileSize", serialization_alias="fileSize")
    url: str
    thumbnail_url: Optional[str] = Field(None, alias="thumbnailUrl", serialization_alias="thumbnailUrl")

    model_config = {"populate_by_name": True}


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


# ============================================================================
# AI Approval Queue Schemas (Level 2 Autonomy)
# ============================================================================

AIActionType = Literal[
    "lead_outreach", "lead_qualification", "rate_negotiation",
    "load_acceptance", "driver_assignment", "compliance_alert", "invoice_approval"
]
AIActionRisk = Literal["low", "medium", "high", "critical"]
AIActionStatus = Literal["pending", "approved", "approved_with_edits", "rejected", "auto_executed", "expired"]


class HQAIActionResponse(BaseModel):
    """AI-generated action in the approval queue."""
    id: str
    action_type: str = Field(alias="actionType")
    risk_level: str = Field(alias="riskLevel")
    status: str
    agent_name: str = Field(alias="agentName")
    title: str
    description: Optional[str] = None
    draft_content: Optional[str] = Field(None, alias="draftContent")
    ai_reasoning: Optional[str] = Field(None, alias="aiReasoning")
    entity_type: Optional[str] = Field(None, alias="entityType")
    entity_id: Optional[str] = Field(None, alias="entityId")
    entity_name: Optional[str] = Field(None, alias="entityName")
    risk_factors: Optional[List[dict]] = Field(None, alias="riskFactors")
    assigned_to_id: Optional[str] = Field(None, alias="assignedToId")
    reviewed_by_id: Optional[str] = Field(None, alias="reviewedById")
    reviewed_at: Optional[datetime] = Field(None, alias="reviewedAt")
    human_edits: Optional[str] = Field(None, alias="humanEdits")
    rejection_reason: Optional[str] = Field(None, alias="rejectionReason")
    was_edited: bool = Field(False, alias="wasEdited")
    created_at: datetime = Field(alias="createdAt")
    expires_at: Optional[datetime] = Field(None, alias="expiresAt")
    executed_at: Optional[datetime] = Field(None, alias="executedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class HQAIActionApprove(BaseModel):
    """Request to approve an AI action."""
    edits: Optional[str] = None  # Optional human edits to the draft


class HQAIActionReject(BaseModel):
    """Request to reject an AI action."""
    reason: str = Field(..., min_length=1)


class HQAIQueueStats(BaseModel):
    """Statistics about the AI approval queue."""
    pending_total: int = Field(alias="pendingTotal")
    pending_by_risk: dict = Field(alias="pendingByRisk")
    pending_by_type: dict = Field(alias="pendingByType")
    today_created: int = Field(alias="todayCreated")
    today_approved: int = Field(alias="todayApproved")
    today_rejected: int = Field(alias="todayRejected")
    today_auto_executed: int = Field(alias="todayAutoExecuted")

    model_config = {"populate_by_name": True}


class HQAIAutonomyRuleResponse(BaseModel):
    """Autonomy rule configuration."""
    id: str
    action_type: str = Field(alias="actionType")
    agent_name: str = Field(alias="agentName")
    name: str
    description: Optional[str] = None
    condition_field: str = Field(alias="conditionField")
    condition_operator: str = Field(alias="conditionOperator")
    condition_value: str = Field(alias="conditionValue")
    resulting_risk: str = Field(alias="resultingRisk")
    is_active: bool = Field(alias="isActive")
    priority: int
    total_actions: int = Field(alias="totalActions")
    approved_without_edits: int = Field(alias="approvedWithoutEdits")
    approved_with_edits: int = Field(alias="approvedWithEdits")
    rejected: int
    success_rate: float = Field(alias="successRate")
    is_level_3_enabled: bool = Field(alias="isLevel3Enabled")

    model_config = {"from_attributes": True, "populate_by_name": True}


# ============================================================================
# Lead Activity & Email Schemas
# ============================================================================

ActivityTypeType = Literal["note", "email_sent", "email_received", "call", "meeting", "follow_up", "status_change", "ai_action"]
FollowUpStatusType = Literal["pending", "due", "completed", "snoozed", "cancelled"]


class HQLeadActivityBase(BaseModel):
    """Base lead activity schema."""
    activity_type: ActivityTypeType = Field(alias="activityType", serialization_alias="activityType")
    subject: Optional[str] = None
    content: Optional[str] = None
    is_pinned: bool = Field(False, alias="isPinned", serialization_alias="isPinned")

    model_config = {"populate_by_name": True}


class HQNoteCreate(BaseModel):
    """Create a note on a lead."""
    content: str = Field(..., min_length=1)
    is_pinned: bool = Field(False, alias="isPinned")

    model_config = {"populate_by_name": True}


class HQNoteUpdate(BaseModel):
    """Update a note."""
    content: Optional[str] = None
    is_pinned: Optional[bool] = Field(None, alias="isPinned")

    model_config = {"populate_by_name": True}


class HQFollowUpCreate(BaseModel):
    """Create a follow-up reminder."""
    follow_up_date: datetime = Field(alias="followUpDate")
    content: str = Field(..., min_length=1)
    subject: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQFollowUpComplete(BaseModel):
    """Complete a follow-up."""
    notes: Optional[str] = None


class HQFollowUpSnooze(BaseModel):
    """Snooze a follow-up."""
    new_date: datetime = Field(alias="newDate")

    model_config = {"populate_by_name": True}


class HQCallLogCreate(BaseModel):
    """Log a phone call."""
    outcome: str = Field(..., min_length=1)  # connected, voicemail, no_answer, busy
    notes: Optional[str] = None
    duration_seconds: Optional[int] = Field(None, alias="durationSeconds")

    model_config = {"populate_by_name": True}


class HQLeadActivityResponse(BaseModel):
    """Lead activity response."""
    id: str
    lead_id: str = Field(alias="leadId", serialization_alias="leadId")
    activity_type: ActivityTypeType = Field(alias="activityType", serialization_alias="activityType")
    subject: Optional[str] = None
    content: Optional[str] = None
    # Email fields
    email_from: Optional[str] = Field(None, alias="emailFrom", serialization_alias="emailFrom")
    email_to: Optional[str] = Field(None, alias="emailTo", serialization_alias="emailTo")
    email_cc: Optional[str] = Field(None, alias="emailCc", serialization_alias="emailCc")
    email_status: Optional[str] = Field(None, alias="emailStatus", serialization_alias="emailStatus")
    email_thread_id: Optional[str] = Field(None, alias="emailThreadId", serialization_alias="emailThreadId")
    # Follow-up fields
    follow_up_date: Optional[datetime] = Field(None, alias="followUpDate", serialization_alias="followUpDate")
    follow_up_status: Optional[FollowUpStatusType] = Field(None, alias="followUpStatus", serialization_alias="followUpStatus")
    follow_up_completed_at: Optional[datetime] = Field(None, alias="followUpCompletedAt", serialization_alias="followUpCompletedAt")
    # Call fields
    call_duration_seconds: Optional[str] = Field(None, alias="callDurationSeconds", serialization_alias="callDurationSeconds")
    call_outcome: Optional[str] = Field(None, alias="callOutcome", serialization_alias="callOutcome")
    # Meta
    is_pinned: bool = Field(False, alias="isPinned", serialization_alias="isPinned")
    metadata: Optional[dict] = None
    created_by_id: Optional[str] = Field(None, alias="createdById", serialization_alias="createdById")
    created_by_name: Optional[str] = Field(None, alias="createdByName", serialization_alias="createdByName")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


# ============================================================================
# Email Schemas
# ============================================================================

class HQSendEmailRequest(BaseModel):
    """Request to send an email to a lead."""
    to_email: str = Field(alias="toEmail")
    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    cc: Optional[str] = None
    template_id: Optional[str] = Field(None, alias="templateId")

    model_config = {"populate_by_name": True}


class HQEmailTemplateBase(BaseModel):
    """Email template base schema."""
    name: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    body: str = Field(..., min_length=1)
    category: Optional[str] = None
    is_global: bool = Field(False, alias="isGlobal", serialization_alias="isGlobal")
    variables: Optional[List[str]] = None

    model_config = {"populate_by_name": True}


class HQEmailTemplateCreate(HQEmailTemplateBase):
    pass


class HQEmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = Field(None, alias="isActive")

    model_config = {"populate_by_name": True}


class HQEmailTemplateResponse(HQEmailTemplateBase):
    id: str
    times_used: str = Field(alias="timesUsed", serialization_alias="timesUsed")
    is_active: bool = Field(alias="isActive", serialization_alias="isActive")
    created_by_id: Optional[str] = Field(None, alias="createdById", serialization_alias="createdById")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class HQRenderTemplateRequest(BaseModel):
    """Request to render an email template for preview."""
    template_id: str = Field(alias="templateId")
    custom_vars: Optional[dict] = Field(None, alias="customVars")

    model_config = {"populate_by_name": True}


class HQRenderTemplateResponse(BaseModel):
    """Rendered template response."""
    subject: str
    body: str


class HQEmailConfigBase(BaseModel):
    """Email configuration base schema."""
    name: str
    provider: str  # smtp, sendgrid, mailgun, ses
    from_email: str = Field(alias="fromEmail", serialization_alias="fromEmail")
    from_name: Optional[str] = Field(None, alias="fromName", serialization_alias="fromName")
    reply_to: Optional[str] = Field(None, alias="replyTo", serialization_alias="replyTo")

    model_config = {"populate_by_name": True}


class HQEmailConfigCreate(HQEmailConfigBase):
    config: dict  # Provider-specific config (SMTP settings, API keys, etc.)
    is_default: bool = Field(False, alias="isDefault")

    model_config = {"populate_by_name": True}


class HQEmailConfigResponse(HQEmailConfigBase):
    id: str
    is_default: bool = Field(alias="isDefault", serialization_alias="isDefault")
    is_active: bool = Field(alias="isActive", serialization_alias="isActive")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


# ============================================================================
# Follow-up Alerts Schemas
# ============================================================================

class HQDueFollowUp(BaseModel):
    """A follow-up that is due or overdue."""
    id: str
    lead_id: str = Field(alias="leadId", serialization_alias="leadId")
    lead_company_name: str = Field(alias="leadCompanyName", serialization_alias="leadCompanyName")
    lead_contact_name: Optional[str] = Field(None, alias="leadContactName", serialization_alias="leadContactName")
    subject: Optional[str] = None
    content: Optional[str] = None
    follow_up_date: datetime = Field(alias="followUpDate", serialization_alias="followUpDate")
    is_overdue: bool = Field(alias="isOverdue", serialization_alias="isOverdue")
    days_overdue: int = Field(0, alias="daysOverdue", serialization_alias="daysOverdue")
    created_by_name: Optional[str] = Field(None, alias="createdByName", serialization_alias="createdByName")

    model_config = {"populate_by_name": True}


class HQFollowUpAlerts(BaseModel):
    """Follow-up alerts summary for a sales rep."""
    overdue_count: int = Field(alias="overdueCount", serialization_alias="overdueCount")
    due_today_count: int = Field(alias="dueTodayCount", serialization_alias="dueTodayCount")
    upcoming_count: int = Field(alias="upcomingCount", serialization_alias="upcomingCount")
    overdue: List[HQDueFollowUp] = []
    due_today: List[HQDueFollowUp] = Field([], alias="dueToday", serialization_alias="dueToday")
    upcoming: List[HQDueFollowUp] = []

    model_config = {"populate_by_name": True}


# ============================================================================
# Deal Schemas (Unified Sales Pipeline)
# ============================================================================

DealStageType = Literal["lead", "contacted", "qualified", "demo", "closing", "won", "lost"]
DealSourceType = Literal["referral", "website", "cold_call", "partner", "trade_show", "linkedin", "fmcsa", "other"]


class HQDealBase(BaseModel):
    company_name: str = Field(alias="companyName", serialization_alias="companyName")
    contact_name: Optional[str] = Field(None, alias="contactName", serialization_alias="contactName")
    contact_email: Optional[str] = Field(None, alias="contactEmail", serialization_alias="contactEmail")
    contact_phone: Optional[str] = Field(None, alias="contactPhone", serialization_alias="contactPhone")
    contact_title: Optional[str] = Field(None, alias="contactTitle", serialization_alias="contactTitle")
    source: DealSourceType = "other"
    estimated_mrr: Optional[Decimal] = Field(None, alias="estimatedMrr", serialization_alias="estimatedMrr")
    estimated_setup_fee: Optional[Decimal] = Field(None, alias="estimatedSetupFee", serialization_alias="estimatedSetupFee")
    estimated_trucks: Optional[str] = Field(None, alias="estimatedTrucks", serialization_alias="estimatedTrucks")
    estimated_close_date: Optional[datetime] = Field(None, alias="estimatedCloseDate", serialization_alias="estimatedCloseDate")
    next_follow_up_date: Optional[datetime] = Field(None, alias="nextFollowUpDate", serialization_alias="nextFollowUpDate")
    notes: Optional[str] = None
    # FMCSA data
    dot_number: Optional[str] = Field(None, alias="dotNumber", serialization_alias="dotNumber")
    mc_number: Optional[str] = Field(None, alias="mcNumber", serialization_alias="mcNumber")
    state: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQDealCreate(HQDealBase):
    assigned_sales_rep_id: Optional[str] = Field(None, alias="assignedSalesRepId", serialization_alias="assignedSalesRepId")


class HQDealUpdate(BaseModel):
    company_name: Optional[str] = Field(None, alias="companyName")
    contact_name: Optional[str] = Field(None, alias="contactName")
    contact_email: Optional[str] = Field(None, alias="contactEmail")
    contact_phone: Optional[str] = Field(None, alias="contactPhone")
    contact_title: Optional[str] = Field(None, alias="contactTitle")
    source: Optional[DealSourceType] = None
    stage: Optional[DealStageType] = None
    probability: Optional[Decimal] = None
    estimated_mrr: Optional[Decimal] = Field(None, alias="estimatedMrr")
    estimated_setup_fee: Optional[Decimal] = Field(None, alias="estimatedSetupFee")
    estimated_trucks: Optional[str] = Field(None, alias="estimatedTrucks")
    estimated_close_date: Optional[datetime] = Field(None, alias="estimatedCloseDate")
    assigned_sales_rep_id: Optional[str] = Field(None, alias="assignedSalesRepId")
    next_follow_up_date: Optional[datetime] = Field(None, alias="nextFollowUpDate")
    notes: Optional[str] = None
    lost_reason: Optional[str] = Field(None, alias="lostReason")
    competitor: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQDealResponse(HQDealBase):
    id: str
    deal_number: str = Field(alias="dealNumber", serialization_alias="dealNumber")
    stage: DealStageType
    probability: Decimal
    assigned_sales_rep_id: Optional[str] = Field(None, alias="assignedSalesRepId", serialization_alias="assignedSalesRepId")
    assigned_sales_rep_name: Optional[str] = Field(None, alias="assignedSalesRepName", serialization_alias="assignedSalesRepName")
    last_contacted_at: Optional[datetime] = Field(None, alias="lastContactedAt", serialization_alias="lastContactedAt")
    carrier_type: Optional[str] = Field(None, alias="carrierType", serialization_alias="carrierType")
    lost_reason: Optional[str] = Field(None, alias="lostReason", serialization_alias="lostReason")
    competitor: Optional[str] = None
    won_at: Optional[datetime] = Field(None, alias="wonAt", serialization_alias="wonAt")
    lost_at: Optional[datetime] = Field(None, alias="lostAt", serialization_alias="lostAt")
    subscription_id: Optional[str] = Field(None, alias="subscriptionId", serialization_alias="subscriptionId")
    created_by_id: Optional[str] = Field(None, alias="createdById", serialization_alias="createdById")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class HQDealStageSummary(BaseModel):
    """Summary of deals for a single pipeline stage."""
    stage: DealStageType
    count: int
    total_value: Decimal = Field(alias="totalValue", serialization_alias="totalValue")
    weighted_value: Decimal = Field(alias="weightedValue", serialization_alias="weightedValue")

    model_config = {"populate_by_name": True}


class HQDealImportRequest(BaseModel):
    """Request to import deals from AI-parsed content."""
    content: str = Field(..., min_length=10, max_length=100000)
    content_type: Literal["csv", "email", "spreadsheet", "text"] = Field("text", alias="contentType")
    assign_to_sales_rep_id: Optional[str] = Field(None, alias="assignToSalesRepId")
    auto_assign_round_robin: bool = Field(False, alias="autoAssignRoundRobin")

    model_config = {"populate_by_name": True}


class HQDealImportResponse(BaseModel):
    """Response from deal import."""
    deals_created: List[dict] = Field(alias="dealsCreated", serialization_alias="dealsCreated")
    errors: List[dict] = []
    total_parsed: int = Field(alias="totalParsed", serialization_alias="totalParsed")
    total_created: int = Field(alias="totalCreated", serialization_alias="totalCreated")

    model_config = {"populate_by_name": True}


class HQDealFMCSAImportRequest(BaseModel):
    """Request to import deals from FMCSA Census data."""
    state: Optional[str] = Field(None, min_length=2, max_length=2)
    min_trucks: int = Field(5, ge=1, alias="minTrucks")
    max_trucks: int = Field(500, ge=1, alias="maxTrucks")
    limit: int = Field(50, ge=1, le=200)
    authority_days: Optional[int] = Field(None, ge=1, le=365, alias="authorityDays")
    assign_to_sales_rep_id: Optional[str] = Field(None, alias="assignToSalesRepId")
    auto_assign_round_robin: bool = Field(False, alias="autoAssignRoundRobin")

    model_config = {"populate_by_name": True}


class HQDealActivityCreate(BaseModel):
    """Create a deal activity."""
    activity_type: str = Field(alias="activityType")
    description: str

    model_config = {"populate_by_name": True}


class HQDealActivityResponse(BaseModel):
    """Deal activity response."""
    id: str
    deal_id: str = Field(alias="dealId", serialization_alias="dealId")
    activity_type: str = Field(alias="activityType", serialization_alias="activityType")
    description: str
    from_stage: Optional[str] = Field(None, alias="fromStage", serialization_alias="fromStage")
    to_stage: Optional[str] = Field(None, alias="toStage", serialization_alias="toStage")
    created_by_id: Optional[str] = Field(None, alias="createdById", serialization_alias="createdById")
    created_by_name: Optional[str] = Field(None, alias="createdByName", serialization_alias="createdByName")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class HQDealWinRequest(BaseModel):
    """Request to win a deal and create a subscription."""
    billing_interval: Literal["monthly", "annual"] = Field(alias="billingInterval")
    monthly_rate: Decimal = Field(alias="monthlyRate", gt=0)
    setup_fee: Optional[Decimal] = Field(None, alias="setupFee", ge=0)

    model_config = {"populate_by_name": True}


# ============================================================================
# Subscription Schemas
# ============================================================================

SubscriptionStatusType = Literal["active", "paused", "cancelled", "past_due", "trialing"]
BillingIntervalType = Literal["monthly", "annual"]


class HQSubscriptionBase(BaseModel):
    billing_interval: BillingIntervalType = Field("monthly", alias="billingInterval", serialization_alias="billingInterval")
    monthly_rate: Decimal = Field(alias="monthlyRate", serialization_alias="monthlyRate")
    annual_rate: Optional[Decimal] = Field(None, alias="annualRate", serialization_alias="annualRate")
    setup_fee: Optional[Decimal] = Field(None, alias="setupFee", serialization_alias="setupFee")
    truck_limit: Optional[str] = Field(None, alias="truckLimit", serialization_alias="truckLimit")
    user_limit: Optional[str] = Field(None, alias="userLimit", serialization_alias="userLimit")
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQSubscriptionCreate(HQSubscriptionBase):
    tenant_id: str = Field(alias="tenantId")
    deal_id: Optional[str] = Field(None, alias="dealId")
    trial_ends_at: Optional[datetime] = Field(None, alias="trialEndsAt")
    started_at: Optional[datetime] = Field(None, alias="startedAt")


class HQSubscriptionFromDeal(BaseModel):
    """Create subscription from a won deal."""
    tenant_id: str = Field(alias="tenantId")
    billing_interval: BillingIntervalType = Field("monthly", alias="billingInterval")
    monthly_rate: Optional[Decimal] = Field(None, alias="monthlyRate")
    annual_rate: Optional[Decimal] = Field(None, alias="annualRate")
    setup_fee: Optional[Decimal] = Field(None, alias="setupFee")
    setup_fee_paid: bool = Field(False, alias="setupFeePaid")
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQSubscriptionUpdate(BaseModel):
    status: Optional[SubscriptionStatusType] = None
    billing_interval: Optional[BillingIntervalType] = Field(None, alias="billingInterval")
    monthly_rate: Optional[Decimal] = Field(None, alias="monthlyRate")
    annual_rate: Optional[Decimal] = Field(None, alias="annualRate")
    setup_fee_paid: Optional[bool] = Field(None, alias="setupFeePaid")
    truck_limit: Optional[str] = Field(None, alias="truckLimit")
    user_limit: Optional[str] = Field(None, alias="userLimit")
    next_billing_date: Optional[datetime] = Field(None, alias="nextBillingDate")
    notes: Optional[str] = None
    cancellation_reason: Optional[str] = Field(None, alias="cancellationReason")
    rate_change_reason: Optional[str] = Field(None, alias="rateChangeReason")

    model_config = {"populate_by_name": True}


class HQSubscriptionResponse(HQSubscriptionBase):
    id: str
    subscription_number: str = Field(alias="subscriptionNumber", serialization_alias="subscriptionNumber")
    tenant_id: str = Field(alias="tenantId", serialization_alias="tenantId")
    tenant_name: Optional[str] = Field(None, alias="tenantName", serialization_alias="tenantName")
    deal_id: Optional[str] = Field(None, alias="dealId", serialization_alias="dealId")
    status: SubscriptionStatusType
    current_mrr: Decimal = Field(alias="currentMrr", serialization_alias="currentMrr")
    setup_fee_paid: bool = Field(alias="setupFeePaid", serialization_alias="setupFeePaid")
    trial_ends_at: Optional[datetime] = Field(None, alias="trialEndsAt", serialization_alias="trialEndsAt")
    started_at: Optional[datetime] = Field(None, alias="startedAt", serialization_alias="startedAt")
    paused_at: Optional[datetime] = Field(None, alias="pausedAt", serialization_alias="pausedAt")
    cancelled_at: Optional[datetime] = Field(None, alias="cancelledAt", serialization_alias="cancelledAt")
    cancellation_reason: Optional[str] = Field(None, alias="cancellationReason", serialization_alias="cancellationReason")
    next_billing_date: Optional[datetime] = Field(None, alias="nextBillingDate", serialization_alias="nextBillingDate")
    created_by_id: Optional[str] = Field(None, alias="createdById", serialization_alias="createdById")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class HQMRRSummary(BaseModel):
    """MRR summary statistics."""
    active_mrr: Decimal = Field(alias="activeMrr", serialization_alias="activeMrr")
    total_subscriptions: int = Field(alias="totalSubscriptions", serialization_alias="totalSubscriptions")
    status_counts: dict = Field(alias="statusCounts", serialization_alias="statusCounts")

    model_config = {"populate_by_name": True}


class HQRateChangeResponse(BaseModel):
    """Rate change history entry."""
    id: str
    previous_mrr: Decimal = Field(alias="previousMrr", serialization_alias="previousMrr")
    new_mrr: Decimal = Field(alias="newMrr", serialization_alias="newMrr")
    reason: Optional[str] = None
    effective_date: datetime = Field(alias="effectiveDate", serialization_alias="effectiveDate")
    changed_by_id: Optional[str] = Field(None, alias="changedById", serialization_alias="changedById")
    changed_by_name: Optional[str] = Field(None, alias="changedByName", serialization_alias="changedByName")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


# ============================================================================
# Contractor Settlement Schemas (1099 Payments)
# ============================================================================

SettlementStatusType = Literal[
    "draft", "pending_approval", "approved", "processing", "paid", "failed", "cancelled"
]
SettlementItemType = Literal["commission", "bonus", "reimbursement", "deduction"]


class HQContractorSettlementItem(BaseModel):
    """Line item in a contractor settlement."""
    type: SettlementItemType
    description: str
    amount: Decimal
    reference_id: Optional[str] = Field(None, alias="referenceId", serialization_alias="referenceId")
    rate: Optional[Decimal] = None  # Commission percentage if applicable
    base_amount: Optional[Decimal] = Field(None, alias="baseAmount", serialization_alias="baseAmount")

    model_config = {"populate_by_name": True}


class HQContractorSettlementCreate(BaseModel):
    """Create a new contractor settlement."""
    contractor_id: str = Field(alias="contractorId")
    period_start: datetime = Field(alias="periodStart")
    period_end: datetime = Field(alias="periodEnd")
    payment_date: datetime = Field(alias="paymentDate")
    items: List[HQContractorSettlementItem] = []
    notes: Optional[str] = None
    include_pending_commissions: bool = Field(True, alias="includePendingCommissions")

    model_config = {"populate_by_name": True}


class HQContractorSettlementUpdate(BaseModel):
    """Update a contractor settlement."""
    payment_date: Optional[datetime] = Field(None, alias="paymentDate")
    items: Optional[List[HQContractorSettlementItem]] = None
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class HQContractorSettlementResponse(BaseModel):
    """Contractor settlement response."""
    id: str
    contractor_id: str = Field(alias="contractorId", serialization_alias="contractorId")
    contractor_name: str = Field(alias="contractorName", serialization_alias="contractorName")
    contractor_email: str = Field(alias="contractorEmail", serialization_alias="contractorEmail")
    settlement_number: str = Field(alias="settlementNumber", serialization_alias="settlementNumber")
    period_start: datetime = Field(alias="periodStart", serialization_alias="periodStart")
    period_end: datetime = Field(alias="periodEnd", serialization_alias="periodEnd")
    payment_date: datetime = Field(alias="paymentDate", serialization_alias="paymentDate")
    status: SettlementStatusType
    items: List[HQContractorSettlementItem] = []
    total_commission: Decimal = Field(alias="totalCommission", serialization_alias="totalCommission")
    total_bonus: Decimal = Field(alias="totalBonus", serialization_alias="totalBonus")
    total_reimbursements: Decimal = Field(alias="totalReimbursements", serialization_alias="totalReimbursements")
    total_deductions: Decimal = Field(alias="totalDeductions", serialization_alias="totalDeductions")
    net_payment: Decimal = Field(alias="netPayment", serialization_alias="netPayment")
    notes: Optional[str] = None
    approved_by_id: Optional[str] = Field(None, alias="approvedById", serialization_alias="approvedById")
    approved_at: Optional[datetime] = Field(None, alias="approvedAt", serialization_alias="approvedAt")
    paid_at: Optional[datetime] = Field(None, alias="paidAt", serialization_alias="paidAt")
    payment_reference: Optional[str] = Field(None, alias="paymentReference", serialization_alias="paymentReference")
    payment_method: Optional[str] = Field(None, alias="paymentMethod", serialization_alias="paymentMethod")
    created_at: datetime = Field(alias="createdAt", serialization_alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt", serialization_alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}

    @classmethod
    def from_orm_model(cls, s, contractor_name: str = "", contractor_email: str = "") -> "HQContractorSettlementResponse":
        """Convert ORM model to response."""
        return cls(
            id=s.id,
            contractorId=s.contractor_id,
            contractorName=contractor_name or (
                f"{s.contractor.first_name} {s.contractor.last_name}" if s.contractor else ""
            ),
            contractorEmail=contractor_email or (s.contractor.email if s.contractor else ""),
            settlementNumber=s.settlement_number,
            periodStart=s.period_start,
            periodEnd=s.period_end,
            paymentDate=s.payment_date,
            status=s.status.value if hasattr(s.status, 'value') else str(s.status),
            items=s.items or [],
            totalCommission=s.total_commission or 0,
            totalBonus=s.total_bonus or 0,
            totalReimbursements=s.total_reimbursements or 0,
            totalDeductions=s.total_deductions or 0,
            netPayment=s.net_payment or 0,
            notes=s.notes,
            approvedById=s.approved_by_id,
            approvedAt=s.approved_at,
            paidAt=s.paid_at,
            paymentReference=s.payment_reference,
            paymentMethod=s.payment_method,
            createdAt=s.created_at,
            updatedAt=s.updated_at,
        )


class HQContractorSettlementApproval(BaseModel):
    """Approve a contractor settlement."""
    notes: Optional[str] = None


class HQContractorSettlementPayment(BaseModel):
    """Mark a contractor settlement as paid."""
    payment_reference: str = Field(alias="paymentReference")
    payment_method: str = Field(alias="paymentMethod")  # check, direct_deposit, wire
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}

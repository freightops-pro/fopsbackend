"""
Multi-Authority Operations Schemas

Pydantic schemas for multi-authority operations including carrier, brokerage, NVOCC, and freight forwarder operations.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


class AuthorityType(str, Enum):
    """Types of operating authorities"""
    CARRIER = "carrier"
    BROKERAGE = "brokerage"
    NVOCC = "nvocc"
    FREIGHT_FORWARDER = "forwarder"


class PaymentTerms(str, Enum):
    """Payment terms options"""
    NET_15 = "net_15"
    NET_30 = "net_30"
    NET_45 = "net_45"
    NET_60 = "net_60"
    COD = "cod"
    PREPAID = "prepaid"


class RelationshipType(str, Enum):
    """Customer relationship types"""
    DIRECT = "direct"
    BROKER = "broker"
    FORWARDER = "forwarder"
    NVOCC = "nvocc"


class IntegrationType(str, Enum):
    """Integration types"""
    ELD = "eld"
    LOADBOARD = "loadboard"
    FACTORING = "factoring"
    ACCOUNTING = "accounting"
    CRM = "crm"
    TMS = "tms"


class SyncFrequency(str, Enum):
    """Sync frequency options"""
    REAL_TIME = "real-time"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


# Authority Schemas
class AuthorityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Authority name")
    authority_type: AuthorityType = Field(..., description="Type of authority")
    dot_mc_number: Optional[str] = Field(None, max_length=20, description="DOT/MC number")
    fmc_number: Optional[str] = Field(None, max_length=20, description="FMC number for NVOCC")
    license_number: Optional[str] = Field(None, max_length=50, description="Other license numbers")
    effective_date: Optional[datetime] = Field(None, description="Effective date")
    expiration_date: Optional[datetime] = Field(None, description="Expiration date")
    contact_name: Optional[str] = Field(None, max_length=100, description="Contact person name")
    contact_phone: Optional[str] = Field(None, max_length=20, description="Contact phone")
    contact_email: Optional[str] = Field(None, max_length=100, description="Contact email")
    business_address: Optional[str] = Field(None, description="Business address")
    settings: Optional[Dict[str, Any]] = Field(None, description="Authority-specific settings")
    insurance_requirements: Optional[Dict[str, Any]] = Field(None, description="Insurance details")
    compliance_requirements: Optional[Dict[str, Any]] = Field(None, description="Compliance settings")
    default_payment_terms: PaymentTerms = Field(PaymentTerms.NET_30, description="Default payment terms")
    default_currency: str = Field("USD", max_length=3, description="Default currency")
    tax_id: Optional[str] = Field(None, max_length=20, description="Tax ID")

    @validator('contact_email')
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v

    @validator('dot_mc_number')
    def validate_dot_mc(cls, v, values):
        if values.get('authority_type') == AuthorityType.CARRIER and not v:
            raise ValueError('DOT/MC number is required for carrier authority')
        return v

    @validator('fmc_number')
    def validate_fmc(cls, v, values):
        if values.get('authority_type') == AuthorityType.NVOCC and not v:
            raise ValueError('FMC number is required for NVOCC authority')
        return v


class AuthorityCreate(AuthorityBase):
    """Schema for creating a new authority"""
    pass


class AuthorityUpdate(BaseModel):
    """Schema for updating an authority"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    authority_type: Optional[AuthorityType] = None
    dot_mc_number: Optional[str] = Field(None, max_length=20)
    fmc_number: Optional[str] = Field(None, max_length=20)
    license_number: Optional[str] = Field(None, max_length=50)
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    contact_name: Optional[str] = Field(None, max_length=100)
    contact_phone: Optional[str] = Field(None, max_length=20)
    contact_email: Optional[str] = Field(None, max_length=100)
    business_address: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    insurance_requirements: Optional[Dict[str, Any]] = None
    compliance_requirements: Optional[Dict[str, Any]] = None
    default_payment_terms: Optional[PaymentTerms] = None
    default_currency: Optional[str] = Field(None, max_length=3)
    tax_id: Optional[str] = Field(None, max_length=20)


class AuthorityResponse(AuthorityBase):
    """Schema for authority response"""
    id: str
    company_id: str
    is_active: bool
    is_primary: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Authority User Schemas
class AuthorityUserBase(BaseModel):
    user_id: str = Field(..., description="User ID")
    can_view: bool = Field(True, description="Can view authority data")
    can_edit: bool = Field(False, description="Can edit authority data")
    can_manage: bool = Field(False, description="Can manage authority")
    can_create_loads: bool = Field(False, description="Can create loads for this authority")
    can_view_financials: bool = Field(False, description="Can view authority financials")
    can_manage_customers: bool = Field(False, description="Can manage customers for this authority")
    is_primary_authority: bool = Field(False, description="Is this the user's primary authority")


class AuthorityUserCreate(AuthorityUserBase):
    """Schema for creating authority user assignment"""
    pass


class AuthorityUserUpdate(BaseModel):
    """Schema for updating authority user assignment"""
    can_view: Optional[bool] = None
    can_edit: Optional[bool] = None
    can_manage: Optional[bool] = None
    can_create_loads: Optional[bool] = None
    can_view_financials: Optional[bool] = None
    can_manage_customers: Optional[bool] = None
    is_primary_authority: Optional[bool] = None


class AuthorityUserResponse(AuthorityUserBase):
    """Schema for authority user response"""
    id: str
    authority_id: str
    assigned_at: datetime
    assigned_by_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Authority Financials Schemas
class AuthorityFinancialsBase(BaseModel):
    period_start: datetime = Field(..., description="Period start date")
    period_end: datetime = Field(..., description="Period end date")
    period_type: str = Field("monthly", description="Period type (daily, weekly, monthly, yearly)")
    total_revenue: int = Field(0, description="Total revenue in cents")
    load_count: int = Field(0, description="Number of loads")
    average_rate: int = Field(0, description="Average rate per load in cents")
    gross_revenue: int = Field(0, description="Gross revenue in cents")
    carrier_payments: int = Field(0, description="Payments to carriers in cents")
    ocean_freight_costs: int = Field(0, description="Ocean freight costs in cents")
    port_charges: int = Field(0, description="Port and terminal charges in cents")
    fuel_cost: int = Field(0, description="Fuel costs in cents")
    maintenance_cost: int = Field(0, description="Maintenance costs in cents")
    driver_pay: int = Field(0, description="Driver pay in cents")
    overhead_cost: int = Field(0, description="Overhead costs in cents")
    total_expenses: int = Field(0, description="Total expenses in cents")
    gross_profit: int = Field(0, description="Gross profit in cents")
    net_profit: int = Field(0, description="Net profit in cents")
    profit_margin: int = Field(0, description="Profit margin percentage * 100")
    loads_managed: int = Field(0, description="Number of loads managed")
    customer_count: int = Field(0, description="Number of customers")

    @validator('period_end')
    def validate_period_end(cls, v, values):
        if 'period_start' in values and v <= values['period_start']:
            raise ValueError('Period end must be after period start')
        return v


class AuthorityFinancialsCreate(AuthorityFinancialsBase):
    """Schema for creating authority financials"""
    pass


class AuthorityFinancialsUpdate(BaseModel):
    """Schema for updating authority financials"""
    total_revenue: Optional[int] = None
    load_count: Optional[int] = None
    average_rate: Optional[int] = None
    gross_revenue: Optional[int] = None
    carrier_payments: Optional[int] = None
    ocean_freight_costs: Optional[int] = None
    port_charges: Optional[int] = None
    fuel_cost: Optional[int] = None
    maintenance_cost: Optional[int] = None
    driver_pay: Optional[int] = None
    overhead_cost: Optional[int] = None
    total_expenses: Optional[int] = None
    gross_profit: Optional[int] = None
    net_profit: Optional[int] = None
    profit_margin: Optional[int] = None
    loads_managed: Optional[int] = None
    customer_count: Optional[int] = None


class AuthorityFinancialsResponse(AuthorityFinancialsBase):
    """Schema for authority financials response"""
    id: str
    authority_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Authority Customer Schemas
class AuthorityCustomerBase(BaseModel):
    customer_id: str = Field(..., description="Customer ID")
    is_primary: bool = Field(False, description="Is this the primary authority for this customer")
    relationship_type: RelationshipType = Field(RelationshipType.DIRECT, description="Relationship type")
    payment_terms: Optional[PaymentTerms] = Field(None, description="Payment terms override")
    credit_limit: Optional[int] = Field(None, description="Credit limit in cents")
    special_instructions: Optional[str] = Field(None, description="Special instructions")
    contract_start_date: Optional[datetime] = Field(None, description="Contract start date")
    contract_end_date: Optional[datetime] = Field(None, description="Contract end date")
    contract_terms: Optional[Dict[str, Any]] = Field(None, description="Contract terms")


class AuthorityCustomerCreate(AuthorityCustomerBase):
    """Schema for creating authority customer assignment"""
    pass


class AuthorityCustomerUpdate(BaseModel):
    """Schema for updating authority customer assignment"""
    is_primary: Optional[bool] = None
    relationship_type: Optional[RelationshipType] = None
    payment_terms: Optional[PaymentTerms] = None
    credit_limit: Optional[int] = None
    special_instructions: Optional[str] = None
    contract_start_date: Optional[datetime] = None
    contract_end_date: Optional[datetime] = None
    contract_terms: Optional[Dict[str, Any]] = None


class AuthorityCustomerResponse(AuthorityCustomerBase):
    """Schema for authority customer response"""
    id: str
    authority_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Authority Integration Schemas
class AuthorityIntegrationBase(BaseModel):
    integration_type: IntegrationType = Field(..., description="Type of integration")
    provider_name: str = Field(..., min_length=1, max_length=100, description="Provider name")
    provider_id: Optional[str] = Field(None, max_length=100, description="External provider ID")
    configuration: Optional[Dict[str, Any]] = Field(None, description="Integration configuration")
    credentials: Optional[Dict[str, Any]] = Field(None, description="Encrypted credentials")
    sync_frequency: SyncFrequency = Field(SyncFrequency.DAILY, description="Sync frequency")


class AuthorityIntegrationCreate(AuthorityIntegrationBase):
    """Schema for creating authority integration"""
    pass


class AuthorityIntegrationUpdate(BaseModel):
    """Schema for updating authority integration"""
    provider_name: Optional[str] = Field(None, min_length=1, max_length=100)
    provider_id: Optional[str] = Field(None, max_length=100)
    configuration: Optional[Dict[str, Any]] = None
    credentials: Optional[Dict[str, Any]] = None
    sync_frequency: Optional[SyncFrequency] = None
    is_active: Optional[bool] = None


class AuthorityIntegrationResponse(AuthorityIntegrationBase):
    """Schema for authority integration response"""
    id: str
    authority_id: str
    is_active: bool
    last_sync: Optional[datetime]
    error_count: int
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Authority Analytics Schemas
class AuthorityAnalyticsResponse(BaseModel):
    """Schema for authority analytics response"""
    authority_info: Dict[str, Any]
    metrics: Dict[str, Any]
    financials: List[Dict[str, Any]]
    period_type: str
    months_analyzed: int


# Authority Summary Schemas
class AuthoritySummary(BaseModel):
    """Schema for authority summary"""
    id: str
    name: str
    authority_type: AuthorityType
    is_primary: bool
    is_active: bool
    user_count: int
    customer_count: int
    integration_count: int
    total_revenue: int
    total_profit: int
    load_count: int

    class Config:
        from_attributes = True


class CompanyAuthoritiesResponse(BaseModel):
    """Schema for company authorities response"""
    company_id: str
    authorities: List[AuthoritySummary]
    total_authorities: int
    primary_authority: Optional[AuthoritySummary]


# Authority Switch Schema
class AuthoritySwitchRequest(BaseModel):
    """Schema for switching user authority"""
    authority_id: str = Field(..., description="New authority ID to switch to")

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class BankingCustomerCreate(BaseModel):
    legal_name: str
    tax_id: str


class BankingCustomerResponse(BaseModel):
    id: str
    status: str
    external_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BankingAccountCreate(BaseModel):
    customer_id: str
    account_type: str
    nickname: Optional[str] = None


class BankingAccountResponse(BaseModel):
    id: str
    customer_id: str
    account_type: str
    nickname: Optional[str]
    currency: str
    balance: float
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BankingCardCreate(BaseModel):
    account_id: str
    cardholder_name: str
    card_type: str = Field(..., pattern="^(virtual|physical)$")


class BankingCardResponse(BaseModel):
    id: str
    account_id: str
    cardholder_name: str
    last_four: str
    card_type: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BankingTransactionResponse(BaseModel):
    id: str
    account_id: str
    amount: float
    currency: str
    description: Optional[str]
    category: str
    posted_at: datetime
    pending: bool

    model_config = {"from_attributes": True}


# =============================================================================
# Banking Application Schemas (Multi-step KYB Onboarding)
# =============================================================================


class PersonCreate(BaseModel):
    """Schema for creating a person (primary applicant, owner, or signer)."""

    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    dob: Optional[date] = None
    ssn_last4: Optional[str] = Field(None, max_length=4)
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    citizenship: Optional[str] = None
    id_type: Optional[str] = None
    id_file_url: Optional[str] = None
    ownership_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    is_controller: bool = False
    role: Optional[str] = None


class PersonResponse(BaseModel):
    """Response schema for a person."""

    id: str
    person_type: str
    first_name: str
    last_name: str
    dob: Optional[date] = None
    ssn_last4: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    citizenship: Optional[str] = None
    ownership_pct: Optional[float] = None
    is_controller: bool = False
    role: Optional[str] = None
    kyc_status: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BusinessCreate(BaseModel):
    """Schema for creating business details."""

    legal_name: str = Field(..., min_length=1)
    dba: Optional[str] = None
    entity_type: str = Field(..., min_length=1)
    ein: Optional[str] = None
    formation_date: Optional[date] = None
    state_of_formation: Optional[str] = None
    physical_address: Optional[str] = None
    mailing_address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    naics_code: Optional[str] = None
    industry_description: Optional[str] = None
    employees: Optional[int] = None
    estimated_revenue: Optional[Decimal] = None
    monthly_volume: Optional[Decimal] = None
    cash_heavy: bool = False
    international_transactions: bool = False


class BusinessResponse(BaseModel):
    """Response schema for business details."""

    id: str
    legal_name: str
    dba: Optional[str] = None
    entity_type: str
    ein: Optional[str] = None
    formation_date: Optional[date] = None
    state_of_formation: Optional[str] = None
    physical_address: Optional[str] = None
    mailing_address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    naics_code: Optional[str] = None
    employees: Optional[int] = None
    estimated_revenue: Optional[float] = None
    monthly_volume: Optional[float] = None
    cash_heavy: bool = False
    international_transactions: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentCreate(BaseModel):
    """Schema for document metadata."""

    doc_type: str  # articles, operating_agreement, ein_letter, dba_cert, other
    file_name: Optional[str] = None
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None


class DocumentResponse(BaseModel):
    """Response schema for a document."""

    id: str
    doc_type: str
    file_name: Optional[str] = None
    file_url: Optional[str] = None
    verified: bool = False
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class AccountChoices(BaseModel):
    """Schema for account selection preferences."""

    products: List[str] = Field(default_factory=list)  # business_checking, business_savings, etc.
    add_debit_card: bool = True
    payroll_integration: bool = False
    initial_deposit: Optional[str] = None
    funding_method: Optional[str] = None  # wire, ach, check, cash


class BankingApplicationCreate(BaseModel):
    """Schema for creating a complete banking application."""

    # Primary applicant
    primary: PersonCreate

    # Beneficial owners (≥25% ownership or significant control)
    owners: List[PersonCreate] = Field(default_factory=list)

    # Authorized signers
    signers: List[PersonCreate] = Field(default_factory=list)

    # Business details
    business: BusinessCreate

    # Document metadata (file URLs after upload)
    documents: Dict[str, Optional[str]] = Field(default_factory=dict)

    # Account preferences
    account_choices: AccountChoices

    @field_validator("owners")
    @classmethod
    def validate_ownership(cls, v: List[PersonCreate]) -> List[PersonCreate]:
        """Validate that ownership percentages sum to 100% if owners present."""
        if not v:
            return v
        total = sum(float(o.ownership_pct or 0) for o in v)
        if abs(total - 100) > 0.01:
            raise ValueError(f"Total ownership must equal 100%, got {total}%")
        return v


class BankingApplicationResponse(BaseModel):
    """Response schema for a banking application."""

    id: str
    reference: str
    status: str
    kyc_status: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Nested data
    business: Optional[BusinessResponse] = None
    primary: Optional[PersonResponse] = None
    owners: List[PersonResponse] = Field(default_factory=list)
    signers: List[PersonResponse] = Field(default_factory=list)
    documents: List[DocumentResponse] = Field(default_factory=list)
    account_choices: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class BankingApplicationSummary(BaseModel):
    """Summary of a banking application for list views."""

    id: str
    reference: str
    status: str
    business_name: Optional[str] = None
    kyc_status: Optional[str] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BankingApplicationUpdate(BaseModel):
    """Schema for updating application status."""

    status: Optional[str] = None
    kyc_status: Optional[str] = None
    rejection_reason: Optional[str] = None


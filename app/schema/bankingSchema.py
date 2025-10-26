from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

# Customer Schemas
class BankingCustomerCreate(BaseModel):
    company_id: UUID
    legal_name: str = Field(..., min_length=1, max_length=255)
    ein: str = Field(..., min_length=9, max_length=20)
    business_address: str = Field(..., min_length=1)
    business_city: str = Field(..., min_length=1, max_length=100)
    business_state: str = Field(..., min_length=2, max_length=50)
    business_zip_code: str = Field(..., min_length=5, max_length=20)
    naics_code: str = Field(..., min_length=1, max_length=10)
    website: Optional[str] = Field(None, max_length=255)
    control_person_name: str = Field(..., min_length=1, max_length=255)

class BankingCustomerUpdate(BaseModel):
    legal_name: Optional[str] = Field(None, min_length=1, max_length=255)
    business_address: Optional[str] = Field(None, min_length=1)
    business_city: Optional[str] = Field(None, min_length=1, max_length=100)
    business_state: Optional[str] = Field(None, min_length=2, max_length=50)
    business_zip_code: Optional[str] = Field(None, min_length=5, max_length=20)
    website: Optional[str] = Field(None, max_length=255)
    control_person_name: Optional[str] = Field(None, min_length=1, max_length=255)

class BankingCustomerOut(BaseModel):
    id: UUID
    company_id: UUID
    synctera_person_id: Optional[str]
    synctera_business_id: Optional[str]
    legal_name: str
    ein: str
    business_address: str
    business_city: str
    business_state: str
    business_zip_code: str
    naics_code: str
    website: Optional[str]
    control_person_name: str
    kyb_status: str
    kyb_submitted_at: Optional[datetime]
    kyb_approved_at: Optional[datetime]
    kyb_rejection_reason: Optional[str]
    status: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Account Schemas
class BankingAccountCreate(BaseModel):
    customer_id: UUID
    account_type: str = Field(..., pattern="^(checking|savings|escrow)$")
    account_name: str = Field(..., min_length=1, max_length=255)

class BankingAccountUpdate(BaseModel):
    account_name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[str] = Field(None, pattern="^(active|suspended|closed|pending)$")

class BankingAccountOut(BaseModel):
    id: UUID
    customer_id: UUID
    synctera_account_id: Optional[str]
    account_type: str
    account_number: Optional[str]
    routing_number: Optional[str]
    account_name: str
    available_balance: float
    current_balance: float
    pending_balance: float
    status: str
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Card Schemas
class BankingCardCreate(BaseModel):
    account_id: UUID
    card_type: str = Field(..., pattern="^(virtual|physical)$")
    card_name: str = Field(..., min_length=1, max_length=255)
    assigned_to: Optional[str] = Field(None, max_length=255)
    daily_limit: Optional[float] = Field(None, ge=0)
    monthly_limit: Optional[float] = Field(None, ge=0)
    restrictions: Optional[Dict[str, Any]] = None

class BankingCardUpdate(BaseModel):
    card_name: Optional[str] = Field(None, min_length=1, max_length=255)
    assigned_to: Optional[str] = Field(None, max_length=255)
    daily_limit: Optional[float] = Field(None, ge=0)
    monthly_limit: Optional[float] = Field(None, ge=0)
    restrictions: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(None, pattern="^(active|locked|expired|cancelled)$")
    is_enabled: Optional[bool] = None

class BankingCardOut(BaseModel):
    id: UUID
    account_id: UUID
    synctera_card_id: Optional[str]
    card_type: str
    card_number: Optional[str]  # Will be masked
    last_four: Optional[str]
    expiry_date: Optional[str]
    card_name: str
    assigned_to: Optional[str]
    daily_limit: Optional[float]
    monthly_limit: Optional[float]
    restrictions: Optional[Dict[str, Any]]
    status: str
    is_enabled: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Transaction Schemas
class BankingTransactionOut(BaseModel):
    id: UUID
    account_id: UUID
    card_id: Optional[UUID]
    synctera_transaction_id: Optional[str]
    amount: float
    type: str
    category: Optional[str]
    description: Optional[str]
    merchant_name: Optional[str]
    merchant_category: Optional[str]
    reference_id: Optional[str]
    transaction_date: datetime
    posted_date: Optional[datetime]
    status: str
    transaction_metadata: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True

# Transfer Schemas
class BankingTransferCreate(BaseModel):
    from_account_id: UUID
    to_account_id: Optional[UUID] = None
    amount: float = Field(..., gt=0)
    transfer_type: str = Field(..., pattern="^(ach|wire|internal)$")
    description: Optional[str] = None
    recipient_name: Optional[str] = Field(None, max_length=255)
    recipient_account: Optional[str] = Field(None, max_length=255)
    recipient_routing: Optional[str] = Field(None, max_length=255)
    scheduled_date: Optional[datetime] = None

class BankingTransferOut(BaseModel):
    id: UUID
    from_account_id: UUID
    to_account_id: Optional[UUID]
    synctera_transfer_id: Optional[str]
    amount: float
    transfer_type: str
    description: Optional[str]
    recipient_name: Optional[str]
    recipient_account: Optional[str]
    recipient_routing: Optional[str]
    status: str
    scheduled_date: Optional[datetime]
    completed_date: Optional[datetime]
    transfer_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# KYB Application Schemas
class KYBApplicationCreate(BaseModel):
    customer_id: UUID
    # Additional KYB-specific fields can be added here

class KYBApplicationOut(BaseModel):
    customer_id: UUID
    kyb_status: str
    kyb_submitted_at: Optional[datetime]
    kyb_approved_at: Optional[datetime]
    kyb_rejection_reason: Optional[str]

    class Config:
        from_attributes = True

# Banking Status Schemas
class BankingStatusOut(BaseModel):
    has_customer: bool
    has_kyb: bool
    kyb_status: Optional[str]
    has_accounts: bool
    has_cards: bool
    total_balance: float
    account_count: int
    card_count: int

# Response Schemas
class BankingCustomerListOut(BaseModel):
    customers: List[BankingCustomerOut]
    total: int

class BankingAccountListOut(BaseModel):
    accounts: List[BankingAccountOut]
    total: int

class BankingCardListOut(BaseModel):
    cards: List[BankingCardOut]
    total: int

class BankingTransactionListOut(BaseModel):
    transactions: List[BankingTransactionOut]
    total: int

class BankingTransferListOut(BaseModel):
    transfers: List[BankingTransferOut]
    total: int

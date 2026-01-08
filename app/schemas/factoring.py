from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class FactoringProviderBase(BaseModel):
    """Base factoring provider schema."""
    provider_name: str
    factoring_rate: float = Field(..., description="Percentage rate (e.g., 3.5 for 3.5%)")
    advance_rate: float = Field(default=95.0, description="Percentage advanced (e.g., 95%)")
    payment_terms_days: Optional[float] = None
    is_active: bool = True


class FactoringProviderCreate(FactoringProviderBase):
    """Schema for creating a factoring provider."""
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    webhook_secret: Optional[str] = None


class FactoringProviderUpdate(BaseModel):
    """Schema for updating a factoring provider."""
    provider_name: Optional[str] = None
    factoring_rate: Optional[float] = None
    advance_rate: Optional[float] = None
    payment_terms_days: Optional[float] = None
    is_active: Optional[bool] = None
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    webhook_secret: Optional[str] = None


class FactoringProviderResponse(FactoringProviderBase):
    """Schema for factoring provider response."""
    id: str
    company_id: str
    is_configured: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FactoringTransactionBase(BaseModel):
    """Base factoring transaction schema."""
    invoice_amount: float
    factoring_fee: float
    advance_amount: float
    reserve_amount: float


class SendToFactoringRequest(BaseModel):
    """Request to send a load/invoice to factoring."""
    load_id: str
    invoice_id: Optional[str] = None
    documents: Optional[List[str]] = Field(default_factory=list, description="Document URLs or IDs")
    notes: Optional[str] = None


class BatchSendToFactoringRequest(BaseModel):
    """Request to send multiple loads to factoring."""
    load_ids: List[str] = Field(..., min_length=1)
    batch_notes: Optional[str] = None


class FactoringTransactionResponse(FactoringTransactionBase):
    """Schema for factoring transaction response."""
    id: str
    company_id: str
    provider_id: str
    load_id: str
    invoice_id: Optional[str]
    status: str
    external_reference_id: Optional[str]
    batch_id: Optional[str]

    # Timestamps
    sent_at: Optional[datetime]
    accepted_at: Optional[datetime]
    verified_at: Optional[datetime]
    funded_at: Optional[datetime]
    paid_at: Optional[datetime]
    rejected_at: Optional[datetime]

    # Payment details
    payment_method: Optional[str]
    payment_reference: Optional[str]

    rejection_reason: Optional[str]
    notes: Optional[str]

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FactoringWebhookPayload(BaseModel):
    """Webhook payload from factoring provider."""
    transaction_id: str  # Our internal ID or external reference
    external_reference_id: Optional[str] = None
    status: Literal["SENT", "ACCEPTED", "VERIFIED", "FUNDED", "PAID", "REJECTED"]
    timestamp: datetime
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    rejection_reason: Optional[str] = None
    metadata: Optional[dict] = None


class FactoringStatusUpdateRequest(BaseModel):
    """Manual status update for factoring transaction."""
    status: Literal["PENDING", "SENT", "ACCEPTED", "VERIFIED", "FUNDED", "PAID", "REJECTED", "CANCELLED"]
    notes: Optional[str] = None


class FactoringSummary(BaseModel):
    """Summary of factoring activity."""
    total_transactions: int
    total_factored_amount: float
    total_fees: float
    pending_count: int
    funded_count: int
    paid_count: int

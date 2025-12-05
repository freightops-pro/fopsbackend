"""Pydantic schemas for integration management."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IntegrationInfo(BaseModel):
    """Integration catalog item schema."""

    id: str
    integration_key: str
    display_name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    integration_type: str  # "eld", "load_board", "accounting", "factoring", "port"
    auth_type: str  # "oauth2", "api_key", "basic_auth", "password", "jwt"
    requires_oauth: bool = False
    features: Optional[List[str]] = None
    support_email: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IntegrationListResponse(BaseModel):
    """Response schema for listing available integrations."""

    integrations: List[IntegrationInfo]


class CompanyIntegrationBase(BaseModel):
    """Base schema for company integration."""

    integration_id: str
    status: str = "not-activated"  # "not-activated", "active", "disabled", "error", "pending"
    credentials: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    auto_sync: bool = True
    sync_interval_minutes: int = 60


class CompanyIntegrationCreate(CompanyIntegrationBase):
    """Schema for creating a company integration."""

    pass


class CompanyIntegrationUpdate(BaseModel):
    """Schema for updating a company integration."""

    credentials: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    auto_sync: Optional[bool] = None
    sync_interval_minutes: Optional[int] = None


class CompanyIntegrationResponse(CompanyIntegrationBase):
    """Response schema for company integration."""

    id: str
    company_id: str
    last_sync_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error_message: Optional[str] = None
    consecutive_failures: int = 0
    activated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    integration: Optional[IntegrationInfo] = None

    class Config:
        from_attributes = True


class IntegrationStats(BaseModel):
    """Statistics about company integrations."""

    total_integrations: int
    active_connections: int
    recent_syncs: int
    failed_syncs: int
    by_type: Dict[str, int]


# Motive-specific schemas
class MotiveCredentials(BaseModel):
    """Schema for Motive OAuth credentials."""

    client_id: str = Field(..., description="Motive OAuth client ID")
    client_secret: str = Field(..., description="Motive OAuth client secret")


class MotiveConnectionTest(BaseModel):
    """Response schema for Motive connection test."""

    connected: bool
    message: str
    company: Optional[str] = None


# Samsara-specific schemas
class SamsaraCredentials(BaseModel):
    """Schema for Samsara OAuth credentials."""

    client_id: str = Field(..., description="Samsara OAuth client ID")
    client_secret: str = Field(..., description="Samsara OAuth client secret")
    use_eu: bool = Field(False, description="Use EU data center endpoint")


class SamsaraConnectionTest(BaseModel):
    """Response schema for Samsara connection test."""

    connected: bool
    message: str
    organization: Optional[str] = None


# ==================== HQ ADMIN SCHEMAS ====================


class IntegrationHealthItem(BaseModel):
    """Health status for a single company integration."""

    id: str
    company_id: str
    company_name: Optional[str] = None
    integration_key: str
    integration_name: str
    integration_type: str
    status: str  # "active", "error", "disabled", "pending"
    last_sync_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error_message: Optional[str] = None
    consecutive_failures: int = 0
    health_status: str = "healthy"  # "healthy", "warning", "critical"


# HaulPay-specific schemas
class HaulPayDocumentAttachment(BaseModel):
    """Schema for document attachment to invoice."""

    url: str = Field(..., description="URL or storage key to the document")
    document_type: str = Field(
        ...,
        description="Type of document: pod, bol, rate_confirmation, invoice, delivery_receipt, etc."
    )
    filename: str = Field(..., description="Original filename")


class HaulPayInvoiceSubmission(BaseModel):
    """Schema for submitting a single invoice to HaulPay for factoring."""

    invoice_id: str = Field(..., description="Internal invoice ID")
    debtor_id: str = Field(..., description="HaulPay debtor ID (broker/customer)")
    carrier_id: Optional[str] = Field(None, description="HaulPay carrier ID (optional, uses default if not provided)")
    document_urls: Optional[List[HaulPayDocumentAttachment]] = Field(
        None,
        description="Optional list of documents to attach (POD, BOL, rate confirmation, etc.)"
    )


class HaulPayBatchSubmissionRequest(BaseModel):
    """Schema for batch submitting multiple invoices to HaulPay."""

    invoices: List[HaulPayInvoiceSubmission] = Field(..., min_length=1, description="List of invoices to submit for factoring")


class HaulPayInvoiceSubmissionResult(BaseModel):
    """Result for a single invoice submission in a batch."""

    invoice_id: str
    success: bool
    haulpay_invoice_id: Optional[str] = None
    status: Optional[str] = None
    advance_rate: Optional[float] = None
    advance_amount: Optional[float] = None
    reserve_amount: Optional[float] = None
    factoring_fee: Optional[float] = None
    error: Optional[str] = None


class HaulPayBatchSubmissionResponse(BaseModel):
    """Response for batch invoice submission."""

    total: int
    successful: int
    failed: int
    results: List[HaulPayInvoiceSubmissionResult]


class HaulPayInvoiceTracking(BaseModel):
    """Factoring tracking information for an invoice."""

    invoice_id: str
    invoice_number: str
    factored: bool
    haulpay_invoice_id: Optional[str] = None
    submitted_at: Optional[str] = None
    status: Optional[str] = None
    advance_rate: Optional[float] = None
    advance_amount: Optional[float] = None
    reserve_amount: Optional[float] = None
    factoring_fee: Optional[float] = None


class IntegrationTypeHealth(BaseModel):
    """Health summary for an integration type."""

    integration_type: str
    integration_key: str
    integration_name: str
    total_connections: int
    active_connections: int
    error_connections: int
    healthy_connections: int
    warning_connections: int
    critical_connections: int
    last_sync_overall: Optional[datetime] = None


class HQIntegrationHealthResponse(BaseModel):
    """Overall HQ integration health dashboard response."""

    total_companies: int
    total_connections: int
    active_connections: int
    error_connections: int
    healthy_connections: int
    warning_connections: int
    critical_connections: int
    by_type: List[IntegrationTypeHealth]
    recent_errors: List[IntegrationHealthItem]


class FailedSyncListResponse(BaseModel):
    """List of failed integration syncs for HQ monitoring."""

    items: List[IntegrationHealthItem]
    total: int


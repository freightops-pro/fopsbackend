"""
WEX EnCompass API Schemas for fuel card payments and virtual card management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ==================== REQUEST SCHEMAS ====================


class CardControlsRequest(BaseModel):
    """Virtual card control settings."""
    min_auth_date: Optional[str] = Field(None, description="Earliest card activation date (YYYY-MM-DD)")
    max_auth_date: Optional[str] = Field(None, description="Latest card authorization date (YYYY-MM-DD)")
    credit_limit: Optional[float] = Field(None, description="Maximum card limit")
    number_of_authorizations: Optional[int] = Field(None, description="Max number of uses")
    mcc_profile_id: Optional[str] = Field(None, description="Merchant category code profile")
    allowed_mcc_codes: Optional[List[str]] = Field(None, description="Allowed MCC codes")


class CreateFuelCardRequest(BaseModel):
    """Request to create a virtual fuel card."""
    merchant_id: str = Field(..., description="WEX merchant ID for the fuel vendor")
    amount: float = Field(..., gt=0, description="Maximum fuel purchase amount")
    driver_id: Optional[str] = Field(None, description="FreightOps driver ID")
    truck_id: Optional[str] = Field(None, description="FreightOps truck/equipment ID")
    load_id: Optional[str] = Field(None, description="Associated load ID for IFTA tracking")
    fuel_stop_location: Optional[str] = Field(None, description="Location description")
    jurisdiction: Optional[str] = Field(None, description="State/jurisdiction for IFTA")
    valid_days: int = Field(7, ge=1, le=90, description="Number of days the card is valid")


class CreateMerchantLogRequest(BaseModel):
    """Request to create a MerchantLog (payment) in WEX."""
    merchant_id: str = Field(..., description="WEX merchant ID")
    amount: float = Field(..., gt=0, description="Payment amount")
    payment_method: str = Field("merchant_charged_card", description="Payment method type")
    card_controls: Optional[CardControlsRequest] = None
    user_defined_fields: Optional[Dict[str, str]] = None
    external_reference: Optional[str] = None
    notes: Optional[str] = None


class CreateFuelVendorRequest(BaseModel):
    """Request to create a fuel vendor in WEX."""
    name: str = Field(..., min_length=1, description="Vendor business name")
    address: Optional[Dict[str, str]] = Field(
        None,
        description="Vendor address {street, city, state, postal_code, country}"
    )
    contact: Optional[Dict[str, str]] = Field(
        None,
        description="Contact info {email, phone, contact_name}"
    )
    tax_id: Optional[str] = Field(None, description="Vendor tax ID (EIN)")


class SyncTransactionsRequest(BaseModel):
    """Request to sync WEX transactions for reconciliation."""
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")


# ==================== RESPONSE SCHEMAS ====================


class VirtualCardDetails(BaseModel):
    """Virtual card details from WEX."""
    card_number: Optional[str] = Field(None, description="Virtual card number")
    security_code: Optional[str] = Field(None, description="CVV/CVC code")
    expiration_month: Optional[str] = Field(None, description="Expiration month (MM)")
    expiration_year: Optional[str] = Field(None, description="Expiration year (YYYY)")
    expiration_date: Optional[str] = Field(None, description="Formatted expiration (MM/YYYY)")
    status: Optional[str] = Field(None, description="Card status")


class FuelCardResponse(BaseModel):
    """Response containing virtual fuel card details."""
    merchant_log_id: str = Field(..., description="WEX payment/MerchantLog ID")
    card_number: Optional[str] = Field(None, description="Virtual card number")
    security_code: Optional[str] = Field(None, description="CVV")
    expiration_month: Optional[str] = None
    expiration_year: Optional[str] = None
    expiration_date: Optional[str] = Field(None, description="Formatted expiration")
    amount: float = Field(..., description="Authorized amount")
    status: Optional[str] = Field(None, description="Card status")
    valid_until: Optional[str] = Field(None, description="Card validity end date")


class CardAuthorizationResponse(BaseModel):
    """Card authorization record."""
    authorization_id: Optional[str] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    merchant_name: Optional[str] = None
    timestamp: Optional[datetime] = None


class CardTransactionResponse(BaseModel):
    """Posted card transaction record."""
    transaction_id: Optional[str] = None
    amount: Optional[float] = None
    gallons: Optional[float] = None
    price_per_gallon: Optional[float] = None
    merchant_name: Optional[str] = None
    jurisdiction: Optional[str] = None
    posted_date: Optional[datetime] = None


class FuelCardStatusResponse(BaseModel):
    """Fuel card status with usage details."""
    merchant_log_id: str
    status: Optional[str] = None
    amount: Optional[float] = None
    virtual_card: Optional[VirtualCardDetails] = None
    authorizations: List[CardAuthorizationResponse] = []
    transactions: List[CardTransactionResponse] = []
    is_used: bool = False
    total_spent: float = 0.0


class FuelVendorResponse(BaseModel):
    """Fuel vendor response."""
    merchant_id: str
    name: str
    status: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    contact: Optional[Dict[str, str]] = None


class TransactionSyncResult(BaseModel):
    """Result of transaction sync operation."""
    period: Dict[str, str]
    total_transactions: int
    created: int
    updated: int
    skipped: int


class JurisdictionSummary(BaseModel):
    """Fuel usage summary for a jurisdiction (IFTA)."""
    gallons: float
    amount: float


class FuelCardSummaryResponse(BaseModel):
    """Summary of fuel card usage for a period."""
    period: Dict[str, str]
    total_transactions: int
    total_amount: float
    total_gallons: float
    avg_price_per_gallon: float
    by_jurisdiction: Dict[str, Dict[str, float]]


class CancelFuelCardResponse(BaseModel):
    """Response for fuel card cancellation."""
    merchant_log_id: str
    status: str
    message: str


# ==================== WEBHOOK SCHEMAS ====================


class WEXAuthorizationPushPayload(BaseModel):
    """
    WEX Authorization Push Webhook payload.

    Sent in real-time when card authorizations occur.
    """
    AccountToken: Optional[str] = Field(None, description="Account token")
    AuthorizationId: str = Field(..., description="Unique authorization ID (use for deduplication)")
    CardNumber: Optional[str] = Field(None, description="Masked card number")
    AuthorizationDateTime: str = Field(..., description="When authorization occurred (ISO 8601)")
    Amount: float = Field(..., description="Authorization amount")
    ApprovalCode: Optional[str] = Field(None, description="Approval code (null for declines)")
    Response: str = Field(..., description="'Approval' or 'Decline'")
    TypeCode: Optional[str] = Field(None, description="Type code (e.g., '0100')")
    TypeDesc: Optional[str] = Field(None, description="Type description (e.g., 'Initial Request')")
    DeclineReasonCode: Optional[str] = Field(None, description="Decline reason code")
    DeclineReasonMessage: Optional[str] = Field(None, description="Decline reason message")
    AvailableCredit: Optional[float] = Field(None, description="Remaining credit after authorization")
    UniqueId: Optional[str] = Field(None, description="MerchantLog or PurchaseLog unique ID")
    CategoryCode: Optional[str] = Field(None, description="Merchant Category Code (MCC)")
    MerchantId: Optional[str] = Field(None, description="Merchant ID")
    MerchantName: Optional[str] = Field(None, description="Merchant name")
    MerchantCity: Optional[str] = Field(None, description="Merchant city")
    MerchantStateProvince: Optional[str] = Field(None, description="Merchant state/province")
    MerchantPostalCode: Optional[str] = Field(None, description="Merchant postal code")
    MerchantCountry: Optional[str] = Field(None, description="Merchant country (ISO 3166-1 alpha-2)")
    MerchantAcquirer: Optional[str] = Field(None, description="Merchant acquirer")
    SourceCurrencyCode: Optional[str] = Field(None, description="Source currency (ISO 4217)")
    SourceCurrencyAmount: Optional[float] = Field(None, description="Amount in source currency")
    CurrencyConversionRate: Optional[float] = Field(None, description="Currency conversion rate")
    BillingCurrencyCode: Optional[str] = Field(None, description="Billing currency code")
    UserDefinedFields: Optional[List[str]] = Field(None, description="User-defined fields array")


class WEXWebhookResponse(BaseModel):
    """Response for WEX webhook acknowledgment."""
    ResponseCode: int = Field(..., description="0 for success, 1 for failure")
    ResponseDescription: Optional[str] = Field(None, description="Detailed message")

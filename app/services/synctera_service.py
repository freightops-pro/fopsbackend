"""
Synctera Banking API Integration Service

Handles all interactions with Synctera's Banking-as-a-Service platform:
- Business verification (KYB)
- Person verification (KYC)
- Account management
- Card issuance
- Transaction processing

Synctera API Docs: https://dev.synctera.com/
"""

import logging
import uuid
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from enum import Enum

import httpx
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SyncteraEnvironment(str, Enum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class SyncteraError(Exception):
    """Custom exception for Synctera API errors."""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class BusinessStatus(str, Enum):
    """Synctera business verification statuses."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PROSPECT = "PROSPECT"
    FROZEN = "FROZEN"
    SANCTION = "SANCTION"


class PersonStatus(str, Enum):
    """Synctera person verification statuses."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PROSPECT = "PROSPECT"
    FROZEN = "FROZEN"
    SANCTION = "SANCTION"


class VerificationStatus(str, Enum):
    """KYC/KYB verification statuses."""
    UNVERIFIED = "UNVERIFIED"
    PENDING = "PENDING"
    PROVISIONAL = "PROVISIONAL"
    VERIFIED = "VERIFIED"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"


class AccountStatus(str, Enum):
    """Synctera account statuses."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


class CardStatus(str, Enum):
    """Synctera card statuses."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


# Request/Response Models
class AddressRequest(BaseModel):
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country_code: str = "US"


class BusinessCreateRequest(BaseModel):
    """Request model for creating a business in Synctera."""
    legal_name: str
    doing_business_as: Optional[str] = None
    entity_type: str  # LLC, CORPORATION, PARTNERSHIP, SOLE_PROPRIETORSHIP
    ein: str
    formation_date: Optional[date] = None
    formation_state: Optional[str] = None
    legal_address: AddressRequest
    phone_number: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    naics_code: Optional[str] = None
    industry: Optional[str] = None


class PersonCreateRequest(BaseModel):
    """Request model for creating a person in Synctera."""
    first_name: str
    last_name: str
    dob: date
    ssn: Optional[str] = None  # Full SSN for verification
    ssn_last_4: Optional[str] = None
    email: str
    phone_number: Optional[str] = None
    legal_address: AddressRequest
    is_customer: bool = True


class AccountCreateRequest(BaseModel):
    """Request model for creating an account."""
    account_type: str  # CHECKING, SAVINGS
    business_id: Optional[str] = None
    customer_id: Optional[str] = None
    nickname: Optional[str] = None


class CardCreateRequest(BaseModel):
    """Request model for creating a card."""
    account_id: str
    card_product_id: str
    type: str = "VIRTUAL"  # VIRTUAL or PHYSICAL
    form: str = "VIRTUAL"  # VIRTUAL or PHYSICAL
    shipping_address: Optional[AddressRequest] = None


class SyncteraClient:
    """
    Client for interacting with Synctera's Banking-as-a-Service API.

    Usage:
        client = SyncteraClient()
        business = await client.create_business(business_data)
        account = await client.create_account(account_data)
    """

    def __init__(self):
        self.api_key = settings.synctera_api_key
        self.base_url = settings.synctera_api_url.rstrip("/")
        self.environment = settings.synctera_environment

        if not self.api_key:
            logger.warning("Synctera API key not configured - banking features will be limited")

        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """Check if Synctera is properly configured."""
        return bool(self.api_key)

    @property
    def is_sandbox(self) -> bool:
        """Check if running in sandbox mode."""
        return self.environment == "sandbox"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an API request to Synctera."""
        if not self.is_configured:
            raise SyncteraError("Synctera API key not configured")

        client = await self._get_client()
        url = f"/v0{endpoint}" if not endpoint.startswith("/v0") else endpoint

        try:
            response = await client.request(
                method=method,
                url=url,
                json=data,
                params=params,
            )

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("message", f"HTTP {response.status_code}")
                logger.error(f"Synctera API error: {error_msg} - {error_data}")
                raise SyncteraError(
                    message=error_msg,
                    status_code=response.status_code,
                    response=error_data,
                )

            return response.json() if response.content else {}

        except httpx.RequestError as e:
            logger.error(f"Synctera request failed: {e}")
            raise SyncteraError(f"Request failed: {str(e)}")

    # =========================================================================
    # Business (KYB) Endpoints
    # =========================================================================

    async def create_business(self, request: BusinessCreateRequest) -> Dict[str, Any]:
        """
        Create a business for KYB verification.

        This is the first step in onboarding a business customer.
        After creation, Synctera will perform KYB checks automatically.
        """
        payload = {
            "legal_name": request.legal_name,
            "entity_type": request.entity_type.upper(),
            "formation_date": request.formation_date.isoformat() if request.formation_date else None,
            "formation_state": request.formation_state,
            "ein": request.ein.replace("-", ""),  # Remove hyphens
            "legal_address": {
                "address_line_1": request.legal_address.address_line_1,
                "address_line_2": request.legal_address.address_line_2,
                "city": request.legal_address.city,
                "state": request.legal_address.state,
                "postal_code": request.legal_address.postal_code,
                "country_code": request.legal_address.country_code,
            },
            "phone_number": request.phone_number,
            "website": request.website,
            "email": request.email,
        }

        if request.doing_business_as:
            payload["doing_business_as"] = request.doing_business_as

        if request.naics_code:
            payload["naics_code"] = request.naics_code

        if request.industry:
            payload["industry"] = request.industry

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        logger.info(f"Creating Synctera business: {request.legal_name}")
        return await self._request("POST", "/businesses", data=payload)

    async def get_business(self, business_id: str) -> Dict[str, Any]:
        """Get business details by ID."""
        return await self._request("GET", f"/businesses/{business_id}")

    async def update_business(
        self,
        business_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update business information."""
        return await self._request("PATCH", f"/businesses/{business_id}", data=updates)

    async def verify_business(self, business_id: str) -> Dict[str, Any]:
        """
        Trigger KYB verification for a business.

        Synctera will run background checks including:
        - Business registration verification
        - OFAC/sanctions screening
        - Beneficial ownership verification
        """
        return await self._request(
            "POST",
            f"/businesses/{business_id}/verify",
            data={"verification_type": "KYB"}
        )

    async def get_business_verification(self, business_id: str) -> Dict[str, Any]:
        """Get KYB verification status for a business."""
        business = await self.get_business(business_id)
        return {
            "business_id": business_id,
            "status": business.get("status"),
            "verification_status": business.get("verification_status"),
            "verification_last_run": business.get("verification_last_run"),
            "kyb_results": business.get("kyb_results", {}),
        }

    # =========================================================================
    # Person (KYC) Endpoints
    # =========================================================================

    async def create_person(
        self,
        request: PersonCreateRequest,
        business_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a person for KYC verification.

        Can be linked to a business as an owner, controller, or authorized signer.
        """
        payload = {
            "first_name": request.first_name,
            "last_name": request.last_name,
            "dob": request.dob.isoformat(),
            "email": request.email,
            "phone_number": request.phone_number,
            "legal_address": {
                "address_line_1": request.legal_address.address_line_1,
                "address_line_2": request.legal_address.address_line_2,
                "city": request.legal_address.city,
                "state": request.legal_address.state,
                "postal_code": request.legal_address.postal_code,
                "country_code": request.legal_address.country_code,
            },
            "is_customer": request.is_customer,
        }

        # SSN handling - prefer full SSN for verification
        if request.ssn:
            payload["ssn"] = request.ssn.replace("-", "")
        elif request.ssn_last_4:
            payload["ssn_last_4"] = request.ssn_last_4

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        if payload.get("legal_address"):
            payload["legal_address"] = {
                k: v for k, v in payload["legal_address"].items() if v is not None
            }

        logger.info(f"Creating Synctera person: {request.first_name} {request.last_name}")
        person = await self._request("POST", "/persons", data=payload)

        # Link to business if provided
        if business_id and person.get("id"):
            await self.link_person_to_business(
                person_id=person["id"],
                business_id=business_id,
                relationship_type="CONTROLLING_PERSON",
            )

        return person

    async def get_person(self, person_id: str) -> Dict[str, Any]:
        """Get person details by ID."""
        return await self._request("GET", f"/persons/{person_id}")

    async def verify_person(self, person_id: str) -> Dict[str, Any]:
        """
        Trigger KYC verification for a person.

        Synctera will run background checks including:
        - Identity verification
        - OFAC/sanctions screening
        - Watchlist screening
        """
        return await self._request(
            "POST",
            f"/persons/{person_id}/verify",
            data={"verification_type": "KYC"}
        )

    async def link_person_to_business(
        self,
        person_id: str,
        business_id: str,
        relationship_type: str = "CONTROLLING_PERSON",  # OWNER, CONTROLLING_PERSON, AUTHORIZED_SIGNER
        ownership_percentage: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Link a person to a business with a specific role."""
        payload = {
            "person_id": person_id,
            "business_id": business_id,
            "relationship_type": relationship_type,
        }

        if ownership_percentage is not None:
            payload["ownership_percentage"] = ownership_percentage

        return await self._request("POST", "/relationships", data=payload)

    # =========================================================================
    # Account Endpoints
    # =========================================================================

    async def create_account(self, request: AccountCreateRequest) -> Dict[str, Any]:
        """
        Create a bank account.

        Requires either a verified business_id or customer_id (person).
        """
        # Map our types to Synctera types
        account_type_map = {
            "checking": "CHECKING",
            "savings": "SAVINGS",
            "money_market": "MONEY_MARKET",
        }

        payload = {
            "account_type": account_type_map.get(
                request.account_type.lower(),
                request.account_type.upper()
            ),
            "balance_ceiling": {
                "amount": 100000000,  # $1M ceiling
                "currency": "USD",
            },
            "balance_floor": {
                "amount": 0,
                "currency": "USD",
            },
        }

        if request.business_id:
            payload["relationships"] = [{
                "relationship_type": "BUSINESS_OWNER",
                "business_id": request.business_id,
            }]
        elif request.customer_id:
            payload["relationships"] = [{
                "relationship_type": "PRIMARY_ACCOUNT_HOLDER",
                "customer_id": request.customer_id,
            }]

        if request.nickname:
            payload["nickname"] = request.nickname

        logger.info(f"Creating Synctera account: {request.account_type}")
        return await self._request("POST", "/accounts", data=payload)

    async def get_account(self, account_id: str) -> Dict[str, Any]:
        """Get account details by ID."""
        return await self._request("GET", f"/accounts/{account_id}")

    async def get_account_balance(self, account_id: str) -> Dict[str, Any]:
        """Get current account balance."""
        account = await self.get_account(account_id)
        return {
            "account_id": account_id,
            "available_balance": account.get("available_balance", {}).get("amount", 0),
            "current_balance": account.get("balance", {}).get("amount", 0),
            "currency": account.get("balance", {}).get("currency", "USD"),
        }

    async def list_accounts(
        self,
        business_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List accounts with optional filters."""
        params = {}
        if business_id:
            params["business_id"] = business_id
        if customer_id:
            params["customer_id"] = customer_id
        if status:
            params["status"] = status

        result = await self._request("GET", "/accounts", params=params)
        return result.get("accounts", [])

    async def close_account(self, account_id: str, reason: str = "CUSTOMER_REQUEST") -> Dict[str, Any]:
        """Close an account."""
        return await self._request(
            "PATCH",
            f"/accounts/{account_id}",
            data={"status": "CLOSED", "close_reason": reason}
        )

    # =========================================================================
    # Card Endpoints
    # =========================================================================

    async def create_card(self, request: CardCreateRequest) -> Dict[str, Any]:
        """
        Issue a new card (virtual or physical).

        Virtual cards are created instantly.
        Physical cards will be shipped to the provided address.
        """
        payload = {
            "account_id": request.account_id,
            "card_product_id": request.card_product_id,
            "type": request.type.upper(),
            "form": request.form.upper(),
        }

        if request.shipping_address and request.form.upper() == "PHYSICAL":
            payload["shipping_address"] = {
                "address_line_1": request.shipping_address.address_line_1,
                "address_line_2": request.shipping_address.address_line_2,
                "city": request.shipping_address.city,
                "state": request.shipping_address.state,
                "postal_code": request.shipping_address.postal_code,
                "country_code": request.shipping_address.country_code,
            }

        logger.info(f"Creating Synctera card for account: {request.account_id}")
        return await self._request("POST", "/cards", data=payload)

    async def get_card(self, card_id: str) -> Dict[str, Any]:
        """Get card details by ID."""
        return await self._request("GET", f"/cards/{card_id}")

    async def get_card_details(self, card_id: str) -> Dict[str, Any]:
        """
        Get sensitive card details (PAN, CVV, expiration).

        This endpoint returns sensitive data and should be called
        only when displaying to the cardholder.
        """
        return await self._request("GET", f"/cards/{card_id}/secrets")

    async def list_cards(
        self,
        account_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List cards with optional filters."""
        params = {}
        if account_id:
            params["account_id"] = account_id
        if status:
            params["status"] = status

        result = await self._request("GET", "/cards", params=params)
        return result.get("cards", [])

    async def activate_card(self, card_id: str) -> Dict[str, Any]:
        """Activate a card."""
        return await self._request(
            "PATCH",
            f"/cards/{card_id}",
            data={"status": "ACTIVE"}
        )

    async def suspend_card(self, card_id: str, reason: str = "CUSTOMER_REQUEST") -> Dict[str, Any]:
        """Suspend a card (can be reactivated)."""
        return await self._request(
            "PATCH",
            f"/cards/{card_id}",
            data={"status": "SUSPENDED", "status_reason": reason}
        )

    async def terminate_card(self, card_id: str, reason: str = "CUSTOMER_REQUEST") -> Dict[str, Any]:
        """Terminate a card (permanent)."""
        return await self._request(
            "PATCH",
            f"/cards/{card_id}",
            data={"status": "TERMINATED", "status_reason": reason}
        )

    # =========================================================================
    # Transaction Endpoints
    # =========================================================================

    async def list_transactions(
        self,
        account_id: str,
        limit: int = 50,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """List transactions for an account."""
        params = {
            "account_id": account_id,
            "limit": limit,
            "offset": offset,
        }

        if start_date:
            params["start_time"] = start_date.isoformat()
        if end_date:
            params["end_time"] = end_date.isoformat()

        result = await self._request("GET", "/transactions", params=params)
        return result.get("transactions", [])

    async def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        """Get transaction details by ID."""
        return await self._request("GET", f"/transactions/{transaction_id}")

    # =========================================================================
    # ACH Transfer Endpoints
    # =========================================================================

    async def create_ach_transfer(
        self,
        source_account_id: str,
        destination_account_number: str,
        destination_routing_number: str,
        amount: int,  # Amount in cents
        currency: str = "USD",
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initiate an ACH transfer.

        Amount should be in cents (e.g., $100.00 = 10000).
        """
        payload = {
            "source_account_id": source_account_id,
            "destination_account_number": destination_account_number,
            "destination_routing_number": destination_routing_number,
            "amount": amount,
            "currency": currency,
            "type": "PUSH",  # PUSH = send money, PULL = receive money
        }

        if description:
            payload["description"] = description

        logger.info(f"Creating ACH transfer from account {source_account_id}: ${amount/100:.2f}")
        return await self._request("POST", "/ach", data=payload)

    # =========================================================================
    # Internal Transfer Endpoints
    # =========================================================================

    async def create_internal_transfer(
        self,
        source_account_id: str,
        destination_account_id: str,
        amount: int,  # Amount in cents
        currency: str = "USD",
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create an internal transfer between Synctera accounts.

        These transfers are instant and free.
        """
        payload = {
            "source_account_id": source_account_id,
            "destination_account_id": destination_account_id,
            "amount": amount,
            "currency": currency,
            "type": "ACCOUNT_TO_ACCOUNT",
        }

        if description:
            payload["description"] = description

        logger.info(f"Creating internal transfer: ${amount/100:.2f}")
        return await self._request("POST", "/internal_transfers", data=payload)

    # =========================================================================
    # Webhook Verification
    # =========================================================================

    def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: str,
    ) -> bool:
        """
        Verify a webhook signature from Synctera.

        Synctera signs webhooks using HMAC-SHA256.
        """
        import hmac
        import hashlib

        if not settings.synctera_webhook_secret:
            logger.warning("Synctera webhook secret not configured - skipping verification")
            return True

        # Construct the signed payload
        signed_payload = f"{timestamp}.{payload.decode()}"

        # Calculate expected signature
        expected_sig = hmac.new(
            settings.synctera_webhook_secret.encode(),
            signed_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Compare signatures
        return hmac.compare_digest(signature, expected_sig)

    # =========================================================================
    # Card Products (for sandbox/setup)
    # =========================================================================

    async def list_card_products(self) -> List[Dict[str, Any]]:
        """List available card products."""
        result = await self._request("GET", "/cards/products")
        return result.get("card_products", [])

    async def get_card_product(self, product_id: str) -> Dict[str, Any]:
        """Get card product details."""
        return await self._request("GET", f"/cards/products/{product_id}")


# Singleton instance
_synctera_client: Optional[SyncteraClient] = None


def get_synctera_client() -> SyncteraClient:
    """Get the Synctera client singleton."""
    global _synctera_client
    if _synctera_client is None:
        _synctera_client = SyncteraClient()
    return _synctera_client

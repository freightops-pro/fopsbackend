"""
WEX EnCompass API Client for fuel card payments and virtual card management.

API Documentation: WEX EnCompass REST API
- Base URL: https://wexpayservices.encompass-suite.com/api
- Authentication: Basic Auth or OAuth2 via Okta
"""

from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class WEXEnCompassClient:
    """
    Client for WEX EnCompass API integration.

    Supports both Basic Authentication and OAuth2 via Okta.
    Provides methods for:
    - Creating and managing MerchantLogs (payments)
    - Virtual card generation
    - Transaction retrieval
    - Merchant management
    """

    # API Endpoints
    BASE_URL = "https://wexpayservices.encompass-suite.com/api"
    OKTA_TOKEN_URL = "https://cp-wex.okta.com/oauth2/ausc718h9qVT8xzSS357/v1/token"

    # API Version
    API_VERSION = "1.0"

    def __init__(
        self,
        org_group_login_id: str,
        username: str,
        password: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        use_oauth: bool = False,
        timeout: float = 30.0,
    ):
        """
        Initialize the WEX EnCompass client.

        Args:
            org_group_login_id: WEX Organization Group Login ID
            username: WEX API username
            password: WEX API password
            client_id: OAuth client ID (required if use_oauth=True)
            client_secret: OAuth client secret (required if use_oauth=True)
            use_oauth: Use OAuth2 authentication instead of Basic Auth
            timeout: Request timeout in seconds
        """
        self.org_group_login_id = org_group_login_id
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self.use_oauth = use_oauth
        self.timeout = timeout

        # OAuth token cache
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _get_basic_auth_header(self) -> str:
        """Generate Basic Authentication header."""
        # Format: OrgGroupLoginId/UserName:password
        credentials = f"{self.org_group_login_id}/{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def _get_oauth_token(self) -> str:
        """Get OAuth2 access token from Okta."""
        if not self.client_id or not self.client_secret:
            raise ValueError("OAuth requires client_id and client_secret")

        # Check if we have a valid cached token
        if self._access_token and self._token_expires_at:
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token

        client = await self._get_client()

        # OAuth2 client credentials flow
        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        response = await client.post(
            self.OKTA_TOKEN_URL,
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "encompass",
            },
        )

        if response.status_code != 200:
            logger.error(f"OAuth token request failed: {response.status_code} - {response.text}")
            raise Exception(f"Failed to get OAuth token: {response.status_code}")

        token_data = response.json()
        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        logger.debug("Successfully obtained OAuth token")
        return self._access_token

    async def _get_auth_header(self) -> str:
        """Get appropriate authorization header."""
        if self.use_oauth:
            token = await self._get_oauth_token()
            return f"Bearer {token}"
        return self._get_basic_auth_header()

    def _get_default_headers(self, idempotency_key: Optional[str] = None) -> Dict[str, str]:
        """Get default request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if idempotency_key:
            headers["idempotency_key"] = idempotency_key
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated API request."""
        client = await self._get_client()
        url = f"{self.BASE_URL}{endpoint}"

        headers = self._get_default_headers(idempotency_key)
        headers["Authorization"] = await self._get_auth_header()

        logger.debug(f"WEX API Request: {method} {url}")

        response = await client.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            params=params,
        )

        if response.status_code >= 400:
            logger.error(f"WEX API Error: {response.status_code} - {response.text}")
            raise Exception(f"WEX API error: {response.status_code} - {response.text}")

        if response.status_code == 204:  # No content
            return {}

        return response.json()

    # ==================== MERCHANT LOG (PAYMENT) OPERATIONS ====================

    async def create_merchant_log(
        self,
        merchant_id: str,
        amount: float,
        payment_method: str = "merchant_charged_card",
        card_controls: Optional[Dict[str, Any]] = None,
        user_defined_fields: Optional[Dict[str, str]] = None,
        external_reference: Optional[str] = None,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new MerchantLog (payment) with optional virtual card generation.

        Args:
            merchant_id: The merchant/vendor ID to pay
            amount: Payment amount in dollars
            payment_method: Payment method type:
                - merchant_charged_card: Virtual card payment
                - ach: ACH bank transfer
                - check: Physical check
                - wire: Wire transfer
            card_controls: Virtual card controls (for merchant_charged_card):
                - min_auth_date: Earliest card activation date (YYYY-MM-DD)
                - max_auth_date: Latest card authorization date (YYYY-MM-DD)
                - credit_limit: Maximum card limit
                - number_of_authorizations: Max number of uses
                - mcc_profile_id: Merchant category code profile
            user_defined_fields: Custom fields (up to 15, configured per org)
            external_reference: External system reference ID
            notes: Payment notes
            idempotency_key: Unique key for idempotent requests

        Returns:
            Created MerchantLog with virtual card details if applicable
        """
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        payload: Dict[str, Any] = {
            "merchant_id": merchant_id,
            "amount": amount,
            "payment_method": payment_method,
        }

        if card_controls:
            payload["card_controls"] = card_controls

        if user_defined_fields:
            payload["user_defined_fields"] = user_defined_fields

        if external_reference:
            payload["external_reference"] = external_reference

        if notes:
            payload["notes"] = notes

        result = await self._request(
            "POST",
            "/merchant-logs/v1",
            data=payload,
            idempotency_key=idempotency_key,
        )

        logger.info(f"Created MerchantLog: {result.get('id')}")
        return result

    async def get_merchant_log(self, merchant_log_id: str) -> Dict[str, Any]:
        """
        Get a MerchantLog by ID.

        Args:
            merchant_log_id: The MerchantLog ID

        Returns:
            MerchantLog details including virtual card info
        """
        return await self._request("GET", f"/merchant-logs/v1/{merchant_log_id}")

    async def update_merchant_log(
        self,
        merchant_log_id: str,
        amount: Optional[float] = None,
        card_controls: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing MerchantLog.

        Args:
            merchant_log_id: The MerchantLog ID to update
            amount: New payment amount
            card_controls: Updated card controls
            status: New status (e.g., 'cancelled')
            notes: Updated notes

        Returns:
            Updated MerchantLog
        """
        payload: Dict[str, Any] = {}

        if amount is not None:
            payload["amount"] = amount
        if card_controls:
            payload["card_controls"] = card_controls
        if status:
            payload["status"] = status
        if notes:
            payload["notes"] = notes

        return await self._request(
            "PATCH",
            f"/merchant-logs/v1/{merchant_log_id}",
            data=payload,
        )

    async def cancel_merchant_log(self, merchant_log_id: str) -> Dict[str, Any]:
        """Cancel a MerchantLog and void any associated virtual card."""
        return await self.update_merchant_log(merchant_log_id, status="cancelled")

    async def get_merchant_log_authorizations(
        self,
        merchant_log_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get authorization history for a MerchantLog.

        Returns list of card authorizations (approved and declined).
        """
        result = await self._request(
            "GET",
            f"/merchant-logs/v1/{merchant_log_id}/authorizations",
        )
        return result.get("authorizations", [])

    async def get_merchant_log_transactions(
        self,
        merchant_log_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get posted transactions for a MerchantLog.

        Returns list of settled/posted transactions.
        """
        result = await self._request(
            "GET",
            f"/merchant-logs/v1/{merchant_log_id}/transactions",
        )
        return result.get("transactions", [])

    # ==================== MERCHANT OPERATIONS ====================

    async def create_merchant(
        self,
        name: str,
        merchant_type: str = "fuel_vendor",
        address: Optional[Dict[str, str]] = None,
        contact: Optional[Dict[str, str]] = None,
        tax_id: Optional[str] = None,
        external_reference: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new merchant/vendor.

        Args:
            name: Merchant business name
            merchant_type: Type of merchant (e.g., fuel_vendor, repair_shop)
            address: Merchant address {street, city, state, postal_code, country}
            contact: Contact info {email, phone, contact_name}
            tax_id: Merchant tax ID (EIN)
            external_reference: External system reference ID
            idempotency_key: Unique key for idempotent requests

        Returns:
            Created merchant record
        """
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        payload: Dict[str, Any] = {
            "name": name,
            "merchant_type": merchant_type,
        }

        if address:
            payload["address"] = address
        if contact:
            payload["contact"] = contact
        if tax_id:
            payload["tax_id"] = tax_id
        if external_reference:
            payload["external_reference"] = external_reference

        result = await self._request(
            "POST",
            "/merchants/v1",
            data=payload,
            idempotency_key=idempotency_key,
        )

        logger.info(f"Created Merchant: {result.get('id')}")
        return result

    async def get_merchant(self, merchant_id: str) -> Dict[str, Any]:
        """Get a merchant by ID."""
        return await self._request("GET", f"/merchants/v1/{merchant_id}")

    async def add_merchant_payment_method(
        self,
        merchant_id: str,
        payment_type: str,
        account_details: Dict[str, str],
        is_default: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a payment method to a merchant.

        Args:
            merchant_id: The merchant ID
            payment_type: Payment type (ach, wire, check)
            account_details: Account details based on payment type:
                - ACH: {routing_number, account_number, account_type}
                - Wire: {routing_number, account_number, bank_name, swift_code}
                - Check: {payable_to, mailing_address}
            is_default: Set as default payment method
            idempotency_key: Unique key for idempotent requests

        Returns:
            Created payment method
        """
        if not idempotency_key:
            idempotency_key = str(uuid.uuid4())

        payload = {
            "payment_type": payment_type,
            "account_details": account_details,
            "is_default": is_default,
        }

        return await self._request(
            "POST",
            f"/merchants/v1/{merchant_id}/payment-methods",
            data=payload,
            idempotency_key=idempotency_key,
        )

    # ==================== VIRTUAL CARD HELPERS ====================

    async def create_fuel_payment(
        self,
        merchant_id: str,
        amount: float,
        driver_id: Optional[str] = None,
        truck_id: Optional[str] = None,
        load_id: Optional[str] = None,
        fuel_stop_location: Optional[str] = None,
        valid_days: int = 7,
        max_uses: int = 1,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a virtual card payment for fuel purchase.

        This is a convenience method that creates a MerchantLog with
        appropriate card controls for fuel purchases.

        Args:
            merchant_id: Fuel vendor merchant ID
            amount: Fuel purchase amount
            driver_id: FreightOps driver ID for tracking
            truck_id: FreightOps truck ID for tracking
            load_id: Associated load ID for IFTA tracking
            fuel_stop_location: Location description
            valid_days: Number of days card is valid
            max_uses: Maximum card uses (default 1 for single use)
            idempotency_key: Unique key for idempotent requests

        Returns:
            MerchantLog with virtual card details including:
            - card_number: Virtual card number
            - security_code: CVV
            - expiration_date: Card expiration
        """
        today = datetime.utcnow().date()
        max_date = today + timedelta(days=valid_days)

        card_controls = {
            "min_auth_date": today.isoformat(),
            "max_auth_date": max_date.isoformat(),
            "credit_limit": amount,
            "number_of_authorizations": max_uses,
            # MCC 5541 = Service Stations (with ancillary services)
            # MCC 5542 = Automated Fuel Dispensers
            "allowed_mcc_codes": ["5541", "5542"],
        }

        user_defined_fields = {}
        if driver_id:
            user_defined_fields["driver_id"] = driver_id
        if truck_id:
            user_defined_fields["truck_id"] = truck_id
        if load_id:
            user_defined_fields["load_id"] = load_id
        if fuel_stop_location:
            user_defined_fields["fuel_location"] = fuel_stop_location

        return await self.create_merchant_log(
            merchant_id=merchant_id,
            amount=amount,
            payment_method="merchant_charged_card",
            card_controls=card_controls,
            user_defined_fields=user_defined_fields if user_defined_fields else None,
            external_reference=load_id,
            notes=f"Fuel purchase - Driver: {driver_id}, Truck: {truck_id}",
            idempotency_key=idempotency_key,
        )

    async def get_virtual_card_details(
        self,
        merchant_log_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get virtual card details for a MerchantLog.

        Returns:
            Virtual card details if available:
            - card_number: Full card number
            - security_code: CVV
            - expiration_month: MM
            - expiration_year: YYYY
            - status: Card status
        """
        merchant_log = await self.get_merchant_log(merchant_log_id)
        return merchant_log.get("virtual_card")

    # ==================== TRANSACTION RECONCILIATION ====================

    async def get_transactions_for_period(
        self,
        start_date: str,
        end_date: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all transactions for a date range.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            status: Filter by status (posted, pending, declined)

        Returns:
            List of transactions
        """
        params: Dict[str, Any] = {
            "start_date": start_date,
            "end_date": end_date,
        }
        if status:
            params["status"] = status

        result = await self._request(
            "GET",
            "/transactions/v1",
            params=params,
        )
        return result.get("transactions", [])

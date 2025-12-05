"""QuickBooks Online API client for interacting with Intuit's QuickBooks API.

This client uses the intuit-oauth SDK for OAuth operations and httpx for API calls.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from intuitlib.client import AuthClient
from intuitlib.exceptions import AuthClientError

logger = logging.getLogger(__name__)


class QuickBooksAPIClient:
    """Client for interacting with QuickBooks Online API using intuit-oauth SDK."""

    # Base URLs
    SANDBOX_BASE_URL = "https://sandbox-quickbooks.api.intuit.com"
    PRODUCTION_BASE_URL = "https://quickbooks.api.intuit.com"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        realm_id: Optional[str] = None,  # Company ID in QuickBooks
        sandbox: bool = True,
        redirect_uri: str = "https://developer.intuit.com/v2/OAuth2Playground/RedirectUrl",
    ):
        """
        Initialize QuickBooks API client.

        Args:
            client_id: QuickBooks OAuth client ID
            client_secret: QuickBooks OAuth client secret
            access_token: Current access token (if available)
            refresh_token: Refresh token for obtaining new access tokens
            realm_id: QuickBooks company/realm ID
            sandbox: Whether to use sandbox environment (default: True)
            redirect_uri: OAuth redirect URI (used for token refresh)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token = access_token
        self._refresh_token = refresh_token
        self.realm_id = realm_id
        self.sandbox = sandbox
        self._token_expires_at: Optional[datetime] = None

        # Initialize the intuit-oauth AuthClient
        environment = "sandbox" if sandbox else "production"
        self._auth_client = AuthClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            environment=environment,
            access_token=access_token,
            refresh_token=refresh_token,
            realm_id=realm_id,
        )

    @property
    def base_url(self) -> str:
        """Get the base URL based on environment."""
        return self.SANDBOX_BASE_URL if self.sandbox else self.PRODUCTION_BASE_URL

    @property
    def api_base_url(self) -> str:
        """Get the API base URL with realm ID."""
        if not self.realm_id:
            raise ValueError("realm_id is required for API calls")
        return f"{self.base_url}/v3/company/{self.realm_id}"

    def refresh_access_token(self) -> Dict[str, Any]:
        """
        Refresh the access token using the intuit-oauth SDK.

        Returns:
            Token response with access_token, refresh_token, and expires_in
        """
        if not self._refresh_token:
            raise ValueError("Refresh token is required to refresh access token")

        try:
            # Use the SDK to refresh the token
            self._auth_client.refresh(refresh_token=self._refresh_token)

            # Update local state from SDK
            self._access_token = self._auth_client.access_token
            self._refresh_token = self._auth_client.refresh_token
            expires_in = self._auth_client.expires_in or 3600
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)  # 1 min buffer

            logger.info("QuickBooks access token refreshed successfully")
            return {
                "access_token": self._access_token,
                "refresh_token": self._refresh_token,
                "expires_in": expires_in,
                "x_refresh_token_expires_in": self._auth_client.x_refresh_token_expires_in,
            }
        except AuthClientError as e:
            logger.error(f"QuickBooks token refresh error: {str(e)}")
            raise

    def _get_access_token(self) -> str:
        """Get valid access token, refreshing if necessary."""
        if self._access_token and self._token_expires_at and datetime.utcnow() < self._token_expires_at:
            return self._access_token

        if not self._refresh_token:
            raise ValueError("No valid access token and no refresh token available")

        self.refresh_access_token()
        if not self._access_token:
            raise ValueError("Failed to obtain access token")

        return self._access_token

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        minor_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated request to QuickBooks API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/invoice/123")
            params: Query parameters
            json_data: Request body JSON
            minor_version: API minor version (e.g., 70)
        """
        token = self._get_access_token()  # Synchronous call using SDK
        url = f"{self.api_base_url}{endpoint}"

        # Add minor version to params
        if params is None:
            params = {}
        if minor_version:
            params["minorversion"] = minor_version

        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method,
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    params=params,
                    json=json_data,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_text = e.response.text
                logger.error(f"QuickBooks API error {e.response.status_code}: {error_text}")
                raise
            except httpx.HTTPError as e:
                logger.error(f"QuickBooks request error: {str(e)}")
                raise

    # Account operations (Chart of Accounts)
    async def get_accounts(
        self,
        start_position: int = 1,
        max_results: int = 20,
        account_type: Optional[str] = None,
        active_only: bool = True,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Query accounts (Chart of Accounts).

        Args:
            start_position: Starting position for pagination (default: 1)
            max_results: Maximum number of results (default: 20)
            account_type: Filter by account type (e.g., "Bank", "Expense", "Income", "Accounts Receivable")
            active_only: Only return active accounts (default: True)
            minor_version: API minor version (default: 70)

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account
        """
        query_parts = ["SELECT * FROM Account"]
        if active_only:
            query_parts.append("WHERE Active = true")
        if account_type:
            if "WHERE" in " ".join(query_parts):
                query_parts.append(f"AND AccountType = '{account_type}'")
            else:
                query_parts.append(f"WHERE AccountType = '{account_type}'")
        query_parts.append(f"STARTPOSITION {start_position} MAXRESULTS {max_results}")

        query = " ".join(query_parts)
        return await self._request(
            "GET",
            "/query",
            params={"query": query},
            minor_version=minor_version,
        )

    async def get_account(self, account_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """
        Get a specific account by ID.

        Args:
            account_id: QuickBooks account ID
            minor_version: API minor version (default: 70)

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account
        """
        return await self._request("GET", f"/account/{account_id}", minor_version=minor_version)

    async def create_account(self, account_data: Dict[str, Any], minor_version: int = 70) -> Dict[str, Any]:
        """
        Create a new account in the Chart of Accounts.

        Args:
            account_data: Account data dictionary with required fields:
                - Name: Account name (required)
                - AccountType: Type of account (required, e.g., "Bank", "Expense", "Income")
                - AccountSubType: Subtype (optional, e.g., "Checking", "Savings")
                - Description: Account description (optional)
                - Active: Whether account is active (optional, default: true)
                - ParentRef: Reference to parent account if this is a sub-account (optional)
            minor_version: API minor version (default: 70)

        Example:
            account_data = {
                "Name": "Operating Account",
                "AccountType": "Bank",
                "AccountSubType": "Checking",
                "Description": "Primary business checking account"
            }

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account
        """
        return await self._request("POST", "/account", json_data=account_data, minor_version=minor_version)

    async def update_account(
        self, account_id: str, account_data: Dict[str, Any], minor_version: int = 70
    ) -> Dict[str, Any]:
        """
        Update an existing account (sparse update).

        Args:
            account_id: QuickBooks account ID
            account_data: Account data dictionary with fields to update. Must include:
                - Id: Account ID (required)
                - SyncToken: Current sync token (required for optimistic locking)
                - sparse: Set to true for sparse update (optional, default: true)
            minor_version: API minor version (default: 70)

        Example:
            account_data = {
                "sparse": True,
                "Id": "123",
                "SyncToken": "0",
                "Name": "Updated Account Name",
                "Description": "Updated description"
            }

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account
        """
        # Ensure sparse update is set
        if "sparse" not in account_data:
            account_data["sparse"] = True
        return await self._request("POST", "/account", json_data=account_data, minor_version=minor_version)

    async def get_account_types(self) -> List[Dict[str, Any]]:
        """
        Get list of available account types and subtypes.

        Returns a list of account type definitions with their valid subtypes.
        This is a helper method that returns static data about QuickBooks account types.
        """
        return [
            {
                "AccountType": "Bank",
                "SubTypes": ["Checking", "Savings", "Money Market", "Rents Held in Trust", "Other"],
            },
            {
                "AccountType": "Accounts Receivable",
                "SubTypes": ["Accounts Receivable"],
            },
            {
                "AccountType": "Other Current Asset",
                "SubTypes": [
                    "Inventory",
                    "Undeposited Funds",
                    "Prepaid Expenses",
                    "Employee Cash Advances",
                    "Other Current Assets",
                ],
            },
            {
                "AccountType": "Fixed Asset",
                "SubTypes": [
                    "Vehicles",
                    "Trucks",
                    "Furniture and Fixtures",
                    "Leasehold Improvements",
                    "Computer Equipment",
                    "Accumulated Depreciation",
                    "Other Fixed Assets",
                ],
            },
            {
                "AccountType": "Other Asset",
                "SubTypes": ["Other Assets"],
            },
            {
                "AccountType": "Accounts Payable",
                "SubTypes": ["Accounts Payable"],
            },
            {
                "AccountType": "Credit Card",
                "SubTypes": ["Credit Card"],
            },
            {
                "AccountType": "Other Current Liability",
                "SubTypes": [
                    "Accrued Liabilities",
                    "Payroll Liabilities",
                    "Sales Tax Payable",
                    "Other Current Liabilities",
                ],
            },
            {
                "AccountType": "Long Term Liability",
                "SubTypes": ["Notes Payable", "Other Long Term Liabilities"],
            },
            {
                "AccountType": "Equity",
                "SubTypes": [
                    "Equity - No Close",
                    "Equity - Retained Earnings",
                    "Equity - Gets Closed",
                ],
            },
            {
                "AccountType": "Income",
                "SubTypes": [
                    "Service/Fee Income",
                    "Product/Other Income",
                    "Discounts/Refunds Given",
                    "Other Primary Income",
                ],
            },
            {
                "AccountType": "Cost of Goods Sold",
                "SubTypes": [
                    "Supplies/Materials - Non-Direct",
                    "Other Costs of Sales - COS",
                ],
            },
            {
                "AccountType": "Expense",
                "SubTypes": [
                    "Advertising/Promotional",
                    "Automobile",
                    "Bad Debt",
                    "Bank Charges",
                    "Charitable Contributions",
                    "Commissions and Fees",
                    "Contractors",
                    "Credit Card Charges",
                    "Depreciation",
                    "Dues and Subscriptions",
                    "Equipment Rental",
                    "Fuel",
                    "Insurance",
                    "Interest Paid",
                    "Legal and Professional Fees",
                    "Meals and Entertainment",
                    "Office/General Administrative Expenses",
                    "Other Expenses",
                    "Postage and Delivery",
                    "Rent or Lease",
                    "Repairs and Maintenance",
                    "Supplies",
                    "Taxes - Property",
                    "Travel",
                    "Utilities",
                    "Vehicle",
                ],
            },
            {
                "AccountType": "Other Income",
                "SubTypes": [
                    "Other Income",
                    "Other Miscellaneous Income",
                    "Gain/Loss on Sale of Fixed Assets",
                ],
            },
            {
                "AccountType": "Other Expense",
                "SubTypes": [
                    "Other Miscellaneous Expense",
                    "Penalties and Settlements",
                    "Amortization",
                ],
            },
        ]

    # Customer operations
    async def get_customers(
        self,
        start_position: int = 1,
        max_results: int = 20,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Query customers.

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/customer
        """
        return await self._request(
            "GET",
            "/query",
            params={
                "query": f"SELECT * FROM Customer STARTPOSITION {start_position} MAXRESULTS {max_results}",
            },
            minor_version=minor_version,
        )

    async def get_customer(self, customer_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """Get a specific customer by ID."""
        return await self._request("GET", f"/customer/{customer_id}", minor_version=minor_version)

    async def create_customer(self, customer_data: Dict[str, Any], minor_version: int = 70) -> Dict[str, Any]:
        """Create a new customer."""
        return await self._request("POST", "/customer", json_data=customer_data, minor_version=minor_version)

    async def update_customer(
        self, customer_id: str, customer_data: Dict[str, Any], minor_version: int = 70
    ) -> Dict[str, Any]:
        """Update an existing customer (sparse update)."""
        return await self._request("POST", f"/customer", json_data=customer_data, minor_version=minor_version)

    # Vendor operations
    async def get_vendors(
        self,
        start_position: int = 1,
        max_results: int = 20,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Query vendors.

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/vendor
        """
        return await self._request(
            "GET",
            "/query",
            params={
                "query": f"SELECT * FROM Vendor STARTPOSITION {start_position} MAXRESULTS {max_results}",
            },
            minor_version=minor_version,
        )

    async def get_vendor(self, vendor_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """Get a specific vendor by ID."""
        return await self._request("GET", f"/vendor/{vendor_id}", minor_version=minor_version)

    # Invoice operations
    async def get_invoices(
        self,
        start_position: int = 1,
        max_results: int = 20,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Query invoices.

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/invoice
        """
        return await self._request(
            "GET",
            "/query",
            params={
                "query": f"SELECT * FROM Invoice STARTPOSITION {start_position} MAXRESULTS {max_results}",
            },
            minor_version=minor_version,
        )

    async def get_invoice(self, invoice_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """Get a specific invoice by ID."""
        return await self._request("GET", f"/invoice/{invoice_id}", minor_version=minor_version)

    async def create_invoice(self, invoice_data: Dict[str, Any], minor_version: int = 70) -> Dict[str, Any]:
        """Create a new invoice."""
        return await self._request("POST", "/invoice", json_data=invoice_data, minor_version=minor_version)

    async def update_invoice(
        self, invoice_id: str, invoice_data: Dict[str, Any], minor_version: int = 70
    ) -> Dict[str, Any]:
        """Update an existing invoice (sparse update)."""
        return await self._request("POST", "/invoice", json_data=invoice_data, minor_version=minor_version)

    async def send_invoice(self, invoice_id: str, email: Optional[str] = None, minor_version: int = 70) -> Dict[str, Any]:
        """Send an invoice via email."""
        data = {"SendTo": email} if email else {}
        return await self._request("POST", f"/invoice/{invoice_id}/send", json_data=data, minor_version=minor_version)

    # Payment operations
    async def get_payments(
        self,
        start_position: int = 1,
        max_results: int = 20,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Query payments.

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/payment
        """
        return await self._request(
            "GET",
            "/query",
            params={
                "query": f"SELECT * FROM Payment STARTPOSITION {start_position} MAXRESULTS {max_results}",
            },
            minor_version=minor_version,
        )

    async def get_payment(self, payment_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """Get a specific payment by ID."""
        return await self._request("GET", f"/payment/{payment_id}", minor_version=minor_version)

    async def create_payment(self, payment_data: Dict[str, Any], minor_version: int = 70) -> Dict[str, Any]:
        """Create a new payment."""
        return await self._request("POST", "/payment", json_data=payment_data, minor_version=minor_version)

    # Bill operations
    async def get_bills(
        self,
        start_position: int = 1,
        max_results: int = 20,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Query bills.

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/bill
        """
        return await self._request(
            "GET",
            "/query",
            params={
                "query": f"SELECT * FROM Bill STARTPOSITION {start_position} MAXRESULTS {max_results}",
            },
            minor_version=minor_version,
        )

    async def get_bill(self, bill_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """Get a specific bill by ID."""
        return await self._request("GET", f"/bill/{bill_id}", minor_version=minor_version)

    async def create_bill(self, bill_data: Dict[str, Any], minor_version: int = 70) -> Dict[str, Any]:
        """Create a new bill."""
        return await self._request("POST", "/bill", json_data=bill_data, minor_version=minor_version)

    async def update_bill(
        self, bill_id: str, bill_data: Dict[str, Any], minor_version: int = 70
    ) -> Dict[str, Any]:
        """Update an existing bill (sparse update)."""
        if "sparse" not in bill_data:
            bill_data["sparse"] = True
        return await self._request("POST", "/bill", json_data=bill_data, minor_version=minor_version)

    # BillPayment operations
    async def get_bill_payments(
        self,
        start_position: int = 1,
        max_results: int = 20,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Query bill payments.

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/billpayment
        """
        return await self._request(
            "GET",
            "/query",
            params={
                "query": f"SELECT * FROM BillPayment STARTPOSITION {start_position} MAXRESULTS {max_results}",
            },
            minor_version=minor_version,
        )

    async def get_bill_payment(self, bill_payment_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """Get a specific bill payment by ID."""
        return await self._request("GET", f"/billpayment/{bill_payment_id}", minor_version=minor_version)

    async def create_bill_payment(
        self, bill_payment_data: Dict[str, Any], minor_version: int = 70
    ) -> Dict[str, Any]:
        """Create a new bill payment."""
        return await self._request("POST", "/billpayment", json_data=bill_payment_data, minor_version=minor_version)

    # Estimate operations
    async def get_estimates(
        self,
        start_position: int = 1,
        max_results: int = 20,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Query estimates.

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/estimate
        """
        return await self._request(
            "GET",
            "/query",
            params={
                "query": f"SELECT * FROM Estimate STARTPOSITION {start_position} MAXRESULTS {max_results}",
            },
            minor_version=minor_version,
        )

    async def get_estimate(self, estimate_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """Get a specific estimate by ID."""
        return await self._request("GET", f"/estimate/{estimate_id}", minor_version=minor_version)

    async def create_estimate(self, estimate_data: Dict[str, Any], minor_version: int = 70) -> Dict[str, Any]:
        """Create a new estimate."""
        return await self._request("POST", "/estimate", json_data=estimate_data, minor_version=minor_version)

    async def update_estimate(
        self, estimate_id: str, estimate_data: Dict[str, Any], minor_version: int = 70
    ) -> Dict[str, Any]:
        """Update an existing estimate (sparse update)."""
        if "sparse" not in estimate_data:
            estimate_data["sparse"] = True
        return await self._request("POST", "/estimate", json_data=estimate_data, minor_version=minor_version)

    async def convert_estimate_to_invoice(
        self, estimate_id: str, minor_version: int = 70
    ) -> Dict[str, Any]:
        """Convert an estimate to an invoice."""
        return await self._request("POST", f"/estimate/{estimate_id}/convert", minor_version=minor_version)

    # JournalEntry operations (Double-Entry Bookkeeping)
    async def get_journal_entries(
        self,
        start_position: int = 1,
        max_results: int = 20,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Query journal entries.

        Args:
            start_position: Starting position for pagination
            max_results: Maximum number of results
            start_date: Filter by start date (YYYY-MM-DD format)
            end_date: Filter by end date (YYYY-MM-DD format)

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/journalentry
        """
        query_parts = ["SELECT * FROM JournalEntry"]
        if start_date or end_date:
            conditions = []
            if start_date:
                conditions.append(f"TxnDate >= '{start_date}'")
            if end_date:
                conditions.append(f"TxnDate <= '{end_date}'")
            query_parts.append(f"WHERE {' AND '.join(conditions)}")
        query_parts.append(f"STARTPOSITION {start_position} MAXRESULTS {max_results}")
        query = " ".join(query_parts)

        return await self._request(
            "GET",
            "/query",
            params={"query": query},
            minor_version=minor_version,
        )

    async def get_journal_entry(self, journal_entry_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """Get a specific journal entry by ID."""
        return await self._request("GET", f"/journalentry/{journal_entry_id}", minor_version=minor_version)

    async def create_journal_entry(
        self, journal_entry_data: Dict[str, Any], minor_version: int = 70
    ) -> Dict[str, Any]:
        """
        Create a new journal entry following double-entry bookkeeping principles.

        The journal entry must balance - total debits must equal total credits.
        Each line must specify either Debit or Credit (not both).

        Example:
            journal_entry_data = {
                "TxnDate": "2024-01-15",
                "Line": [
                    {
                        "Id": "0",
                        "Description": "Adjustment entry",
                        "Amount": 100.00,
                        "DetailType": "JournalEntryLineDetail",
                        "JournalEntryLineDetail": {
                            "PostingType": "Debit",
                            "AccountRef": {"value": "123", "name": "Expense Account"}
                        }
                    },
                    {
                        "Id": "1",
                        "Description": "Adjustment entry",
                        "Amount": 100.00,
                        "DetailType": "JournalEntryLineDetail",
                        "JournalEntryLineDetail": {
                            "PostingType": "Credit",
                            "AccountRef": {"value": "456", "name": "Liability Account"}
                        }
                    }
                ]
            }

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/journalentry
        """
        # Validate that debits equal credits
        total_debits = 0.0
        total_credits = 0.0

        if "Line" in journal_entry_data:
            for line in journal_entry_data["Line"]:
                if line.get("DetailType") == "JournalEntryLineDetail":
                    detail = line.get("JournalEntryLineDetail", {})
                    posting_type = detail.get("PostingType")
                    amount = float(line.get("Amount", 0))

                    if posting_type == "Debit":
                        total_debits += amount
                    elif posting_type == "Credit":
                        total_credits += amount

            if abs(total_debits - total_credits) > 0.01:  # Allow small floating point differences
                raise ValueError(
                    f"Journal entry must balance. Debits: {total_debits}, Credits: {total_credits}"
                )

        return await self._request("POST", "/journalentry", json_data=journal_entry_data, minor_version=minor_version)

    async def update_journal_entry(
        self, journal_entry_id: str, journal_entry_data: Dict[str, Any], minor_version: int = 70
    ) -> Dict[str, Any]:
        """Update an existing journal entry (sparse update)."""
        if "sparse" not in journal_entry_data:
            journal_entry_data["sparse"] = True
        return await self._request(
            "POST", "/journalentry", json_data=journal_entry_data, minor_version=minor_version
        )

    # Bookkeeping Helper Methods
    def validate_double_entry(
        self, journal_entry_data: Dict[str, Any]
    ) -> tuple:
        """
        Validate that a journal entry follows double-entry bookkeeping principles.

        Returns:
            Tuple of (is_valid, total_debits, total_credits)
        """
        total_debits = 0.0
        total_credits = 0.0

        if "Line" not in journal_entry_data:
            return False, 0.0, 0.0

        for line in journal_entry_data["Line"]:
            if line.get("DetailType") == "JournalEntryLineDetail":
                detail = line.get("JournalEntryLineDetail", {})
                posting_type = detail.get("PostingType")
                amount = float(line.get("Amount", 0))

                if posting_type == "Debit":
                    total_debits += amount
                elif posting_type == "Credit":
                    total_credits += amount

        is_balanced = abs(total_debits - total_credits) < 0.01
        return is_balanced, total_debits, total_credits

    def create_balanced_journal_entry(
        self,
        date: str,
        description: str,
        debit_account_id: str,
        debit_account_name: str,
        credit_account_id: str,
        credit_account_name: str,
        amount: float,
    ) -> Dict[str, Any]:
        """
        Helper method to create a balanced journal entry (double-entry bookkeeping).

        Args:
            date: Transaction date (YYYY-MM-DD format)
            description: Description for the journal entry
            debit_account_id: Account ID to debit
            debit_account_name: Account name to debit
            credit_account_id: Account ID to credit
            credit_account_name: Account name to credit
            amount: Amount to debit/credit (must be positive)

        Returns:
            Journal entry data dictionary ready to be sent to create_journal_entry
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        return {
            "TxnDate": date,
            "PrivateNote": description,
            "Line": [
                {
                    "Id": "0",
                    "Description": description,
                    "Amount": amount,
                    "DetailType": "JournalEntryLineDetail",
                    "JournalEntryLineDetail": {
                        "PostingType": "Debit",
                        "AccountRef": {"value": debit_account_id, "name": debit_account_name},
                    },
                },
                {
                    "Id": "1",
                    "Description": description,
                    "Amount": amount,
                    "DetailType": "JournalEntryLineDetail",
                    "JournalEntryLineDetail": {
                        "PostingType": "Credit",
                        "AccountRef": {"value": credit_account_id, "name": credit_account_name},
                    },
                },
            ],
        }

    # Employee operations
    async def get_employees(
        self,
        start_position: int = 1,
        max_results: int = 20,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Query employees.

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/employee
        """
        return await self._request(
            "GET",
            "/query",
            params={
                "query": f"SELECT * FROM Employee STARTPOSITION {start_position} MAXRESULTS {max_results}",
            },
            minor_version=minor_version,
        )

    async def get_employee(self, employee_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """Get a specific employee by ID."""
        return await self._request("GET", f"/employee/{employee_id}", minor_version=minor_version)

    async def create_employee(self, employee_data: Dict[str, Any], minor_version: int = 70) -> Dict[str, Any]:
        """Create a new employee."""
        return await self._request("POST", "/employee", json_data=employee_data, minor_version=minor_version)

    async def update_employee(
        self, employee_id: str, employee_data: Dict[str, Any], minor_version: int = 70
    ) -> Dict[str, Any]:
        """Update an existing employee (sparse update)."""
        if "sparse" not in employee_data:
            employee_data["sparse"] = True
        return await self._request("POST", "/employee", json_data=employee_data, minor_version=minor_version)

    # Refund operations
    async def get_refund_receipts(
        self,
        start_position: int = 1,
        max_results: int = 20,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Query refund receipts.

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/refundreceipt
        """
        return await self._request(
            "GET",
            "/query",
            params={
                "query": f"SELECT * FROM RefundReceipt STARTPOSITION {start_position} MAXRESULTS {max_results}",
            },
            minor_version=minor_version,
        )

    async def get_refund_receipt(self, refund_receipt_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """Get a specific refund receipt by ID."""
        return await self._request("GET", f"/refundreceipt/{refund_receipt_id}", minor_version=minor_version)

    async def create_refund_receipt(
        self, refund_receipt_data: Dict[str, Any], minor_version: int = 70
    ) -> Dict[str, Any]:
        """Create a new refund receipt."""
        return await self._request("POST", "/refundreceipt", json_data=refund_receipt_data, minor_version=minor_version)

    # Item/Product operations
    async def get_items(
        self,
        start_position: int = 1,
        max_results: int = 20,
        item_type: Optional[str] = None,  # "Inventory", "NonInventory", "Service", "Group", "Assembly"
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Query items (products/services).

        Args:
            start_position: Starting position for pagination
            max_results: Maximum number of results
            item_type: Filter by item type (Inventory, NonInventory, Service, Group, Assembly)
            minor_version: API minor version

        Reference: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/item
        """
        query_parts = ["SELECT * FROM Item"]
        if item_type:
            query_parts.append(f"WHERE Type = '{item_type}'")
        query_parts.append(f"STARTPOSITION {start_position} MAXRESULTS {max_results}")
        query = " ".join(query_parts)

        return await self._request(
            "GET",
            "/query",
            params={"query": query},
            minor_version=minor_version,
        )

    async def get_item(self, item_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """Get a specific item by ID."""
        return await self._request("GET", f"/item/{item_id}", minor_version=minor_version)

    async def create_item(self, item_data: Dict[str, Any], minor_version: int = 70) -> Dict[str, Any]:
        """Create a new item (product/service)."""
        return await self._request("POST", "/item", json_data=item_data, minor_version=minor_version)

    async def update_item(
        self, item_id: str, item_data: Dict[str, Any], minor_version: int = 70
    ) -> Dict[str, Any]:
        """Update an existing item (sparse update)."""
        if "sparse" not in item_data:
            item_data["sparse"] = True
        return await self._request("POST", "/item", json_data=item_data, minor_version=minor_version)

    # Report operations
    async def get_profit_and_loss(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Get Profit and Loss report.

        Args:
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
        """
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request("GET", "/reports/ProfitAndLoss", params=params, minor_version=minor_version)

    async def get_balance_sheet(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """Get Balance Sheet report."""
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request("GET", "/reports/BalanceSheet", params=params, minor_version=minor_version)

    async def get_cash_flow(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """Get Cash Flow report."""
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request("GET", "/reports/CashFlow", params=params, minor_version=minor_version)

    async def get_general_ledger(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        account_id: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Get General Ledger report (all transactions by account).

        Args:
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            account_id: Filter by specific account ID (optional)
        """
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if account_id:
            params["account"] = account_id
        return await self._request("GET", "/reports/GeneralLedger", params=params, minor_version=minor_version)

    async def get_account_transactions(
        self,
        account_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Get all transactions for a specific account (bookkeeping view).

        This is useful for account reconciliation and reviewing account activity.

        Args:
            account_id: Account ID to query
            start_date: Start date filter (YYYY-MM-DD format)
            end_date: End date filter (YYYY-MM-DD format)
        """
        query_parts = [
            "SELECT * FROM Transaction",
            f"WHERE AccountRef.value = '{account_id}'",
        ]
        if start_date:
            query_parts.append(f"AND TxnDate >= '{start_date}'")
        if end_date:
            query_parts.append(f"AND TxnDate <= '{end_date}'")
        query_parts.append("ORDERBY TxnDate DESC")

        query = " ".join(query_parts)
        return await self._request("GET", "/query", params={"query": query}, minor_version=minor_version)

    async def get_trial_balance(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """Get Trial Balance report."""
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return await self._request("GET", "/reports/TrialBalance", params=params, minor_version=minor_version)

    async def get_aged_receivables(
        self,
        as_of_date: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """Get Aged Receivables report."""
        params = {}
        if as_of_date:
            params["as_of_date"] = as_of_date
        return await self._request("GET", "/reports/AgedReceivables", params=params, minor_version=minor_version)

    async def get_aged_payables(
        self,
        as_of_date: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """Get Aged Payables report."""
        params = {}
        if as_of_date:
            params["as_of_date"] = as_of_date
        return await self._request("GET", "/reports/AgedPayables", params=params, minor_version=minor_version)

    # Company Info
    async def get_company_info(self, minor_version: int = 70) -> Dict[str, Any]:
        """Get company information."""
        # CompanyInfo endpoint requires the realm_id as part of the path
        return await self._request("GET", f"/companyinfo/{self.realm_id}", minor_version=minor_version)

    # Change Data Capture (CDC) - for syncing changes
    async def get_changes(
        self,
        entities: Optional[List[str]] = None,
        changed_since: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Get changes since a specific timestamp (Change Data Capture).

        Args:
            entities: List of entity types to check (e.g., ["Invoice", "Customer"])
            changed_since: Timestamp in ISO format (e.g., "2024-01-01T00:00:00")
        """
        params = {}
        if entities:
            params["entities"] = ",".join(entities)
        if changed_since:
            params["changedSince"] = changed_since
        return await self._request("GET", "/cdc", params=params, minor_version=minor_version)

    # Batch Operations
    async def batch_request(
        self,
        batch_items: List[Dict[str, Any]],
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Execute multiple operations in a single batch request (up to 10 requests).

        Args:
            batch_items: List of batch item dictionaries, each with:
                - bId: Batch item ID (unique within the batch)
                - operation: Operation type ("create", "update", "delete", "query")
                - entity: Entity type (e.g., "Invoice", "Customer")
                - data: Entity data (for create/update operations)
                - query: Query string (for query operations)

        Example:
            batch_items = [
                {
                    "bId": "bid1",
                    "operation": "create",
                    "entity": "Customer",
                    "data": {"Name": "New Customer"}
                },
                {
                    "bId": "bid2",
                    "operation": "query",
                    "entity": "Invoice",
                    "query": "SELECT * FROM Invoice WHERE Balance > '100'"
                }
            ]

        Reference: https://developer.intuit.com/app/developer/qbo/docs/learn/explore-the-quickbooks-online-api/batch
        """
        if len(batch_items) > 10:
            raise ValueError("Batch requests are limited to 10 items")

        batch_request_data = {
            "BatchItemRequest": batch_items,
        }
        return await self._request("POST", "/batch", json_data=batch_request_data, minor_version=minor_version)

    # Advanced Query Operations
    async def query(
        self,
        query_string: str,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Execute a custom SQL-like query against QuickBooks data.

        Args:
            query_string: SQL-like query string (e.g., "SELECT * FROM Invoice WHERE Balance > '100'")

        Supported query features:
            - SELECT with field filtering
            - WHERE clauses with operators (=, !=, >, <, >=, <=, LIKE, IN)
            - ORDER BY for sorting
            - STARTPOSITION and MAXRESULTS for pagination

        Example queries:
            - "SELECT * FROM Customer WHERE Active = true"
            - "SELECT Id, Name, Balance FROM Invoice WHERE Balance > '1000' ORDER BY Balance DESC"
            - "SELECT * FROM Item WHERE Type = 'Service' STARTPOSITION 1 MAXRESULTS 50"

        Reference: https://developer.intuit.com/app/developer/qbo/docs/learn/explore-the-quickbooks-online-api/data-queries
        """
        return await self._request(
            "GET",
            "/query",
            params={"query": query_string},
            minor_version=minor_version,
        )

    # PDF Generation
    async def get_invoice_pdf(self, invoice_id: str, minor_version: int = 70) -> bytes:
        """
        Get PDF version of an invoice.

        Args:
            invoice_id: QuickBooks invoice ID

        Returns:
            PDF file as bytes
        """
        token = self._get_access_token()
        url = f"{self.api_base_url}/invoice/{invoice_id}/pdf"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/pdf",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as e:
                logger.error(f"QuickBooks PDF generation error: {e}")
                raise

    async def get_estimate_pdf(self, estimate_id: str, minor_version: int = 70) -> bytes:
        """Get PDF version of an estimate."""
        token = self._get_access_token()
        url = f"{self.api_base_url}/estimate/{estimate_id}/pdf"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/pdf",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as e:
                logger.error(f"QuickBooks PDF generation error: {e}")
                raise

    async def get_bill_pdf(self, bill_id: str, minor_version: int = 70) -> bytes:
        """Get PDF version of a bill."""
        token = self._get_access_token()
        url = f"{self.api_base_url}/bill/{bill_id}/pdf"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/pdf",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.content
            except httpx.HTTPError as e:
                logger.error(f"QuickBooks PDF generation error: {e}")
                raise

    # Email Operations
    async def send_invoice_email(
        self,
        invoice_id: str,
        email_address: Optional[str] = None,
        cc_email_addresses: Optional[List[str]] = None,
        subject: Optional[str] = None,
        message: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Send an invoice via email.

        Args:
            invoice_id: QuickBooks invoice ID
            email_address: Recipient email address (if not specified, uses customer's email)
            cc_email_addresses: List of CC email addresses
            subject: Email subject (optional)
            message: Email message body (optional)
        """
        email_data = {}
        if email_address:
            email_data["SendTo"] = email_address
        if cc_email_addresses:
            email_data["CCEmail"] = {"Address": cc_email_addresses}
        if subject:
            email_data["Subject"] = subject
        if message:
            email_data["Message"] = message

        return await self._request(
            "POST", f"/invoice/{invoice_id}/send", json_data=email_data, minor_version=minor_version
        )

    async def send_estimate_email(
        self,
        estimate_id: str,
        email_address: Optional[str] = None,
        cc_email_addresses: Optional[List[str]] = None,
        subject: Optional[str] = None,
        message: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """Send an estimate via email."""
        email_data = {}
        if email_address:
            email_data["SendTo"] = email_address
        if cc_email_addresses:
            email_data["CCEmail"] = {"Address": cc_email_addresses}
        if subject:
            email_data["Subject"] = subject
        if message:
            email_data["Message"] = message

        return await self._request(
            "POST", f"/estimate/{estimate_id}/send", json_data=email_data, minor_version=minor_version
        )

    # Attachments
    async def upload_attachment(
        self,
        entity_type: str,  # e.g., "Invoice", "Customer"
        entity_id: str,
        file_name: str,
        file_content: bytes,
        content_type: str = "application/pdf",
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Upload an attachment to an entity.

        Args:
            entity_type: Type of entity (Invoice, Customer, etc.)
            entity_id: ID of the entity
            file_name: Name of the file
            file_content: File content as bytes
            content_type: MIME type of the file (default: application/pdf)
        """
        # QuickBooks uses multipart/form-data for attachments
        token = self._get_access_token()
        url = f"{self.api_base_url}/attachable"

        import io
        files = {
            "file_content": (file_name, io.BytesIO(file_content), content_type),
        }
        data = {
            "AttachableRef": [
                {
                    "EntityRef": {"type": entity_type, "value": entity_id},
                }
            ],
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    files=files,
                    data=data,
                    timeout=60.0,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"QuickBooks attachment upload error: {e}")
                raise

    async def get_attachments(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Get attachments for an entity or list all attachments.

        Args:
            entity_type: Filter by entity type (optional)
            entity_id: Filter by entity ID (optional)
        """
        if entity_type and entity_id:
            query = f"SELECT * FROM Attachable WHERE AttachableRef.EntityRef.type = '{entity_type}' AND AttachableRef.EntityRef.value = '{entity_id}'"
        else:
            query = "SELECT * FROM Attachable"
        return await self._request("GET", "/query", params={"query": query}, minor_version=minor_version)

    # Void/Delete Operations
    async def void_invoice(self, invoice_id: str, minor_version: int = 70) -> Dict[str, Any]:
        """Void an invoice."""
        invoice_data = {
            "sparse": True,
            "Id": invoice_id,
            "SyncToken": "0",  # Will need to fetch current SyncToken first
            "Void": True,
        }
        return await self._request("POST", "/invoice", json_data=invoice_data, minor_version=minor_version)

    async def delete_entity(
        self,
        entity_type: str,
        entity_id: str,
        sync_token: str,
        minor_version: int = 70,
    ) -> Dict[str, Any]:
        """
        Delete an entity (soft delete - sets Active=false for most entities).

        Args:
            entity_type: Type of entity (Customer, Item, etc.)
            entity_id: ID of the entity
            sync_token: Current sync token (for optimistic locking)
        """
        delete_data = {
            "Id": entity_id,
            "SyncToken": sync_token,
            "Active": False,
        }
        return await self._request("POST", f"/{entity_type.lower()}", json_data=delete_data, minor_version=minor_version)


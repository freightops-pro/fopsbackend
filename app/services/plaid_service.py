"""
Plaid Integration Service - External Bank Account Connections

Handles:
- Plaid Link token generation
- Bank account connections
- Transaction syncing
- Balance updates
- Webhook processing
"""

import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from plaid import ApiClient, Configuration
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.item_get_request import ItemGetRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from cryptography.fernet import Fernet

from app.core.config import get_settings

settings = get_settings()


class PlaidService:
    """
    Service for integrating with Plaid for external bank connections.

    This enables customers to connect their existing bank accounts
    to view all finances in one place and auto-reconcile transactions.
    """

    def __init__(self):
        # Configure Plaid client
        configuration = Configuration(
            host=self._get_plaid_host(),
            api_key={
                'clientId': os.getenv('PLAID_CLIENT_ID'),
                'secret': os.getenv('PLAID_SECRET'),
            }
        )

        api_client = ApiClient(configuration)
        self.client = plaid_api.PlaidApi(api_client)

        # Encryption key for access tokens
        encryption_key = os.getenv('PLAID_ENCRYPTION_KEY')
        if not encryption_key:
            raise ValueError("PLAID_ENCRYPTION_KEY not set - required for token encryption")
        self.cipher = Fernet(encryption_key.encode())

    def _get_plaid_host(self) -> str:
        """Get Plaid API host based on environment."""
        env = os.getenv('PLAID_ENV', 'sandbox')
        hosts = {
            'sandbox': 'https://sandbox.plaid.com',
            'development': 'https://development.plaid.com',
            'production': 'https://production.plaid.com',
        }
        return hosts.get(env, hosts['sandbox'])

    async def create_link_token(
        self,
        db: AsyncSession,
        company_id: str,
        user_id: str,
        redirect_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Plaid Link token for initiating bank connection flow.

        This token is used by the frontend Plaid Link component to
        start the OAuth-style bank connection process.

        Args:
            db: Database session
            company_id: Company connecting the bank
            user_id: User initiating connection
            redirect_uri: Optional OAuth redirect (for mobile apps)

        Returns:
            {
                "link_token": "link-sandbox-xxx",
                "expiration": "2025-12-16T12:00:00Z"
            }
        """
        request = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(
                client_user_id=user_id
            ),
            client_name="FreightOps TMS",
            products=[Products("transactions"), Products("auth")],
            country_codes=[CountryCode("US")],
            language='en',
            redirect_uri=redirect_uri,
            webhook='https://api.freightops.com/api/webhooks/plaid',  # Update with your domain
        )

        response = self.client.link_token_create(request)

        return {
            "link_token": response['link_token'],
            "expiration": response['expiration'],
        }

    async def exchange_public_token(
        self,
        db: AsyncSession,
        company_id: str,
        public_token: str,
        institution_id: Optional[str] = None,
        institution_name: Optional[str] = None
    ) -> str:
        """
        Exchange Plaid public token for permanent access token.

        Called after user successfully connects their bank via Plaid Link.
        The public token is temporary and must be exchanged immediately.

        Args:
            db: Database session
            company_id: Company ID
            public_token: Temporary token from Plaid Link
            institution_id: Bank institution ID (e.g., "ins_109508")
            institution_name: Bank name (e.g., "Chase")

        Returns:
            plaid_item_id: ID of created PlaidItem record
        """
        # Exchange public token for access token
        exchange_request = ItemPublicTokenExchangeRequest(
            public_token=public_token
        )
        exchange_response = self.client.item_public_token_exchange(exchange_request)

        access_token = exchange_response['access_token']
        item_id = exchange_response['item_id']

        # Encrypt access token before storing
        encrypted_token = self.cipher.encrypt(access_token.encode()).decode()

        # Get institution details if not provided
        if not institution_name:
            item_request = ItemGetRequest(access_token=access_token)
            item_response = self.client.item_get(item_request)
            institution_id = item_response['item']['institution_id']
            # Could call /institutions/get_by_id for full name
            institution_name = institution_id  # Placeholder

        # Create PlaidItem record
        import uuid
        plaid_item_id = str(uuid.uuid4())

        await db.execute(
            """
            INSERT INTO plaid_item (
                id, company_id, item_id, access_token,
                institution_id, institution_name,
                status, created_at, updated_at
            ) VALUES (
                :id, :company_id, :item_id, :access_token,
                :institution_id, :institution_name,
                'active', :now, :now
            )
            """,
            {
                "id": plaid_item_id,
                "company_id": company_id,
                "item_id": item_id,
                "access_token": encrypted_token,
                "institution_id": institution_id,
                "institution_name": institution_name,
                "now": datetime.utcnow(),
            }
        )

        # Fetch and store accounts
        await self.sync_accounts(db, plaid_item_id)

        # Fetch initial transactions
        await self.sync_transactions(db, plaid_item_id)

        await db.commit()

        return plaid_item_id

    async def sync_accounts(
        self,
        db: AsyncSession,
        plaid_item_id: str
    ) -> List[str]:
        """
        Sync bank accounts from Plaid.

        Fetches all accounts for a connected bank and updates balances.

        Args:
            db: Database session
            plaid_item_id: PlaidItem ID

        Returns:
            List of plaid_account IDs created/updated
        """
        # Get access token
        result = await db.execute(
            "SELECT access_token, company_id FROM plaid_item WHERE id = :id",
            {"id": plaid_item_id}
        )
        row = result.fetchone()
        if not row:
            raise ValueError(f"PlaidItem {plaid_item_id} not found")

        encrypted_token = row[0]
        company_id = row[1]

        # Decrypt access token
        access_token = self.cipher.decrypt(encrypted_token.encode()).decode()

        # Fetch accounts from Plaid
        accounts_request = AccountsGetRequest(access_token=access_token)
        accounts_response = self.client.accounts_get(accounts_request)

        plaid_account_ids = []

        for account in accounts_response['accounts']:
            import uuid
            plaid_account_id = str(uuid.uuid4())

            # Check if account already exists
            existing = await db.execute(
                "SELECT id FROM plaid_account WHERE account_id = :account_id",
                {"account_id": account['account_id']}
            )
            existing_row = existing.fetchone()

            if existing_row:
                # Update existing account
                await db.execute(
                    """
                    UPDATE plaid_account
                    SET current_balance = :current_balance,
                        available_balance = :available_balance,
                        updated_at = :now
                    WHERE account_id = :account_id
                    """,
                    {
                        "current_balance": account['balances']['current'],
                        "available_balance": account['balances']['available'],
                        "account_id": account['account_id'],
                        "now": datetime.utcnow(),
                    }
                )
                plaid_account_ids.append(existing_row[0])
            else:
                # Create new account
                await db.execute(
                    """
                    INSERT INTO plaid_account (
                        id, company_id, item_id, account_id,
                        name, official_name, account_type, account_subtype,
                        mask, current_balance, available_balance, balance_limit,
                        currency_code, enabled_for_sync, created_at, updated_at
                    ) VALUES (
                        :id, :company_id, :item_id, :account_id,
                        :name, :official_name, :account_type, :account_subtype,
                        :mask, :current_balance, :available_balance, :balance_limit,
                        :currency_code, true, :now, :now
                    )
                    """,
                    {
                        "id": plaid_account_id,
                        "company_id": company_id,
                        "item_id": plaid_item_id,
                        "account_id": account['account_id'],
                        "name": account['name'],
                        "official_name": account.get('official_name'),
                        "account_type": account['type'],
                        "account_subtype": account.get('subtype'),
                        "mask": account.get('mask'),
                        "current_balance": account['balances']['current'],
                        "available_balance": account['balances']['available'],
                        "balance_limit": account['balances'].get('limit'),
                        "currency_code": account['balances']['iso_currency_code'] or 'USD',
                        "now": datetime.utcnow(),
                    }
                )
                plaid_account_ids.append(plaid_account_id)

        await db.commit()

        return plaid_account_ids

    async def sync_transactions(
        self,
        db: AsyncSession,
        plaid_item_id: str,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sync transactions using Plaid's Transactions Sync API.

        This is more efficient than the legacy /transactions/get endpoint
        as it only fetches new/modified transactions since last sync.

        Args:
            db: Database session
            plaid_item_id: PlaidItem ID
            cursor: Optional sync cursor for incremental updates

        Returns:
            {
                "added": 15,
                "modified": 2,
                "removed": 1,
                "next_cursor": "xxx",
                "has_more": false
            }
        """
        # Get access token and cursor
        result = await db.execute(
            "SELECT access_token, sync_cursor, company_id FROM plaid_item WHERE id = :id",
            {"id": plaid_item_id}
        )
        row = result.fetchone()
        if not row:
            raise ValueError(f"PlaidItem {plaid_item_id} not found")

        encrypted_token = row[0]
        stored_cursor = row[1] if not cursor else cursor
        company_id = row[2]

        # Decrypt access token
        access_token = self.cipher.decrypt(encrypted_token.encode()).decode()

        # Sync transactions
        sync_request = TransactionsSyncRequest(
            access_token=access_token,
            cursor=stored_cursor,
        )

        sync_response = self.client.transactions_sync(sync_request)

        added_count = 0
        modified_count = 0
        removed_count = 0

        # Process added transactions
        for transaction in sync_response['added']:
            await self._store_transaction(db, company_id, plaid_item_id, transaction)
            added_count += 1

        # Process modified transactions
        for transaction in sync_response['modified']:
            await self._update_transaction(db, transaction)
            modified_count += 1

        # Process removed transactions
        for transaction_id in sync_response['removed']:
            await db.execute(
                "DELETE FROM plaid_transaction WHERE transaction_id = :id",
                {"id": transaction_id}
            )
            removed_count += 1

        # Update cursor
        next_cursor = sync_response['next_cursor']
        await db.execute(
            """
            UPDATE plaid_item
            SET sync_cursor = :cursor, last_synced_at = :now
            WHERE id = :id
            """,
            {
                "cursor": next_cursor,
                "now": datetime.utcnow(),
                "id": plaid_item_id,
            }
        )

        await db.commit()

        return {
            "added": added_count,
            "modified": modified_count,
            "removed": removed_count,
            "next_cursor": next_cursor,
            "has_more": sync_response['has_more'],
        }

    async def _store_transaction(
        self,
        db: AsyncSession,
        company_id: str,
        item_id: str,
        transaction: Dict[str, Any]
    ):
        """Store a new Plaid transaction."""
        # Get plaid_account_id from account_id
        result = await db.execute(
            "SELECT id FROM plaid_account WHERE account_id = :account_id",
            {"account_id": transaction['account_id']}
        )
        row = result.fetchone()
        if not row:
            return  # Account not synced yet

        plaid_account_id = row[0]

        import uuid
        plaid_transaction_id = str(uuid.uuid4())

        # Extract location if available
        location = transaction.get('location', {})

        await db.execute(
            """
            INSERT INTO plaid_transaction (
                id, company_id, account_id, transaction_id,
                amount, currency_code, description, merchant_name,
                category_primary, category_detailed, category_id,
                date, authorized_date, posted_date,
                pending, transaction_type, payment_channel, payment_method,
                location_address, location_city, location_state, location_zip,
                reconciled, created_at, updated_at
            ) VALUES (
                :id, :company_id, :account_id, :transaction_id,
                :amount, :currency_code, :description, :merchant_name,
                :category_primary, :category_detailed, :category_id,
                :date, :authorized_date, :posted_date,
                :pending, :transaction_type, :payment_channel, :payment_method,
                :location_address, :location_city, :location_state, :location_zip,
                false, :now, :now
            )
            """,
            {
                "id": plaid_transaction_id,
                "company_id": company_id,
                "account_id": plaid_account_id,
                "transaction_id": transaction['transaction_id'],
                "amount": transaction['amount'],
                "currency_code": transaction.get('iso_currency_code', 'USD'),
                "description": transaction.get('name'),
                "merchant_name": transaction.get('merchant_name'),
                "category_primary": transaction.get('personal_finance_category', {}).get('primary'),
                "category_detailed": transaction.get('personal_finance_category', {}).get('detailed'),
                "category_id": None,  # Legacy field
                "date": transaction['date'],
                "authorized_date": transaction.get('authorized_date'),
                "posted_date": transaction.get('date'),  # Use date as posted_date
                "pending": transaction['pending'],
                "transaction_type": transaction.get('transaction_type'),
                "payment_channel": transaction.get('payment_channel'),
                "payment_method": None,  # Not provided by Plaid
                "location_address": location.get('address'),
                "location_city": location.get('city'),
                "location_state": location.get('region'),
                "location_zip": location.get('postal_code'),
                "now": datetime.utcnow(),
            }
        )

    async def _update_transaction(
        self,
        db: AsyncSession,
        transaction: Dict[str, Any]
    ):
        """Update an existing Plaid transaction."""
        await db.execute(
            """
            UPDATE plaid_transaction
            SET amount = :amount,
                description = :description,
                merchant_name = :merchant_name,
                pending = :pending,
                updated_at = :now
            WHERE transaction_id = :transaction_id
            """,
            {
                "amount": transaction['amount'],
                "description": transaction.get('name'),
                "merchant_name": transaction.get('merchant_name'),
                "pending": transaction['pending'],
                "transaction_id": transaction['transaction_id'],
                "now": datetime.utcnow(),
            }
        )

    async def get_connected_banks(
        self,
        db: AsyncSession,
        company_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all connected banks for a company.

        Returns:
            [
                {
                    "id": "xxx",
                    "institution_name": "Chase",
                    "status": "active",
                    "accounts_count": 3,
                    "last_synced_at": "2025-12-15T10:00:00Z"
                }
            ]
        """
        result = await db.execute(
            """
            SELECT
                pi.id,
                pi.institution_name,
                pi.status,
                pi.last_synced_at,
                COUNT(pa.id) as accounts_count
            FROM plaid_item pi
            LEFT JOIN plaid_account pa ON pa.item_id = pi.id
            WHERE pi.company_id = :company_id
            GROUP BY pi.id, pi.institution_name, pi.status, pi.last_synced_at
            ORDER BY pi.created_at DESC
            """,
            {"company_id": company_id}
        )

        banks = []
        for row in result.fetchall():
            banks.append({
                "id": row[0],
                "institution_name": row[1],
                "status": row[2],
                "last_synced_at": row[3].isoformat() if row[3] else None,
                "accounts_count": row[4],
            })

        return banks

    async def disconnect_bank(
        self,
        db: AsyncSession,
        plaid_item_id: str
    ):
        """
        Disconnect a bank (soft delete - mark as inactive).

        Does not delete historical transactions, just stops syncing.
        """
        await db.execute(
            """
            UPDATE plaid_item
            SET status = 'disconnected', updated_at = :now
            WHERE id = :id
            """,
            {
                "id": plaid_item_id,
                "now": datetime.utcnow(),
            }
        )

        await db.execute(
            """
            UPDATE plaid_account
            SET enabled_for_sync = false, updated_at = :now
            WHERE item_id = :item_id
            """,
            {
                "item_id": plaid_item_id,
                "now": datetime.utcnow(),
            }
        )

        await db.commit()

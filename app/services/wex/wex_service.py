"""
WEX Service - High-level WEX EnCompass integration for FreightOps.

Handles:
- Company credential management
- Fuel card payments and virtual card generation
- Transaction reconciliation with IFTA reporting
- Merchant (fuel vendor) management
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import CompanyIntegration, Integration
from app.models.fuel import FuelTransaction
from app.services.wex.wex_client import WEXEnCompassClient

logger = logging.getLogger(__name__)


class WEXService:
    """
    High-level WEX EnCompass service for FreightOps.

    Provides fuel card management, virtual card payments,
    and transaction reconciliation for IFTA reporting.
    """

    INTEGRATION_KEY = "wex_encompass"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._clients: Dict[str, WEXEnCompassClient] = {}

    async def _get_client(self, company_id: str) -> WEXEnCompassClient:
        """
        Get or create a WEX client for a company.

        Loads credentials from the company's WEX integration settings.
        """
        if company_id in self._clients:
            return self._clients[company_id]

        # Get company's WEX integration credentials
        result = await self.db.execute(
            select(CompanyIntegration)
            .join(Integration)
            .where(
                CompanyIntegration.company_id == company_id,
                Integration.integration_key == self.INTEGRATION_KEY,
                CompanyIntegration.status == "active",
            )
        )
        integration = result.scalar_one_or_none()

        if not integration:
            raise ValueError(
                f"WEX EnCompass integration not configured for company {company_id}. "
                "Please configure WEX credentials in integration settings."
            )

        credentials = integration.credentials or {}

        # Required credentials
        org_group_login_id = credentials.get("org_group_login_id")
        username = credentials.get("username")
        password = credentials.get("password")

        if not all([org_group_login_id, username, password]):
            raise ValueError(
                "WEX credentials incomplete. Required: org_group_login_id, username, password"
            )

        # Optional OAuth credentials
        client_id = credentials.get("client_id")
        client_secret = credentials.get("client_secret")
        use_oauth = credentials.get("use_oauth", False)

        client = WEXEnCompassClient(
            org_group_login_id=org_group_login_id,
            username=username,
            password=password,
            client_id=client_id,
            client_secret=client_secret,
            use_oauth=use_oauth,
        )

        self._clients[company_id] = client
        return client

    async def close(self) -> None:
        """Close all WEX clients."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()

    # ==================== FUEL CARD OPERATIONS ====================

    async def create_fuel_card(
        self,
        company_id: str,
        merchant_id: str,
        amount: float,
        driver_id: Optional[str] = None,
        truck_id: Optional[str] = None,
        load_id: Optional[str] = None,
        fuel_stop_location: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        valid_days: int = 7,
    ) -> Dict[str, Any]:
        """
        Create a virtual fuel card for a driver.

        Args:
            company_id: FreightOps company ID
            merchant_id: WEX merchant ID for the fuel vendor
            amount: Maximum fuel purchase amount
            driver_id: FreightOps driver ID
            truck_id: FreightOps truck/equipment ID
            load_id: Associated load ID for IFTA tracking
            fuel_stop_location: Location description for the fuel stop
            jurisdiction: State/jurisdiction for IFTA tracking
            valid_days: Number of days the card is valid

        Returns:
            Virtual card details including:
            - merchant_log_id: WEX payment ID
            - card_number: Virtual card number
            - security_code: CVV
            - expiration_date: Card expiration
            - amount: Authorized amount
        """
        client = await self._get_client(company_id)

        idempotency_key = f"{company_id}-{driver_id or 'no-driver'}-{uuid.uuid4()}"

        result = await client.create_fuel_payment(
            merchant_id=merchant_id,
            amount=amount,
            driver_id=driver_id,
            truck_id=truck_id,
            load_id=load_id,
            fuel_stop_location=fuel_stop_location,
            valid_days=valid_days,
            idempotency_key=idempotency_key,
        )

        # Store pending fuel transaction for reconciliation
        if jurisdiction:
            await self._create_pending_fuel_transaction(
                company_id=company_id,
                wex_merchant_log_id=result.get("id"),
                driver_id=driver_id,
                truck_id=truck_id,
                load_id=load_id,
                amount=amount,
                jurisdiction=jurisdiction,
                location=fuel_stop_location,
            )

        # Extract virtual card details
        virtual_card = result.get("virtual_card", {})

        return {
            "merchant_log_id": result.get("id"),
            "card_number": virtual_card.get("card_number"),
            "security_code": virtual_card.get("security_code"),
            "expiration_month": virtual_card.get("expiration_month"),
            "expiration_year": virtual_card.get("expiration_year"),
            "expiration_date": f"{virtual_card.get('expiration_month', '')}/{virtual_card.get('expiration_year', '')}",
            "amount": amount,
            "status": result.get("status"),
            "valid_until": result.get("card_controls", {}).get("max_auth_date"),
        }

    async def get_fuel_card_status(
        self,
        company_id: str,
        merchant_log_id: str,
    ) -> Dict[str, Any]:
        """
        Get the current status of a fuel card/payment.

        Args:
            company_id: FreightOps company ID
            merchant_log_id: WEX MerchantLog ID

        Returns:
            Card status and usage details
        """
        client = await self._get_client(company_id)

        merchant_log = await client.get_merchant_log(merchant_log_id)
        authorizations = await client.get_merchant_log_authorizations(merchant_log_id)
        transactions = await client.get_merchant_log_transactions(merchant_log_id)

        return {
            "merchant_log_id": merchant_log_id,
            "status": merchant_log.get("status"),
            "amount": merchant_log.get("amount"),
            "virtual_card": merchant_log.get("virtual_card"),
            "authorizations": authorizations,
            "transactions": transactions,
            "is_used": len(transactions) > 0,
            "total_spent": sum(t.get("amount", 0) for t in transactions),
        }

    async def cancel_fuel_card(
        self,
        company_id: str,
        merchant_log_id: str,
    ) -> Dict[str, Any]:
        """
        Cancel a fuel card/payment.

        Args:
            company_id: FreightOps company ID
            merchant_log_id: WEX MerchantLog ID

        Returns:
            Cancellation result
        """
        client = await self._get_client(company_id)

        result = await client.cancel_merchant_log(merchant_log_id)

        # Update pending fuel transaction if exists
        await self._cancel_pending_fuel_transaction(company_id, merchant_log_id)

        return {
            "merchant_log_id": merchant_log_id,
            "status": "cancelled",
            "message": "Fuel card cancelled successfully",
        }

    # ==================== MERCHANT MANAGEMENT ====================

    async def create_fuel_vendor(
        self,
        company_id: str,
        name: str,
        address: Optional[Dict[str, str]] = None,
        contact: Optional[Dict[str, str]] = None,
        tax_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new fuel vendor in WEX.

        Args:
            company_id: FreightOps company ID
            name: Vendor business name
            address: Vendor address
            contact: Contact information
            tax_id: Vendor tax ID

        Returns:
            Created vendor details with WEX merchant ID
        """
        client = await self._get_client(company_id)

        result = await client.create_merchant(
            name=name,
            merchant_type="fuel_vendor",
            address=address,
            contact=contact,
            tax_id=tax_id,
        )

        return {
            "merchant_id": result.get("id"),
            "name": result.get("name"),
            "status": result.get("status"),
        }

    async def get_fuel_vendor(
        self,
        company_id: str,
        merchant_id: str,
    ) -> Dict[str, Any]:
        """Get fuel vendor details."""
        client = await self._get_client(company_id)
        return await client.get_merchant(merchant_id)

    # ==================== TRANSACTION RECONCILIATION ====================

    async def sync_transactions(
        self,
        company_id: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """
        Sync WEX transactions to FreightOps fuel transactions.

        This reconciles WEX posted transactions with FreightOps
        fuel transaction records for IFTA reporting.

        Args:
            company_id: FreightOps company ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Sync summary with counts of created/updated transactions
        """
        client = await self._get_client(company_id)

        transactions = await client.get_transactions_for_period(
            start_date=start_date,
            end_date=end_date,
            status="posted",
        )

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for txn in transactions:
            try:
                result = await self._reconcile_transaction(company_id, txn)
                if result == "created":
                    created_count += 1
                elif result == "updated":
                    updated_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                logger.error(f"Failed to reconcile transaction {txn.get('id')}: {e}")
                skipped_count += 1

        await self.db.commit()

        return {
            "period": {"start_date": start_date, "end_date": end_date},
            "total_transactions": len(transactions),
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
        }

    async def _reconcile_transaction(
        self,
        company_id: str,
        wex_transaction: Dict[str, Any],
    ) -> str:
        """
        Reconcile a single WEX transaction with FreightOps.

        Returns: 'created', 'updated', or 'skipped'
        """
        wex_id = wex_transaction.get("id")

        # Check if transaction already exists
        result = await self.db.execute(
            select(FuelTransaction).where(
                FuelTransaction.company_id == company_id,
                FuelTransaction.external_id == wex_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing transaction if needed
            if existing.status != "posted":
                existing.status = "posted"
                posted_date_str = wex_transaction.get("posted_date")
                if posted_date_str:
                    existing.posted_at = datetime.fromisoformat(posted_date_str)
                else:
                    existing.posted_at = datetime.utcnow()
                return "updated"
            return "skipped"

        # Extract user-defined fields for IFTA tracking
        user_fields = wex_transaction.get("user_defined_fields", {}) or {}
        driver_id = user_fields.get("driver_id")
        truck_id = user_fields.get("truck_id")
        load_id = user_fields.get("load_id")

        # Parse transaction date (expects YYYY-MM-DD or ISO format)
        txn_date_str = wex_transaction.get("transaction_date")
        if txn_date_str:
            txn_date = datetime.fromisoformat(txn_date_str).date()
        else:
            txn_date = datetime.utcnow().date()

        # Parse posted date
        posted_date_str = wex_transaction.get("posted_date")
        posted_at = datetime.fromisoformat(posted_date_str) if posted_date_str else datetime.utcnow()

        # Create new fuel transaction
        fuel_txn = FuelTransaction(
            id=str(uuid.uuid4()),
            company_id=company_id,
            external_id=wex_id,
            external_source="wex_encompass",
            driver_id=driver_id,
            truck_id=truck_id,
            load_id=load_id,
            transaction_date=txn_date,
            gallons=wex_transaction.get("gallons", 0),
            cost=wex_transaction.get("amount", 0),
            price_per_gallon=wex_transaction.get("price_per_gallon", 0),
            jurisdiction=wex_transaction.get("jurisdiction") or user_fields.get("jurisdiction"),
            location=wex_transaction.get("merchant_name"),
            status="posted",
            posted_at=posted_at,
        )

        self.db.add(fuel_txn)
        return "created"

    async def _create_pending_fuel_transaction(
        self,
        company_id: str,
        wex_merchant_log_id: str,
        driver_id: Optional[str],
        truck_id: Optional[str],
        load_id: Optional[str],
        amount: float,
        jurisdiction: str,
        location: Optional[str],
    ) -> None:
        """Create a pending fuel transaction for tracking."""
        fuel_txn = FuelTransaction(
            id=str(uuid.uuid4()),
            company_id=company_id,
            external_id=wex_merchant_log_id,
            external_source="wex_encompass",
            driver_id=driver_id,
            truck_id=truck_id,
            load_id=load_id,
            transaction_date=datetime.utcnow().date(),  # Use date not datetime
            gallons=0,  # Will be updated when transaction posts
            cost=amount,
            price_per_gallon=0,
            jurisdiction=jurisdiction,
            location=location,
            status="pending",
        )
        self.db.add(fuel_txn)
        await self.db.commit()

    async def _cancel_pending_fuel_transaction(
        self,
        company_id: str,
        wex_merchant_log_id: str,
    ) -> None:
        """Cancel a pending fuel transaction."""
        result = await self.db.execute(
            select(FuelTransaction).where(
                FuelTransaction.company_id == company_id,
                FuelTransaction.external_id == wex_merchant_log_id,
                FuelTransaction.status == "pending",
            )
        )
        txn = result.scalar_one_or_none()

        if txn:
            txn.status = "cancelled"
            await self.db.commit()

    # ==================== REPORTING ====================

    async def get_fuel_card_summary(
        self,
        company_id: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """
        Get a summary of fuel card usage for a period.

        Args:
            company_id: FreightOps company ID
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Summary with totals and breakdowns
        """
        client = await self._get_client(company_id)

        transactions = await client.get_transactions_for_period(
            start_date=start_date,
            end_date=end_date,
        )

        total_amount = sum(t.get("amount", 0) for t in transactions)
        total_gallons = sum(t.get("gallons", 0) for t in transactions)

        # Group by jurisdiction for IFTA
        by_jurisdiction: Dict[str, Dict[str, float]] = {}
        for txn in transactions:
            jurisdiction = txn.get("jurisdiction", "UNKNOWN")
            if jurisdiction not in by_jurisdiction:
                by_jurisdiction[jurisdiction] = {"gallons": 0, "amount": 0}
            by_jurisdiction[jurisdiction]["gallons"] += txn.get("gallons", 0)
            by_jurisdiction[jurisdiction]["amount"] += txn.get("amount", 0)

        return {
            "period": {"start_date": start_date, "end_date": end_date},
            "total_transactions": len(transactions),
            "total_amount": total_amount,
            "total_gallons": total_gallons,
            "avg_price_per_gallon": total_amount / total_gallons if total_gallons > 0 else 0,
            "by_jurisdiction": by_jurisdiction,
        }

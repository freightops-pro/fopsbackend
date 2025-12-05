"""Service for syncing fuel purchases from Motive."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting import LedgerEntry
from app.services.motive.motive_client import MotiveAPIClient

logger = logging.getLogger(__name__)


class FuelSyncService:
    """Service for syncing Motive fuel purchases to usage ledger."""

    def __init__(self, db: AsyncSession):
        """Initialize fuel sync service."""
        self.db = db

    async def sync_fuel_purchases(
        self,
        company_id: str,
        client_id: str,
        client_secret: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sync fuel purchases from Motive to usage ledger.

        Args:
            company_id: Company ID
            client_id: Motive OAuth client ID
            client_secret: Motive OAuth client secret
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            Dict with sync results
        """
        client = MotiveAPIClient(client_id, client_secret)
        synced_count = 0
        created_count = 0
        errors: List[str] = []

        try:
            # Fetch fuel purchases from Motive
            all_purchases: List[Dict[str, Any]] = []
            page = 1
            per_page = 100

            while True:
                response = await client.get_fuel_purchases(
                    start_date=start_date,
                    end_date=end_date,
                    per_page=per_page,
                    page_no=page,
                )
                purchases = response.get("fuel_purchases", []) or response.get("data", [])
                if not purchases:
                    break
                all_purchases.extend(purchases)
                if len(purchases) < per_page:
                    break
                page += 1

            # Sync each fuel purchase
            for purchase_data in all_purchases:
                try:
                    result = await self._sync_single_fuel_purchase(company_id, purchase_data)
                    if result["created"]:
                        created_count += 1
                    synced_count += 1
                except Exception as e:
                    error_msg = f"Error syncing fuel purchase {purchase_data.get('id', 'unknown')}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            return {
                "success": True,
                "total_purchases": len(all_purchases),
                "synced": synced_count,
                "created": created_count,
                "errors": errors,
            }
        except Exception as e:
            logger.error(f"Fuel purchase sync error: {e}", exc_info=True)
            raise

    async def _sync_single_fuel_purchase(
        self, company_id: str, purchase_data: Dict[str, Any]
    ) -> Dict[str, bool]:
        """
        Sync a single fuel purchase from Motive to usage ledger.

        Args:
            company_id: Company ID
            purchase_data: Fuel purchase data from Motive API

        Returns:
            Dict with sync result
        """
        motive_purchase_id = purchase_data.get("id")
        if not motive_purchase_id:
            raise ValueError("Purchase ID is required")

        # Check if already synced (by external reference in metadata)
        from sqlalchemy import select

        result = await self.db.execute(
            select(LedgerEntry).where(
                LedgerEntry.company_id == company_id,
                LedgerEntry.metadata_json["motive_purchase_id"].astext == str(motive_purchase_id),
            )
        )
        existing = result.scalar_one_or_none()

        # Extract purchase data
        transaction_time = purchase_data.get("transaction_time") or purchase_data.get("timestamp")
        if not transaction_time:
            raise ValueError("Transaction time is required")

        # Parse transaction time
        try:
            if isinstance(transaction_time, str):
                transaction_dt = datetime.fromisoformat(transaction_time.replace("Z", "+00:00"))
            else:
                transaction_dt = datetime.fromtimestamp(transaction_time)
        except Exception:
            transaction_dt = datetime.utcnow()

        # Get fuel amount and gallons
        total_amount = purchase_data.get("total_amount") or purchase_data.get("amount", 0)
        gallons = purchase_data.get("gallons") or purchase_data.get("quantity", 0)

        # Get location for jurisdiction detection
        merchant_info = purchase_data.get("merchant_info") or purchase_data.get("merchant", {})
        state = merchant_info.get("state") or purchase_data.get("state")
        city = merchant_info.get("city") or purchase_data.get("city")

        # Determine jurisdiction (simplified - would need proper jurisdiction mapping)
        jurisdiction = state or "UNKNOWN"

        # Get vehicle/driver info
        vehicle_id = purchase_data.get("vehicle_id")
        driver_id = purchase_data.get("driver_id")

        # Create or update ledger entry
        if existing:
            # Update existing entry
            existing.recorded_at = transaction_dt
            existing.category = "fuel"
            existing.amount = float(total_amount)
            existing.quantity = float(gallons) if gallons else None
            existing.unit = "GALLONS"
            if existing.metadata_json:
                existing.metadata_json.update({
                    "motive_purchase_id": motive_purchase_id,
                    "merchant": merchant_info,
                    "vehicle_id": vehicle_id,
                    "driver_id": driver_id,
                    "jurisdiction": jurisdiction,
                })
            else:
                existing.metadata_json = {
                    "motive_purchase_id": motive_purchase_id,
                    "merchant": merchant_info,
                    "vehicle_id": vehicle_id,
                    "driver_id": driver_id,
                    "jurisdiction": jurisdiction,
                    "source": "motive",
                }
            existing.description = f"Motive fuel purchase at {merchant_info.get('name', 'Unknown')}"
            return {"created": False}
        else:
            # Create new entry
            entry = LedgerEntry(
                id=str(uuid.uuid4()),
                company_id=company_id,
                recorded_at=transaction_dt,
                category="fuel",
                amount=float(total_amount),
                quantity=float(gallons) if gallons else None,
                unit="GALLONS",
                description=f"Motive fuel purchase at {merchant_info.get('name', 'Unknown')}",
                metadata_json={
                    "motive_purchase_id": motive_purchase_id,
                    "merchant": merchant_info,
                    "vehicle_id": vehicle_id,
                    "driver_id": driver_id,
                    "jurisdiction": jurisdiction,
                    "source": "motive",
                },
            )
            self.db.add(entry)
            await self.db.commit()
            await self.db.refresh(entry)
            return {"created": True}


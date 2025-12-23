from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fuel import FuelTransaction, JurisdictionRollup
from app.schemas.fuel import (
    FuelImportRequest,
    FuelSummaryResponse,
    JurisdictionSummaryResponse,
)
from app.models.integration import CompanyIntegration, Integration


class FuelService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def summary(self, company_id: str) -> FuelSummaryResponse:
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(FuelTransaction.gallons), 0),
                func.coalesce(func.sum(FuelTransaction.cost), 0),
            ).where(FuelTransaction.company_id == company_id)
        )
        gallons, cost = result.one()

        result_taxable = await self.db.execute(
            select(
                func.coalesce(func.sum(JurisdictionRollup.taxable_gallons), 0),
                func.coalesce(func.sum(JurisdictionRollup.tax_due), 0),
            ).where(JurisdictionRollup.company_id == company_id)
        )
        taxable_gallons, tax_due = result_taxable.one()

        avg_price = float(cost) / float(gallons) if gallons else 0
        return FuelSummaryResponse(
            total_gallons=float(gallons),
            taxable_gallons=float(taxable_gallons),
            total_cost=float(cost),
            tax_due=float(tax_due),
            avg_price_per_gallon=avg_price,
        )

    async def jurisdictions(self, company_id: str) -> List[JurisdictionSummaryResponse]:
        result = await self.db.execute(
            select(JurisdictionRollup).where(JurisdictionRollup.company_id == company_id)
        )
        summaries: List[JurisdictionSummaryResponse] = []
        for rollup in result.scalars().all():
            summaries.append(
                JurisdictionSummaryResponse(
                    jurisdiction=rollup.jurisdiction,
                    gallons=float(rollup.gallons or 0),
                    taxable_gallons=float(rollup.taxable_gallons or 0),
                    miles=float(rollup.miles or 0),
                    tax_due=float(rollup.tax_due or 0),
                    surcharge_due=float(rollup.surcharge_due or 0),
                    last_trip_date=rollup.last_trip_date,
                )
            )
        
        # Enhance with Motive IFTA data if available
        try:
            motive_integration_result = await self.db.execute(
                select(CompanyIntegration)
                .join(Integration)
                .where(
                    CompanyIntegration.company_id == company_id,
                    Integration.integration_key == "motive",
                    CompanyIntegration.status == "active",
                )
            )
            motive_integration = motive_integration_result.scalar_one_or_none()
            
            if motive_integration and motive_integration.credentials:
                from app.services.motive.motive_client import MotiveAPIClient
                
                client_id = motive_integration.credentials.get("client_id")
                client_secret = motive_integration.credentials.get("client_secret")
                
                if client_id and client_secret:
                    client = MotiveAPIClient(client_id, client_secret)
                    # Get IFTA mileage summary from Motive
                    ifta_response = await client.get_ifta_mileage_summary()
                    ifta_summary = ifta_response.get("mileage_summary", []) or ifta_response.get("data", [])
                    
                    # Merge Motive IFTA data with existing jurisdiction data
                    ifta_by_jurisdiction = {}
                    for item in ifta_summary:
                        jurisdiction = item.get("jurisdiction") or item.get("state")
                        if jurisdiction:
                            ifta_by_jurisdiction[jurisdiction] = item
                    
                    # Update summaries with Motive data
                    for summary in summaries:
                        ifta_data = ifta_by_jurisdiction.get(summary.jurisdiction)
                        if ifta_data:
                            # Enhance with Motive mileage data
                            motive_miles = ifta_data.get("miles") or ifta_data.get("total_miles", 0)
                            if motive_miles and summary.miles == 0:
                                summary.miles = float(motive_miles)
        except Exception as e:
            # Log but don't fail if Motive integration fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to enhance IFTA data with Motive: {e}")
        
        return summaries

    async def import_statement(self, company_id: str, payload: FuelImportRequest) -> None:
        """
        Import fuel statement data from CSV file.
        Parses the statement file, creates fuel transactions, and updates jurisdiction rollups.

        Expected CSV columns:
        - date: Transaction date (YYYY-MM-DD or MM/DD/YYYY)
        - gallons: Fuel amount in gallons
        - amount: Transaction cost in USD
        - state: State code (e.g., TX, CA)
        - location: Station/location name
        - card_last4: Last 4 digits of fuel card (optional)
        - driver_id: Driver ID (optional)
        - truck_id: Equipment ID (optional)
        """
        from app.models.document import Document

        # Fetch the uploaded file
        file_result = await self.db.execute(
            select(Document).where(
                Document.id == payload.file_id,
                Document.company_id == company_id,
            )
        )
        document = file_result.scalar_one_or_none()

        if not document:
            raise ValueError(f"File not found: {payload.file_id}")

        # Parse statement month for rollup period
        year, month = map(int, payload.statement_month.split("-"))
        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year + 1, 1, 1)
        else:
            period_end = date(year, month + 1, 1)

        # Read and parse CSV content
        file_content = document.content if hasattr(document, "content") else None
        if not file_content:
            # Try to read from file path if content not stored directly
            file_path = getattr(document, "file_path", None) or getattr(document, "storage_path", None)
            if file_path:
                import aiofiles
                async with aiofiles.open(file_path, mode='rb') as f:
                    file_content = await f.read()
            else:
                raise ValueError("Cannot access file content")

        # Decode and parse CSV
        if isinstance(file_content, bytes):
            file_content = file_content.decode("utf-8-sig")

        transactions = self._parse_csv_statement(file_content, payload.card_program)

        # Create fuel transactions
        for tx in transactions:
            fuel_tx = FuelTransaction(
                id=str(uuid.uuid4()),
                company_id=company_id,
                driver_id=tx.get("driver_id"),
                truck_id=tx.get("truck_id"),
                transaction_date=tx["date"],
                jurisdiction=tx.get("state", "").upper(),
                location=tx.get("location"),
                gallons=Decimal(str(tx["gallons"])),
                cost=Decimal(str(tx["amount"])),
                price_per_gallon=Decimal(str(tx["amount"])) / Decimal(str(tx["gallons"])) if tx["gallons"] > 0 else None,
                fuel_card=tx.get("card_last4"),
                external_source=payload.card_program,
                status="posted",
                posted_at=datetime.utcnow(),
            )
            self.db.add(fuel_tx)

        # Update jurisdiction rollups
        await self._update_jurisdiction_rollups(
            company_id=company_id,
            transactions=transactions,
            period_start=period_start,
            period_end=period_end,
        )

        await self.db.commit()

    def _parse_csv_statement(self, content: str, card_program: str) -> List[Dict[str, Any]]:
        """Parse fuel statement CSV content into transaction records."""
        transactions = []
        reader = csv.DictReader(io.StringIO(content))

        # Normalize column names (handle different naming conventions)
        column_mappings = {
            "date": ["date", "transaction_date", "trans_date", "txn_date"],
            "gallons": ["gallons", "quantity", "qty", "units"],
            "amount": ["amount", "cost", "total", "price", "net_cost"],
            "state": ["state", "jurisdiction", "region", "province"],
            "location": ["location", "site", "station", "merchant", "store"],
            "card_last4": ["card", "card_last4", "card_number", "last4"],
            "driver_id": ["driver_id", "driver", "operator_id"],
            "truck_id": ["truck_id", "unit_id", "vehicle", "equipment_id"],
        }

        for row in reader:
            # Normalize column names to lowercase
            normalized_row = {k.lower().strip(): v for k, v in row.items()}

            # Extract values with column mapping
            tx = {}
            for field, possible_names in column_mappings.items():
                for name in possible_names:
                    if name in normalized_row and normalized_row[name]:
                        tx[field] = normalized_row[name]
                        break

            # Parse date
            date_str = tx.get("date", "")
            if date_str:
                tx["date"] = self._parse_date(date_str)
            else:
                continue  # Skip rows without date

            # Parse numeric fields
            try:
                gallons_str = tx.get("gallons", "0").replace(",", "")
                amount_str = tx.get("amount", "0").replace(",", "").replace("$", "")
                tx["gallons"] = float(gallons_str) if gallons_str else 0
                tx["amount"] = float(amount_str) if amount_str else 0
            except (ValueError, TypeError):
                continue  # Skip invalid rows

            if tx["gallons"] > 0:
                transactions.append(tx)

        return transactions

    def _parse_date(self, date_str: str) -> date:
        """Parse date from various formats."""
        formats = [
            "%Y-%m-%d",      # 2024-01-15
            "%m/%d/%Y",      # 01/15/2024
            "%m/%d/%y",      # 01/15/24
            "%d-%m-%Y",      # 15-01-2024
            "%Y/%m/%d",      # 2024/01/15
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date: {date_str}")

    async def _update_jurisdiction_rollups(
        self,
        company_id: str,
        transactions: List[Dict[str, Any]],
        period_start: date,
        period_end: date,
    ) -> None:
        """Update jurisdiction rollups with new transaction data."""
        # Aggregate by jurisdiction
        jurisdiction_data: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"gallons": 0.0, "cost": 0.0, "last_date": None}
        )

        for tx in transactions:
            state = tx.get("state", "").upper()
            if not state:
                continue

            jurisdiction_data[state]["gallons"] += tx.get("gallons", 0)
            jurisdiction_data[state]["cost"] += tx.get("amount", 0)

            tx_date = tx.get("date")
            if tx_date:
                current_last = jurisdiction_data[state]["last_date"]
                if not current_last or tx_date > current_last:
                    jurisdiction_data[state]["last_date"] = tx_date

        # Update or create jurisdiction rollups
        for jurisdiction, data in jurisdiction_data.items():
            # Check for existing rollup
            existing_result = await self.db.execute(
                select(JurisdictionRollup).where(
                    JurisdictionRollup.company_id == company_id,
                    JurisdictionRollup.jurisdiction == jurisdiction,
                    JurisdictionRollup.period_start == period_start,
                    JurisdictionRollup.period_end == period_end,
                )
            )
            existing = existing_result.scalar_one_or_none()

            if existing:
                # Update existing rollup
                existing.gallons = Decimal(str(existing.gallons or 0)) + Decimal(str(data["gallons"]))
                existing.taxable_gallons = existing.gallons  # Simplified - all fuel is taxable
                existing.last_trip_date = data["last_date"]
                existing.updated_at = datetime.utcnow()
            else:
                # Create new rollup
                rollup = JurisdictionRollup(
                    id=str(uuid.uuid4()),
                    company_id=company_id,
                    period_start=period_start,
                    period_end=period_end,
                    jurisdiction=jurisdiction,
                    gallons=Decimal(str(data["gallons"])),
                    taxable_gallons=Decimal(str(data["gallons"])),  # Simplified
                    miles=Decimal("0"),  # Miles come from ELD/mileage tracking
                    tax_due=Decimal("0"),  # Calculated separately
                    surcharge_due=Decimal("0"),
                    last_trip_date=data["last_date"],
                )
                self.db.add(rollup)


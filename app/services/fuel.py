from __future__ import annotations

import uuid
from datetime import date
from typing import List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fuel import FuelTransaction, JurisdictionRollup
from app.schemas.fuel import (
    FuelImportRequest,
    FuelSummaryResponse,
    JurisdictionSummaryResponse,
)
from sqlalchemy import select
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
        Import fuel statement data.
        This should parse the statement file and create jurisdiction rollups.
        For now, this is a stub that will be implemented with actual file parsing.
        """
        # TODO: Implement actual fuel statement parsing from payload.file_id
        # For now, raise an error to indicate this needs implementation
        raise NotImplementedError(
            "Fuel statement import is not yet fully implemented. "
            "File parsing and jurisdiction rollup calculation is required."
        )


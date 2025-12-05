from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting import LedgerEntry
from app.schemas.usage_ledger import UsageLedgerEntry as UsageLedgerEntrySchema


class UsageLedgerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def preview(self, company_id: str, limit: int = 20) -> List[UsageLedgerEntrySchema]:
        """Get preview of usage ledger entries."""
        result = await self.db.execute(
            select(LedgerEntry)
            .where(LedgerEntry.company_id == company_id)
            .order_by(LedgerEntry.recorded_at.desc())
            .limit(limit)
        )
        entries = list(result.scalars().all())
        
        # Map to usage ledger format
        usage_entries = []
        for entry in entries:
            # Determine entry type from category
            entry_type = "MILES" if entry.category == "revenue" else "FUEL"
            if "detention" in entry.category.lower():
                entry_type = "DETENTION"
            elif "accessorial" in entry.category.lower():
                entry_type = "ACCESSORIAL"
            
            # Determine unit
            unit = entry.unit or "USD"
            if entry_type == "MILES":
                unit = "MILES"
            elif entry_type == "FUEL":
                unit = "GALLONS"
            elif entry_type == "DETENTION":
                unit = "MINUTES"
            
            usage_entries.append(
                UsageLedgerEntrySchema(
                    id=entry.id,
                    source="ACCOUNTING",  # Could be determined from entry metadata
                    load_id=entry.load_id or "",
                    leg_id=None,  # Would need to extract from metadata
                    driver_id=None,  # Would need to extract from metadata
                    truck_id=None,  # Would need to extract from metadata
                    entry_type=entry_type,
                    quantity=float(entry.quantity or 0),
                    unit=unit,
                    jurisdiction=None,  # Would need to extract from metadata
                    recorded_at=entry.recorded_at,
                    metadata=entry.metadata_json,
                )
            )
        
        return usage_entries


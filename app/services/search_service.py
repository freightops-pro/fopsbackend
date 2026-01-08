"""Global search service for searching across multiple entities."""

import logging
import time
from typing import List

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accounting import Customer
from app.models.driver import Driver
from app.models.equipment import Equipment
from app.models.load import Load
from app.schemas.search import SearchResult

logger = logging.getLogger(__name__)


class SearchService:
    """Service for global search across multiple entities."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(
        self, company_id: str, query: str, limit: int = 20
    ) -> tuple[List[SearchResult], int]:
        """
        Perform global search across multiple entity types.

        Args:
            company_id: Company ID to search within
            query: Search query string
            limit: Maximum results per entity type

        Returns:
            Tuple of (results list, time taken in ms)
        """
        start_time = time.time()

        if not query or len(query.strip()) < 2:
            return [], 0

        query = query.strip()
        results: List[SearchResult] = []

        # Search loads
        load_results = await self._search_loads(company_id, query, limit)
        results.extend(load_results)

        # Search drivers
        driver_results = await self._search_drivers(company_id, query, limit)
        results.extend(driver_results)

        # Search equipment
        equipment_results = await self._search_equipment(company_id, query, limit)
        results.extend(equipment_results)

        # Search customers
        customer_results = await self._search_customers(company_id, query, limit)
        results.extend(customer_results)

        # Sort by relevance score (descending)
        results.sort(key=lambda x: x.score, reverse=True)

        # Limit total results
        results = results[:limit * 2]  # Return max 40 results total

        elapsed_ms = int((time.time() - start_time) * 1000)
        return results, elapsed_ms

    async def _search_loads(
        self, company_id: str, query: str, limit: int
    ) -> List[SearchResult]:
        """Search loads by load number, customer name, origin/destination."""
        try:
            query_lower = f"%{query.lower()}%"

            stmt = (
                select(Load)
                .where(Load.company_id == company_id)
                .where(
                    or_(
                        func.lower(Load.load_number).like(query_lower),
                        func.lower(Load.customer_name).like(query_lower),
                        func.lower(Load.commodity).like(query_lower),
                    )
                )
                .limit(limit)
            )

            result = await self.db.execute(stmt)
            loads = result.scalars().all()

            search_results = []
            for load in loads:
                # Calculate simple relevance score
                score = 1.0
                if load.load_number and query.lower() in load.load_number.lower():
                    score += 2.0  # Boost exact load number matches

                # Build subtitle with origin/destination if available
                subtitle_parts = []
                if load.customer_name:
                    subtitle_parts.append(load.customer_name)
                if load.commodity:
                    subtitle_parts.append(load.commodity)
                subtitle = " • ".join(subtitle_parts) if subtitle_parts else None

                search_results.append(
                    SearchResult(
                        id=load.id,
                        type="load",
                        title=f"Load #{load.load_number or load.id[:8]}",
                        subtitle=subtitle,
                        link=f"/dispatch/load-manager?load={load.id}",
                        score=score,
                    )
                )

            return search_results

        except Exception as e:
            logger.error(f"Error searching loads: {str(e)}")
            return []

    async def _search_drivers(
        self, company_id: str, query: str, limit: int
    ) -> List[SearchResult]:
        """Search drivers by name, email, phone, license number."""
        try:
            query_lower = f"%{query.lower()}%"

            stmt = (
                select(Driver)
                .where(Driver.company_id == company_id)
                .where(
                    or_(
                        func.lower(Driver.first_name).like(query_lower),
                        func.lower(Driver.last_name).like(query_lower),
                        func.lower(Driver.email).like(query_lower),
                        func.lower(Driver.phone).like(query_lower),
                        func.lower(Driver.cdl_number).like(query_lower),
                    )
                )
                .limit(limit)
            )

            result = await self.db.execute(stmt)
            drivers = result.scalars().all()

            search_results = []
            for driver in drivers:
                score = 1.0
                full_name = f"{driver.first_name} {driver.last_name}"

                # Build subtitle with CDL and status info
                subtitle_parts = []
                if driver.cdl_number:
                    subtitle_parts.append(f"CDL: {driver.cdl_number}")
                if driver.employment_type:
                    subtitle_parts.append(driver.employment_type.replace("_", " ").title())
                subtitle = " • ".join(subtitle_parts) if subtitle_parts else None

                search_results.append(
                    SearchResult(
                        id=driver.id,
                        type="driver",
                        title=full_name,
                        subtitle=subtitle,
                        link=f"/fleet/drivers?driver={driver.id}",
                        score=score,
                    )
                )

            return search_results

        except Exception as e:
            logger.error(f"Error searching drivers: {str(e)}")
            return []

    async def _search_equipment(
        self, company_id: str, query: str, limit: int
    ) -> List[SearchResult]:
        """Search equipment by unit number, VIN, make, model."""
        try:
            query_lower = f"%{query.lower()}%"

            stmt = (
                select(Equipment)
                .where(Equipment.company_id == company_id)
                .where(
                    or_(
                        func.lower(Equipment.unit_number).like(query_lower),
                        func.lower(Equipment.vin).like(query_lower),
                        func.lower(Equipment.make).like(query_lower),
                        func.lower(Equipment.model).like(query_lower),
                    )
                )
                .limit(limit)
            )

            result = await self.db.execute(stmt)
            equipment_list = result.scalars().all()

            search_results = []
            for equip in equipment_list:
                score = 1.0
                if equip.unit_number and query.lower() in equip.unit_number.lower():
                    score += 2.0  # Boost exact unit number matches

                # Build subtitle with make/model and type
                subtitle_parts = []
                if equip.make and equip.model:
                    subtitle_parts.append(f"{equip.make} {equip.model}")
                elif equip.make:
                    subtitle_parts.append(equip.make)
                if equip.equipment_type:
                    subtitle_parts.append(equip.equipment_type.replace("_", " ").title())
                subtitle = " • ".join(subtitle_parts) if subtitle_parts else None

                search_results.append(
                    SearchResult(
                        id=equip.id,
                        type="equipment",
                        title=f"Unit {equip.unit_number or equip.id[:8]}",
                        subtitle=subtitle,
                        link=f"/fleet/equipment?unit={equip.id}",
                        score=score,
                    )
                )

            return search_results

        except Exception as e:
            logger.error(f"Error searching equipment: {str(e)}")
            return []

    async def _search_customers(
        self, company_id: str, query: str, limit: int
    ) -> List[SearchResult]:
        """Search customers by name, contact info."""
        try:
            query_lower = f"%{query.lower()}%"

            stmt = (
                select(Customer)
                .where(Customer.company_id == company_id)
                .where(
                    or_(
                        func.lower(Customer.name).like(query_lower),
                        func.lower(Customer.email).like(query_lower),
                        func.lower(Customer.phone).like(query_lower),
                    )
                )
                .limit(limit)
            )

            result = await self.db.execute(stmt)
            customers = result.scalars().all()

            search_results = []
            for customer in customers:
                score = 1.0

                # Build subtitle with contact info
                subtitle_parts = []
                if customer.status:
                    subtitle_parts.append(customer.status.title())
                if customer.email:
                    subtitle_parts.append(customer.email)
                subtitle = " • ".join(subtitle_parts) if subtitle_parts else None

                search_results.append(
                    SearchResult(
                        id=customer.id,
                        type="customer",
                        title=customer.name,
                        subtitle=subtitle,
                        link=f"/accounting/customers?customer={customer.id}",
                        score=score,
                    )
                )

            return search_results

        except Exception as e:
            logger.error(f"Error searching customers: {str(e)}")
            return []

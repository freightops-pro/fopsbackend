"""
Drayage Service Layer.

Provides business logic for container drayage operations including:
- Container lifecycle management
- Chassis pool management
- Chassis usage tracking
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.drayage import (
    ChassisPool,
    ChassisUsage,
    DrayageContainer,
)


class DrayageService:
    """Service for managing drayage containers, chassis pools, and chassis usage."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ==================== CONTAINER METHODS ====================

    async def list_containers(self, company_id: str) -> List[DrayageContainer]:
        """List all containers for a company."""
        result = await self.db.execute(
            select(DrayageContainer)
            .where(DrayageContainer.company_id == company_id)
            .options(
                selectinload(DrayageContainer.steamship_line),
                selectinload(DrayageContainer.terminal),
                selectinload(DrayageContainer.appointments),
                selectinload(DrayageContainer.charges),
                selectinload(DrayageContainer.chassis_usages),
                selectinload(DrayageContainer.events),
            )
            .order_by(DrayageContainer.created_at.desc())
        )
        containers = result.scalars().unique().all()
        return list(containers)

    async def get_container(self, company_id: str, container_id: str) -> DrayageContainer:
        """Get a single container by ID."""
        result = await self.db.execute(
            select(DrayageContainer)
            .where(
                DrayageContainer.company_id == company_id,
                DrayageContainer.id == container_id,
            )
            .options(
                selectinload(DrayageContainer.steamship_line),
                selectinload(DrayageContainer.terminal),
                selectinload(DrayageContainer.appointments),
                selectinload(DrayageContainer.charges),
                selectinload(DrayageContainer.chassis_usages),
                selectinload(DrayageContainer.events),
            )
        )
        container = result.scalars().unique().one_or_none()
        if not container:
            raise ValueError("Container not found")
        return container

    async def create_container(self, company_id: str, payload: Dict[str, Any]) -> DrayageContainer:
        """Create a new container."""
        # Check for duplicate container number within company
        existing_container = await self.db.execute(
            select(DrayageContainer).where(
                DrayageContainer.company_id == company_id,
                DrayageContainer.container_number == payload.get("container_number"),
            )
        )
        if existing_container.scalar_one_or_none():
            raise ValueError(f"Container with number '{payload.get('container_number')}' already exists")

        container = DrayageContainer(
            id=str(uuid.uuid4()),
            company_id=company_id,
            load_id=payload.get("load_id"),
            container_number=payload.get("container_number"),
            container_size=payload.get("container_size"),
            container_type=payload.get("container_type"),
            is_hazmat=payload.get("is_hazmat", False),
            hazmat_class=payload.get("hazmat_class"),
            is_overweight=payload.get("is_overweight", False),
            gross_weight_lbs=payload.get("gross_weight_lbs"),
            booking_number=payload.get("booking_number"),
            bill_of_lading=payload.get("bill_of_lading"),
            house_bill=payload.get("house_bill"),
            seal_number=payload.get("seal_number"),
            reference_number=payload.get("reference_number"),
            steamship_line_id=payload.get("steamship_line_id"),
            ssl_scac=payload.get("ssl_scac"),
            terminal_id=payload.get("terminal_id"),
            port_code=payload.get("port_code"),
            terminal_code=payload.get("terminal_code"),
            vessel_name=payload.get("vessel_name"),
            voyage_number=payload.get("voyage_number"),
            vessel_eta=payload.get("vessel_eta"),
            vessel_ata=payload.get("vessel_ata"),
            status=payload.get("status", "BOOKING"),
            discharge_date=payload.get("discharge_date"),
            last_free_day=payload.get("last_free_day"),
            per_diem_start_date=payload.get("per_diem_start_date"),
            detention_start_date=payload.get("detention_start_date"),
            empty_return_by=payload.get("empty_return_by"),
            pickup_terminal_code=payload.get("pickup_terminal_code"),
            pickup_appointment_id=payload.get("pickup_appointment_id"),
            pickup_scheduled_at=payload.get("pickup_scheduled_at"),
            pickup_actual_at=payload.get("pickup_actual_at"),
            outgate_at=payload.get("outgate_at"),
            delivery_location=payload.get("delivery_location"),
            delivery_appointment_at=payload.get("delivery_appointment_at"),
            delivery_actual_at=payload.get("delivery_actual_at"),
            return_terminal_code=payload.get("return_terminal_code"),
            return_appointment_id=payload.get("return_appointment_id"),
            return_scheduled_at=payload.get("return_scheduled_at"),
            return_actual_at=payload.get("return_actual_at"),
            ingate_at=payload.get("ingate_at"),
            chassis_number=payload.get("chassis_number"),
            chassis_pool_id=payload.get("chassis_pool_id"),
            chassis_pool_code=payload.get("chassis_pool_code"),
            chassis_outgate_at=payload.get("chassis_outgate_at"),
            chassis_return_at=payload.get("chassis_return_at"),
            holds=payload.get("holds"),
            hold_notes=payload.get("hold_notes"),
            demurrage_days=payload.get("demurrage_days", 0),
            demurrage_amount=payload.get("demurrage_amount"),
            per_diem_days=payload.get("per_diem_days", 0),
            per_diem_amount=payload.get("per_diem_amount"),
            detention_days=payload.get("detention_days", 0),
            detention_amount=payload.get("detention_amount"),
            chassis_per_diem_amount=payload.get("chassis_per_diem_amount"),
            total_accessorial_charges=payload.get("total_accessorial_charges"),
            port_raw_data=payload.get("port_raw_data"),
            notes=payload.get("notes"),
            metadata_json=payload.get("metadata_json"),
        )
        self.db.add(container)
        await self.db.commit()

        # Refresh with eager loading
        container_id = container.id
        self.db.expire(container)

        result = await self.db.execute(
            select(DrayageContainer)
            .where(DrayageContainer.id == container_id)
            .options(
                selectinload(DrayageContainer.steamship_line),
                selectinload(DrayageContainer.terminal),
                selectinload(DrayageContainer.appointments),
                selectinload(DrayageContainer.charges),
                selectinload(DrayageContainer.chassis_usages),
                selectinload(DrayageContainer.events),
            )
        )
        container_with_relations = result.scalars().unique().one()
        return container_with_relations

    async def update_container(
        self,
        company_id: str,
        container_id: str,
        payload: Dict[str, Any],
    ) -> DrayageContainer:
        """Update a container."""
        container = await self._get_container(company_id, container_id)

        # Update fields if provided
        for field, value in payload.items():
            if hasattr(container, field) and field not in ["id", "company_id", "created_at"]:
                setattr(container, field, value)

        await self.db.commit()

        # Refresh with eager loading
        result = await self.db.execute(
            select(DrayageContainer)
            .where(DrayageContainer.id == container_id)
            .options(
                selectinload(DrayageContainer.steamship_line),
                selectinload(DrayageContainer.terminal),
                selectinload(DrayageContainer.appointments),
                selectinload(DrayageContainer.charges),
                selectinload(DrayageContainer.chassis_usages),
                selectinload(DrayageContainer.events),
            )
        )
        container_with_relations = result.scalars().unique().one()
        return container_with_relations

    async def delete_container(self, company_id: str, container_id: str) -> None:
        """Delete a container."""
        container = await self._get_container(company_id, container_id)
        await self.db.delete(container)
        await self.db.commit()

    async def assign_container_to_load(
        self,
        company_id: str,
        container_id: str,
        load_id: str,
    ) -> DrayageContainer:
        """Assign a container to a load."""
        container = await self._get_container(company_id, container_id)
        container.load_id = load_id
        container.status = "DISPATCHED"
        await self.db.commit()

        # Refresh with eager loading
        result = await self.db.execute(
            select(DrayageContainer)
            .where(DrayageContainer.id == container_id)
            .options(
                selectinload(DrayageContainer.steamship_line),
                selectinload(DrayageContainer.terminal),
                selectinload(DrayageContainer.appointments),
                selectinload(DrayageContainer.charges),
                selectinload(DrayageContainer.chassis_usages),
                selectinload(DrayageContainer.events),
            )
        )
        container_with_relations = result.scalars().unique().one()
        return container_with_relations

    async def release_container(self, company_id: str, container_id: str) -> DrayageContainer:
        """Release a container from its current load."""
        container = await self._get_container(company_id, container_id)
        container.load_id = None
        container.status = "AVAILABLE"
        await self.db.commit()

        # Refresh with eager loading
        result = await self.db.execute(
            select(DrayageContainer)
            .where(DrayageContainer.id == container_id)
            .options(
                selectinload(DrayageContainer.steamship_line),
                selectinload(DrayageContainer.terminal),
                selectinload(DrayageContainer.appointments),
                selectinload(DrayageContainer.charges),
                selectinload(DrayageContainer.chassis_usages),
                selectinload(DrayageContainer.events),
            )
        )
        container_with_relations = result.scalars().unique().one()
        return container_with_relations

    async def update_container_status(
        self,
        company_id: str,
        container_id: str,
        status: str,
    ) -> DrayageContainer:
        """Update container status."""
        container = await self._get_container(company_id, container_id)
        container.status = status
        await self.db.commit()

        # Refresh with eager loading
        result = await self.db.execute(
            select(DrayageContainer)
            .where(DrayageContainer.id == container_id)
            .options(
                selectinload(DrayageContainer.steamship_line),
                selectinload(DrayageContainer.terminal),
                selectinload(DrayageContainer.appointments),
                selectinload(DrayageContainer.charges),
                selectinload(DrayageContainer.chassis_usages),
                selectinload(DrayageContainer.events),
            )
        )
        container_with_relations = result.scalars().unique().one()
        return container_with_relations

    async def _get_container(self, company_id: str, container_id: str) -> DrayageContainer:
        """Internal helper to get container with validation."""
        result = await self.db.execute(
            select(DrayageContainer).where(
                DrayageContainer.company_id == company_id,
                DrayageContainer.id == container_id,
            )
        )
        container = result.scalar_one_or_none()
        if not container:
            raise ValueError("Container not found")
        return container

    # ==================== CHASSIS POOL METHODS ====================

    async def list_chassis_pools(self, company_id: str) -> List[ChassisPool]:
        """List all chassis pools for a company."""
        result = await self.db.execute(
            select(ChassisPool)
            .where(ChassisPool.company_id == company_id)
            .options(selectinload(ChassisPool.chassis_usages))
            .order_by(ChassisPool.pool_code)
        )
        pools = result.scalars().unique().all()
        return list(pools)

    async def create_chassis_pool(self, company_id: str, payload: Dict[str, Any]) -> ChassisPool:
        """Create a new chassis pool."""
        # Check for duplicate pool code within company
        existing_pool = await self.db.execute(
            select(ChassisPool).where(
                ChassisPool.company_id == company_id,
                ChassisPool.pool_code == payload.get("pool_code"),
            )
        )
        if existing_pool.scalar_one_or_none():
            raise ValueError(f"Chassis pool with code '{payload.get('pool_code')}' already exists")

        pool = ChassisPool(
            id=str(uuid.uuid4()),
            company_id=company_id,
            pool_code=payload.get("pool_code"),
            name=payload.get("name"),
            provider_type=payload.get("provider_type"),
            api_base_url=payload.get("api_base_url"),
            api_credentials=payload.get("api_credentials"),
            api_status=payload.get("api_status", "not_configured"),
            per_diem_rate_20=payload.get("per_diem_rate_20"),
            per_diem_rate_40=payload.get("per_diem_rate_40"),
            per_diem_rate_45=payload.get("per_diem_rate_45"),
            per_diem_rate_reefer=payload.get("per_diem_rate_reefer"),
            free_days=payload.get("free_days", 1),
            split_free_time=payload.get("split_free_time", True),
            allowed_terminals=payload.get("allowed_terminals"),
            restricted_steamship_lines=payload.get("restricted_steamship_lines"),
            operating_regions=payload.get("operating_regions"),
            billing_contact_email=payload.get("billing_contact_email"),
            billing_portal_url=payload.get("billing_portal_url"),
            account_number=payload.get("account_number"),
            notes=payload.get("notes"),
            is_active=payload.get("is_active", True),
        )
        self.db.add(pool)
        await self.db.commit()

        # Refresh with eager loading
        pool_id = pool.id
        self.db.expire(pool)

        result = await self.db.execute(
            select(ChassisPool)
            .where(ChassisPool.id == pool_id)
            .options(selectinload(ChassisPool.chassis_usages))
        )
        pool_with_relations = result.scalars().unique().one()
        return pool_with_relations

    async def update_chassis_pool(
        self,
        company_id: str,
        pool_id: str,
        payload: Dict[str, Any],
    ) -> ChassisPool:
        """Update a chassis pool."""
        pool = await self._get_chassis_pool(company_id, pool_id)

        # Update fields if provided
        for field, value in payload.items():
            if hasattr(pool, field) and field not in ["id", "company_id", "created_at"]:
                setattr(pool, field, value)

        await self.db.commit()

        # Refresh with eager loading
        result = await self.db.execute(
            select(ChassisPool)
            .where(ChassisPool.id == pool_id)
            .options(selectinload(ChassisPool.chassis_usages))
        )
        pool_with_relations = result.scalars().unique().one()
        return pool_with_relations

    async def _get_chassis_pool(self, company_id: str, pool_id: str) -> ChassisPool:
        """Internal helper to get chassis pool with validation."""
        result = await self.db.execute(
            select(ChassisPool).where(
                ChassisPool.company_id == company_id,
                ChassisPool.id == pool_id,
            )
        )
        pool = result.scalar_one_or_none()
        if not pool:
            raise ValueError("Chassis pool not found")
        return pool

    # ==================== CHASSIS USAGE METHODS ====================

    async def list_active_chassis_usage(self, company_id: str) -> List[ChassisUsage]:
        """List all active chassis usage records for a company."""
        result = await self.db.execute(
            select(ChassisUsage)
            .where(
                ChassisUsage.company_id == company_id,
                ChassisUsage.status == "ACTIVE",
            )
            .options(
                selectinload(ChassisUsage.container),
                selectinload(ChassisUsage.chassis_pool),
            )
            .order_by(ChassisUsage.outgate_at.desc())
        )
        usages = result.scalars().unique().all()
        return list(usages)

    async def checkout_chassis(
        self,
        company_id: str,
        container_id: str,
        payload: Dict[str, Any],
    ) -> ChassisUsage:
        """Checkout a chassis for a container."""
        # Verify container exists
        container = await self._get_container(company_id, container_id)

        # Verify chassis pool exists
        chassis_pool = await self._get_chassis_pool(company_id, payload.get("chassis_pool_id"))

        usage = ChassisUsage(
            id=str(uuid.uuid4()),
            company_id=company_id,
            container_id=container.id,
            chassis_pool_id=chassis_pool.id,
            chassis_number=payload.get("chassis_number"),
            chassis_size=payload.get("chassis_size"),
            chassis_type=payload.get("chassis_type", "STANDARD"),
            outgate_terminal=payload.get("outgate_terminal"),
            outgate_at=payload.get("outgate_at", datetime.utcnow()),
            ingate_terminal=payload.get("ingate_terminal"),
            ingate_at=payload.get("ingate_at"),
            free_days=payload.get("free_days", chassis_pool.free_days),
            chargeable_days=payload.get("chargeable_days", 0),
            rate_per_day=payload.get("rate_per_day"),
            total_amount=payload.get("total_amount"),
            status=payload.get("status", "ACTIVE"),
            notes=payload.get("notes"),
        )
        self.db.add(usage)

        # Update container with chassis info
        container.chassis_number = payload.get("chassis_number")
        container.chassis_pool_id = chassis_pool.id
        container.chassis_pool_code = chassis_pool.pool_code
        container.chassis_outgate_at = payload.get("outgate_at", datetime.utcnow())

        await self.db.commit()

        # Refresh with eager loading
        usage_id = usage.id
        self.db.expire(usage)

        result = await self.db.execute(
            select(ChassisUsage)
            .where(ChassisUsage.id == usage_id)
            .options(
                selectinload(ChassisUsage.container),
                selectinload(ChassisUsage.chassis_pool),
            )
        )
        usage_with_relations = result.scalars().unique().one()
        return usage_with_relations

    async def return_chassis(
        self,
        company_id: str,
        usage_id: str,
        payload: Dict[str, Any],
    ) -> ChassisUsage:
        """Return a chassis, marking the usage as completed."""
        usage = await self._get_chassis_usage(company_id, usage_id)

        # Update usage record
        usage.ingate_terminal = payload.get("ingate_terminal")
        usage.ingate_at = payload.get("ingate_at", datetime.utcnow())
        usage.status = payload.get("status", "RETURNED")
        usage.chargeable_days = payload.get("chargeable_days", 0)
        usage.total_amount = payload.get("total_amount")
        if payload.get("notes"):
            usage.notes = payload.get("notes")

        # Update container with chassis return info
        container = await self._get_container(company_id, usage.container_id)
        container.chassis_return_at = payload.get("ingate_at", datetime.utcnow())

        await self.db.commit()

        # Refresh with eager loading
        result = await self.db.execute(
            select(ChassisUsage)
            .where(ChassisUsage.id == usage_id)
            .options(
                selectinload(ChassisUsage.container),
                selectinload(ChassisUsage.chassis_pool),
            )
        )
        usage_with_relations = result.scalars().unique().one()
        return usage_with_relations

    async def _get_chassis_usage(self, company_id: str, usage_id: str) -> ChassisUsage:
        """Internal helper to get chassis usage with validation."""
        result = await self.db.execute(
            select(ChassisUsage).where(
                ChassisUsage.company_id == company_id,
                ChassisUsage.id == usage_id,
            )
        )
        usage = result.scalar_one_or_none()
        if not usage:
            raise ValueError("Chassis usage not found")
        return usage

"""
Drayage API Routers.

Provides endpoints for container drayage operations including:
- Container lifecycle management
- Chassis pool configuration
- Chassis usage tracking
- Container lookup via port APIs
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.core.db import get_db
from app.models.drayage import (
    ChassisPool,
    ChassisUsage,
    DrayageContainer,
    DrayageEvent,
)
from app.routers.drayage.container_lookup import router as container_lookup_router

# Main router that combines all drayage routes
router = APIRouter()

# Include sub-routers
router.include_router(container_lookup_router)


# =============================================================================
# Dependency Functions
# =============================================================================


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    """Extract company_id from authenticated user."""
    return current_user.company_id


async def _db(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    """Get database session."""
    return db


# =============================================================================
# Helper Functions
# =============================================================================


def _container_to_dict(container: DrayageContainer) -> dict:
    """Convert container model to dictionary."""
    return {
        "id": container.id,
        "company_id": container.company_id,
        "load_id": container.load_id,
        "container_number": container.container_number,
        "container_size": container.container_size,
        "container_type": container.container_type,
        "is_hazmat": container.is_hazmat,
        "hazmat_class": container.hazmat_class,
        "is_overweight": container.is_overweight,
        "gross_weight_lbs": container.gross_weight_lbs,
        "booking_number": container.booking_number,
        "bill_of_lading": container.bill_of_lading,
        "house_bill": container.house_bill,
        "seal_number": container.seal_number,
        "reference_number": container.reference_number,
        "ssl_scac": container.ssl_scac,
        "port_code": container.port_code,
        "terminal_code": container.terminal_code,
        "vessel_name": container.vessel_name,
        "voyage_number": container.voyage_number,
        "vessel_eta": container.vessel_eta.isoformat() if container.vessel_eta else None,
        "vessel_ata": container.vessel_ata.isoformat() if container.vessel_ata else None,
        "status": container.status,
        "discharge_date": container.discharge_date.isoformat() if container.discharge_date else None,
        "last_free_day": container.last_free_day.isoformat() if container.last_free_day else None,
        "per_diem_start_date": container.per_diem_start_date.isoformat() if container.per_diem_start_date else None,
        "detention_start_date": container.detention_start_date.isoformat() if container.detention_start_date else None,
        "empty_return_by": container.empty_return_by.isoformat() if container.empty_return_by else None,
        "pickup_terminal_code": container.pickup_terminal_code,
        "pickup_scheduled_at": container.pickup_scheduled_at.isoformat() if container.pickup_scheduled_at else None,
        "pickup_actual_at": container.pickup_actual_at.isoformat() if container.pickup_actual_at else None,
        "outgate_at": container.outgate_at.isoformat() if container.outgate_at else None,
        "delivery_location": container.delivery_location,
        "delivery_appointment_at": container.delivery_appointment_at.isoformat() if container.delivery_appointment_at else None,
        "delivery_actual_at": container.delivery_actual_at.isoformat() if container.delivery_actual_at else None,
        "return_terminal_code": container.return_terminal_code,
        "return_scheduled_at": container.return_scheduled_at.isoformat() if container.return_scheduled_at else None,
        "return_actual_at": container.return_actual_at.isoformat() if container.return_actual_at else None,
        "ingate_at": container.ingate_at.isoformat() if container.ingate_at else None,
        "chassis_number": container.chassis_number,
        "chassis_pool_id": container.chassis_pool_id,
        "chassis_pool_code": container.chassis_pool_code,
        "chassis_outgate_at": container.chassis_outgate_at.isoformat() if container.chassis_outgate_at else None,
        "chassis_return_at": container.chassis_return_at.isoformat() if container.chassis_return_at else None,
        "holds": container.holds,
        "hold_notes": container.hold_notes,
        "demurrage_days": container.demurrage_days,
        "demurrage_amount": float(container.demurrage_amount) if container.demurrage_amount else None,
        "per_diem_days": container.per_diem_days,
        "per_diem_amount": float(container.per_diem_amount) if container.per_diem_amount else None,
        "detention_days": container.detention_days,
        "detention_amount": float(container.detention_amount) if container.detention_amount else None,
        "chassis_per_diem_amount": float(container.chassis_per_diem_amount) if container.chassis_per_diem_amount else None,
        "total_accessorial_charges": float(container.total_accessorial_charges) if container.total_accessorial_charges else None,
        "notes": container.notes,
        "metadata_json": container.metadata_json,
        "created_at": container.created_at.isoformat(),
        "updated_at": container.updated_at.isoformat(),
    }


def _chassis_pool_to_dict(pool: ChassisPool) -> dict:
    """Convert chassis pool model to dictionary."""
    return {
        "id": pool.id,
        "company_id": pool.company_id,
        "pool_code": pool.pool_code,
        "name": pool.name,
        "provider_type": pool.provider_type,
        "api_base_url": pool.api_base_url,
        "api_status": pool.api_status,
        "per_diem_rate_20": float(pool.per_diem_rate_20) if pool.per_diem_rate_20 else None,
        "per_diem_rate_40": float(pool.per_diem_rate_40) if pool.per_diem_rate_40 else None,
        "per_diem_rate_45": float(pool.per_diem_rate_45) if pool.per_diem_rate_45 else None,
        "per_diem_rate_reefer": float(pool.per_diem_rate_reefer) if pool.per_diem_rate_reefer else None,
        "free_days": pool.free_days,
        "split_free_time": pool.split_free_time,
        "allowed_terminals": pool.allowed_terminals,
        "restricted_steamship_lines": pool.restricted_steamship_lines,
        "operating_regions": pool.operating_regions,
        "billing_contact_email": pool.billing_contact_email,
        "billing_portal_url": pool.billing_portal_url,
        "account_number": pool.account_number,
        "notes": pool.notes,
        "is_active": pool.is_active,
        "created_at": pool.created_at.isoformat(),
        "updated_at": pool.updated_at.isoformat(),
    }


def _chassis_usage_to_dict(usage: ChassisUsage) -> dict:
    """Convert chassis usage model to dictionary."""
    return {
        "id": usage.id,
        "company_id": usage.company_id,
        "container_id": usage.container_id,
        "chassis_pool_id": usage.chassis_pool_id,
        "chassis_number": usage.chassis_number,
        "chassis_size": usage.chassis_size,
        "chassis_type": usage.chassis_type,
        "outgate_terminal": usage.outgate_terminal,
        "outgate_at": usage.outgate_at.isoformat(),
        "ingate_terminal": usage.ingate_terminal,
        "ingate_at": usage.ingate_at.isoformat() if usage.ingate_at else None,
        "free_days": usage.free_days,
        "chargeable_days": usage.chargeable_days,
        "rate_per_day": float(usage.rate_per_day) if usage.rate_per_day else None,
        "total_amount": float(usage.total_amount) if usage.total_amount else None,
        "status": usage.status,
        "notes": usage.notes,
        "created_at": usage.created_at.isoformat(),
        "updated_at": usage.updated_at.isoformat(),
    }


# =============================================================================
# Container Endpoints
# =============================================================================


@router.get("/containers", summary="List all containers")
async def list_containers(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
    status_filter: Optional[str] = None,
    ssl_scac: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """List containers for the company with optional filtering."""
    query = (
        select(DrayageContainer)
        .where(DrayageContainer.company_id == company_id)
        .options(
            selectinload(DrayageContainer.steamship_line),
            selectinload(DrayageContainer.terminal),
            selectinload(DrayageContainer.appointments),
            selectinload(DrayageContainer.chassis_usages),
            selectinload(DrayageContainer.charges),
        )
        .order_by(DrayageContainer.created_at.desc())
    )

    if status_filter:
        query = query.where(DrayageContainer.status == status_filter)
    if ssl_scac:
        query = query.where(DrayageContainer.ssl_scac == ssl_scac)

    count_query = select(DrayageContainer).where(DrayageContainer.company_id == company_id)
    if status_filter:
        count_query = count_query.where(DrayageContainer.status == status_filter)
    if ssl_scac:
        count_query = count_query.where(DrayageContainer.ssl_scac == ssl_scac)

    total_result = await db.execute(select(func.count()).select_from(count_query.subquery()))
    total = total_result.scalar_one()

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    containers = result.scalars().unique().all()

    return {
        "containers": [_container_to_dict(c) for c in containers],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/containers", status_code=status.HTTP_201_CREATED, summary="Create container")
async def create_container(
    payload: dict,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> dict:
    """Create a new drayage container."""
    existing = await db.execute(
        select(DrayageContainer).where(
            DrayageContainer.company_id == company_id,
            DrayageContainer.container_number == payload.get("container_number"),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Container {payload.get('container_number')} already exists",
        )

    container = DrayageContainer(
        id=str(uuid4()),
        company_id=company_id,
        container_number=payload.get("container_number"),
        container_size=payload.get("container_size"),
        container_type=payload.get("container_type"),
        status=payload.get("status", "BOOKING"),
        booking_number=payload.get("booking_number"),
        bill_of_lading=payload.get("bill_of_lading"),
        house_bill=payload.get("house_bill"),
        seal_number=payload.get("seal_number"),
        reference_number=payload.get("reference_number"),
        ssl_scac=payload.get("ssl_scac"),
        port_code=payload.get("port_code"),
        terminal_code=payload.get("terminal_code"),
        vessel_name=payload.get("vessel_name"),
        voyage_number=payload.get("voyage_number"),
        is_hazmat=payload.get("is_hazmat", False),
        hazmat_class=payload.get("hazmat_class"),
        is_overweight=payload.get("is_overweight", False),
        gross_weight_lbs=payload.get("gross_weight_lbs"),
        notes=payload.get("notes"),
    )

    if payload.get("vessel_eta"):
        container.vessel_eta = datetime.fromisoformat(payload["vessel_eta"].replace("Z", "+00:00"))
    if payload.get("last_free_day"):
        container.last_free_day = datetime.fromisoformat(payload["last_free_day"].replace("Z", "+00:00"))
    if payload.get("discharge_date"):
        container.discharge_date = datetime.fromisoformat(payload["discharge_date"].replace("Z", "+00:00"))

    db.add(container)
    await db.commit()
    await db.refresh(container)

    return _container_to_dict(container)


@router.get("/containers/{container_id}", summary="Get container details")
async def get_container(
    container_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> dict:
    """Get detailed information about a specific container."""
    result = await db.execute(
        select(DrayageContainer)
        .where(
            DrayageContainer.id == container_id,
            DrayageContainer.company_id == company_id,
        )
        .options(
            selectinload(DrayageContainer.steamship_line),
            selectinload(DrayageContainer.terminal),
            selectinload(DrayageContainer.appointments),
            selectinload(DrayageContainer.chassis_usages),
            selectinload(DrayageContainer.charges),
            selectinload(DrayageContainer.events),
        )
    )
    container = result.scalar_one_or_none()

    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    return _container_to_dict(container)


@router.put("/containers/{container_id}", summary="Update container")
async def update_container(
    container_id: str,
    payload: dict,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> dict:
    """Update container details."""
    result = await db.execute(
        select(DrayageContainer).where(
            DrayageContainer.id == container_id,
            DrayageContainer.company_id == company_id,
        )
    )
    container = result.scalar_one_or_none()

    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    updateable_fields = [
        "container_number", "container_size", "container_type", "is_hazmat",
        "hazmat_class", "is_overweight", "gross_weight_lbs", "booking_number",
        "bill_of_lading", "house_bill", "seal_number", "reference_number",
        "ssl_scac", "port_code", "terminal_code", "vessel_name", "voyage_number",
        "status", "notes", "chassis_number", "chassis_pool_code",
        "pickup_terminal_code", "return_terminal_code", "delivery_location",
    ]

    for field in updateable_fields:
        if field in payload:
            setattr(container, field, payload[field])

    datetime_fields = [
        "vessel_eta", "vessel_ata", "discharge_date", "last_free_day",
        "per_diem_start_date", "detention_start_date", "empty_return_by",
        "pickup_scheduled_at", "pickup_actual_at", "outgate_at",
        "delivery_appointment_at", "delivery_actual_at",
        "return_scheduled_at", "return_actual_at", "ingate_at",
        "chassis_outgate_at", "chassis_return_at",
    ]

    for field in datetime_fields:
        if field in payload and payload[field]:
            setattr(
                container,
                field,
                datetime.fromisoformat(payload[field].replace("Z", "+00:00")),
            )

    if "holds" in payload:
        container.holds = payload["holds"]
    if "metadata_json" in payload:
        container.metadata_json = payload["metadata_json"]

    await db.commit()
    await db.refresh(container)

    return _container_to_dict(container)


@router.delete("/containers/{container_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete container")
async def delete_container(
    container_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> None:
    """Delete a container."""
    result = await db.execute(
        select(DrayageContainer).where(
            DrayageContainer.id == container_id,
            DrayageContainer.company_id == company_id,
        )
    )
    container = result.scalar_one_or_none()

    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    await db.delete(container)
    await db.commit()


# =============================================================================
# Chassis Pool Endpoints
# =============================================================================


@router.get("/chassis-pools", summary="List chassis pools")
async def list_chassis_pools(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
    is_active: Optional[bool] = None,
) -> List[dict]:
    """List all chassis pools for the company."""
    query = select(ChassisPool).where(ChassisPool.company_id == company_id)

    if is_active is not None:
        query = query.where(ChassisPool.is_active == is_active)

    query = query.order_by(ChassisPool.name)

    result = await db.execute(query)
    pools = result.scalars().all()

    return [_chassis_pool_to_dict(pool) for pool in pools]


@router.post("/chassis-pools", status_code=status.HTTP_201_CREATED, summary="Create chassis pool")
async def create_chassis_pool(
    payload: dict,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> dict:
    """Create a new chassis pool."""
    existing = await db.execute(
        select(ChassisPool).where(
            ChassisPool.company_id == company_id,
            ChassisPool.pool_code == payload.get("pool_code"),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chassis pool {payload.get('pool_code')} already exists",
        )

    pool = ChassisPool(
        id=str(uuid4()),
        company_id=company_id,
        pool_code=payload.get("pool_code"),
        name=payload.get("pool_name", payload.get("name")),
        provider_type=payload.get("provider_type"),
        per_diem_rate_20=payload.get("per_diem_rate_20"),
        per_diem_rate_40=payload.get("per_diem_rate_40"),
        per_diem_rate_45=payload.get("per_diem_rate_45"),
        per_diem_rate_reefer=payload.get("per_diem_rate_reefer"),
        free_days=payload.get("free_days", 1),
        split_free_time=payload.get("split_free_time", True),
        account_number=payload.get("account_number"),
        billing_contact_email=payload.get("billing_contact"),
        billing_portal_url=payload.get("billing_portal_url"),
        notes=payload.get("notes"),
        is_active=payload.get("is_active", True),
    )

    db.add(pool)
    await db.commit()
    await db.refresh(pool)

    return _chassis_pool_to_dict(pool)


@router.put("/chassis-pools/{pool_id}", summary="Update chassis pool")
async def update_chassis_pool(
    pool_id: str,
    payload: dict,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> dict:
    """Update chassis pool configuration."""
    result = await db.execute(
        select(ChassisPool).where(
            ChassisPool.id == pool_id,
            ChassisPool.company_id == company_id,
        )
    )
    pool = result.scalar_one_or_none()

    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chassis pool {pool_id} not found",
        )

    updateable_fields = [
        "pool_code", "provider_type", "per_diem_rate_20",
        "per_diem_rate_40", "per_diem_rate_45", "per_diem_rate_reefer",
        "free_days", "split_free_time", "account_number",
        "billing_portal_url", "api_base_url", "api_status", "notes", "is_active",
    ]

    for field in updateable_fields:
        if field in payload:
            setattr(pool, field, payload[field])

    if "pool_name" in payload:
        pool.name = payload["pool_name"]
    if "name" in payload:
        pool.name = payload["name"]
    if "billing_contact" in payload:
        pool.billing_contact_email = payload["billing_contact"]

    await db.commit()
    await db.refresh(pool)

    return _chassis_pool_to_dict(pool)


@router.delete("/chassis-pools/{pool_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete chassis pool")
async def delete_chassis_pool(
    pool_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> None:
    """Delete a chassis pool."""
    result = await db.execute(
        select(ChassisPool).where(
            ChassisPool.id == pool_id,
            ChassisPool.company_id == company_id,
        )
    )
    pool = result.scalar_one_or_none()

    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chassis pool {pool_id} not found",
        )

    usage_result = await db.execute(
        select(ChassisUsage).where(
            ChassisUsage.chassis_pool_id == pool_id,
            ChassisUsage.status == "ACTIVE",
        )
    )
    active_usage = usage_result.first()

    if active_usage:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete pool with active chassis usage",
        )

    await db.delete(pool)
    await db.commit()


# =============================================================================
# Chassis Usage Endpoints
# =============================================================================


@router.get("/chassis-usage", summary="List active chassis usage")
async def list_chassis_usage(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
    status_filter: Optional[str] = None,
    chassis_pool_id: Optional[str] = None,
) -> List[dict]:
    """List chassis usage records."""
    query = (
        select(ChassisUsage)
        .where(ChassisUsage.company_id == company_id)
        .options(
            selectinload(ChassisUsage.container),
            selectinload(ChassisUsage.chassis_pool),
        )
        .order_by(ChassisUsage.outgate_at.desc())
    )

    if status_filter:
        query = query.where(ChassisUsage.status == status_filter)

    if chassis_pool_id:
        query = query.where(ChassisUsage.chassis_pool_id == chassis_pool_id)

    result = await db.execute(query)
    usage_records = result.scalars().unique().all()

    return [_chassis_usage_to_dict(usage) for usage in usage_records]


@router.post("/chassis-usage/{usage_id}/return", summary="Return chassis")
async def return_chassis(
    usage_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> dict:
    """Return chassis and calculate charges."""
    result = await db.execute(
        select(ChassisUsage)
        .where(
            ChassisUsage.id == usage_id,
            ChassisUsage.company_id == company_id,
        )
        .options(selectinload(ChassisUsage.container))
    )
    usage = result.scalar_one_or_none()

    if not usage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chassis usage {usage_id} not found",
        )

    if usage.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chassis usage is already {usage.status}",
        )

    ingate_at = datetime.utcnow()
    usage.ingate_at = ingate_at
    usage.status = "RETURNED"

    total_days = (ingate_at - usage.outgate_at).days
    chargeable_days = max(0, total_days - usage.free_days)
    usage.chargeable_days = chargeable_days

    if usage.rate_per_day and chargeable_days > 0:
        usage.total_amount = float(usage.rate_per_day) * chargeable_days

    if usage.container:
        usage.container.chassis_return_at = ingate_at

    await db.commit()
    await db.refresh(usage)

    return _chassis_usage_to_dict(usage)


__all__ = ["router", "container_lookup_router"]

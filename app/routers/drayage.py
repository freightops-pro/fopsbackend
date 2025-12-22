"""
Drayage API Router.

Provides endpoints for container drayage operations including:
- Container lifecycle management
- Chassis pool configuration
- Chassis usage tracking
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.core.db import get_db
from app.models.drayage import (
    ChassisPool,
    ChassisUsage,
    DrayageContainer,
)

router = APIRouter()


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
    """
    List containers for the company with optional filtering.

    Query Parameters:
    - status_filter: Filter by container status (BOOKING, RELEASED, AVAILABLE, etc.)
    - ssl_scac: Filter by steamship line SCAC code
    - limit: Maximum number of results (default 100)
    - offset: Number of results to skip (default 0)
    """
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

    # Get total count
    count_query = select(DrayageContainer).where(DrayageContainer.company_id == company_id)
    if status_filter:
        count_query = count_query.where(DrayageContainer.status == status_filter)
    if ssl_scac:
        count_query = count_query.where(DrayageContainer.ssl_scac == ssl_scac)

    from sqlalchemy import func
    total_result = await db.execute(select(func.count()).select_from(count_query.subquery()))
    total = total_result.scalar_one()

    # Apply pagination
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
    """
    Create a new drayage container.

    Required fields:
    - container_number: Container number (e.g., MSCU1234567)
    - container_size: Size (20, 40, 40HC, 45)
    - container_type: Type (DRY, REEFER, FLAT, TANK)

    Optional fields:
    - booking_number: Booking reference
    - bill_of_lading: BOL number
    - ssl_scac: Steamship line SCAC code
    - terminal_code: Terminal code
    - vessel_name: Vessel name
    - vessel_eta: Vessel ETA (ISO datetime)
    - last_free_day: Last free day (ISO datetime)
    - and many more...
    """
    # Check for duplicate container number
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

    # Create container
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

    # Handle datetime fields
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
    """
    Update container details.

    Supports updating any container field except id, company_id, and created_at.
    """
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

    # Update fields
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

    # Handle datetime fields
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

    # Handle JSON fields
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
    """
    Delete a container.

    Note: This will also delete all related appointments, charges, and events.
    """
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


@router.post("/containers/{container_id}/assign-load", summary="Assign container to load")
async def assign_container_to_load(
    container_id: str,
    payload: dict,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> dict:
    """
    Assign container to a load for dispatch.

    Required fields:
    - load_id: Load ID to assign to
    """
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

    load_id = payload.get("load_id")
    if not load_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="load_id is required",
        )

    # Verify load exists and belongs to company
    from app.models.load import Load
    load_result = await db.execute(
        select(Load).where(Load.id == load_id, Load.company_id == company_id)
    )
    load = load_result.scalar_one_or_none()

    if not load:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Load {load_id} not found",
        )

    container.load_id = load_id
    if container.status == "AVAILABLE":
        container.status = "DISPATCHED"

    await db.commit()
    await db.refresh(container)

    return _container_to_dict(container)


@router.post("/containers/{container_id}/release", summary="Release container from load")
async def release_container_from_load(
    container_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> dict:
    """
    Release container from assigned load.

    Sets load_id to null and updates status back to AVAILABLE.
    """
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

    container.load_id = None
    if container.status == "DISPATCHED":
        container.status = "AVAILABLE"

    await db.commit()
    await db.refresh(container)

    return _container_to_dict(container)


@router.post("/containers/{container_id}/update-status", summary="Update container status")
async def update_container_status(
    container_id: str,
    payload: dict,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> dict:
    """
    Update container status.

    Required fields:
    - status: New status (BOOKING, RELEASED, AVAILABLE, DISPATCHED, PICKED_UP,
              IN_TRANSIT, DELIVERED, EMPTY, RETURNED, CANCELLED)

    Optional fields:
    - notes: Status change notes
    - create_event: Whether to create a status change event (default: true)
    """
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

    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status is required",
        )

    valid_statuses = [
        "BOOKING", "RELEASED", "AVAILABLE", "HOLD", "DISPATCHED",
        "PICKED_UP", "IN_TRANSIT", "DELIVERED", "EMPTY", "RETURNED", "CANCELLED"
    ]

    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
        )

    old_status = container.status
    container.status = new_status

    # Create event if requested
    if payload.get("create_event", True):
        from app.models.drayage import DrayageEvent

        event = DrayageEvent(
            id=str(uuid4()),
            company_id=company_id,
            container_id=container_id,
            event_type="STATUS_CHANGE",
            event_at=datetime.utcnow(),
            description=f"Status changed from {old_status} to {new_status}",
            source="SYSTEM",
            metadata_json={
                "old_status": old_status,
                "new_status": new_status,
                "notes": payload.get("notes"),
            },
        )
        db.add(event)

    await db.commit()
    await db.refresh(container)

    return _container_to_dict(container)


# =============================================================================
# Chassis Pool Endpoints
# =============================================================================


@router.get("/chassis-pools", summary="List chassis pools")
async def list_chassis_pools(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
    is_active: Optional[bool] = None,
) -> List[dict]:
    """
    List all chassis pools for the company.

    Query Parameters:
    - is_active: Filter by active status (default: all pools)
    """
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
    """
    Create a new chassis pool.

    Required fields:
    - pool_code: Pool code (e.g., DCLI, TRAC, FLXV)
    - name: Pool name
    - provider_type: Provider type (pool, private, ssl_provided)

    Optional fields:
    - per_diem_rate_20: Per diem rate for 20' chassis
    - per_diem_rate_40: Per diem rate for 40' chassis
    - per_diem_rate_45: Per diem rate for 45' chassis
    - per_diem_rate_reefer: Per diem rate for reefer chassis
    - free_days: Free days (default: 1)
    - split_free_time: Whether free time is split (default: true)
    - account_number: Account number with pool
    - and more...
    """
    # Check for duplicate pool code
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
        name=payload.get("name"),
        provider_type=payload.get("provider_type"),
        per_diem_rate_20=payload.get("per_diem_rate_20"),
        per_diem_rate_40=payload.get("per_diem_rate_40"),
        per_diem_rate_45=payload.get("per_diem_rate_45"),
        per_diem_rate_reefer=payload.get("per_diem_rate_reefer"),
        free_days=payload.get("free_days", 1),
        split_free_time=payload.get("split_free_time", True),
        account_number=payload.get("account_number"),
        billing_contact_email=payload.get("billing_contact_email"),
        billing_portal_url=payload.get("billing_portal_url"),
        notes=payload.get("notes"),
        is_active=payload.get("is_active", True),
    )

    # Handle JSON fields
    if "allowed_terminals" in payload:
        pool.allowed_terminals = payload["allowed_terminals"]
    if "restricted_steamship_lines" in payload:
        pool.restricted_steamship_lines = payload["restricted_steamship_lines"]
    if "operating_regions" in payload:
        pool.operating_regions = payload["operating_regions"]
    if "api_credentials" in payload:
        pool.api_credentials = payload["api_credentials"]

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

    # Update fields
    updateable_fields = [
        "pool_code", "name", "provider_type", "per_diem_rate_20",
        "per_diem_rate_40", "per_diem_rate_45", "per_diem_rate_reefer",
        "free_days", "split_free_time", "account_number",
        "billing_contact_email", "billing_portal_url", "api_base_url",
        "api_status", "notes", "is_active",
    ]

    for field in updateable_fields:
        if field in payload:
            setattr(pool, field, payload[field])

    # Handle JSON fields
    if "allowed_terminals" in payload:
        pool.allowed_terminals = payload["allowed_terminals"]
    if "restricted_steamship_lines" in payload:
        pool.restricted_steamship_lines = payload["restricted_steamship_lines"]
    if "operating_regions" in payload:
        pool.operating_regions = payload["operating_regions"]
    if "api_credentials" in payload:
        pool.api_credentials = payload["api_credentials"]

    await db.commit()
    await db.refresh(pool)

    return _chassis_pool_to_dict(pool)


@router.delete("/chassis-pools/{pool_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete chassis pool")
async def delete_chassis_pool(
    pool_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> None:
    """
    Delete a chassis pool.

    Note: Pool must have no active chassis usage records.
    """
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

    # Check for active chassis usage
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
    """
    List chassis usage records.

    Query Parameters:
    - status_filter: Filter by status (ACTIVE, RETURNED, INVOICED)
    - chassis_pool_id: Filter by chassis pool
    """
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


@router.post("/containers/{container_id}/checkout-chassis", status_code=status.HTTP_201_CREATED, summary="Checkout chassis")
async def checkout_chassis(
    container_id: str,
    payload: dict,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> dict:
    """
    Checkout chassis for a container.

    Required fields:
    - chassis_number: Chassis number
    - chassis_pool_id: Chassis pool ID
    - chassis_size: Chassis size (20, 40, 45)
    - chassis_type: Chassis type (STANDARD, EXTENDABLE, REEFER, FLATBED)

    Optional fields:
    - outgate_terminal: Terminal where chassis was picked up
    - outgate_at: Checkout datetime (defaults to now)
    """
    # Verify container exists
    container_result = await db.execute(
        select(DrayageContainer).where(
            DrayageContainer.id == container_id,
            DrayageContainer.company_id == company_id,
        )
    )
    container = container_result.scalar_one_or_none()

    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found",
        )

    # Verify chassis pool exists
    pool_id = payload.get("chassis_pool_id")
    pool_result = await db.execute(
        select(ChassisPool).where(
            ChassisPool.id == pool_id,
            ChassisPool.company_id == company_id,
        )
    )
    pool = pool_result.scalar_one_or_none()

    if not pool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chassis pool {pool_id} not found",
        )

    # Check if chassis is already checked out
    chassis_number = payload.get("chassis_number")
    existing_result = await db.execute(
        select(ChassisUsage).where(
            ChassisUsage.chassis_number == chassis_number,
            ChassisUsage.status == "ACTIVE",
        )
    )
    existing_usage = existing_result.scalar_one_or_none()

    if existing_usage:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chassis {chassis_number} is already checked out",
        )

    # Create chassis usage record
    outgate_at = payload.get("outgate_at")
    if outgate_at:
        outgate_at = datetime.fromisoformat(outgate_at.replace("Z", "+00:00"))
    else:
        outgate_at = datetime.utcnow()

    usage = ChassisUsage(
        id=str(uuid4()),
        company_id=company_id,
        container_id=container_id,
        chassis_pool_id=pool_id,
        chassis_number=chassis_number,
        chassis_size=payload.get("chassis_size"),
        chassis_type=payload.get("chassis_type"),
        outgate_terminal=payload.get("outgate_terminal"),
        outgate_at=outgate_at,
        free_days=pool.free_days,
        status="ACTIVE",
        notes=payload.get("notes"),
    )

    # Determine per diem rate based on chassis size
    size = payload.get("chassis_size")
    if size == "20":
        usage.rate_per_day = pool.per_diem_rate_20
    elif size == "40":
        usage.rate_per_day = pool.per_diem_rate_40
    elif size == "45":
        usage.rate_per_day = pool.per_diem_rate_45
    elif payload.get("chassis_type") == "REEFER":
        usage.rate_per_day = pool.per_diem_rate_reefer

    # Update container with chassis info
    container.chassis_number = chassis_number
    container.chassis_pool_id = pool_id
    container.chassis_pool_code = pool.pool_code
    container.chassis_outgate_at = outgate_at

    db.add(usage)
    await db.commit()
    await db.refresh(usage)

    return _chassis_usage_to_dict(usage)


@router.post("/chassis-usage/{usage_id}/return", summary="Return chassis")
async def return_chassis(
    usage_id: str,
    payload: dict,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(_db),
) -> dict:
    """
    Return chassis and calculate charges.

    Optional fields:
    - ingate_terminal: Terminal where chassis was returned
    - ingate_at: Return datetime (defaults to now)
    """
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

    # Set return information
    ingate_at = payload.get("ingate_at")
    if ingate_at:
        ingate_at = datetime.fromisoformat(ingate_at.replace("Z", "+00:00"))
    else:
        ingate_at = datetime.utcnow()

    usage.ingate_at = ingate_at
    usage.ingate_terminal = payload.get("ingate_terminal")
    usage.status = "RETURNED"

    # Calculate chargeable days
    total_days = (ingate_at - usage.outgate_at).days
    chargeable_days = max(0, total_days - usage.free_days)
    usage.chargeable_days = chargeable_days

    # Calculate total amount
    if usage.rate_per_day and chargeable_days > 0:
        usage.total_amount = float(usage.rate_per_day) * chargeable_days

    # Update container
    if usage.container:
        usage.container.chassis_return_at = ingate_at

    await db.commit()
    await db.refresh(usage)

    return _chassis_usage_to_dict(usage)


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

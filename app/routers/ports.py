from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.port import (
    ContainerEventHistory,
    ContainerTrackingEventSchema,
    ContainerTrackingHistoryResponse,
    ContainerTrackingRequest,
    ContainerTrackingResponse,
    PortIntegrationCreate,
    PortIntegrationResponse,
    PortIntegrationUpdate,
    PortInfo,
    PortListResponse,
)
from app.services.port.port_service import PortService

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> PortService:
    return PortService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


@router.get("/available", response_model=PortListResponse)
async def list_available_ports(service: PortService = Depends(_service)) -> PortListResponse:
    """List all available ports."""
    try:
        ports = await service.list_available_ports()
        port_infos = []
        for port in ports:
            try:
                port_info = PortInfo.model_validate(port)
                port_infos.append(port_info)
            except Exception as e:
                # Log but don't fail - skip invalid ports
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to validate port {port.id}: {e}")
                continue
        return PortListResponse(ports=port_infos)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error listing ports: {e}", exc_info=True)
        # Return empty list instead of failing
        return PortListResponse(ports=[])


@router.get("/integrations", response_model=List[PortIntegrationResponse])
async def list_port_integrations(
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> List[PortIntegrationResponse]:
    """List company port integrations."""
    integrations = await service.get_company_port_integrations(company_id)
    return [PortIntegrationResponse.model_validate(integration) for integration in integrations]


@router.post("/integrations", response_model=PortIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_port_integration(
    payload: PortIntegrationCreate,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
    service: PortService = Depends(_service),
) -> PortIntegrationResponse:
    """Create a new port integration."""
    import uuid
    from sqlalchemy import select
    from app.models.port import Port, PortIntegration

    # Verify port exists
    port_result = await db.execute(select(Port).where(Port.id == payload.port_id))
    port = port_result.scalar_one_or_none()
    if not port:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Port not found")

    # Create integration
    integration = PortIntegration(
        id=str(uuid.uuid4()),
        company_id=company_id,
        port_id=payload.port_id,
        credentials_json=payload.credentials,
        config_json=payload.config,
        status="pending",
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    return PortIntegrationResponse.model_validate(integration)


@router.patch("/integrations/{integration_id}", response_model=PortIntegrationResponse)
async def update_port_integration(
    integration_id: str,
    payload: PortIntegrationUpdate,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> PortIntegrationResponse:
    """Update a port integration."""
    from sqlalchemy import select
    from app.models.port import PortIntegration

    result = await db.execute(
        select(PortIntegration).where(
            PortIntegration.id == integration_id,
            PortIntegration.company_id == company_id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    # Update fields
    if payload.credentials is not None:
        integration.credentials_json = payload.credentials
    if payload.config is not None:
        integration.config_json = payload.config
    if payload.status is not None:
        integration.status = payload.status
    if payload.auto_sync is not None:
        integration.auto_sync = "true" if payload.auto_sync else "false"
    if payload.sync_interval_minutes is not None:
        integration.sync_interval_minutes = payload.sync_interval_minutes

    await db.commit()
    await db.refresh(integration)

    return PortIntegrationResponse.model_validate(integration)


@router.delete("/integrations/{integration_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_port_integration(
    integration_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a port integration."""
    from sqlalchemy import delete, select
    from app.models.port import PortIntegration

    result = await db.execute(
        select(PortIntegration).where(
            PortIntegration.id == integration_id,
            PortIntegration.company_id == company_id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    await db.execute(delete(PortIntegration).where(PortIntegration.id == integration_id))
    await db.commit()


@router.post("/operations/track-container", response_model=ContainerTrackingResponse)
async def track_container(
    payload: ContainerTrackingRequest,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> ContainerTrackingResponse:
    """Track a container at a port."""
    try:
        return await service.track_container(
            company_id=company_id,
            container_number=payload.container_number,
            port_code=payload.port_code,
            load_id=payload.load_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error tracking container: {str(e)}",
        )


@router.get("/containers/{container_number}/history", response_model=ContainerTrackingHistoryResponse)
async def get_container_history(
    container_number: str,
    port_code: str | None = None,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> ContainerTrackingHistoryResponse:
    """Get container tracking history."""
    from app.models.port import ContainerTrackingEvent
    from sqlalchemy import select

    tracking_records = await service.get_container_tracking_history(
        company_id=company_id,
        container_number=container_number,
        port_code=port_code,
    )

    if not tracking_records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container tracking not found")

    # Get all events for these tracking records
    tracking_ids = [record.id for record in tracking_records]
    db = service.db
    result = await db.execute(
        select(ContainerTrackingEvent)
        .where(ContainerTrackingEvent.container_tracking_id.in_(tracking_ids))
        .order_by(ContainerTrackingEvent.event_timestamp.desc())
    )
    events = list(result.scalars().all())

    # Get current status from most recent tracking
    current_tracking = tracking_records[0] if tracking_records else None

    return ContainerTrackingHistoryResponse(
        container_number=container_number,
        port_code=current_tracking.port_code if current_tracking else port_code or "",
        current_status=current_tracking.status if current_tracking else "UNKNOWN",
        tracking_records=[
            ContainerTrackingResponse(
                container_number=record.container_number,
                port_code=record.port_code,
                terminal=record.terminal,
                status=record.status,
                location=record.location,
                vessel=record.vessel,
                dates=record.dates,
                container_details=record.container_details,
                holds=record.holds or [],
                charges=record.charges,
                last_updated_at=record.last_updated_at,
                tracking_id=record.id,
                load_id=record.load_id,
            )
            for record in tracking_records
        ],
        events=[ContainerTrackingEventSchema.model_validate(event) for event in events],
        load_id=current_tracking.load_id if current_tracking else None,
    )


@router.get("/containers/{container_number}/events", response_model=ContainerEventHistory)
async def get_container_events(
    container_number: str,
    port_code: str | None = None,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> ContainerEventHistory:
    """Get container event history."""
    from app.models.port import ContainerTracking, ContainerTrackingEvent
    from sqlalchemy import select

    # Get tracking records
    tracking_records = await service.get_container_tracking_history(
        company_id=company_id,
        container_number=container_number,
        port_code=port_code,
    )

    if not tracking_records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container tracking not found")

    # Get all events
    tracking_ids = [record.id for record in tracking_records]
    db = service.db
    result = await db.execute(
        select(ContainerTrackingEvent)
        .where(ContainerTrackingEvent.container_tracking_id.in_(tracking_ids))
        .order_by(ContainerTrackingEvent.event_timestamp.desc())
    )
    events = list(result.scalars().all())

    return ContainerEventHistory(
        container_number=container_number,
        events=[ContainerTrackingEventSchema.model_validate(event) for event in events],
        total_events=len(events),
    )


@router.get("/loads/{load_id}/container-tracking", response_model=ContainerTrackingResponse)
async def get_load_container_tracking(
    load_id: str,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> ContainerTrackingResponse:
    """Get container tracking for a specific load."""
    tracking = await service.get_load_container_tracking(company_id=company_id, load_id=load_id)

    if not tracking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container tracking not found for this load")

    return ContainerTrackingResponse(
        container_number=tracking.container_number,
        port_code=tracking.port_code,
        terminal=tracking.terminal,
        status=tracking.status,
        location=tracking.location,
        vessel=tracking.vessel,
        dates=tracking.dates,
        container_details=tracking.container_details,
        holds=tracking.holds or [],
        charges=tracking.charges,
        last_updated_at=tracking.last_updated_at,
        tracking_id=tracking.id,
        load_id=tracking.load_id,
    )


# ==================== VESSEL OPERATIONS ====================


@router.get("/operations/vessel-schedule")
async def get_vessel_schedule(
    port_code: str,
    vessel_name: str | None = None,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> List[dict]:
    """Get vessel schedule for a port. Works with any port that supports vessel schedules."""
    try:
        return await service.get_vessel_schedule(
            company_id=company_id,
            port_code=port_code,
            vessel_name=vessel_name,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting vessel schedule: {str(e)}",
        )


@router.get("/operations/active-vessels")
async def get_active_vessels(
    port_code: str,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> List[dict]:
    """Get active vessel visits at a port."""
    try:
        return await service.get_active_vessel_visits(
            company_id=company_id,
            port_code=port_code,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting active vessels: {str(e)}",
        )


# ==================== APPOINTMENT OPERATIONS ====================


@router.get("/operations/appointments")
async def get_gate_appointments(
    port_code: str,
    container_number: str | None = None,
    appointment_date: str | None = None,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> List[dict]:
    """Get gate appointments. Works with any port that supports appointments."""
    try:
        from datetime import datetime
        appt_date = datetime.fromisoformat(appointment_date) if appointment_date else None
        return await service.get_gate_appointments(
            company_id=company_id,
            port_code=port_code,
            container_number=container_number,
            appointment_date=appt_date,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting appointments: {str(e)}",
        )


@router.post("/operations/appointments")
async def create_gate_appointment(
    port_code: str,
    container_number: str,
    transaction_type: str,
    appointment_time: str,
    trucking_company: str,
    driver_license: str | None = None,
    truck_license: str | None = None,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> dict:
    """Create a gate appointment. Requires tenant's own port credentials."""
    try:
        from datetime import datetime
        appt_time = datetime.fromisoformat(appointment_time)
        return await service.create_gate_appointment(
            company_id=company_id,
            port_code=port_code,
            container_number=container_number,
            transaction_type=transaction_type,
            appointment_time=appt_time,
            trucking_company=trucking_company,
            driver_license=driver_license,
            truck_license=truck_license,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating appointment: {str(e)}",
        )


@router.delete("/operations/appointments/{appointment_id}")
async def cancel_gate_appointment(
    appointment_id: str,
    port_code: str,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> dict:
    """Cancel a gate appointment."""
    try:
        return await service.cancel_gate_appointment(
            company_id=company_id,
            port_code=port_code,
            appointment_id=appointment_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error canceling appointment: {str(e)}",
        )


# ==================== GATE/TRUCK OPERATIONS ====================


@router.get("/operations/gate-transactions")
async def get_gate_transactions(
    port_code: str,
    container_number: str | None = None,
    since: str | None = None,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> List[dict]:
    """Get gate transaction history."""
    try:
        from datetime import datetime
        since_dt = datetime.fromisoformat(since) if since else None
        return await service.get_gate_transactions(
            company_id=company_id,
            port_code=port_code,
            container_number=container_number,
            since=since_dt,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting gate transactions: {str(e)}",
        )


@router.get("/operations/truck-visits")
async def get_truck_visits(
    port_code: str,
    truck_license: str | None = None,
    since: str | None = None,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> List[dict]:
    """Get truck visit information."""
    try:
        from datetime import datetime
        since_dt = datetime.fromisoformat(since) if since else None
        return await service.get_truck_visits(
            company_id=company_id,
            port_code=port_code,
            truck_license=truck_license,
            since=since_dt,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting truck visits: {str(e)}",
        )


# ==================== BOOKING/ORDER OPERATIONS ====================


@router.get("/operations/bookings")
async def get_bookings(
    port_code: str,
    booking_number: str | None = None,
    vessel_visit: str | None = None,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> List[dict]:
    """Get booking information."""
    try:
        return await service.get_bookings(
            company_id=company_id,
            port_code=port_code,
            booking_number=booking_number,
            vessel_visit=vessel_visit,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting bookings: {str(e)}",
        )


@router.get("/operations/service-orders")
async def get_service_orders(
    port_code: str,
    container_number: str | None = None,
    order_type: str | None = None,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> List[dict]:
    """Get service orders."""
    try:
        return await service.get_service_orders(
            company_id=company_id,
            port_code=port_code,
            container_number=container_number,
            order_type=order_type,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting service orders: {str(e)}",
        )


# ==================== BILLING OPERATIONS ====================


@router.get("/operations/billable-events")
async def get_billable_events(
    port_code: str,
    container_number: str | None = None,
    since: str | None = None,
    company_id: str = Depends(_company_id),
    service: PortService = Depends(_service),
) -> List[dict]:
    """Get billable events for containers."""
    try:
        from datetime import datetime
        since_dt = datetime.fromisoformat(since) if since else None
        return await service.get_billable_events(
            company_id=company_id,
            port_code=port_code,
            container_number=container_number,
            since=since_dt,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting billable events: {str(e)}",
        )


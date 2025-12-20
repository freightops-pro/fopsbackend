from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.load import (
    LoadCreate,
    LoadResponse,
    LoadUpdate,
    LoadStopScheduleUpdate,
    LoadAssignmentUpdate,
    CreatePortAppointmentRequest,
    PortAppointmentResponse,
)
from app.services.load import LoadService
from app.services.document_processing import DocumentProcessingService
from app.services.drayage.container_lookup_service import ContainerLookupService

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> LoadService:
    return LoadService(db)


async def _doc_service(db: AsyncSession = Depends(get_db)) -> DocumentProcessingService:
    return DocumentProcessingService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


# Rate confirmation extraction - MUST be before /{load_id} route
@router.post("/extract-from-rate-confirmation")
async def extract_from_rate_confirmation(
    rateConfirmation: UploadFile = File(...),
    company_id: str = Depends(_company_id),
    service: DocumentProcessingService = Depends(_doc_service),
):
    """Extract load data from a rate confirmation PDF."""
    try:
        result = await service.extract_rate_confirmation(
            company_id=company_id,
            file=rateConfirmation,
        )
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "loadData": None,
        }


@router.get("", response_model=List[LoadResponse])
async def list_loads(company_id: str = Depends(_company_id), service: LoadService = Depends(_service)) -> List[LoadResponse]:
    loads_with_expenses = await service.list_loads_with_expenses(company_id)
    return [LoadResponse.model_validate(load) for load in loads_with_expenses]


# ==================== CONTAINER AUTO-LOOKUP ====================


class ContainerLookupRequest(BaseModel):
    """Request to look up container information for load creation."""
    container_number: str
    port_code: Optional[str] = None  # UN/LOCODE (e.g., USHOU, USLAX)
    terminal: Optional[str] = None


class ContainerLookupResponseData(BaseModel):
    """Container data response for auto-population."""
    success: bool
    container_number: str
    error: Optional[str] = None

    # Container data for load auto-population
    status: Optional[str] = None
    status_description: Optional[str] = None
    is_available: Optional[bool] = None
    holds: Optional[List[str]] = None

    # Location info
    port_code: Optional[str] = None
    terminal: Optional[str] = None
    carrier_scac: Optional[str] = None

    # Vessel info
    vessel_name: Optional[str] = None
    vessel_voyage: Optional[str] = None
    vessel_eta: Optional[datetime] = None

    # Critical dates for drayage
    last_free_day: Optional[datetime] = None
    discharge_date: Optional[datetime] = None
    empty_return_by: Optional[datetime] = None

    # Container specs
    size: Optional[str] = None
    container_type: Optional[str] = None

    # Charges from port
    demurrage_amount: Optional[float] = None


@router.post("/container-lookup", response_model=ContainerLookupResponseData)
async def lookup_container_for_load(
    request: ContainerLookupRequest,
    company_id: str = Depends(_company_id),
):
    """
    Look up container information from PORT API for auto-populating load data.

    Call this endpoint when:
    - User selects load_type = "container"
    - User enters a container number

    Returns container status, vessel info, LFD, terminal, and other data
    from the port's terminal operating system.

    Example flow:
    1. User enters container number "MAEU1234567" and port "USHOU"
    2. Frontend calls POST /loads/container-lookup
    3. Backend queries Port Houston API
    4. Returns container data for form auto-population

    If port_code not provided, searches across all supported ports.
    """
    service = ContainerLookupService()
    result = await service.lookup_container(
        container_number=request.container_number,
        port_code=request.port_code,
        terminal=request.terminal,
    )

    return ContainerLookupResponseData(
        success=result.success,
        container_number=result.container_number,
        error=result.error,
        status=result.status,
        status_description=result.status_description,
        is_available=result.is_available,
        holds=result.holds,
        port_code=result.port_code,
        terminal=result.terminal,
        carrier_scac=result.carrier_scac,
        vessel_name=result.vessel_name,
        vessel_voyage=result.vessel_voyage,
        vessel_eta=result.vessel_eta,
        last_free_day=result.last_free_day,
        discharge_date=result.discharge_date,
        empty_return_by=result.empty_return_by,
        size=result.size,
        container_type=result.container_type,
        demurrage_amount=result.demurrage_amount,
    )


@router.get("/container-lookup/{container_number}", response_model=ContainerLookupResponseData)
async def lookup_container_by_number(
    container_number: str,
    port_code: Optional[str] = Query(None, description="Port UN/LOCODE (e.g., USHOU, USLAX). Searches all if not provided."),
    company_id: str = Depends(_company_id),
):
    """
    Look up container information by number (GET method).

    Same as POST /container-lookup but as GET for convenience.
    If port_code not provided, searches across all supported ports.
    """
    request = ContainerLookupRequest(
        container_number=container_number,
        port_code=port_code,
    )
    return await lookup_container_for_load(request, company_id)


# Driver-specific endpoints - MUST be before /{load_id} route
@router.get("/driver/{driver_id}", response_model=List[LoadResponse])
async def list_driver_loads(
    driver_id: str,
    status_filter: str | None = None,
    company_id: str = Depends(_company_id),
    service: LoadService = Depends(_service),
) -> List[LoadResponse]:
    """Get loads assigned to a specific driver.

    status_filter options:
    - current: Active loads (in_transit, at_pickup, at_delivery, etc.)
    - past: Completed or cancelled loads
    - future: Assigned but not yet started
    - Or any specific status like 'delivered', 'in_transit', etc.
    """
    loads = await service.list_driver_loads(company_id, driver_id, status_filter)
    return [LoadResponse.model_validate(load) for load in loads]


@router.get("/driver/{driver_id}/active", response_model=LoadResponse | None)
async def get_driver_active_load(
    driver_id: str,
    company_id: str = Depends(_company_id),
    service: LoadService = Depends(_service),
) -> LoadResponse | None:
    """Get the current active load for a driver."""
    load = await service.get_driver_active_load(company_id, driver_id)
    if load:
        return LoadResponse.model_validate(load)
    return None


@router.get("/{load_id}", response_model=LoadResponse)
async def get_load(
    load_id: str,
    company_id: str = Depends(_company_id),
    service: LoadService = Depends(_service),
) -> LoadResponse:
    try:
        load_with_expenses = await service.get_load_with_expenses(company_id, load_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return LoadResponse.model_validate(load_with_expenses)


class LoadCreateResponse(LoadResponse):
    """Extended response that includes new customer creation info."""
    new_customer_created: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_load(
    payload: LoadCreate,
    company_id: str = Depends(_company_id),
    service: LoadService = Depends(_service),
) -> LoadCreateResponse:
    load, new_customer_name = await service.create_load(company_id, payload)
    response = LoadCreateResponse.model_validate(load)
    response.new_customer_created = new_customer_name
    return response


@router.put("/{load_id}", response_model=LoadResponse)
async def update_load(
    load_id: str,
    payload: LoadUpdate,
    company_id: str = Depends(_company_id),
    service: LoadService = Depends(_service),
) -> LoadResponse:
    load = await service.update_load(company_id, load_id, payload)
    return LoadResponse.model_validate(load)


@router.patch("/{load_id}/stops/{stop_id}/schedule", response_model=LoadResponse)
async def update_stop_schedule(
    load_id: str,
    stop_id: str,
    payload: LoadStopScheduleUpdate,
    company_id: str = Depends(_company_id),
    service: LoadService = Depends(_service),
) -> LoadResponse:
    try:
        load = await service.update_stop_schedule(company_id, load_id, stop_id, payload.scheduled_at)
        return LoadResponse.model_validate(load)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{load_id}/assign", response_model=LoadResponse)
async def assign_load(
    load_id: str,
    payload: LoadAssignmentUpdate,
    company_id: str = Depends(_company_id),
    service: LoadService = Depends(_service),
) -> LoadResponse:
    try:
        load = await service.assign_load(company_id, load_id, payload.driver_id, payload.truck_id)
        return LoadResponse.model_validate(load)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ==================== PORT APPOINTMENT ENDPOINTS ====================


@router.post("/{load_id}/port-appointment", response_model=PortAppointmentResponse)
async def create_port_appointment(
    load_id: str,
    payload: CreatePortAppointmentRequest,
    company_id: str = Depends(_company_id),
    service: LoadService = Depends(_service),
    db: AsyncSession = Depends(get_db),
) -> PortAppointmentResponse:
    """
    Create a port appointment for a container load.

    This will:
    1. Call the port's API to create the appointment
    2. Extract the entry code / ePass from the response
    3. Save the appointment details to the load
    4. Return the entry code for the driver

    Requires the tenant to have port credentials configured.
    """
    from app.services.port.port_service import PortService

    try:
        # Get the load first
        load = await service.get_load(company_id, load_id)

        # Verify it's a container load with a port
        if not load.container_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Load does not have a container number"
            )
        if not load.origin_port_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Load does not have an origin port specified"
            )

        # Create port service and appointment
        port_service = PortService(db)
        result = await port_service.create_gate_appointment(
            company_id=company_id,
            port_code=load.origin_port_code,
            container_number=load.container_number,
            transaction_type=payload.transaction_type,
            appointment_time=payload.appointment_time,
            trucking_company=payload.trucking_company,
            driver_license=payload.driver_license,
            truck_license=payload.truck_license,
        )

        # Extract entry code from metadata if present
        # Port Houston may return it as gapptNbr, accessCode, entryCode, or ePassCode
        metadata = result.get("metadata", {})
        entry_code = (
            metadata.get("accessCode") or
            metadata.get("entryCode") or
            metadata.get("ePassCode") or
            metadata.get("gapptNbr") or
            result.get("appointment_number")
        )

        # Update load with appointment details
        load.port_appointment_id = result.get("appointment_id")
        load.port_appointment_number = result.get("appointment_number")
        load.port_entry_code = entry_code
        load.port_appointment_time = payload.appointment_time
        load.port_appointment_gate = metadata.get("gate")
        load.port_appointment_status = result.get("status", "SCHEDULED")
        load.port_appointment_terminal = metadata.get("facility") or metadata.get("terminal")

        await db.commit()
        await db.refresh(load)

        return PortAppointmentResponse(
            load_id=load_id,
            appointment_id=result.get("appointment_id", ""),
            appointment_number=result.get("appointment_number", ""),
            entry_code=entry_code,
            appointment_time=payload.appointment_time,
            gate=load.port_appointment_gate,
            terminal=load.port_appointment_terminal,
            status=load.port_appointment_status or "SCHEDULED",
        )

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create port appointment: {str(exc)}"
        )


@router.delete("/{load_id}/port-appointment")
async def cancel_port_appointment(
    load_id: str,
    company_id: str = Depends(_company_id),
    service: LoadService = Depends(_service),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an existing port appointment for a load."""
    from app.services.port.port_service import PortService

    try:
        load = await service.get_load(company_id, load_id)

        if not load.port_appointment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Load does not have an active port appointment"
            )
        if not load.origin_port_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Load does not have an origin port specified"
            )

        port_service = PortService(db)
        await port_service.cancel_gate_appointment(
            company_id=company_id,
            port_code=load.origin_port_code,
            appointment_id=load.port_appointment_id,
        )

        # Clear appointment fields
        load.port_appointment_id = None
        load.port_appointment_number = None
        load.port_entry_code = None
        load.port_appointment_time = None
        load.port_appointment_gate = None
        load.port_appointment_status = "CANCELLED"
        load.port_appointment_terminal = None

        await db.commit()

        return {"success": True, "message": "Port appointment cancelled"}

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel port appointment: {str(exc)}"
        )


@router.get("/{load_id}/port-appointment", response_model=PortAppointmentResponse)
async def get_port_appointment(
    load_id: str,
    company_id: str = Depends(_company_id),
    service: LoadService = Depends(_service),
) -> PortAppointmentResponse:
    """Get the port appointment details for a load."""
    try:
        load = await service.get_load(company_id, load_id)

        if not load.port_appointment_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Load does not have a port appointment"
            )

        return PortAppointmentResponse(
            load_id=load_id,
            appointment_id=load.port_appointment_id,
            appointment_number=load.port_appointment_number or "",
            entry_code=load.port_entry_code,
            appointment_time=load.port_appointment_time,
            gate=load.port_appointment_gate,
            terminal=load.port_appointment_terminal,
            status=load.port_appointment_status or "UNKNOWN",
        )

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ==================== DRIVER APP ENDPOINTS ====================

class LoadArrivalRequest(BaseModel):
    """Driver arrival at pickup/delivery stop."""
    stop_type: str  # "pickup" or "delivery"
    stop_id: str | None = None
    arrival_time: datetime
    latitude: float
    longitude: float
    notes: str | None = None


class LoadDepartureRequest(BaseModel):
    """Driver departure from pickup/delivery stop."""
    stop_type: str  # "pickup" or "delivery"
    stop_id: str | None = None
    departure_time: datetime
    latitude: float
    longitude: float
    notes: str | None = None


class LoadStatusUpdateRequest(BaseModel):
    """Update load status from driver app."""
    status: str  # e.g., "in_progress", "at_pickup", "loading", "in_transit", "at_delivery", "delivered"
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = None


@router.post("/{load_id}/arrival")
async def record_load_arrival(
    load_id: str,
    request: LoadArrivalRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
):
    """Record driver arrival at pickup or delivery location."""
    try:
        # Get load and verify access
        load_service = LoadService(db)
        load = await load_service.get_load(load_id)

        if not load:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Load {load_id} not found"
            )

        # Verify driver has access to this load
        if current_user.role == "DRIVER" and load.driver_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this load"
            )

        # Update load based on stop type
        if request.stop_type == "pickup":
            load.pickup_arrival_time = request.arrival_time
            load.pickup_arrival_lat = request.latitude
            load.pickup_arrival_lng = request.longitude
            load.status = "at_pickup"
        elif request.stop_type == "delivery":
            load.delivery_arrival_time = request.arrival_time
            load.delivery_arrival_lat = request.latitude
            load.delivery_arrival_lng = request.longitude
            load.status = "at_delivery"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stop_type: {request.stop_type}"
            )

        db.add(load)
        await db.commit()
        await db.refresh(load)

        # TODO: Broadcast update via WebSocket when WebSocketManager is implemented

        return {
            "message": f"Arrival at {request.stop_type} recorded successfully",
            "load_id": load_id,
            "status": load.status,
            "arrival_time": request.arrival_time.isoformat(),
        }

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{load_id}/departure")
async def record_load_departure(
    load_id: str,
    request: LoadDepartureRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
):
    """Record driver departure from pickup or delivery location."""
    try:
        # Get load and verify access
        load_service = LoadService(db)
        load = await load_service.get_load(load_id)

        if not load:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Load {load_id} not found"
            )

        # Verify driver has access to this load
        if current_user.role == "DRIVER" and load.driver_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this load"
            )

        # Update load based on stop type
        if request.stop_type == "pickup":
            load.pickup_departure_time = request.departure_time
            load.pickup_departure_lat = request.latitude
            load.pickup_departure_lng = request.longitude
            load.status = "in_transit"
        elif request.stop_type == "delivery":
            load.delivery_departure_time = request.departure_time
            load.delivery_departure_lat = request.latitude
            load.delivery_departure_lng = request.longitude
            load.status = "delivered"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid stop_type: {request.stop_type}"
            )

        db.add(load)
        await db.commit()
        await db.refresh(load)

        # TODO: Broadcast update via WebSocket when WebSocketManager is implemented

        return {
            "message": f"Departure from {request.stop_type} recorded successfully",
            "load_id": load_id,
            "status": load.status,
            "departure_time": request.departure_time.isoformat(),
        }

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{load_id}/status")
async def update_load_status(
    load_id: str,
    request: LoadStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(deps.get_current_user),
):
    """Update load status from driver app."""
    try:
        # Get load and verify access
        load_service = LoadService(db)
        load = await load_service.get_load(load_id)

        if not load:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Load {load_id} not found"
            )

        # Verify driver has access to this load
        if current_user.role == "DRIVER" and load.driver_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this load"
            )

        # Update load status
        old_status = load.status
        load.status = request.status

        # Update location if provided
        if request.latitude and request.longitude:
            load.last_known_lat = request.latitude
            load.last_known_lng = request.longitude

        db.add(load)
        await db.commit()
        await db.refresh(load)

        # TODO: Broadcast update via WebSocket when WebSocketManager is implemented

        return {
            "message": "Load status updated successfully",
            "load_id": load_id,
            "old_status": old_status,
            "new_status": request.status,
        }

    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


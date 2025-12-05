from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
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
    loads = await service.list_loads(company_id)
    return [LoadResponse.model_validate(load) for load in loads]


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
        load = await service.get_load(company_id, load_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return LoadResponse.model_validate(load)


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


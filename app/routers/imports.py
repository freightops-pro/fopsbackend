"""CSV import router for bulk data imports."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.imports import ImportResult
from app.services.import_service import ImportService

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> ImportService:
    """Dependency for ImportService."""
    return ImportService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    """Dependency for company_id from current user."""
    return current_user.company_id


@router.post("/drivers", response_model=ImportResult)
async def import_drivers(
    file: UploadFile = File(...),
    company_id: str = Depends(_company_id),
    service: ImportService = Depends(_service),
) -> ImportResult:
    """
    Import drivers from CSV file.

    Required CSV columns:
    - first_name, last_name, email, phone

    Optional columns:
    - license_number, license_state, license_expiry
    - hire_date, employment_type, pay_rate, pay_type
    - address, city, state, zip
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported",
        )

    try:
        file_bytes = await file.read()
        result = await service.import_drivers(company_id, file_bytes, file.filename)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        )


@router.post("/equipment", response_model=ImportResult)
async def import_equipment(
    file: UploadFile = File(...),
    company_id: str = Depends(_company_id),
    service: ImportService = Depends(_service),
) -> ImportResult:
    """
    Import equipment (trucks/trailers) from CSV file.

    Required CSV columns:
    - unit_number, equipment_type (TRUCK or TRAILER)

    Optional columns:
    - status, make, model, year, vin
    - current_mileage, gps_provider, gps_device_id
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported",
        )

    try:
        file_bytes = await file.read()
        result = await service.import_equipment(company_id, file_bytes, file.filename)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        )


@router.post("/loads", response_model=ImportResult)
async def import_loads(
    file: UploadFile = File(...),
    company_id: str = Depends(_company_id),
    service: ImportService = Depends(_service),
) -> ImportResult:
    """
    Import loads from CSV file.

    Required CSV columns:
    - customer_name
    - pickup_city, pickup_state, pickup_zip
    - delivery_city, delivery_state, delivery_zip

    Optional columns:
    - pickup_date, pickup_time, delivery_date, delivery_time
    - commodity, weight, base_rate
    - reference_number, special_instructions
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are supported",
        )

    try:
        file_bytes = await file.read()
        result = await service.import_loads(company_id, file_bytes, file.filename)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        )


@router.get("/templates/{entity_type}")
async def download_template(
    entity_type: str,
    company_id: str = Depends(_company_id),
    service: ImportService = Depends(_service),
) -> Response:
    """
    Download CSV template for entity type.

    Supported entity types: drivers, equipment, loads
    """
    if entity_type not in ["drivers", "equipment", "loads"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity type: {entity_type}. Must be one of: drivers, equipment, loads",
        )

    try:
        template_bytes = service.generate_template(entity_type)
        return Response(
            content=template_bytes,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={entity_type}_import_template.csv"
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template generation failed: {str(e)}",
        )

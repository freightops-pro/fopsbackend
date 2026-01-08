"""CSV import router for bulk data imports."""

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.imports import ImportError, ImportResult
from app.services.import_service import ImportService

router = APIRouter()


class ValidationPreview(BaseModel):
    """Preview of what will be imported."""
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: List[ImportError]
    warnings: List[str]
    sample_data: List[Dict[str, Any]] = Field(default_factory=list, description="First 3 rows")


async def _service(db: AsyncSession = Depends(get_db)) -> ImportService:
    """Dependency for ImportService."""
    return ImportService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    """Dependency for company_id from current user."""
    return current_user.company_id


@router.post("/drivers/validate", response_model=ValidationPreview)
async def validate_drivers_import(
    file: UploadFile = File(...),
    service: ImportService = Depends(_service),
) -> ValidationPreview:
    """
    Validate driver import file without actually importing.
    Returns preview of what will be imported and any errors.
    """
    valid_extensions = (".csv", ".xlsx", ".xls")
    if not file.filename.lower().endswith(valid_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV and Excel files are supported (.csv, .xlsx, .xls)",
        )

    try:
        file_bytes = await file.read()
        total, valid, errors, warnings, sample = service.validate_import(
            file_bytes, file.filename, "drivers"
        )

        return ValidationPreview(
            total_rows=total,
            valid_rows=valid,
            invalid_rows=total - valid,
            errors=errors[:10],  # Limit to first 10 errors
            warnings=warnings,
            sample_data=sample,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}",
        )


@router.post("/drivers")
async def import_drivers(
    file: UploadFile = File(...),
    validate_only: bool = False,
    company_id: str = Depends(_company_id),
    service: ImportService = Depends(_service),
):
    """
    Import drivers from CSV or Excel file.

    Query parameters:
    - validate_only: If true, only validates the file without importing

    Required columns:
    - first_name, last_name, email, phone

    Optional columns:
    - license_number, license_state, license_expiry
    - hire_date, employment_type, pay_rate, pay_type
    - address, city, state, zip
    """
    valid_extensions = (".csv", ".xlsx", ".xls")
    if not file.filename.lower().endswith(valid_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV and Excel files are supported (.csv, .xlsx, .xls)",
        )

    try:
        file_bytes = await file.read()

        # Validation only mode
        if validate_only:
            total, valid, errors, warnings, sample = service.validate_import(
                file_bytes, file.filename, "drivers"
            )
            return ValidationPreview(
                total_rows=total,
                valid_rows=valid,
                invalid_rows=total - valid,
                errors=errors[:10],
                warnings=warnings,
                sample_data=sample,
            )

        # Full import
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


@router.post("/equipment/validate", response_model=ValidationPreview)
async def validate_equipment_import(
    file: UploadFile = File(...),
    service: ImportService = Depends(_service),
) -> ValidationPreview:
    """
    Validate equipment import file without actually importing.
    Returns preview of what will be imported and any errors.
    """
    valid_extensions = (".csv", ".xlsx", ".xls")
    if not file.filename.lower().endswith(valid_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV and Excel files are supported (.csv, .xlsx, .xls)",
        )

    try:
        file_bytes = await file.read()
        total, valid, errors, warnings, sample = service.validate_import(
            file_bytes, file.filename, "equipment"
        )

        return ValidationPreview(
            total_rows=total,
            valid_rows=valid,
            invalid_rows=total - valid,
            errors=errors[:10],
            warnings=warnings,
            sample_data=sample,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}",
        )


@router.post("/equipment")
async def import_equipment(
    file: UploadFile = File(...),
    validate_only: bool = False,
    company_id: str = Depends(_company_id),
    service: ImportService = Depends(_service),
):
    """
    Import equipment (trucks/trailers) from CSV or Excel file.

    Query parameters:
    - validate_only: If true, only validates the file without importing

    Required columns:
    - unit_number, equipment_type (TRUCK or TRAILER)

    Optional columns:
    - status, make, model, year, vin
    - current_mileage, gps_provider, gps_device_id
    """
    valid_extensions = (".csv", ".xlsx", ".xls")
    if not file.filename.lower().endswith(valid_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV and Excel files are supported (.csv, .xlsx, .xls)",
        )

    try:
        file_bytes = await file.read()

        # Validation only mode
        if validate_only:
            total, valid, errors, warnings, sample = service.validate_import(
                file_bytes, file.filename, "equipment"
            )
            return ValidationPreview(
                total_rows=total,
                valid_rows=valid,
                invalid_rows=total - valid,
                errors=errors[:10],
                warnings=warnings,
                sample_data=sample,
            )

        # Full import
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


@router.post("/loads/validate", response_model=ValidationPreview)
async def validate_loads_import(
    file: UploadFile = File(...),
    service: ImportService = Depends(_service),
) -> ValidationPreview:
    """
    Validate loads import file without actually importing.
    Returns preview of what will be imported and any errors.
    """
    valid_extensions = (".csv", ".xlsx", ".xls")
    if not file.filename.lower().endswith(valid_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV and Excel files are supported (.csv, .xlsx, .xls)",
        )

    try:
        file_bytes = await file.read()
        total, valid, errors, warnings, sample = service.validate_import(
            file_bytes, file.filename, "loads"
        )

        return ValidationPreview(
            total_rows=total,
            valid_rows=valid,
            invalid_rows=total - valid,
            errors=errors[:10],
            warnings=warnings,
            sample_data=sample,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}",
        )


@router.post("/loads")
async def import_loads(
    file: UploadFile = File(...),
    validate_only: bool = False,
    company_id: str = Depends(_company_id),
    service: ImportService = Depends(_service),
):
    """
    Import loads from CSV or Excel file.

    Query parameters:
    - validate_only: If true, only validates the file without importing

    Required columns:
    - customer_name
    - pickup_city, pickup_state, pickup_zip
    - delivery_city, delivery_state, delivery_zip

    Optional columns:
    - pickup_date, pickup_time, delivery_date, delivery_time
    - commodity, weight, base_rate
    - reference_number, special_instructions
    """
    valid_extensions = (".csv", ".xlsx", ".xls")
    if not file.filename.lower().endswith(valid_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV and Excel files are supported (.csv, .xlsx, .xls)",
        )

    try:
        file_bytes = await file.read()

        # Validation only mode
        if validate_only:
            total, valid, errors, warnings, sample = service.validate_import(
                file_bytes, file.filename, "loads"
            )
            return ValidationPreview(
                total_rows=total,
                valid_rows=valid,
                invalid_rows=total - valid,
                errors=errors[:10],
                warnings=warnings,
                sample_data=sample,
            )

        # Full import
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
) -> FileResponse:
    """
    Download CSV template for entity type.

    Supported entity types: drivers, equipment, loads

    Templates are served as static files from the templates directory.
    """
    if entity_type not in ["drivers", "equipment", "loads"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity type: {entity_type}. Must be one of: drivers, equipment, loads",
        )

    # Get the template file path
    template_dir = Path(__file__).parent.parent.parent / "templates"
    template_file = template_dir / f"{entity_type}_import_template.csv"

    if not template_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template file not found for {entity_type}",
        )

    return FileResponse(
        path=template_file,
        media_type="text/csv",
        filename=f"{entity_type}_import_template.csv",
    )

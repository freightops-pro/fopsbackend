"""CSV import service for bulk data imports."""

import csv
import io
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver import Driver
from app.models.equipment import Equipment
from app.models.load import Load
from app.schemas.imports import (
    DriverImportRow,
    EquipmentImportRow,
    ImportError,
    ImportResult,
    LoadImportRow,
    ValidationResult,
)

logger = logging.getLogger(__name__)


class ImportService:
    """Service for handling CSV imports."""

    # Required columns for each entity type
    REQUIRED_COLUMNS = {
        "drivers": ["first_name", "last_name", "email", "phone"],
        "equipment": ["unit_number", "equipment_type"],
        "loads": [
            "customer_name",
            "pickup_city",
            "pickup_state",
            "pickup_zip",
            "delivery_city",
            "delivery_state",
            "delivery_zip",
        ],
    }

    # Schema mapping
    SCHEMAS = {
        "drivers": DriverImportRow,
        "equipment": EquipmentImportRow,
        "loads": LoadImportRow,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    def parse_csv(self, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """Parse CSV file and return list of row dictionaries."""
        try:
            # Detect encoding
            try:
                content = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = file_bytes.decode("utf-8-sig")  # Try with BOM
            except UnicodeDecodeError:
                content = file_bytes.decode("latin-1")  # Fallback

            # Parse CSV
            csv_file = io.StringIO(content)
            reader = csv.DictReader(csv_file)

            # Convert to list and strip whitespace from keys and values
            rows = []
            for row in reader:
                cleaned_row = {
                    k.strip().lower().replace(" ", "_"): v.strip() if v else None
                    for k, v in row.items()
                    if k
                }
                rows.append(cleaned_row)

            return rows

        except Exception as e:
            logger.error(f"Error parsing CSV {filename}: {str(e)}")
            raise ValueError(f"Failed to parse CSV: {str(e)}")

    def validate_headers(
        self, headers: List[str], entity_type: str
    ) -> ValidationResult:
        """Validate that required headers are present."""
        required = self.REQUIRED_COLUMNS.get(entity_type, [])
        headers_lower = [h.lower().replace(" ", "_") for h in headers]

        errors = []
        warnings = []
        suggestions = []

        # Check for missing required columns
        for req_col in required:
            if req_col not in headers_lower:
                errors.append(f"Missing required column: '{req_col}'")

                # Check for similar column names (typos)
                for header in headers_lower:
                    if self._is_similar(req_col, header):
                        suggestions.append(
                            f"Did you mean '{req_col}' instead of '{header}'?"
                        )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    def _is_similar(self, str1: str, str2: str, threshold: float = 0.7) -> bool:
        """Check if two strings are similar (simple similarity check)."""
        # Simple Levenshtein-like check
        if len(str1) < 3 or len(str2) < 3:
            return False

        # Check if one contains most characters of the other
        common_chars = sum(1 for c in str1 if c in str2)
        similarity = common_chars / max(len(str1), len(str2))
        return similarity >= threshold

    def validate_row(
        self, row: Dict[str, Any], schema: Any
    ) -> Tuple[bool, List[str], Optional[Any]]:
        """
        Validate a single row against a Pydantic schema.

        Returns:
            (is_valid, errors, validated_data)
        """
        try:
            # Filter out None values and empty strings
            cleaned_row = {k: v for k, v in row.items() if v not in [None, "", "null"]}
            validated = schema(**cleaned_row)
            return True, [], validated
        except ValidationError as e:
            errors = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
            return False, errors, None
        except Exception as e:
            return False, [str(e)], None

    def generate_template(self, entity_type: str) -> bytes:
        """Generate CSV template with headers and sample row."""
        if entity_type == "drivers":
            headers = [
                "first_name",
                "last_name",
                "email",
                "phone",
                "license_number",
                "license_state",
                "license_expiry",
                "hire_date",
                "employment_type",
                "pay_rate",
                "pay_type",
                "address",
                "city",
                "state",
                "zip",
            ]
            sample = [
                "John",
                "Doe",
                "john.doe@example.com",
                "555-123-4567",
                "D1234567",
                "CA",
                "2025-12-31",
                "2024-01-15",
                "FULL_TIME",
                "0.45",
                "per_mile",
                "123 Main St",
                "Los Angeles",
                "CA",
                "90001",
            ]
        elif entity_type == "equipment":
            headers = [
                "unit_number",
                "equipment_type",
                "status",
                "make",
                "model",
                "year",
                "vin",
                "current_mileage",
                "gps_provider",
                "gps_device_id",
            ]
            sample = [
                "T001",
                "TRUCK",
                "ACTIVE",
                "Freightliner",
                "Cascadia",
                "2022",
                "1FUJGHDV1JLNA1234",
                "50000",
                "SAMSARA",
                "DEV123",
            ]
        elif entity_type == "loads":
            headers = [
                "customer_name",
                "pickup_city",
                "pickup_state",
                "pickup_zip",
                "pickup_date",
                "pickup_time",
                "delivery_city",
                "delivery_state",
                "delivery_zip",
                "delivery_date",
                "delivery_time",
                "commodity",
                "weight",
                "base_rate",
                "reference_number",
                "special_instructions",
            ]
            sample = [
                "ABC Corp",
                "Chicago",
                "IL",
                "60601",
                "2024-02-01",
                "09:00",
                "Dallas",
                "TX",
                "75201",
                "2024-02-03",
                "17:00",
                "Electronics",
                "25000",
                "2500.00",
                "REF001",
                "Fragile - handle with care",
            ]
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerow(sample)

        return output.getvalue().encode("utf-8")

    async def check_duplicate_driver(
        self, company_id: str, email: str, phone: str, license_number: Optional[str]
    ) -> Optional[str]:
        """Check if driver already exists. Returns driver ID if found."""
        result = await self.db.execute(
            select(Driver).where(
                Driver.company_id == company_id,
                (Driver.email == email)
                | (Driver.phone == phone)
                | (
                    (Driver.license_number == license_number)
                    if license_number
                    else False
                ),
            )
        )
        existing = result.scalar_one_or_none()
        return existing.id if existing else None

    async def check_duplicate_equipment(
        self, company_id: str, unit_number: str, vin: Optional[str]
    ) -> Optional[str]:
        """Check if equipment already exists. Returns equipment ID if found."""
        result = await self.db.execute(
            select(Equipment).where(
                Equipment.company_id == company_id,
                (Equipment.unit_number == unit_number)
                | ((Equipment.vin == vin) if vin else False),
            )
        )
        existing = result.scalar_one_or_none()
        return existing.id if existing else None

    async def import_drivers(
        self, company_id: str, file_bytes: bytes, filename: str
    ) -> ImportResult:
        """Import drivers from CSV file."""
        try:
            # Parse CSV
            rows = self.parse_csv(file_bytes, filename)

            if not rows:
                return ImportResult(
                    total=0,
                    successful=0,
                    failed=0,
                    errors=[],
                    warnings=["CSV file is empty"],
                )

            # Validate headers
            headers = list(rows[0].keys())
            validation = self.validate_headers(headers, "drivers")

            if not validation.valid:
                return ImportResult(
                    total=0,
                    successful=0,
                    failed=0,
                    errors=[
                        ImportError(row=0, error=err) for err in validation.errors
                    ],
                    warnings=validation.warnings,
                )

            # Import rows
            successful_ids = []
            errors = []
            warnings = []
            schema = self.SCHEMAS["drivers"]

            for idx, row in enumerate(rows, start=1):
                try:
                    # Validate row
                    is_valid, validation_errors, validated_data = self.validate_row(
                        row, schema
                    )

                    if not is_valid:
                        errors.append(
                            ImportError(
                                row=idx,
                                error="; ".join(validation_errors),
                            )
                        )
                        continue

                    # Check for duplicates
                    duplicate_id = await self.check_duplicate_driver(
                        company_id,
                        validated_data.email,
                        validated_data.phone,
                        validated_data.license_number,
                    )

                    if duplicate_id:
                        warnings.append(
                            f"Row {idx}: Driver with email '{validated_data.email}' already exists (skipped)"
                        )
                        continue

                    # Create driver
                    driver = Driver(
                        id=str(uuid.uuid4()),
                        company_id=company_id,
                        first_name=validated_data.first_name,
                        last_name=validated_data.last_name,
                        email=validated_data.email,
                        phone=validated_data.phone,
                        license_number=validated_data.license_number,
                        license_state=validated_data.license_state,
                        # Note: license_expiry parsing would need date parsing logic
                        employment_type=validated_data.employment_type or "FULL_TIME",
                        # Note: hire_date parsing would need date parsing logic
                        # pay_rate and other fields would be added to Worker record
                    )

                    self.db.add(driver)
                    await self.db.flush()
                    successful_ids.append(driver.id)

                except Exception as e:
                    logger.error(f"Error importing driver row {idx}: {str(e)}")
                    errors.append(ImportError(row=idx, error=str(e)))

            # Commit all changes
            await self.db.commit()

            return ImportResult(
                total=len(rows),
                successful=len(successful_ids),
                failed=len(errors),
                errors=errors,
                created_ids=successful_ids,
                warnings=warnings,
            )

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error importing drivers: {str(e)}")
            raise

    async def import_equipment(
        self, company_id: str, file_bytes: bytes, filename: str
    ) -> ImportResult:
        """Import equipment from CSV file."""
        try:
            # Parse CSV
            rows = self.parse_csv(file_bytes, filename)

            if not rows:
                return ImportResult(
                    total=0,
                    successful=0,
                    failed=0,
                    errors=[],
                    warnings=["CSV file is empty"],
                )

            # Validate headers
            headers = list(rows[0].keys())
            validation = self.validate_headers(headers, "equipment")

            if not validation.valid:
                return ImportResult(
                    total=0,
                    successful=0,
                    failed=0,
                    errors=[
                        ImportError(row=0, error=err) for err in validation.errors
                    ],
                    warnings=validation.warnings,
                )

            # Import rows
            successful_ids = []
            errors = []
            warnings = []
            schema = self.SCHEMAS["equipment"]

            for idx, row in enumerate(rows, start=1):
                try:
                    # Validate row
                    is_valid, validation_errors, validated_data = self.validate_row(
                        row, schema
                    )

                    if not is_valid:
                        errors.append(
                            ImportError(
                                row=idx,
                                error="; ".join(validation_errors),
                            )
                        )
                        continue

                    # Check for duplicates
                    duplicate_id = await self.check_duplicate_equipment(
                        company_id,
                        validated_data.unit_number,
                        validated_data.vin,
                    )

                    if duplicate_id:
                        warnings.append(
                            f"Row {idx}: Equipment with unit number '{validated_data.unit_number}' already exists (skipped)"
                        )
                        continue

                    # Create equipment
                    equipment = Equipment(
                        id=str(uuid.uuid4()),
                        company_id=company_id,
                        unit_number=validated_data.unit_number,
                        equipment_type=validated_data.equipment_type.upper(),
                        status=validated_data.status or "ACTIVE",
                        make=validated_data.make,
                        model=validated_data.model,
                        year=validated_data.year,
                        vin=validated_data.vin,
                        current_mileage=validated_data.current_mileage,
                        gps_provider=validated_data.gps_provider,
                        gps_device_id=validated_data.gps_device_id,
                    )

                    self.db.add(equipment)
                    await self.db.flush()
                    successful_ids.append(equipment.id)

                except Exception as e:
                    logger.error(f"Error importing equipment row {idx}: {str(e)}")
                    errors.append(ImportError(row=idx, error=str(e)))

            # Commit all changes
            await self.db.commit()

            return ImportResult(
                total=len(rows),
                successful=len(successful_ids),
                failed=len(errors),
                errors=errors,
                created_ids=successful_ids,
                warnings=warnings,
            )

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error importing equipment: {str(e)}")
            raise

    async def import_loads(
        self, company_id: str, file_bytes: bytes, filename: str
    ) -> ImportResult:
        """
        Import loads from CSV file.

        Note: This is a basic implementation. Full load creation would require:
        - Customer lookup/creation
        - Location geocoding
        - Date/time parsing
        - More complex validation
        """
        try:
            # Parse CSV
            rows = self.parse_csv(file_bytes, filename)

            if not rows:
                return ImportResult(
                    total=0,
                    successful=0,
                    failed=0,
                    errors=[],
                    warnings=["CSV file is empty"],
                )

            # Validate headers
            headers = list(rows[0].keys())
            validation = self.validate_headers(headers, "loads")

            if not validation.valid:
                return ImportResult(
                    total=0,
                    successful=0,
                    failed=0,
                    errors=[
                        ImportError(row=0, error=err) for err in validation.errors
                    ],
                    warnings=validation.warnings,
                )

            # Import rows
            successful_ids = []
            errors = []
            warnings = []
            schema = self.SCHEMAS["loads"]

            for idx, row in enumerate(rows, start=1):
                try:
                    # Validate row
                    is_valid, validation_errors, validated_data = self.validate_row(
                        row, schema
                    )

                    if not is_valid:
                        errors.append(
                            ImportError(
                                row=idx,
                                error="; ".join(validation_errors),
                            )
                        )
                        continue

                    # TODO: Implement load creation
                    # This would require:
                    # - Customer lookup/creation (using dispatch service)
                    # - Location lookup/geocoding (using location service)
                    # - Date parsing and validation
                    # - Full load record creation with all relationships

                    warnings.append(
                        f"Row {idx}: Load import not yet fully implemented"
                    )

                except Exception as e:
                    logger.error(f"Error importing load row {idx}: {str(e)}")
                    errors.append(ImportError(row=idx, error=str(e)))

            # Commit all changes
            await self.db.commit()

            return ImportResult(
                total=len(rows),
                successful=len(successful_ids),
                failed=len(errors),
                errors=errors,
                created_ids=successful_ids,
                warnings=warnings,
            )

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error importing loads: {str(e)}")
            raise

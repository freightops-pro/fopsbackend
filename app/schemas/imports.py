"""Import schemas for CSV bulk imports."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ImportError(BaseModel):
    """Error encountered during import."""
    row: int = Field(..., description="Row number (1-indexed)")
    field: Optional[str] = Field(None, description="Field with error")
    error: str = Field(..., description="Error message")
    value: Optional[str] = Field(None, description="Invalid value")


class ImportResult(BaseModel):
    """Result of an import operation."""
    total: int = Field(..., description="Total rows in CSV")
    successful: int = Field(..., description="Successfully imported")
    failed: int = Field(..., description="Failed validation/import")
    errors: List[ImportError] = Field(default_factory=list, description="Detailed error list")
    created_ids: List[str] = Field(default_factory=list, description="IDs of created records")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal issues")


class ValidationResult(BaseModel):
    """Result of CSV structure validation."""
    valid: bool = Field(..., description="Whether CSV structure is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions to fix errors")


class DriverImportRow(BaseModel):
    """Schema for driver import CSV row."""
    first_name: str
    last_name: str
    email: str
    phone: str
    license_number: Optional[str] = None
    license_state: Optional[str] = None
    license_expiry: Optional[str] = None
    hire_date: Optional[str] = None
    employment_type: Optional[str] = None
    pay_rate: Optional[float] = None
    pay_type: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None


class EquipmentImportRow(BaseModel):
    """Schema for equipment import CSV row."""
    unit_number: str
    equipment_type: str  # TRUCK or TRAILER
    status: Optional[str] = "ACTIVE"
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    vin: Optional[str] = None
    current_mileage: Optional[int] = None
    gps_provider: Optional[str] = None
    gps_device_id: Optional[str] = None


class LoadImportRow(BaseModel):
    """Schema for load import CSV row."""
    customer_name: str
    pickup_city: str
    pickup_state: str
    pickup_zip: str
    pickup_date: Optional[str] = None
    pickup_time: Optional[str] = None
    delivery_city: str
    delivery_state: str
    delivery_zip: str
    delivery_date: Optional[str] = None
    delivery_time: Optional[str] = None
    commodity: Optional[str] = None
    weight: Optional[float] = None
    base_rate: Optional[float] = None
    reference_number: Optional[str] = None
    special_instructions: Optional[str] = None

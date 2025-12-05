from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ==================== FUEL CARD SCHEMAS ====================


class FuelCardCreate(BaseModel):
    """Create a new fuel card (physical or virtual)."""
    card_number: str = Field(..., min_length=4, description="Card number (at least last 4 digits)")
    card_provider: Literal["wex", "comdata", "efs", "fleetcor", "motive", "other"] = Field(
        ..., description="Fuel card provider"
    )
    card_type: Literal["physical", "virtual"] = Field(default="physical")
    card_nickname: Optional[str] = Field(None, description="User-friendly name for the card")
    driver_id: Optional[str] = Field(None, description="Assigned driver ID")
    truck_id: Optional[str] = Field(None, description="Assigned truck/equipment ID")
    expiration_date: Optional[date] = None
    daily_limit: Optional[float] = None
    transaction_limit: Optional[float] = None
    notes: Optional[str] = None


class FuelCardUpdate(BaseModel):
    """Update fuel card details."""
    card_nickname: Optional[str] = None
    driver_id: Optional[str] = None
    truck_id: Optional[str] = None
    status: Optional[Literal["active", "inactive", "lost", "expired"]] = None
    expiration_date: Optional[date] = None
    daily_limit: Optional[float] = None
    transaction_limit: Optional[float] = None
    notes: Optional[str] = None


class FuelCardResponse(BaseModel):
    """Fuel card response."""
    id: str
    card_number: str  # Masked (last 4 digits)
    card_provider: str
    card_type: str
    card_nickname: Optional[str] = None
    driver_id: Optional[str] = None
    driver_name: Optional[str] = None  # Populated from join
    truck_id: Optional[str] = None
    status: str
    expiration_date: Optional[date] = None
    daily_limit: Optional[float] = None
    transaction_limit: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FuelCardListResponse(BaseModel):
    """List of fuel cards."""
    cards: List[FuelCardResponse]
    total: int


# ==================== EXISTING SCHEMAS ====================


class FuelImportRequest(BaseModel):
    card_program: str
    statement_month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    file_id: str
    notes: Optional[str] = None


class FuelSummaryResponse(BaseModel):
    total_gallons: float
    taxable_gallons: float
    total_cost: float
    tax_due: float
    avg_price_per_gallon: float


class JurisdictionSummaryResponse(BaseModel):
    jurisdiction: str
    gallons: float
    taxable_gallons: float
    miles: float
    tax_due: float
    surcharge_due: float
    last_trip_date: Optional[date]


class FuelUploadResponse(BaseModel):
    success: bool
    message: str


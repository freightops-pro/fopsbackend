from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

class LoadBoardBase(BaseModel):
    posted_rate: Decimal
    commission_percentage: Decimal

class LoadBoardCreate(LoadBoardBase):
    load_id: str
    broker_company_id: str

class LoadBoardUpdate(BaseModel):
    posted_rate: Optional[Decimal] = None
    commission_percentage: Optional[Decimal] = None
    is_available: Optional[bool] = None
    carrier_company_id: Optional[str] = None

class LoadBoardResponse(LoadBoardBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    broker_company_id: str
    load_id: str
    is_available: bool
    carrier_company_id: Optional[str] = None
    booking_confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class LoadBoardWithDetails(LoadBoardResponse):
    load: Optional[dict] = None  # Will contain load details
    broker_company: Optional[dict] = None  # Will contain broker company details
    carrier_company: Optional[dict] = None  # Will contain carrier company details

class LoadBookingBase(BaseModel):
    requested_rate: Decimal
    message: Optional[str] = None

class LoadBookingCreate(LoadBookingBase):
    load_board_id: str
    carrier_company_id: str

class LoadBookingUpdate(BaseModel):
    status: Optional[str] = None
    broker_response: Optional[str] = None
    broker_rate: Optional[Decimal] = None

class LoadBookingResponse(LoadBookingBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    load_board_id: str
    carrier_company_id: str
    status: str
    broker_response: Optional[str] = None
    broker_rate: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime

class LoadBookingWithDetails(LoadBookingResponse):
    load_board: Optional[dict] = None  # Will contain load board details
    carrier_company: Optional[dict] = None  # Will contain carrier company details

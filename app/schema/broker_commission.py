from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal

class BrokerCommissionBase(BaseModel):
    total_load_value: Decimal
    commission_percentage: Decimal
    commission_amount: Decimal
    notes: Optional[str] = None

class BrokerCommissionCreate(BrokerCommissionBase):
    load_id: str
    broker_company_id: str
    carrier_company_id: str

class BrokerCommissionUpdate(BaseModel):
    payment_status: Optional[str] = None
    payment_date: Optional[datetime] = None
    settlement_id: Optional[str] = None
    notes: Optional[str] = None

class BrokerCommissionResponse(BrokerCommissionBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    load_id: str
    broker_company_id: str
    carrier_company_id: str
    payment_status: str
    payment_date: Optional[datetime] = None
    settlement_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class BrokerCommissionWithDetails(BrokerCommissionResponse):
    load: Optional[dict] = None  # Will contain load details
    broker_company: Optional[dict] = None  # Will contain broker company details
    carrier_company: Optional[dict] = None  # Will contain carrier company details
    settlement: Optional[dict] = None  # Will contain settlement details

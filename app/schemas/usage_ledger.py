from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UsageLedgerEntry(BaseModel):
    id: str
    source: str
    load_id: str
    leg_id: Optional[str] = None
    driver_id: Optional[str] = None
    truck_id: Optional[str] = None
    entry_type: str
    quantity: float
    unit: str
    jurisdiction: Optional[str] = None
    recorded_at: datetime
    metadata: Optional[dict] = None

    model_config = {"from_attributes": True}


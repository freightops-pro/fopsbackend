from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MatchingReason(BaseModel):
    label: str
    detail: Optional[str] = None
    weight: float = 0.0


class MatchingSuggestion(BaseModel):
    driver_id: str
    driver_name: Optional[str] = None
    truck_id: Optional[str] = None
    score: float = Field(ge=0, le=100)
    reasons: List[MatchingReason] = Field(default_factory=list)
    eta_available: Optional[datetime] = None
    compliance_score: Optional[float] = None
    average_rating: Optional[float] = None
    completed_loads: Optional[int] = None


class MatchingResponse(BaseModel):
    load_id: str
    generated_at: datetime
    suggestions: List[MatchingSuggestion]


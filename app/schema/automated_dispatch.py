from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class RulePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

class AutomatedDispatchRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    priority: RulePriority = Field(default=RulePriority.NORMAL)
    enabled: bool = Field(default=True)
    conditions: List[str] = Field(..., min_items=1)
    actions: List[str] = Field(..., min_items=1)
    weight: float = Field(default=1.0, ge=0.0, le=10.0)

class AutomatedDispatchRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    priority: Optional[RulePriority] = None
    enabled: Optional[bool] = None
    conditions: Optional[List[str]] = Field(None, min_items=1)
    actions: Optional[List[str]] = Field(None, min_items=1)
    weight: Optional[float] = Field(None, ge=0.0, le=10.0)

class AutomatedDispatchRuleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    priority: RulePriority
    enabled: bool
    conditions: List[str]
    actions: List[str]
    weight: float
    created_at: datetime
    updated_at: datetime
    company_id: int

    class Config:
        from_attributes = True

class DriverMatchRequest(BaseModel):
    load_id: Optional[str] = None
    rules: List[int] = Field(default_factory=list)
    max_matches: int = Field(default=10, ge=1, le=50)

class DriverMatchResponse(BaseModel):
    driver_id: str
    driver_name: str
    score: float = Field(ge=0.0, le=100.0)
    reasons: List[str]
    location: str
    equipment: str
    hours_remaining: float
    performance: float
    estimated_cost: float
    estimated_miles: float
    estimated_fuel_cost: float
    match_factors: Dict[str, Any]

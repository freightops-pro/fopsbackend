from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime

class OnboardingTaskOut(BaseModel):
    id: int
    name: str
    order: int
    completed: bool
    completed_at: Optional[datetime]
    class Config:
        from_attributes = True

class OnboardingFlowOut(BaseModel):
    id: int
    employee_id: str
    employee_name: str
    position: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    tasks: List[OnboardingTaskOut]

    # Backward-compat: coerce int -> str for existing rows (Pydantic v2)
    @field_validator("employee_id", mode="before")
    @classmethod
    def _coerce_employee_id(cls, v):
        return None if v is None else str(v)
    class Config:
        from_attributes = True

class OnboardingFlowCreate(BaseModel):
    employee_id: str
    employee_name: str
    position: Optional[str]

class OnboardingTaskUpdate(BaseModel):
    completed: bool

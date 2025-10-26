from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

class FilterType(str, Enum):
    MULTISELECT = "multiselect"
    SELECT = "select"
    SEARCH = "search"
    DATERANGE = "daterange"
    NUMBER = "number"
    BOOLEAN = "boolean"

class FilterOption(BaseModel):
    id: str
    label: str
    value: str
    count: Optional[int] = 0

class FilterGroupCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    type: FilterType
    options: List[FilterOption] = Field(default_factory=list)
    icon: Optional[str] = None

class FilterGroupUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[FilterType] = None
    options: Optional[List[FilterOption]] = None
    icon: Optional[str] = None

class FilterGroupResponse(BaseModel):
    id: str
    label: str
    type: FilterType
    options: List[FilterOption]
    icon: Optional[str]
    created_at: datetime
    updated_at: datetime
    company_id: int

    class Config:
        from_attributes = True

class SavedFilterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    filters: Dict[str, Any] = Field(..., min_items=1)
    is_global: bool = Field(default=False)

class SavedFilterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    filters: Optional[Dict[str, Any]] = Field(None, min_items=1)
    is_global: Optional[bool] = None

class SavedFilterResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    filters: Dict[str, Any]
    is_global: bool
    created_at: datetime
    updated_at: datetime
    user_id: int
    company_id: int

    class Config:
        from_attributes = True

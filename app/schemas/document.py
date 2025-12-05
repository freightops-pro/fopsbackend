from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DocumentProcessingJobCreate(BaseModel):
    load_id: Optional[str] = None


class DocumentProcessingJobResponse(BaseModel):
    id: str
    company_id: str
    load_id: Optional[str]
    filename: str
    status: str
    raw_text: Optional[str]
    parsed_payload: Optional[Dict[str, Any]]
    field_confidence: Optional[Dict[str, float]]
    errors: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


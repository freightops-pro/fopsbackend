from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

AutomationChannel = Literal["email", "sms", "slack", "in_app"]

AutomationTrigger = Literal[
    "cdl_expiring",
    "medical_card_expiring",
    "permit_expiring",
    "incident_high_severity",
    "ifta_tax_threshold",
    "maintenance_overdue",
]


class AutomationRuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    trigger: AutomationTrigger
    channels: List[AutomationChannel] = Field(..., min_length=1)
    recipients: List[str] = Field(..., min_length=1)
    lead_time_days: Optional[int] = Field(None, ge=0, le=90)
    threshold_value: Optional[float] = None
    escalation_days: Optional[int] = Field(None, ge=0, le=30)


class AutomationRuleCreate(AutomationRuleBase):
    pass


class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    trigger: Optional[AutomationTrigger] = None
    channels: Optional[List[AutomationChannel]] = Field(None, min_length=1)
    recipients: Optional[List[str]] = Field(None, min_length=1)
    lead_time_days: Optional[int] = Field(None, ge=0, le=90)
    threshold_value: Optional[float] = None
    escalation_days: Optional[int] = Field(None, ge=0, le=30)
    is_active: Optional[bool] = None


class AutomationRuleResponse(AutomationRuleBase):
    id: str
    company_id: str
    is_active: bool
    last_triggered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NotificationLogResponse(BaseModel):
    id: str
    rule_id: str
    channel: AutomationChannel
    recipient: str
    status: str
    detail: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


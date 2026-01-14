"""
HQ AI Monitoring Schemas

Master Spec Module 5: AI usage tracking and anomaly detection
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.models.hq_ai_anomaly_alert import AnomalyType, AlertSeverity


# ============================================================================
# AI Usage Log Schemas
# ============================================================================


class AIUsageLogCreate(BaseModel):
    """Schema for creating an AI usage log entry."""

    tenant_id: str = Field(..., serialization_alias="tenantId")
    user_id: Optional[str] = Field(None, serialization_alias="userId")
    operation: str
    model: str
    prompt_tokens: int = Field(..., serialization_alias="promptTokens")
    completion_tokens: int = Field(..., serialization_alias="completionTokens")
    total_cost: float = Field(..., serialization_alias="totalCost")
    latency_ms: int = Field(..., serialization_alias="latencyMs")
    metadata: Optional[dict] = None

    model_config = ConfigDict(populate_by_name=True)


class AIUsageLogResponse(BaseModel):
    """Schema for AI usage log response."""

    id: str
    tenant_id: str = Field(..., serialization_alias="tenantId")
    user_id: Optional[str] = Field(None, serialization_alias="userId")
    operation: str
    model: str
    prompt_tokens: int = Field(..., serialization_alias="promptTokens")
    completion_tokens: int = Field(..., serialization_alias="completionTokens")
    total_tokens: int = Field(..., serialization_alias="totalTokens")
    total_cost: float = Field(..., serialization_alias="totalCost")
    latency_ms: int = Field(..., serialization_alias="latencyMs")
    metadata: Optional[dict] = None
    created_at: datetime = Field(..., serialization_alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AIUsageStatsResponse(BaseModel):
    """Schema for AI usage statistics response."""

    total_requests: int = Field(..., serialization_alias="totalRequests")
    total_tokens: int = Field(..., serialization_alias="totalTokens")
    total_cost: float = Field(..., serialization_alias="totalCost")
    avg_latency_ms: float = Field(..., serialization_alias="avgLatencyMs")
    by_operation: dict = Field(..., serialization_alias="byOperation")
    by_model: dict = Field(..., serialization_alias="byModel")

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# AI Anomaly Alert Schemas
# ============================================================================


class AIAnomalyAlertResponse(BaseModel):
    """Schema for AI anomaly alert response."""

    id: str
    tenant_id: str = Field(..., serialization_alias="tenantId")
    anomaly_type: AnomalyType = Field(..., serialization_alias="anomalyType")
    severity: AlertSeverity
    message: str
    metadata: Optional[dict] = None
    is_resolved: bool = Field(..., serialization_alias="isResolved")
    resolved_at: Optional[datetime] = Field(None, serialization_alias="resolvedAt")
    resolved_by: Optional[str] = Field(None, serialization_alias="resolvedBy")
    created_at: datetime = Field(..., serialization_alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ResolveAnomalyRequest(BaseModel):
    """Schema for resolving an anomaly alert."""

    resolution_notes: Optional[str] = Field(None, serialization_alias="resolutionNotes")

    model_config = ConfigDict(populate_by_name=True)

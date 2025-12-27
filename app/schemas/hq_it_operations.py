"""HQ IT Operations schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


# ============================================================================
# Feature Flags
# ============================================================================

FeatureFlagEnvironmentType = Literal["all", "production", "staging", "development"]


class FeatureFlagBase(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    environment: FeatureFlagEnvironmentType = "development"
    rollout_percentage: int = Field(0, ge=0, le=100)
    target_tenants: List[str] = Field(default_factory=list)


class FeatureFlagCreate(FeatureFlagBase):
    pass


class FeatureFlagUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    environment: Optional[FeatureFlagEnvironmentType] = None
    rollout_percentage: Optional[int] = Field(None, ge=0, le=100)
    target_tenants: Optional[List[str]] = None


class FeatureFlagResponse(FeatureFlagBase):
    id: str
    enabled: bool
    created_by_id: str
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Service Health
# ============================================================================

ServiceTypeType = Literal["internal", "external", "database", "cache"]
ServiceStatusType = Literal["operational", "degraded", "outage"]


class ServiceHealthBase(BaseModel):
    name: str
    service_type: ServiceTypeType
    endpoint: str
    health_check_url: Optional[str] = None
    region: str = "US-East"


class ServiceHealthCreate(ServiceHealthBase):
    pass


class ServiceHealthUpdate(BaseModel):
    name: Optional[str] = None
    health_check_url: Optional[str] = None
    region: Optional[str] = None
    is_active: Optional[bool] = None


class ServiceHealthResponse(ServiceHealthBase):
    id: str
    is_active: bool
    current_status: ServiceStatusType
    current_latency_ms: int
    uptime_30d: float
    last_checked_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ServiceHealthCheckResult(BaseModel):
    """Result of a health check."""
    service_id: str
    status: ServiceStatusType
    latency_ms: int
    error: Optional[str] = None
    checked_at: datetime


# ============================================================================
# Deployments
# ============================================================================

DeploymentEnvironmentType = Literal["production", "staging", "development"]
DeploymentStatusType = Literal["success", "failed", "in_progress", "rolled_back"]


class DeploymentCreate(BaseModel):
    version: str
    environment: DeploymentEnvironmentType
    commit_hash: Optional[str] = None
    changes_count: int = 0


class DeploymentResponse(BaseModel):
    id: str
    version: str
    environment: DeploymentEnvironmentType
    status: DeploymentStatusType
    commit_hash: Optional[str] = None
    changes_count: int
    duration_seconds: Optional[int] = None
    deployed_by_id: str
    deployed_by_name: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    rollback_of_id: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================================
# Background Jobs (from scheduler)
# ============================================================================

JobStatusType = Literal["running", "completed", "failed", "pending"]
JobTypeType = Literal["scheduled", "queued", "recurring"]


class BackgroundJobResponse(BaseModel):
    """Background job status from APScheduler."""
    id: str
    name: str
    job_type: JobTypeType
    status: JobStatusType
    next_run_time: Optional[datetime] = None
    last_run_time: Optional[datetime] = None
    last_duration_seconds: Optional[float] = None
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None


# ============================================================================
# Dashboard Stats
# ============================================================================

class ITOperationsDashboard(BaseModel):
    """IT Operations dashboard summary."""
    services_operational: int
    services_degraded: int
    services_outage: int
    overall_uptime: float
    total_deployments_30d: int
    deployment_success_rate: float
    feature_flags_total: int
    feature_flags_enabled: int
    jobs_running: int
    jobs_failed_24h: int

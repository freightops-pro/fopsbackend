"""HQ IT Operations models for feature flags and system monitoring."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Boolean, Integer, Float, Text, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.core.db import Base


class FeatureFlagEnvironment(str, enum.Enum):
    ALL = "all"
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"


class HQFeatureFlag(Base):
    """Feature flags for controlling feature rollouts."""

    __tablename__ = "hq_feature_flag"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    environment: Mapped[str] = mapped_column(String(20), default="development", nullable=False)
    rollout_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_tenants: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list, nullable=True)
    created_by_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ServiceType(str, enum.Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    DATABASE = "database"
    CACHE = "cache"


class ServiceStatus(str, enum.Enum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OUTAGE = "outage"


class HQServiceHealth(Base):
    """Service health configuration and status tracking."""

    __tablename__ = "hq_service_health"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    service_type: Mapped[str] = mapped_column(String(20), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    health_check_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    region: Mapped[str] = mapped_column(String(50), default="US-East", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    current_status: Mapped[str] = mapped_column(String(20), default="operational", nullable=False)
    current_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    uptime_30d: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class DeploymentStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    ROLLED_BACK = "rolled_back"


class HQDeployment(Base):
    """Deployment history tracking."""

    __tablename__ = "hq_deployment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    commit_hash: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    changes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deployed_by_id: Mapped[str] = mapped_column(String(36), nullable=False)
    deployed_by_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rollback_of_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

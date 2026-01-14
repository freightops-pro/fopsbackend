"""HQ AI Usage and Anomaly models for AI cost monitoring."""

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class AIProvider(str, enum.Enum):
    """Master Spec: AI service provider."""
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    GOOGLE = "GOOGLE"
    AWS_BEDROCK = "AWS_BEDROCK"
    OTHER = "OTHER"


class AnomalyType(str, enum.Enum):
    """Master Spec: Type of AI usage anomaly."""
    COST_SPIKE = "COST_SPIKE"
    USAGE_SPIKE = "USAGE_SPIKE"
    LATENCY_SPIKE = "LATENCY_SPIKE"
    ERROR_RATE_SPIKE = "ERROR_RATE_SPIKE"
    UNUSUAL_PATTERN = "UNUSUAL_PATTERN"


class AnomalySeverity(str, enum.Enum):
    """Master Spec: Severity level of anomaly."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class HQAIUsageLog(Base):
    """Master Spec Module 5: AI usage and cost tracking per tenant."""

    __tablename__ = "hq_ai_usage_log"

    id = Column(String, primary_key=True)

    # Tenant tracking
    tenant_id = Column(String, ForeignKey("hq_tenant.id"), nullable=True, index=True)

    # Provider and model
    provider = Column(
        Enum(AIProvider, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        index=True
    )
    model = Column(String, nullable=False, index=True, comment="e.g., gpt-4, claude-3-opus")

    # Request details
    endpoint = Column(String, nullable=True, comment="API endpoint called")
    feature = Column(String, nullable=True, index=True, comment="Feature that triggered AI call (e.g., dispatch_recommendation)")

    # Usage metrics
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)

    # Cost tracking
    cost_usd = Column(Numeric(10, 6), nullable=False, comment="Cost in USD")

    # Performance metrics
    latency_ms = Column(Integer, nullable=True, comment="Response time in milliseconds")
    is_success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    # Relationships
    tenant = relationship("HQTenant")


class HQAIAnomalyAlert(Base):
    """Master Spec Module 5: AI usage anomaly detection and alerts."""

    __tablename__ = "hq_ai_anomaly_alert"

    id = Column(String, primary_key=True)

    # Tenant tracking
    tenant_id = Column(String, ForeignKey("hq_tenant.id"), nullable=True, index=True)

    # Anomaly classification
    anomaly_type = Column(
        Enum(AnomalyType, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        index=True
    )
    severity = Column(
        Enum(AnomalySeverity, values_callable=lambda enum_class: [e.value for e in enum_class]),
        nullable=False,
        index=True
    )

    # Detection details
    description = Column(Text, nullable=False)
    metric_name = Column(String, nullable=False, comment="Metric that triggered alert (e.g., hourly_cost, error_rate)")
    current_value = Column(Numeric(12, 2), nullable=False)
    expected_value = Column(Numeric(12, 2), nullable=False)
    threshold = Column(Numeric(12, 2), nullable=False, comment="Threshold that was exceeded")

    # Context
    detection_window_hours = Column(Integer, nullable=False, comment="Hours of data analyzed")
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    feature = Column(String, nullable=True)

    # Resolution tracking
    is_resolved = Column(Boolean, nullable=False, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_id = Column(String, ForeignKey("hq_employee.id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)

    # Timestamps
    detected_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    tenant = relationship("HQTenant")
    resolved_by = relationship("HQEmployee")

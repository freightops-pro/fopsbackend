from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Float, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class AIUsageLog(Base):
    """Track AI feature usage per company for billing and rate limiting."""
    __tablename__ = "ai_usage_log"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("user.id"), nullable=True, index=True)

    # Type of AI operation
    operation_type = Column(String, nullable=False, index=True)  # 'ocr', 'chat', 'audit', 'email_parse'

    # Metrics
    tokens_used = Column(Integer, nullable=True)  # For Claude/GPT
    cost_usd = Column(Float, nullable=True)  # Estimated cost

    # Context
    entity_type = Column(String, nullable=True)  # 'load', 'invoice', 'document'
    entity_id = Column(String, nullable=True)

    # Success/failure tracking
    status = Column(String, nullable=False, default="success")  # 'success', 'failed', 'rate_limited'
    error_message = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    # Relationships
    company = relationship("Company")
    user = relationship("User")


class AIUsageQuota(Base):
    """Monthly AI usage quotas per company."""
    __tablename__ = "ai_usage_quota"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, unique=True, index=True)

    # Monthly limits (resets on billing date)
    monthly_ocr_limit = Column(Integer, nullable=False, default=25)  # Free tier: 25 docs/month (AI required)
    monthly_chat_limit = Column(Integer, nullable=False, default=100)  # Free tier: 100 messages/month
    monthly_audit_limit = Column(Integer, nullable=False, default=200)  # Free tier: 200 audits/month

    # Current usage (resets monthly)
    current_month = Column(String, nullable=False)  # Format: "YYYY-MM"
    current_ocr_usage = Column(Integer, nullable=False, default=0)
    current_chat_usage = Column(Integer, nullable=False, default=0)
    current_audit_usage = Column(Integer, nullable=False, default=0)

    # Plan information
    plan_tier = Column(String, nullable=False, default="free")  # 'free', 'starter', 'pro', 'enterprise'
    is_unlimited = Column(String, nullable=False, default="false")  # SQLite-compatible boolean

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company")

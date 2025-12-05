"""Integration models for third-party service connections."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class Integration(Base):
    """Available integration catalog (Samsara, Motive, etc.)."""

    __tablename__ = "integration"

    id = Column(String, primary_key=True)
    integration_key = Column(String, nullable=False, unique=True, index=True)  # e.g., "motive", "samsara"
    display_name = Column(String, nullable=False)  # e.g., "Motive"
    description = Column(Text, nullable=True)
    logo_url = Column(String, nullable=True)  # URL to logo image
    integration_type = Column(String, nullable=False, index=True)  # "eld", "load_board", "accounting", etc.
    auth_type = Column(String, nullable=False)  # "oauth2", "api_key", "basic_auth", "password", "jwt"
    requires_oauth = Column(Boolean, nullable=False, default=False)
    features = Column(JSON, nullable=True)  # List of supported features
    support_email = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company_integrations = relationship("CompanyIntegration", back_populates="integration")


class CompanyIntegration(Base):
    """Company-specific integration connection with credentials."""

    __tablename__ = "company_integration"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    integration_id = Column(String, ForeignKey("integration.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="not-activated")  # "not-activated", "active", "disabled", "error", "pending"
    credentials = Column(JSON, nullable=True)  # Encrypted credentials (API keys, tokens, etc.)
    config = Column(JSON, nullable=True)  # Integration-specific configuration
    last_sync_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_error_at = Column(DateTime, nullable=True)
    last_error_message = Column(Text, nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    auto_sync = Column(Boolean, nullable=False, default=True)
    sync_interval_minutes = Column(Integer, nullable=False, default=60)  # How often to sync
    activated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company", back_populates="integrations")
    integration = relationship("Integration", back_populates="company_integrations")


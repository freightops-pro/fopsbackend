"""
Enterprise-specific SQLAlchemy models
"""

from sqlalchemy import Column, String, Boolean, DateTime, func, ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import relationship
from app.config.db import Base
import uuid

class WhiteLabelConfig(Base):
    __tablename__ = "white_label_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    custom_domain = Column(String, nullable=True)
    custom_logo_url = Column(String, nullable=True)
    custom_css = Column(Text, nullable=True)
    custom_js = Column(Text, nullable=True)
    company_name = Column(String, nullable=True)
    support_email = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Companies", back_populates="white_label_config")

# APIKey model is defined in api_key.py to avoid conflicts

class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    events = Column(JSON, nullable=True)
    secret = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Companies", back_populates="webhooks")

class CustomWorkflow(Base):
    __tablename__ = "custom_workflows"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    trigger_type = Column(String, nullable=False)
    trigger_config = Column(JSON, nullable=True)
    steps = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Companies", back_populates="custom_workflows")

class EnterpriseIntegration(Base):
    __tablename__ = "enterprise_integrations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'erp', 'tms', 'eld', 'load_board', 'factoring'
    config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Companies", back_populates="enterprise_integrations")

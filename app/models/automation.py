from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class AutomationRule(Base):
    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    name = Column(String, nullable=False)
    trigger = Column(String, nullable=False, index=True)
    channels = Column(JSON, nullable=False, default=list)
    recipients = Column(JSON, nullable=False, default=list)

    lead_time_days = Column(Integer, nullable=True)
    threshold_value = Column(Numeric(12, 2), nullable=True)
    escalation_days = Column(Integer, nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    last_triggered_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company", back_populates="automationRules")


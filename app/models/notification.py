from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class NotificationLog(Base):
    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    rule_id = Column(String, ForeignKey("automationrule.id"), nullable=False, index=True)
    channel = Column(String, nullable=False)
    recipient = Column(String, nullable=False)
    status = Column(String, nullable=False, default="sent")
    detail = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    company = relationship("Company")
    rule = relationship("AutomationRule")


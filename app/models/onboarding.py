from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.config.db import Base
import datetime

class OnboardingFlow(Base):
    __tablename__ = "onboarding_flows"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, nullable=False)
    employee_name = Column(String, nullable=False)
    position = Column(String, nullable=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="In Progress")
    tasks = relationship("OnboardingTask", back_populates="flow")

class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"
    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(Integer, ForeignKey("onboarding_flows.id"), nullable=False)
    name = Column(String, nullable=False)
    order = Column(Integer, nullable=False)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    flow = relationship("OnboardingFlow", back_populates="tasks")

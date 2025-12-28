from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, JSON, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class Driver(Base):
    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("user.id"), nullable=True, index=True)
    worker_id = Column(String, ForeignKey("worker.id"), nullable=True, index=True)

    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    phone_carrier = Column(String, nullable=True)

    cdl_number = Column(String, nullable=True)
    cdl_expiration = Column(Date, nullable=True)
    medical_card_expiration = Column(Date, nullable=True)

    profile_metadata = Column("metadata", JSON, nullable=True)
    preference_profile = Column(JSON, nullable=True)
    compliance_score = Column(Float, nullable=True)
    average_rating = Column(Float, nullable=True)
    total_completed_loads = Column(Float, nullable=False, default=0)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company", back_populates="drivers")
    worker = relationship("Worker", foreign_keys=[worker_id], backref="driver_profile")
    incidents = relationship("DriverIncident", back_populates="driver", cascade="all, delete-orphan")
    training_records = relationship("DriverTraining", back_populates="driver", cascade="all, delete-orphan")
    
    # ADD THIS: Relationship to User
    user = relationship("User", back_populates="driver", foreign_keys=[user_id])


class DriverIncident(Base):
    id = Column(String, primary_key=True)
    driver_id = Column(String, ForeignKey("driver.id"), nullable=False, index=True)
    occurred_at = Column(DateTime, nullable=False)
    incident_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    description = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    driver = relationship("Driver", back_populates="incidents")


class DriverTraining(Base):
    id = Column(String, primary_key=True)
    driver_id = Column(String, ForeignKey("driver.id"), nullable=False, index=True)
    course_name = Column(String, nullable=False)
    completed_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    instructor = Column(String, nullable=True)
    notes = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    driver = relationship("Driver", back_populates="training_records")


class DriverDocument(Base):
    __tablename__ = "driver_document"

    id = Column(String, primary_key=True)
    driver_id = Column(String, ForeignKey("driver.id"), nullable=False, index=True)
    document_type = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())

    driver = relationship("Driver")

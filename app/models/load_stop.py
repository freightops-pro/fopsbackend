from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from app.config.db import Base

class LoadStop(Base):
    __tablename__ = "load_stops"
    
    id = Column(String, primary_key=True, index=True)
    load_id = Column(String, ForeignKey("loads.id"), nullable=False)
    stop_type = Column(String, nullable=False)  # pickup, yard, delivery
    business_name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    zip = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    appointment_start = Column(DateTime, nullable=True)
    appointment_end = Column(DateTime, nullable=True)
    driver_assist = Column(Boolean, default=False)
    sequence_number = Column(Integer, nullable=False)
    special_instructions = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    load = relationship("Loads", back_populates="stops")
    start_legs = relationship("LoadLeg", foreign_keys="LoadLeg.start_stop_id", back_populates="start_stop")
    end_legs = relationship("LoadLeg", foreign_keys="LoadLeg.end_stop_id", back_populates="end_stop")


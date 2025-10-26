from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text, Numeric, Float
from sqlalchemy.orm import relationship
from app.config.db import Base
from datetime import datetime

class LoadLeg(Base):
    __tablename__ = "load_legs"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    load_id = Column(String, ForeignKey("simple_loads.id"), nullable=False)
    leg_number = Column(Integer, nullable=False)
    
    # Driver assignment
    driver_id = Column(String, ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    
    # Stop references
    start_stop_id = Column(String, ForeignKey("load_stops.id"), nullable=True)
    end_stop_id = Column(String, ForeignKey("load_stops.id"), nullable=True)
    
    # Location information
    origin = Column(String(255), nullable=False)
    destination = Column(String(255), nullable=False)
    handoff_location = Column(String(255), nullable=True)
    
    # Distance and miles
    miles = Column(Float, nullable=True)
    
    # Timing
    pickup_time = Column(DateTime, nullable=False)
    delivery_time = Column(DateTime, nullable=False)
    actual_pickup_time = Column(DateTime, nullable=True)
    actual_delivery_time = Column(DateTime, nullable=True)
    
    # Status tracking
    status = Column(String(50), default="pending")  # pending, assigned, in_progress, completed, cancelled
    dispatched = Column(Boolean, default=False)
    dispatched_at = Column(DateTime, nullable=True)
    
    # Equipment
    equipment_type = Column(String(100), nullable=True)
    equipment_id = Column(String, ForeignKey("trucks.id"), nullable=True)
    
    # Financial
    leg_rate = Column(Numeric(10, 2), nullable=True)
    driver_pay = Column(Numeric(10, 2), nullable=True)
    
    # Additional information
    notes = Column(Text, nullable=True)
    special_instructions = Column(Text, nullable=True)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Companies", back_populates="load_legs")
    load = relationship("SimpleLoad", back_populates="legs")
    driver = relationship("Users", foreign_keys=[driver_id])
    equipment = relationship("Truck", foreign_keys=[equipment_id])
    start_stop = relationship("LoadStop", foreign_keys=[start_stop_id], back_populates="start_legs")
    end_stop = relationship("LoadStop", foreign_keys=[end_stop_id], back_populates="end_legs")

class TransloadOperation(Base):
    __tablename__ = "transload_operations"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    load_id = Column(String, ForeignKey("simple_loads.id"), nullable=False)
    
    # Facility information
    facility_id = Column(Integer, nullable=False)  # References transload facility
    facility_name = Column(String(255), nullable=False)
    facility_location = Column(String(255), nullable=False)
    
    # Operation details
    operation_type = Column(String(50), default="transload")  # transload, cross_dock, storage
    dock_door = Column(Integer, nullable=True)
    
    # Inbound/Outbound loads
    inbound_leg_id = Column(Integer, ForeignKey("load_legs.id"), nullable=True)
    outbound_leg_id = Column(Integer, ForeignKey("load_legs.id"), nullable=True)
    
    # Timing
    scheduled_start = Column(DateTime, nullable=False)
    scheduled_end = Column(DateTime, nullable=True)
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(50), default="scheduled")  # scheduled, in_progress, completed, cancelled
    
    # Labor and equipment
    labor_assigned = Column(Integer, default=0)
    equipment_staged = Column(Text, nullable=True)  # JSON array of equipment
    
    # Costs
    handling_cost = Column(Numeric(10, 2), nullable=True)
    storage_cost = Column(Numeric(10, 2), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Companies")
    # load = relationship("SimpleLoad")  # Temporarily commented out
    inbound_leg = relationship("LoadLeg", foreign_keys=[inbound_leg_id])
    outbound_leg = relationship("LoadLeg", foreign_keys=[outbound_leg_id])

class TransloadFacility(Base):
    __tablename__ = "transload_facilities"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    
    # Facility details
    name = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    
    # Capacity
    capacity = Column(Integer, nullable=False)  # Number of loads
    dock_doors = Column(Integer, nullable=False)
    
    # Contact information
    contact_name = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    contact_email = Column(String(255), nullable=True)
    
    # Services
    services = Column(Text, nullable=True)  # JSON array of services offered
    operating_hours = Column(Text, nullable=True)  # JSON object with hours
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Companies")

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class Load(Base):
    __tablename__ = "freight_load"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    customer_name = Column(String, nullable=False)
    load_type = Column(String, nullable=False)
    commodity = Column(String, nullable=False)
    base_rate = Column(Numeric(12, 2), nullable=False)
    status = Column(String, nullable=False, default="draft")
    notes = Column(String, nullable=True)

    # Container-specific fields
    container_number = Column(String, nullable=True)
    container_size = Column(String, nullable=True)
    container_type = Column(String, nullable=True)
    vessel_name = Column(String, nullable=True)
    voyage_number = Column(String, nullable=True)
    origin_port_code = Column(String, nullable=True)
    destination_port_code = Column(String, nullable=True)
    drayage_appointment = Column(String, nullable=True)
    customs_hold = Column(String, nullable=True)
    customs_reference = Column(String, nullable=True)

    # Port appointment fields (ePass/entry code from port system)
    port_appointment_id = Column(String, nullable=True)  # Port's internal appointment ID
    port_appointment_number = Column(String, nullable=True)  # Confirmation number (e.g., APT-12345)
    port_entry_code = Column(String, nullable=True)  # Code driver enters at gate keypad
    port_appointment_time = Column(DateTime, nullable=True)  # Scheduled appointment time
    port_appointment_gate = Column(String, nullable=True)  # Which gate to use
    port_appointment_status = Column(String, nullable=True)  # SCHEDULED, USED, EXPIRED, CANCELLED
    port_appointment_terminal = Column(String, nullable=True)  # Terminal name

    metadata_json = Column("metadata", JSON, nullable=True)
    required_skills = Column(JSON, nullable=True)
    preferred_driver_ids = Column(JSON, nullable=True)
    preferred_truck_ids = Column(JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    stops = relationship("LoadStop", back_populates="load", cascade="all, delete-orphan", order_by="LoadStop.sequence")


class LoadStop(Base):
    __tablename__ = "freight_load_stop"

    id = Column(String, primary_key=True)
    load_id = Column(String, ForeignKey("freight_load.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    stop_type = Column(String, nullable=False)  # pickup, drop, checkpoint
    location_name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    instructions = Column(String, nullable=True)
    metadata_json = Column("metadata", JSON, nullable=True)
    distance_miles = Column(Float, nullable=True)
    fuel_estimate_gallons = Column(Float, nullable=True)
    dwell_minutes_estimate = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    load = relationship("Load", back_populates="stops")


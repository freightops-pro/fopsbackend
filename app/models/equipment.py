from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class Equipment(Base):
    __tablename__ = "fleet_equipment"
    __table_args__ = (
        UniqueConstraint("company_id", "unit_number", name="uq_equipment_company_unit_number"),
        # VIN uniqueness is enforced via partial index in DB (only when VIN is not null/empty)
    )

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    unit_number = Column(String, nullable=False)
    equipment_type = Column(String, nullable=False)  # TRACTOR, TRAILER, etc.
    status = Column(String, nullable=False, default="ACTIVE")
    operational_status = Column(String, nullable=True)

    make = Column(String, nullable=True)
    model = Column(String, nullable=True)
    year = Column(Integer, nullable=True)
    vin = Column(String, nullable=True)

    current_mileage = Column(Integer, nullable=True)
    current_engine_hours = Column(Float, nullable=True)

    gps_provider = Column(String, nullable=True)
    gps_device_id = Column(String, nullable=True)
    eld_provider = Column(String, nullable=True)
    eld_device_id = Column(String, nullable=True)

    assigned_driver_id = Column(String, nullable=True)
    assigned_truck_id = Column(String, nullable=True)

    # Owner operator support - links equipment to contractor who owns it
    owner_id = Column(String, ForeignKey("worker.id"), nullable=True, index=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    usage_events = relationship(
        "EquipmentUsageEvent",
        back_populates="equipment",
        cascade="all, delete-orphan",
        order_by="desc(EquipmentUsageEvent.recorded_at)",
    )
    maintenance_events = relationship(
        "EquipmentMaintenanceEvent",
        back_populates="equipment",
        cascade="all, delete-orphan",
        order_by="desc(EquipmentMaintenanceEvent.service_date)",
    )
    maintenance_forecasts = relationship(
        "EquipmentMaintenanceForecast",
        back_populates="equipment",
        cascade="all, delete-orphan",
        order_by="desc(EquipmentMaintenanceForecast.generated_at)",
    )


class EquipmentUsageEvent(Base):
    __tablename__ = "fleet_equipment_usage"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    equipment_id = Column(String, ForeignKey("fleet_equipment.id"), nullable=False, index=True)

    recorded_at = Column(DateTime, nullable=False, server_default=func.now())
    source = Column(String, nullable=True)  # manual, telematics, import
    odometer = Column(Integer, nullable=True)
    engine_hours = Column(Float, nullable=True)
    notes = Column(String, nullable=True)

    equipment = relationship("Equipment", back_populates="usage_events")


class EquipmentMaintenanceEvent(Base):
    __tablename__ = "fleet_equipment_maintenance"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    equipment_id = Column(String, ForeignKey("fleet_equipment.id"), nullable=False, index=True)

    service_type = Column(String, nullable=False)
    service_date = Column(Date, nullable=False)
    vendor = Column(String, nullable=True)
    odometer = Column(Integer, nullable=True)
    engine_hours = Column(Float, nullable=True)
    cost = Column(Numeric(12, 2), nullable=True)
    notes = Column(String, nullable=True)

    next_due_date = Column(Date, nullable=True)
    next_due_mileage = Column(Integer, nullable=True)
    invoice_id = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    equipment = relationship("Equipment", back_populates="maintenance_events")
    forecasts = relationship(
        "EquipmentMaintenanceForecast",
        back_populates="basis_event",
        cascade="all, delete-orphan",
    )


class EquipmentMaintenanceForecast(Base):
    __tablename__ = "fleet_maintenance_forecast"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    equipment_id = Column(String, ForeignKey("fleet_equipment.id"), nullable=False, index=True)
    basis_event_id = Column(String, ForeignKey("fleet_equipment_maintenance.id"), nullable=True, index=True)

    service_type = Column(String, nullable=False)
    status = Column(String, nullable=False)  # OK, DUE_SOON, OVERDUE
    projected_service_date = Column(Date, nullable=True)
    projected_service_mileage = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=False, default=0.5)
    risk_score = Column(Float, nullable=False, default=0.0)
    notes = Column(String, nullable=True)

    generated_at = Column(DateTime, nullable=False, server_default=func.now())

    equipment = relationship("Equipment", back_populates="maintenance_forecasts")
    basis_event = relationship("EquipmentMaintenanceEvent", back_populates="forecasts")


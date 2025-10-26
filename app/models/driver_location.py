from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.config.db import Base


class DriverLocationHistory(Base):
    """Model for tracking driver location history"""
    __tablename__ = "driver_location_history"

    id = Column(Integer, primary_key=True, index=True)
    
    # Driver relationship
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, index=True)
    driver = relationship("Driver", foreign_keys=[driver_id])
    
    # Company relationship for multi-tenant isolation
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    company = relationship("Companies")
    
    # Location data
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float, nullable=False)  # Meters
    speed = Column(Float, nullable=True)  # MPH
    heading = Column(Float, nullable=True)  # Degrees (0-360)
    altitude = Column(Float, nullable=True)  # Meters
    
    # Status
    is_moving = Column(Boolean, default=False)
    is_on_duty = Column(Boolean, default=True)
    
    # Load context (if driver is on active load)
    load_id = Column(Integer, ForeignKey("simple_loads.id"), nullable=True)
    load = relationship("SimpleLoad")
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_driver_location_timestamp', 'driver_id', 'timestamp'),
        Index('idx_driver_location_company', 'company_id', 'timestamp'),
        Index('idx_driver_location_load', 'load_id', 'timestamp'),
    )


class DriverConnectionLog(Base):
    """Model for tracking driver WebSocket connection history"""
    __tablename__ = "driver_connection_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Driver relationship
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, index=True)
    driver = relationship("Driver", foreign_keys=[driver_id])
    
    # Company relationship
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    company = relationship("Companies")
    
    # Connection details
    connected_at = Column(DateTime(timezone=True), nullable=False)
    disconnected_at = Column(DateTime(timezone=True), nullable=True)
    session_duration = Column(Integer, nullable=True)  # Seconds
    
    # Connection metadata
    connection_type = Column(String(20), default="websocket")  # websocket, rest_api, mobile_app
    device_info = Column(Text, nullable=True)  # JSON string with device details
    app_version = Column(String(20), nullable=True)
    
    # Disconnection details
    disconnect_reason = Column(String(50), nullable=True)  # normal, timeout, error, network_loss
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_driver_connection_timestamp', 'driver_id', 'connected_at'),
        Index('idx_driver_connection_company', 'company_id', 'connected_at'),
        Index('idx_driver_connection_active', 'driver_id', 'disconnected_at'),
    )

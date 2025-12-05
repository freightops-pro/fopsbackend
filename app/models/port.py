from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class Port(Base):
    """Port information and configuration."""
    __tablename__ = "port"

    id = Column(String, primary_key=True)
    port_code = Column(String, nullable=False, unique=True, index=True)  # UN/LOCODE format (e.g., USNYC)
    port_name = Column(String, nullable=False)
    unlocode = Column(String, nullable=True)  # UN/LOCODE
    region = Column(String, nullable=True)  # e.g., "East Coast", "West Coast"
    state = Column(String, nullable=True)  # US state code
    country = Column(String, nullable=False, default="US")
    services_supported = Column(JSON, nullable=True)  # List of supported services
    adapter_class = Column(String, nullable=True)  # Which adapter to use
    auth_type = Column(String, nullable=True)  # oauth2, api_key, basic_auth, etc.
    rate_limits = Column(JSON, nullable=True)  # Rate limiting config
    compliance_standards = Column(JSON, nullable=True)  # Compliance standards
    logo_url = Column(String, nullable=True)  # URL to port logo image
    is_active = Column(String, nullable=False, default="true")
    
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    integrations = relationship("PortIntegration", back_populates="port", cascade="all, delete-orphan")


class PortIntegration(Base):
    """Company-specific port integration credentials and configuration."""
    __tablename__ = "port_integration"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    port_id = Column(String, ForeignKey("port.id"), nullable=False, index=True)
    
    # Encrypted credentials (JSON format)
    credentials_json = Column("credentials", JSON, nullable=True)  # API keys, tokens, etc.
    config_json = Column("config", JSON, nullable=True)  # Integration-specific config
    
    status = Column(String, nullable=False, default="pending")  # active, disabled, error, pending
    last_sync_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_error_at = Column(DateTime, nullable=True)
    last_error_message = Column(Text, nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    auto_sync = Column(String, nullable=False, default="true")
    sync_interval_minutes = Column(Integer, nullable=False, default=60)
    activated_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    port = relationship("Port", back_populates="integrations")
    container_trackings = relationship("ContainerTracking", back_populates="integration", cascade="all, delete-orphan")


class ContainerTracking(Base):
    """Container status snapshots linked to loads."""
    __tablename__ = "container_tracking"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    load_id = Column(String, ForeignKey("freight_load.id"), nullable=True, index=True)  # Nullable for tracking without load
    port_integration_id = Column(String, ForeignKey("port_integration.id"), nullable=True, index=True)
    
    container_number = Column(String, nullable=False, index=True)
    port_code = Column(String, nullable=False, index=True)
    terminal = Column(String, nullable=True)
    
    # Status information
    status = Column(String, nullable=False)  # AVAILABLE, IN_TRANSIT, ON_VESSEL, HELD, etc.
    location = Column(JSON, nullable=True)  # {terminal, yard_location, gate_status, etc.}
    
    # Vessel information
    vessel = Column(JSON, nullable=True)  # {name, voyage, eta, etc.}
    
    # Dates
    dates = Column(JSON, nullable=True)  # {discharge_date, last_free_day, return_by_date, etc.}
    
    # Container details
    container_details = Column(JSON, nullable=True)  # {size, type, weight, seal_number, etc.}
    
    # Holds and charges
    holds = Column(JSON, nullable=True)  # List of hold types
    charges = Column(JSON, nullable=True)  # {demurrage, per_diem, last_free_day, etc.}
    
    # Metadata
    raw_data = Column(JSON, nullable=True)  # Raw response from port API
    last_updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    integration = relationship("PortIntegration", back_populates="container_trackings")
    events = relationship("ContainerTrackingEvent", back_populates="tracking", cascade="all, delete-orphan", order_by="ContainerTrackingEvent.event_timestamp")


class ContainerTrackingEvent(Base):
    """Individual events in container lifecycle."""
    __tablename__ = "container_tracking_event"

    id = Column(String, primary_key=True)
    container_tracking_id = Column(String, ForeignKey("container_tracking.id"), nullable=False, index=True)
    
    event_type = Column(String, nullable=False)  # DISCHARGE, INGATE, OUTGATE, HOLD_PLACED, etc.
    event_timestamp = Column(DateTime, nullable=False, index=True)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    event_metadata = Column(JSON, nullable=True)  # Additional event-specific data
    
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    
    tracking = relationship("ContainerTracking", back_populates="events")


from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.config.db import Base


class Location(Base):
    """Model for managing multiple company locations/terminals"""
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    
    # Company relationship
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    company = relationship("Companies", back_populates="locations")
    
    # Location details
    name = Column(String(100), nullable=False)  # e.g., "Main Terminal", "West Coast Office"
    location_type = Column(String(50), nullable=False)  # terminal, office, warehouse, yard
    address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(50), nullable=False)
    zip_code = Column(String(20), nullable=False)
    country = Column(String(50), default="US")
    
    # Contact information
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    contact_person = Column(String(100), nullable=True)
    
    # Operational details
    is_active = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)  # Primary location for company
    timezone = Column(String(50), default="UTC")
    
    # Capacity and facilities
    capacity_trucks = Column(Integer, nullable=True)  # Truck parking capacity
    capacity_trailers = Column(Integer, nullable=True)  # Trailer storage capacity
    has_fuel_island = Column(Boolean, default=False)
    has_scale = Column(Boolean, default=False)
    has_shop = Column(Boolean, default=False)
    has_office = Column(Boolean, default=False)
    
    # Geographic coordinates
    latitude = Column(String(20), nullable=True)
    longitude = Column(String(20), nullable=True)
    
    # Additional metadata
    notes = Column(Text, nullable=True)
    operating_hours = Column(JSON, nullable=True)  # Store as JSON
    facilities = Column(JSON, nullable=True)  # Additional facilities
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    drivers = relationship("Driver", back_populates="home_location")
    vehicles = relationship("Truck", back_populates="home_location")
    loads_pickup = relationship("Loads", foreign_keys="Loads.pickupLocationId", back_populates="pickup_location")
    loads_delivery = relationship("Loads", foreign_keys="Loads.deliveryLocationId", back_populates="delivery_location")
    company = relationship("Companies", back_populates="locations")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_company_locations', 'company_id', 'is_active'),
        Index('idx_company_primary', 'company_id', 'is_primary'),
        Index('idx_location_type', 'location_type', 'is_active'),
    )


class LocationUser(Base):
    """Model for managing user access to specific locations"""
    __tablename__ = "location_users"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relationships
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    location = relationship("Location")
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    user = relationship("Users", foreign_keys=[user_id])
    
    # Access permissions
    can_view = Column(Boolean, default=True)
    can_edit = Column(Boolean, default=False)
    can_manage = Column(Boolean, default=False)  # Full management access
    can_dispatch = Column(Boolean, default=False)  # Dispatch loads from this location
    can_view_financials = Column(Boolean, default=False)  # View location P&L
    
    # Assignment details
    is_primary_location = Column(Boolean, default=False)  # User's primary location
    assigned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    assigned_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    assigned_by = relationship("Users", foreign_keys=[assigned_by_id])
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Unique constraint
    __table_args__ = (
        Index('idx_location_user_unique', 'location_id', 'user_id', unique=True),
        Index('idx_user_locations', 'user_id', 'is_primary_location'),
    )


class LocationEquipment(Base):
    """Model for tracking equipment assigned to locations"""
    __tablename__ = "location_equipment"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relationships
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    location = relationship("Location")
    vehicle_id = Column(String, ForeignKey("trucks.id"), nullable=False)
    vehicle = relationship("Truck")
    
    # Assignment details
    assigned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    assigned_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    assigned_by = relationship("Users")
    
    # Status
    is_active = Column(Boolean, default=True)
    status = Column(String(20), default="assigned")  # assigned, maintenance, out_of_service
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Unique constraint - one vehicle can only be at one location
    __table_args__ = (
        Index('idx_location_vehicle_unique', 'vehicle_id', 'is_active', unique=True, postgresql_where=Column('is_active') == True),
        Index('idx_location_equipment', 'location_id', 'is_active'),
    )


class LocationFinancials(Base):
    """Model for tracking financial metrics per location"""
    __tablename__ = "location_financials"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relationships
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    location = relationship("Location")
    
    # Financial period
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    period_type = Column(String(20), default="monthly")  # daily, weekly, monthly, yearly
    
    # Revenue metrics
    total_revenue = Column(Integer, default=0)  # Revenue in cents
    load_count = Column(Integer, default=0)
    average_rate = Column(Integer, default=0)  # Average rate per load in cents
    
    # Expense metrics
    fuel_cost = Column(Integer, default=0)
    maintenance_cost = Column(Integer, default=0)
    driver_pay = Column(Integer, default=0)
    overhead_cost = Column(Integer, default=0)
    total_expenses = Column(Integer, default=0)
    
    # Profitability
    gross_profit = Column(Integer, default=0)
    net_profit = Column(Integer, default=0)
    profit_margin = Column(Integer, default=0)  # Percentage * 100 (e.g., 1500 = 15%)
    
    # Operational metrics
    trucks_utilized = Column(Integer, default=0)
    trailers_utilized = Column(Integer, default=0)
    driver_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Indexes
    __table_args__ = (
        Index('idx_location_period', 'location_id', 'period_start', 'period_end'),
        Index('idx_location_period_type', 'location_id', 'period_type'),
    )


class InterLocationTransfer(Base):
    """Model for tracking equipment transfers between locations"""
    __tablename__ = "inter_location_transfers"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relationships
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    from_location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    from_location = relationship("Location", foreign_keys=[from_location_id])
    to_location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    to_location = relationship("Location", foreign_keys=[to_location_id])
    vehicle_id = Column(String, ForeignKey("trucks.id"), nullable=False)
    vehicle = relationship("Truck")
    
    # Transfer details
    transfer_date = Column(DateTime(timezone=True), nullable=False)
    scheduled_date = Column(DateTime(timezone=True), nullable=True)
    completed_date = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    status = Column(String(20), default="scheduled")  # scheduled, in_transit, completed, cancelled
    
    # Personnel
    driver_id = Column(String, ForeignKey("drivers.id"), nullable=True)
    driver = relationship("Driver")
    requested_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    requested_by = relationship("Users", foreign_keys=[requested_by_id])
    approved_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    approved_by = relationship("Users", foreign_keys=[approved_by_id])
    
    # Transfer metadata
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    estimated_cost = Column(Integer, nullable=True)  # Cost in cents
    actual_cost = Column(Integer, nullable=True)  # Cost in cents
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Indexes
    __table_args__ = (
        Index('idx_company_transfers', 'company_id', 'transfer_date'),
        Index('idx_vehicle_transfers', 'vehicle_id', 'status'),
        Index('idx_location_transfers', 'from_location_id', 'to_location_id'),
    )

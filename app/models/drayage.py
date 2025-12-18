"""
Drayage Module Data Models.

Extends FreightOps for container drayage operations:
- Container lifecycle (booking → availability → pickup → delivery → return)
- Steamship line integration with free time rules
- Chassis pool management
- Demurrage/per diem tracking
- Port terminal configurations
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Float,
    Integer,
    Boolean,
    JSON,
    Numeric,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


# ==================== STEAMSHIP LINE ====================


class SteamshipLine(Base):
    """
    Steamship line (SSL) configuration and API credentials.

    Stores carrier-specific settings for:
    - API integration (container tracking, booking, etc.)
    - Free time rules (port/rail demurrage, detention)
    - Contact information
    """

    __tablename__ = "drayage_steamship_line"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("company.id"), index=True)

    # Carrier identification
    scac_code: Mapped[str] = mapped_column(String(4), index=True)  # Standard Carrier Alpha Code
    name: Mapped[str] = mapped_column(String(255))
    short_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "MSC", "CMA"
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # API Configuration
    api_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # maersk, msc, cma_cgm, hapag, etc.
    api_base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_credentials: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Encrypted in production
    api_status: Mapped[str] = mapped_column(String(50), default="not_configured")  # configured, active, error

    # Free Time Rules (defaults, can be overridden per container)
    port_free_days: Mapped[int] = mapped_column(Integer, default=4)  # Port demurrage free days
    rail_free_days: Mapped[int] = mapped_column(Integer, default=2)  # Rail ramp free days
    detention_free_days: Mapped[int] = mapped_column(Integer, default=4)  # Equipment detention free days
    weekend_counts: Mapped[bool] = mapped_column(Boolean, default=False)  # Does weekend count toward free time?
    holiday_counts: Mapped[bool] = mapped_column(Boolean, default=False)  # Do holidays count?

    # Demurrage rates (USD per day, tiered)
    demurrage_rate_tier1: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)  # Days 1-5
    demurrage_rate_tier2: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)  # Days 6-10
    demurrage_rate_tier3: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)  # Days 11+
    detention_rate_per_day: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Per diem (port storage) - varies by container size
    per_diem_rate_20: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    per_diem_rate_40: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    per_diem_rate_45: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Contact Information
    customer_service_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    customer_service_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    equipment_return_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    demurrage_dispute_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    containers = relationship("DrayageContainer", back_populates="steamship_line")

    __table_args__ = (
        UniqueConstraint("company_id", "scac_code", name="uq_ssl_company_scac"),
        Index("ix_ssl_company_active", "company_id", "is_active"),
    )


# ==================== CHASSIS POOL ====================


class ChassisPool(Base):
    """
    Chassis pool provider configuration.

    Major pools: DCLI, TRAC, Flexi-Van
    Tracks per diem rates and pool-specific restrictions.
    """

    __tablename__ = "drayage_chassis_pool"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("company.id"), index=True)

    # Pool identification
    pool_code: Mapped[str] = mapped_column(String(20), index=True)  # DCLI, TRAC, FLXV, etc.
    name: Mapped[str] = mapped_column(String(255))
    provider_type: Mapped[str] = mapped_column(String(50))  # pool, private, ssl_provided

    # API Configuration
    api_base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_credentials: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    api_status: Mapped[str] = mapped_column(String(50), default="not_configured")

    # Per Diem Rates (USD per day)
    per_diem_rate_20: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    per_diem_rate_40: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    per_diem_rate_45: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    per_diem_rate_reefer: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Free time
    free_days: Mapped[int] = mapped_column(Integer, default=1)  # Usually 1 day split
    split_free_time: Mapped[bool] = mapped_column(Boolean, default=True)  # 1 day pick, 1 day return

    # Pool restrictions
    allowed_terminals: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # List of terminal codes
    restricted_steamship_lines: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    operating_regions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # [LA, NYC, SAV, etc.]

    # Billing
    billing_contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    billing_portal_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    chassis_usages = relationship("ChassisUsage", back_populates="chassis_pool")

    __table_args__ = (
        UniqueConstraint("company_id", "pool_code", name="uq_chassis_company_pool"),
    )


# ==================== TERMINAL ====================


class Terminal(Base):
    """
    Port terminal configuration for drayage operations.

    Stores appointment system details, operating hours, and cut-off times.
    """

    __tablename__ = "drayage_terminal"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("company.id"), index=True)

    # Terminal identification
    port_code: Mapped[str] = mapped_column(String(10), index=True)  # USLAX, USLGB, etc.
    terminal_code: Mapped[str] = mapped_column(String(20), index=True)  # TRAPAC, LBCT, PNCT, etc.
    firms_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # US Customs FIRMS code
    name: Mapped[str] = mapped_column(String(255))

    # Appointment System
    appointment_system: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # advent, tideworks, n4, etc.
    appointment_lead_time_hours: Mapped[int] = mapped_column(Integer, default=24)  # Min hours in advance
    appointment_window_minutes: Mapped[int] = mapped_column(Integer, default=60)  # Appointment window
    dual_transaction_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    same_day_appointments: Mapped[bool] = mapped_column(Boolean, default=False)

    # Operating Hours (JSON: {"mon": {"open": "07:00", "close": "17:00"}, ...})
    gate_hours: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    first_shift: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # "07:00-15:00"
    second_shift: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # "15:00-23:00"
    third_shift: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # "23:00-07:00"

    # Cut-off Times
    vessel_cutoff_hours: Mapped[int] = mapped_column(Integer, default=48)  # Hours before vessel departure
    reefer_cutoff_hours: Mapped[int] = mapped_column(Integer, default=72)  # Reefers need more lead time
    hazmat_cutoff_hours: Mapped[int] = mapped_column(Integer, default=96)  # Hazmat even more

    # Turn Times (average minutes)
    avg_turn_time_import: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_turn_time_export: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_turn_time_dual: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Contact Information
    dispatch_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    trouble_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    gate_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # API Credentials (terminal-specific, separate from port adapter)
    api_credentials: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    api_status: Mapped[str] = mapped_column(String(50), default="not_configured")

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    appointments = relationship("DrayageAppointment", back_populates="terminal")
    containers = relationship("DrayageContainer", back_populates="terminal")

    __table_args__ = (
        UniqueConstraint("company_id", "terminal_code", name="uq_terminal_company_code"),
        Index("ix_terminal_port", "port_code", "terminal_code"),
    )


# ==================== DRAYAGE CONTAINER ====================


class DrayageContainer(Base):
    """
    Container for drayage operations with full lifecycle tracking.

    Lifecycle: BOOKING → RELEASED → AVAILABLE → DISPATCHED → PICKED_UP →
               DELIVERED → EMPTY → RETURNED

    Links to Load for dispatch, but maintains independent container data.
    """

    __tablename__ = "drayage_container"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("company.id"), index=True)
    load_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("freight_load.id"), nullable=True, index=True)

    # Container identification
    container_number: Mapped[str] = mapped_column(String(20), index=True)
    container_size: Mapped[str] = mapped_column(String(10))  # 20, 40, 40HC, 45, etc.
    container_type: Mapped[str] = mapped_column(String(20))  # DRY, REEFER, FLAT, TANK, etc.
    is_hazmat: Mapped[bool] = mapped_column(Boolean, default=False)
    hazmat_class: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_overweight: Mapped[bool] = mapped_column(Boolean, default=False)
    gross_weight_lbs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # References
    booking_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    bill_of_lading: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    house_bill: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    seal_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Customer PO, etc.

    # Steamship Line
    steamship_line_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("drayage_steamship_line.id"), nullable=True, index=True
    )
    ssl_scac: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)  # Denormalized for quick access

    # Terminal/Port
    terminal_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("drayage_terminal.id"), nullable=True, index=True
    )
    port_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    terminal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Vessel Information
    vessel_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    voyage_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vessel_eta: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    vessel_ata: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # Actual arrival

    # Container Lifecycle Status
    status: Mapped[str] = mapped_column(String(30), default="BOOKING", index=True)
    # BOOKING, RELEASED, AVAILABLE, HOLD, DISPATCHED, PICKED_UP, IN_TRANSIT,
    # DELIVERED, EMPTY, RETURNED, CANCELLED

    # Critical Dates
    discharge_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_free_day: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)  # LFD - CRITICAL!
    per_diem_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    detention_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    empty_return_by: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Pickup Information
    pickup_terminal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pickup_appointment_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    pickup_scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pickup_actual_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    outgate_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Delivery Information
    delivery_location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    delivery_appointment_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivery_actual_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Empty Return Information
    return_terminal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    return_appointment_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    return_scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    return_actual_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ingate_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Chassis Information
    chassis_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    chassis_pool_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    chassis_pool_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    chassis_outgate_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    chassis_return_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Holds (JSON list: ["CUSTOMS", "FREIGHT", "USDA", "FDA", "TERMINAL"])
    holds: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    hold_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Financials (calculated)
    demurrage_days: Mapped[int] = mapped_column(Integer, default=0)
    demurrage_amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    per_diem_days: Mapped[int] = mapped_column(Integer, default=0)
    per_diem_amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    detention_days: Mapped[int] = mapped_column(Integer, default=0)
    detention_amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    chassis_per_diem_amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    total_accessorial_charges: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Raw port data (from container tracking)
    port_raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    steamship_line = relationship("SteamshipLine", back_populates="containers")
    terminal = relationship("Terminal", back_populates="containers")
    appointments = relationship("DrayageAppointment", back_populates="container")
    charges = relationship("DrayageCharge", back_populates="container")
    chassis_usages = relationship("ChassisUsage", back_populates="container")
    events = relationship("DrayageEvent", back_populates="container", order_by="DrayageEvent.event_at")

    __table_args__ = (
        Index("ix_container_company_status", "company_id", "status"),
        Index("ix_container_lfd", "company_id", "last_free_day"),
        Index("ix_container_ssl", "company_id", "ssl_scac"),
    )


# ==================== DRAYAGE APPOINTMENT ====================


class DrayageAppointment(Base):
    """
    Port terminal appointment for pickup or return.

    Tracks appointment lifecycle and supports dual transactions.
    """

    __tablename__ = "drayage_appointment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("company.id"), index=True)
    container_id: Mapped[str] = mapped_column(String(36), ForeignKey("drayage_container.id"), index=True)
    terminal_id: Mapped[str] = mapped_column(String(36), ForeignKey("drayage_terminal.id"), index=True)

    # Appointment type
    appointment_type: Mapped[str] = mapped_column(String(20))  # PICKUP, RETURN, DUAL
    transaction_type: Mapped[str] = mapped_column(String(20))  # IMPORT_PICKUP, EXPORT_RETURN, EMPTY_RETURN

    # Port appointment reference
    port_appointment_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    port_confirmation_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    port_entry_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Gate keypad code

    # Scheduling
    scheduled_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    scheduled_window_start: Mapped[datetime] = mapped_column(DateTime)
    scheduled_window_end: Mapped[datetime] = mapped_column(DateTime)
    shift: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # 1ST, 2ND, 3RD

    # Actual times
    gate_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    gate_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_turn_time_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Driver/Equipment assignment
    driver_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    truck_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    truck_license: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    driver_license: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="SCHEDULED")
    # SCHEDULED, CONFIRMED, IN_PROGRESS, COMPLETED, CANCELLED, MISSED, RESCHEDULED

    # Dual transaction (for picking up import + dropping off empty in one trip)
    is_dual_transaction: Mapped[bool] = mapped_column(Boolean, default=False)
    dual_container_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    dual_container_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    port_raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    container = relationship("DrayageContainer", back_populates="appointments")
    terminal = relationship("Terminal", back_populates="appointments")

    __table_args__ = (
        Index("ix_appointment_schedule", "company_id", "scheduled_date", "status"),
    )


# ==================== DRAYAGE CHARGE ====================


class DrayageCharge(Base):
    """
    Demurrage, per diem, detention, and other drayage-related charges.

    Tracks charges at container level with detailed breakdown.
    """

    __tablename__ = "drayage_charge"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("company.id"), index=True)
    container_id: Mapped[str] = mapped_column(String(36), ForeignKey("drayage_container.id"), index=True)

    # Charge type
    charge_type: Mapped[str] = mapped_column(String(30))
    # DEMURRAGE, PER_DIEM, DETENTION, CHASSIS_PER_DIEM, FLIP, STORAGE,
    # EXAM_FEE, REEFER_FUEL, OVERWEIGHT, HAZMAT, PRE_PULL, YARD_STORAGE

    # Charge details
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(30))  # SSL, TERMINAL, CHASSIS_POOL, TRUCKING_CO

    # Date range
    charge_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    charge_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    chargeable_days: Mapped[int] = mapped_column(Integer, default=0)

    # Rate and amount
    rate_per_day: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    rate_tier: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # TIER1, TIER2, TIER3
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=1)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))

    # Status
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    # PENDING, INVOICED, DISPUTED, WAIVED, PAID

    # Invoice reference
    invoice_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    container = relationship("DrayageContainer", back_populates="charges")

    __table_args__ = (
        Index("ix_charge_type_status", "company_id", "charge_type", "status"),
    )


# ==================== CHASSIS USAGE ====================


class ChassisUsage(Base):
    """
    Tracks chassis usage per container for per diem billing.
    """

    __tablename__ = "drayage_chassis_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("company.id"), index=True)
    container_id: Mapped[str] = mapped_column(String(36), ForeignKey("drayage_container.id"), index=True)
    chassis_pool_id: Mapped[str] = mapped_column(String(36), ForeignKey("drayage_chassis_pool.id"), index=True)

    # Chassis details
    chassis_number: Mapped[str] = mapped_column(String(20), index=True)
    chassis_size: Mapped[str] = mapped_column(String(10))  # 20, 40, 45
    chassis_type: Mapped[str] = mapped_column(String(20))  # STANDARD, EXTENDABLE, REEFER, FLATBED

    # Usage period
    outgate_terminal: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    outgate_at: Mapped[datetime] = mapped_column(DateTime)
    ingate_terminal: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ingate_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Billing
    free_days: Mapped[int] = mapped_column(Integer, default=1)
    chargeable_days: Mapped[int] = mapped_column(Integer, default=0)
    rate_per_day: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    total_amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE, RETURNED, INVOICED

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    container = relationship("DrayageContainer", back_populates="chassis_usages")
    chassis_pool = relationship("ChassisPool", back_populates="chassis_usages")


# ==================== DRAYAGE EVENT ====================


class DrayageEvent(Base):
    """
    Container event timeline for drayage operations.

    Tracks every milestone in the container lifecycle.
    """

    __tablename__ = "drayage_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("company.id"), index=True)
    container_id: Mapped[str] = mapped_column(String(36), ForeignKey("drayage_container.id"), index=True)

    # Event details
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    # VESSEL_ARRIVAL, DISCHARGE, AVAILABLE, HOLD_PLACED, HOLD_RELEASED,
    # LFD_SET, LFD_EXTENDED, APPOINTMENT_CREATED, OUTGATE, DELIVERY,
    # EMPTY, INGATE, RETURNED, DEMURRAGE_START, DETENTION_START

    event_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Source of event
    source: Mapped[str] = mapped_column(String(30))  # PORT_API, SSL_API, DRIVER, DISPATCHER, SYSTEM

    # Related entity
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # APPOINTMENT, CHARGE, etc.
    related_entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Metadata
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    container = relationship("DrayageContainer", back_populates="events")

    __table_args__ = (
        Index("ix_event_container_type", "container_id", "event_type"),
    )

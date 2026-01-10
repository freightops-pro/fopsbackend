"""
Canada Regional Database Models

Canada-specific compliance tables isolated from other regions.
These tables are ONLY used for companies with operating_region='canada'.
"""

from sqlalchemy import Column, String, Integer, Boolean, DECIMAL, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.models.base import Base


class CanadaHOSLog(Base):
    """
    Canadian Hours of Service driver logs.

    ONLY used for Canada region companies.
    Similar to USA but with different limits (13-hour driving vs 11-hour).
    """
    __tablename__ = "canada_hos_logs"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    driver_id = Column(String, nullable=False, index=True)
    load_id = Column(String, nullable=True, index=True)

    # Log Entry
    log_date = Column(TIMESTAMP, nullable=False, index=True)
    duty_status = Column(String, nullable=False)  # driving, on_duty_not_driving, sleeper_berth, off_duty
    duration_minutes = Column(Integer, nullable=False)

    # Location
    location = Column(String, nullable=True)
    province = Column(String, nullable=True)  # Canadian province
    odometer_km = Column(DECIMAL(10, 2), nullable=True)

    # HOS Tracking
    driving_hours_today = Column(DECIMAL(5, 2), nullable=False, default=0)
    on_duty_hours_today = Column(DECIMAL(5, 2), nullable=False, default=0)
    cycle_hours_used = Column(DECIMAL(5, 2), nullable=False, default=0)  # 70-hour or 120-hour cycle

    # Violations
    hos_violation = Column(Boolean, nullable=False, default=False)
    violation_type = Column(String, nullable=True)  # over_13_driving, over_14_on_duty, insufficient_rest

    # EROD (Electronic Recording Device)
    erod_provider = Column(String, nullable=True)
    erod_device_id = Column(String, nullable=True)

    # Additional
    notes = Column(Text, nullable=True)
    metadata = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


class CanadaERODEvent(Base):
    """
    Canadian EROD (Electronic Recording Device) events.

    Similar to USA ELD but called EROD in Canada.
    Tracks all duty status changes electronically.
    """
    __tablename__ = "canada_erod_events"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    driver_id = Column(String, nullable=False, index=True)

    # Event Details
    event_type = Column(String, nullable=False)  # duty_status_change, login, logout, certification
    event_timestamp = Column(TIMESTAMP, nullable=False, index=True)
    event_code = Column(String, nullable=False)

    # Duty Status
    duty_status = Column(String, nullable=True)  # driving, on_duty_not_driving, sleeper_berth, off_duty

    # Location
    latitude = Column(DECIMAL(10, 7), nullable=True)
    longitude = Column(DECIMAL(10, 7), nullable=True)
    location_description = Column(String, nullable=True)
    province = Column(String, nullable=True)

    # Vehicle
    vehicle_id = Column(String, nullable=True)
    odometer_km = Column(DECIMAL(10, 2), nullable=True)

    # EROD Device
    erod_provider = Column(String, nullable=False)
    erod_device_id = Column(String, nullable=False)
    erod_sequence_id = Column(Integer, nullable=False)

    # Additional
    notes = Column(Text, nullable=True)
    metadata = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


class CanadaIFTARecord(Base):
    """
    Canadian IFTA (International Fuel Tax Agreement) records.

    Tracks fuel purchases and mileage by province for tax reporting.
    Used for interprovincial and cross-border (Canada-USA) operations.
    """
    __tablename__ = "canada_ifta_records"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    vehicle_id = Column(String, nullable=False, index=True)
    driver_id = Column(String, nullable=True)

    # Quarter
    quarter = Column(String, nullable=False, index=True)  # Q1-2026, Q2-2026, etc.
    year = Column(Integer, nullable=False)

    # Jurisdiction (Province or State)
    jurisdiction = Column(String, nullable=False, index=True)  # ON, QC, BC, etc. or US states

    # Distance
    miles_driven = Column(DECIMAL(10, 2), nullable=False)  # IFTA uses miles even in Canada
    km_driven = Column(DECIMAL(10, 2), nullable=False)  # Also track in km for convenience

    # Fuel
    fuel_purchased_liters = Column(DECIMAL(10, 2), nullable=True)
    fuel_purchased_gallons = Column(DECIMAL(10, 2), nullable=True)  # IFTA uses gallons
    fuel_cost_cad = Column(DECIMAL(10, 2), nullable=True)

    # Tax
    tax_rate = Column(DECIMAL(10, 4), nullable=True)
    tax_amount_cad = Column(DECIMAL(10, 2), nullable=True)

    # Additional
    notes = Column(Text, nullable=True)
    metadata = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())


class CanadaTDGShipment(Base):
    """
    TDG (Transportation of Dangerous Goods) shipment records.

    Tracks hazmat/dangerous goods shipments for compliance with
    Canadian TDG regulations.
    """
    __tablename__ = "canada_tdg_shipments"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    load_id = Column(String, nullable=False, index=True)
    driver_id = Column(String, nullable=False)

    # TDG Classification
    un_number = Column(String, nullable=False)  # UN identification number
    shipping_name = Column(String, nullable=False)
    tdg_class = Column(String, nullable=False)  # Class 1-9
    packing_group = Column(String, nullable=True)  # I, II, III

    # Quantity
    quantity = Column(DECIMAL(10, 2), nullable=False)
    unit = Column(String, nullable=False)  # kg, L, etc.

    # Placarding
    placard_required = Column(Boolean, nullable=False)
    placard_numbers = Column(JSONB, nullable=True)  # Array of placard numbers

    # Emergency Response
    emergency_phone = Column(String, nullable=False)
    emergency_contact_name = Column(String, nullable=False)

    # Driver Certification
    driver_tdg_certificate = Column(String, nullable=False)
    driver_tdg_expiry = Column(TIMESTAMP, nullable=False)

    # Documentation
    shipping_document_number = Column(String, nullable=False)
    emergency_response_plan = Column(Text, nullable=True)

    # Status
    status = Column(String, nullable=False)  # planned, in_transit, delivered, incident

    # Additional
    metadata = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())


class CanadaCompanyData(Base):
    """
    Canada-specific company registration data.

    Stores NSC, CVOR, and other Canadian regulatory information.
    One-to-one with company table.
    """
    __tablename__ = "canada_company_data"

    id = Column(String, primary_key=True)
    company_id = Column(String, unique=True, nullable=False, index=True)

    # Federal Registration
    nsc_number = Column(String, unique=True, nullable=False)  # National Safety Code
    carrier_profile_number = Column(String, nullable=True)  # Federal carrier profile

    # Provincial Registration
    cvor_number = Column(String, unique=True, nullable=True)  # Ontario CVOR
    cvor_expiry = Column(TIMESTAMP, nullable=True)
    home_province = Column(String, nullable=False)  # Base of operations

    # IFTA
    ifta_number = Column(String, unique=True, nullable=True)
    ifta_expiry = Column(TIMESTAMP, nullable=True)

    # TDG (Transportation of Dangerous Goods)
    tdg_certified = Column(Boolean, nullable=False, default=False)
    tdg_certificate_number = Column(String, nullable=True)
    tdg_expiry = Column(TIMESTAMP, nullable=True)

    # Safety Rating
    safety_rating = Column(String, nullable=True)  # Satisfactory, Conditional, Unsatisfactory
    safety_rating_date = Column(TIMESTAMP, nullable=True)

    # Insurance
    liability_insurance_policy = Column(String, nullable=True)
    liability_insurance_expiry = Column(TIMESTAMP, nullable=True)
    cargo_insurance_policy = Column(String, nullable=True)
    cargo_insurance_expiry = Column(TIMESTAMP, nullable=True)

    # Quebec Operations
    operates_in_quebec = Column(Boolean, nullable=False, default=False)
    french_language_capable = Column(Boolean, nullable=False, default=False)
    quebec_permit_number = Column(String, nullable=True)

    # Border Crossing
    fast_approved = Column(Boolean, nullable=False, default=False)  # FAST program
    fast_number = Column(String, nullable=True)
    ace_aci_certified = Column(Boolean, nullable=False, default=False)  # ACE/ACI customs clearance

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    registration_validated = Column(Boolean, nullable=False, default=False)

    # Metadata
    registration_date = Column(TIMESTAMP, nullable=True)
    metadata = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())


class CanadaBorderCrossing(Base):
    """
    Border crossing records for Canada-USA freight.

    Tracks customs clearance times, delays, and issues for
    cross-border optimization.
    """
    __tablename__ = "canada_border_crossings"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    load_id = Column(String, nullable=False, index=True)
    driver_id = Column(String, nullable=False)

    # Border Port
    border_port = Column(String, nullable=False, index=True)  # Windsor, Buffalo, Laredo, etc.
    direction = Column(String, nullable=False)  # entering_canada, entering_usa
    crossing_date = Column(TIMESTAMP, nullable=False)

    # Timing
    arrival_time = Column(TIMESTAMP, nullable=False)
    clearance_time = Column(TIMESTAMP, nullable=True)
    departure_time = Column(TIMESTAMP, nullable=True)
    wait_time_minutes = Column(Integer, nullable=True)

    # Customs
    customs_status = Column(String, nullable=False)  # cleared, inspection, rejected, pending
    pars_paps_number = Column(String, nullable=True)  # Pre-arrival processing number
    ace_aci_used = Column(Boolean, nullable=False, default=False)
    fast_lane_used = Column(Boolean, nullable=False, default=False)

    # Documentation
    customs_broker = Column(String, nullable=True)
    commercial_invoice_number = Column(String, nullable=True)
    canada_customs_invoice = Column(String, nullable=True)

    # Issues
    inspection_required = Column(Boolean, nullable=False, default=False)
    issues_encountered = Column(Text, nullable=True)
    delay_reason = Column(String, nullable=True)

    # Additional
    metadata = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

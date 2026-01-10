"""
USA-Specific Data Models

These tables are ONLY used for United States operations.
They don't affect Brazil or other regions.

Tables:
- usa_hos_logs: Hours of Service (driver logs)
- usa_eld_events: Electronic Logging Device events
- usa_ifta_records: IFTA fuel tax records
- usa_dot_inspections: DOT roadside inspection records
"""

from sqlalchemy import Boolean, Column, DateTime, String, Text, DECIMAL, Integer, JSON, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class USAHOSLog(Base):
    """
    USA Hours of Service (HOS) driver logs.

    ONLY used for USA region companies.
    Tracks driver duty status per FMCSA regulations.
    """
    __tablename__ = "usa_hos_logs"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    driver_id = Column(String, nullable=False, index=True)
    load_id = Column(String, nullable=True, index=True)

    # Log Entry
    log_date = Column(DateTime, nullable=False, index=True)
    duty_status = Column(String, nullable=False)  # driving, on_duty_not_driving, sleeper_berth, off_duty
    duration_minutes = Column(Integer, nullable=False)

    # Location
    location_latitude = Column(DECIMAL(10, 8), nullable=True)
    location_longitude = Column(DECIMAL(11, 8), nullable=True)
    location_description = Column(String, nullable=True)

    # Odometer
    odometer_start = Column(DECIMAL(10, 2), nullable=True)
    odometer_end = Column(DECIMAL(10, 2), nullable=True)

    # ELD Data
    eld_device_id = Column(String, nullable=True)
    eld_event_type = Column(String, nullable=True)  # automatic, driver_manual, edit
    eld_sequence_id = Column(String, nullable=True)

    # Compliance
    hos_violation = Column(Boolean, nullable=False, default=False)
    violation_type = Column(String, nullable=True)  # 11_hour_limit, 14_hour_limit, 70_hour_limit

    # Annotations
    notes = Column(Text, nullable=True)
    certified = Column(Boolean, nullable=False, default=False)
    certified_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class USAELDEvent(Base):
    """
    USA Electronic Logging Device (ELD) events.

    ONLY used for USA region companies.
    Raw ELD data from devices (Samsara, Motive, Geotab, etc.)
    """
    __tablename__ = "usa_eld_events"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    driver_id = Column(String, nullable=False, index=True)
    vehicle_id = Column(String, nullable=False, index=True)

    # Event Details
    event_timestamp = Column(DateTime, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # status_change, diagnostic, malfunction
    event_code = Column(String, nullable=False)

    # Device Info
    eld_provider = Column(String, nullable=False)  # samsara, motive, geotab, etc.
    eld_device_id = Column(String, nullable=False)
    eld_firmware_version = Column(String, nullable=True)

    # Location
    latitude = Column(DECIMAL(10, 8), nullable=True)
    longitude = Column(DECIMAL(11, 8), nullable=True)
    location_description = Column(String, nullable=True)

    # Vehicle Data
    odometer_miles = Column(DECIMAL(10, 2), nullable=True)
    engine_hours = Column(DECIMAL(10, 2), nullable=True)
    speed_mph = Column(Integer, nullable=True)

    # Raw Data
    raw_event_data = Column(JSON, nullable=True)  # Full ELD provider response

    created_at = Column(DateTime, nullable=False, server_default=func.now())


class USAIFTARecord(Base):
    """
    USA IFTA (International Fuel Tax Agreement) records.

    ONLY used for USA/Canada region companies.
    Tracks fuel purchases and mileage by jurisdiction for tax reporting.
    """
    __tablename__ = "usa_ifta_records"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    vehicle_id = Column(String, nullable=False, index=True)
    driver_id = Column(String, nullable=True, index=True)

    # Trip Details
    trip_date = Column(DateTime, nullable=False, index=True)
    load_id = Column(String, nullable=True, index=True)

    # Jurisdiction
    jurisdiction = Column(String, nullable=False)  # State/Province code (TX, CA, ON, etc.)
    jurisdiction_type = Column(String, nullable=False)  # state, province

    # Mileage
    miles_driven = Column(DECIMAL(10, 2), nullable=False)
    taxable_miles = Column(DECIMAL(10, 2), nullable=False)

    # Fuel
    fuel_purchased_gallons = Column(DECIMAL(10, 2), nullable=True)
    fuel_cost_usd = Column(DECIMAL(10, 2), nullable=True)
    fuel_station = Column(String, nullable=True)

    # Tax Calculation
    tax_rate_per_gallon = Column(DECIMAL(10, 4), nullable=True)
    tax_owed = Column(DECIMAL(10, 2), nullable=True)

    # Quarter (for quarterly reporting)
    tax_quarter = Column(String, nullable=False)  # Q1-2025, Q2-2025, etc.
    tax_year = Column(Integer, nullable=False)

    # Reporting Status
    reported = Column(Boolean, nullable=False, default=False)
    reported_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())


class USADOTInspection(Base):
    """
    USA DOT roadside inspection records.

    ONLY used for USA region companies.
    Tracks FMCSA roadside inspections and violations.
    """
    __tablename__ = "usa_dot_inspections"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    driver_id = Column(String, nullable=False, index=True)
    vehicle_id = Column(String, nullable=False, index=True)

    # Inspection Details
    inspection_date = Column(DateTime, nullable=False, index=True)
    inspection_level = Column(String, nullable=False)  # Level 1-6
    inspection_report_number = Column(String, unique=True, nullable=False)

    # Location
    inspection_state = Column(String, nullable=False)
    inspection_location = Column(String, nullable=True)
    inspecting_officer = Column(String, nullable=True)

    # Result
    result = Column(String, nullable=False)  # passed, passed_with_violations, out_of_service
    out_of_service = Column(Boolean, nullable=False, default=False)

    # Violations
    violation_codes = Column(JSON, nullable=True)  # Array of FMCSA violation codes
    total_violations = Column(Integer, nullable=False, default=0)
    severity_weight = Column(DECIMAL(5, 2), nullable=True)  # For CSA scoring

    # Impact on CSA Score
    csa_points = Column(Integer, nullable=True)
    csa_category = Column(String, nullable=True)  # unsafe_driving, hos_compliance, etc.

    # Documents
    inspection_report_pdf = Column(String, nullable=True)  # S3/storage URL
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())


class USACompanyData(Base):
    """
    USA-specific company registration data.

    ONLY used for USA region companies.
    Stores DOT, MC, SCAC, IFTA, etc.
    """
    __tablename__ = "usa_company_data"

    id = Column(String, primary_key=True)
    company_id = Column(String, unique=True, nullable=False, index=True)

    # DOT Registration
    dot_number = Column(String, unique=True, nullable=False)
    mc_number = Column(String, unique=True, nullable=True)  # For for-hire carriers
    scac_code = Column(String, unique=True, nullable=True)  # Standard Carrier Alpha Code

    # Operating Authority
    operating_authority = Column(String, nullable=True)  # interstate, intrastate
    authority_status = Column(String, nullable=False, default="active")  # active, suspended, revoked

    # IFTA
    ifta_account_number = Column(String, nullable=True)
    ifta_states = Column(JSON, nullable=True)  # Array of states with IFTA authority
    ifta_decal_year = Column(Integer, nullable=True)

    # UCR (Unified Carrier Registration)
    ucr_number = Column(String, nullable=True)
    ucr_expiry = Column(DateTime, nullable=True)

    # BOC-3 (Process Agent Filing)
    boc3_filed = Column(Boolean, nullable=False, default=False)
    boc3_filing_date = Column(DateTime, nullable=True)

    # Safety Rating
    csa_safety_rating = Column(String, nullable=True)  # satisfactory, conditional, unsatisfactory
    csa_score = Column(DECIMAL(5, 2), nullable=True)
    last_safety_audit = Column(DateTime, nullable=True)

    # Insurance
    cargo_insurance_policy = Column(String, nullable=True)
    liability_insurance_policy = Column(String, nullable=True)
    insurance_expiry = Column(DateTime, nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    registration_validated = Column(Boolean, nullable=False, default=False)

    # Metadata
    registration_date = Column(DateTime, nullable=True)
    metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

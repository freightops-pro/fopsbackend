"""
EU (European Union) Regional Database Models

Tables for EU-specific freight compliance:
- eu_ecmr_documents - Electronic Consignment Notes (e-CMR)
- eu_cabotage_operations - Cabotage tracking (3-in-7 rule)
- eu_posted_worker_declarations - Posted worker compliance
- eu_tachograph_data - Digital tachograph downloads
- eu_company_data - EU-specific company registrations

All data stored in metric units (km, kg) as per EU standards.
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import JSONB
from app.core.db import Base


class EUEcmrDocument(Base):
    """
    e-CMR (Electronic Consignment Note) records

    e-CMR is the digital version of the paper CMR (Convention Relative au Contrat
    de Transport International de Marchandises par Route).

    Legally equivalent to paper CMR under Additional Protocol (2008).
    """

    __tablename__ = "eu_ecmr_documents"

    # Primary Identification
    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    load_id = Column(String, nullable=False, index=True)

    # Document Details
    consignment_note_number = Column(String, nullable=False, unique=True, index=True)
    issue_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    document_type = Column(
        String, nullable=False, default="e-CMR"
    )  # e-CMR, paper CMR, hybrid

    # Parties
    sender_name = Column(String, nullable=False)
    sender_address = Column(Text, nullable=False)
    sender_country_code = Column(String(2), nullable=False)

    carrier_name = Column(String, nullable=False)
    carrier_license_number = Column(String, nullable=True)  # EU Community License
    carrier_country_code = Column(String(2), nullable=False)

    consignee_name = Column(String, nullable=False)
    consignee_address = Column(Text, nullable=False)
    consignee_country_code = Column(String(2), nullable=False)

    # Goods Description
    goods_description = Column(Text, nullable=False)
    weight_kg = Column(Float, nullable=False)
    package_count = Column(Integer, nullable=False)
    package_type = Column(String, nullable=True)  # pallets, boxes, etc.

    # Dangerous Goods (ADR)
    is_dangerous_goods = Column(Boolean, nullable=False, default=False)
    un_number = Column(String, nullable=True)  # UN classification for dangerous goods
    adr_class = Column(String, nullable=True)

    # Temperature Control (ATP)
    requires_temperature_control = Column(Boolean, nullable=False, default=False)
    temperature_range = Column(String, nullable=True)  # e.g., "2-8°C"
    atp_certificate_number = Column(String, nullable=True)

    # Transport Details
    vehicle_registration = Column(String, nullable=True)
    trailer_registration = Column(String, nullable=True)
    driver_name = Column(String, nullable=True)
    tachograph_card_number = Column(String, nullable=True)

    # Route
    place_of_loading = Column(Text, nullable=False)
    place_of_delivery = Column(Text, nullable=False)
    loading_date = Column(DateTime, nullable=True)
    delivery_date = Column(DateTime, nullable=True)

    # Instructions and Conditions
    special_instructions = Column(Text, nullable=True)
    payment_instructions = Column(Text, nullable=True)

    # Digital Signatures (base64 encoded)
    sender_signature = Column(Text, nullable=True)
    sender_signature_timestamp = Column(DateTime, nullable=True)

    carrier_signature = Column(Text, nullable=True)
    carrier_signature_timestamp = Column(DateTime, nullable=True)

    consignee_signature = Column(Text, nullable=True)
    consignee_signature_timestamp = Column(DateTime, nullable=True)

    # Status
    status = Column(
        String, nullable=False, default="draft"
    )  # draft, signed, in_transit, delivered, cancelled

    # Platform Integration
    ecmr_platform = Column(
        String, nullable=True
    )  # transporeon, timocom, national system
    platform_document_id = Column(String, nullable=True)

    # Additional Data
    additional_data = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class EUCabotageOperation(Base):
    """
    Cabotage operations tracking

    EU Cabotage Rules (Regulation 1072/2009 + Mobility Package):
    - Max 3 cabotage operations within 7 days after international transport
    - Must leave country for 4 days before next cabotage period
    - Strictly enforced in France, Germany, Italy, Spain, Poland
    """

    __tablename__ = "eu_cabotage_operations"

    # Primary Identification
    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    vehicle_id = Column(String, nullable=False, index=True)
    load_id = Column(String, nullable=False, index=True)

    # Country and Dates
    country_code = Column(String(2), nullable=False, index=True)
    operation_date = Column(DateTime, nullable=False, index=True)
    operation_number = Column(
        Integer, nullable=False
    )  # 1, 2, or 3 (within 7-day window)

    # Preceding International Transport
    preceding_international_load_id = Column(String, nullable=True)
    international_unloading_date = Column(DateTime, nullable=True)

    # Route Details
    origin_city = Column(String, nullable=False)
    destination_city = Column(String, nullable=False)
    distance_km = Column(Float, nullable=False)

    # Validation
    is_compliant = Column(Boolean, nullable=False, default=True)
    violation_reason = Column(Text, nullable=True)

    # Enforcement
    checked_by_authority = Column(Boolean, nullable=False, default=False)
    check_date = Column(DateTime, nullable=True)
    check_location = Column(String, nullable=True)
    fine_amount = Column(Float, nullable=True)  # If violation found

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class EUPostedWorkerDeclaration(Base):
    """
    Posted Worker Declarations (Mobility Package requirement)

    Regulation (EU) 2020/1055:
    - Declaration required after 3 days in foreign country
    - Must include driver details, accommodation, duration
    - Submitted to receiving country's authority
    """

    __tablename__ = "eu_posted_worker_declarations"

    # Primary Identification
    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    driver_id = Column(String, nullable=False, index=True)

    # Posting Details
    host_country_code = Column(String(2), nullable=False, index=True)
    posting_start_date = Column(DateTime, nullable=False)
    posting_end_date = Column(DateTime, nullable=True)
    days_in_country = Column(Integer, nullable=False, default=0)

    # Driver Information
    driver_name = Column(String, nullable=False)
    driver_nationality = Column(String(2), nullable=False)
    driver_residence_country = Column(String(2), nullable=False)

    # Employment Details
    employment_contract_country = Column(String(2), nullable=False)
    applicable_social_security_system = Column(String(2), nullable=False)

    # Accommodation
    accommodation_address = Column(Text, nullable=False)
    accommodation_type = Column(
        String, nullable=False
    )  # hotel, company, private, truck

    # Transport Operations
    loads_during_posting = Column(JSON, nullable=True)  # List of load IDs

    # Submission to Authority
    submitted_to_authority = Column(Boolean, nullable=False, default=False)
    submission_date = Column(DateTime, nullable=True)
    submission_reference = Column(String, nullable=True)
    authority_response = Column(Text, nullable=True)

    # Status
    status = Column(
        String, nullable=False, default="draft"
    )  # draft, submitted, approved, rejected

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class EUTachographData(Base):
    """
    Digital tachograph data downloads

    EU Regulation (EC) 165/2014:
    - Company must download vehicle unit data every 90 days
    - Driver card data must be downloaded every 28 days
    - Data retention: 1 year minimum
    """

    __tablename__ = "eu_tachograph_data"

    # Primary Identification
    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)

    # Download Type
    download_type = Column(
        String, nullable=False
    )  # vehicle_unit, driver_card, remote

    # Vehicle or Driver
    vehicle_id = Column(String, nullable=True, index=True)
    driver_id = Column(String, nullable=True, index=True)

    # Tachograph Details
    tachograph_serial_number = Column(String, nullable=False)
    driver_card_number = Column(String, nullable=True)

    # Download Information
    download_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    data_period_start = Column(DateTime, nullable=False)
    data_period_end = Column(DateTime, nullable=False)
    days_of_data = Column(Integer, nullable=False)

    # File Information
    file_name = Column(String, nullable=False)
    file_format = Column(String, nullable=False, default="DDD")  # DDD, ESM, V1B, C1B
    file_size_bytes = Column(Integer, nullable=False)
    file_storage_path = Column(
        String, nullable=False
    )  # S3/R2 path to encrypted file

    # Analysis Results
    violations_detected = Column(Integer, nullable=False, default=0)
    violation_types = Column(JSON, nullable=True)  # List of violation types
    total_driving_time_hours = Column(Float, nullable=True)
    total_rest_time_hours = Column(Float, nullable=True)

    # Compliance Status
    is_compliant = Column(Boolean, nullable=False, default=True)
    requires_review = Column(Boolean, nullable=False, default=False)
    reviewed_by = Column(String, nullable=True)
    review_date = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class EUCompanyData(Base):
    """
    EU-specific company registration and licensing data

    Stored per-company for multi-tenant support.
    Each carrier provides their own EU credentials.
    """

    __tablename__ = "eu_company_data"

    # Primary Identification
    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, unique=True, index=True)

    # EU Community License (mandatory for international transport)
    eu_license_number = Column(String, nullable=False, unique=True)
    eu_license_issuing_country = Column(String(2), nullable=False)
    eu_license_valid_until = Column(DateTime, nullable=False)
    eu_license_type = Column(
        String, nullable=False, default="community"
    )  # community, bilateral

    # Company Registration
    company_registration_number = Column(String, nullable=False)
    vat_number = Column(String, nullable=True)  # For cross-border invoicing
    eori_number = Column(String, nullable=True)  # For customs (non-EU borders)

    # Operating Countries
    operating_countries = Column(
        JSON, nullable=False
    )  # List of ISO country codes where company operates

    # e-CMR Configuration
    ecmr_enabled = Column(Boolean, nullable=False, default=False)
    ecmr_platform = Column(String, nullable=True)  # transporeon, timocom, etc.
    ecmr_platform_credentials = Column(
        Text, nullable=True
    )  # Encrypted JSON with API keys

    # Insurance
    liability_insurance_policy = Column(String, nullable=True)
    liability_insurance_valid_until = Column(DateTime, nullable=True)
    insurance_coverage_amount = Column(Float, nullable=True)  # EUR

    # Fleet Information
    total_vehicles = Column(Integer, nullable=False, default=0)
    total_drivers = Column(Integer, nullable=False, default=0)

    # Compliance Features
    tachograph_download_frequency_days = Column(Integer, nullable=False, default=28)
    automatic_posted_worker_declarations = Column(Boolean, nullable=False, default=True)
    cabotage_tracking_enabled = Column(Boolean, nullable=False, default=True)

    # Contact Information
    compliance_officer_name = Column(String, nullable=True)
    compliance_officer_email = Column(String, nullable=True)
    compliance_officer_phone = Column(String, nullable=True)

    # Additional Data (flexible storage)
    additional_data = Column(JSONB, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

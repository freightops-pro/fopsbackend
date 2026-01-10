"""
Mexico Regional Database Models

Mexico-specific compliance tables isolated from other regions.
These tables are ONLY used for companies with operating_region='mexico'.
"""

from sqlalchemy import Column, String, Integer, Boolean, DECIMAL, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.models.base import Base


class MexicoCartaPorte(Base):
    """
    Mexican Carta de Porte 3.0 digital waybills.

    ONLY used for Mexico region companies.
    Carta de Porte is a CFDI (Comprobante Fiscal Digital por Internet)
    document that must be digitally sealed by SAT before transport begins.
    """
    __tablename__ = "mexico_carta_porte"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    load_id = Column(String, nullable=False, index=True)

    # CFDI/Carta de Porte Identification
    serie = Column(String, nullable=False, default="CP")  # Series (CP for Carta de Porte)
    folio = Column(String, nullable=False)  # Load number
    uuid = Column(String, unique=True, nullable=True)  # SAT digital seal (UUID)

    # SAT Status
    status = Column(String, nullable=False)  # draft, pending_seal, sealed, cancelled
    sat_seal = Column(Text, nullable=True)  # SAT digital seal
    authorization_date = Column(TIMESTAMP, nullable=True)

    # XML Data
    xml_unsigned = Column(Text, nullable=False)  # Generated XML before SAT seal
    xml_signed = Column(Text, nullable=True)  # Sealed XML from SAT

    # Transport Details
    rfc_emisor = Column(String, nullable=False)  # Carrier's RFC
    rfc_receptor = Column(String, nullable=True)  # Shipper/Receiver RFC
    driver_name = Column(String, nullable=False)
    driver_license = Column(String, nullable=False)
    driver_rfc = Column(String, nullable=True)

    # Vehicle Details
    vehicle_plate = Column(String, nullable=False)
    vehicle_year = Column(Integer, nullable=True)
    config_vehicular = Column(String, nullable=False, default="C2")  # Vehicle configuration

    # Cargo Details
    total_distance_km = Column(DECIMAL(10, 2), nullable=False)
    total_weight_kg = Column(DECIMAL(10, 2), nullable=False)
    cargo_value_mxn = Column(DECIMAL(15, 2), nullable=False)
    cargo_description = Column(Text, nullable=False)

    # SCT Permit
    sct_permit_type = Column(String, nullable=False)  # TPAF01, TPAF02, etc.
    sct_permit_number = Column(String, nullable=False)

    # Insurance
    insurance_company = Column(String, nullable=True)
    insurance_policy = Column(String, nullable=True)

    # Additional
    error_message = Column(Text, nullable=True)
    metadata = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())


class MexicoSATSubmission(Base):
    """
    Log of SAT API submissions for CFDI/Carta de Porte sealing.

    Tracks all interactions with SAT (Servicio de Administración Tributaria)
    for compliance auditing.
    """
    __tablename__ = "mexico_sat_submissions"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)

    # Submission Details
    document_type = Column(String, nullable=False)  # carta_porte, cfdi_ingreso, etc.
    document_id = Column(String, nullable=False, index=True)  # References mexico_carta_porte.id
    submission_type = Column(String, nullable=False)  # seal, cancel, query

    # SAT Response
    status_code = Column(String, nullable=False)  # HTTP status code
    sat_status = Column(String, nullable=False)  # success, rejected, error
    uuid = Column(String, nullable=True)  # UUID assigned by SAT
    sat_seal = Column(Text, nullable=True)  # Digital seal from SAT
    response_message = Column(Text, nullable=True)

    # XML Exchange
    request_xml = Column(Text, nullable=False)
    response_xml = Column(Text, nullable=True)

    # Timing
    request_timestamp = Column(TIMESTAMP, nullable=False, server_default=func.now())
    response_timestamp = Column(TIMESTAMP, nullable=True)
    response_time_ms = Column(Integer, nullable=True)

    # Error Handling
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())


class MexicoCompanyData(Base):
    """
    Mexico-specific company registration data.

    Stores RFC, SCT permits, and other Mexican regulatory information.
    One-to-one with company table.
    """
    __tablename__ = "mexico_company_data"

    id = Column(String, primary_key=True)
    company_id = Column(String, unique=True, nullable=False, index=True)

    # Tax Registration
    rfc = Column(String, unique=True, nullable=False)  # Tax ID (12-13 characters)

    # Transport Registration
    sct_permit = Column(String, unique=True, nullable=False)  # SCT permit number
    sct_permit_type = Column(String, nullable=False)  # TPAF01, TPAF02, TPAF03, etc.
    sct_permit_expiry = Column(TIMESTAMP, nullable=True)

    # Insurance
    insurance_company = Column(String, nullable=True)
    insurance_policy = Column(String, nullable=True)
    insurance_expiry = Column(TIMESTAMP, nullable=True)

    # Digital Certificate for SAT
    certificate_type = Column(String, nullable=True)  # CSD (Certificado de Sello Digital)
    certificate_serial = Column(String, nullable=True)
    certificate_expiry = Column(TIMESTAMP, nullable=True)
    certificate_data = Column(Text, nullable=True)  # Encrypted certificate

    # SAT Configuration
    sat_environment = Column(String, nullable=False, default="production")  # production or test

    # Security
    gps_jammer_detection_available = Column(Boolean, nullable=False, default=False)
    cargo_insurance_active = Column(Boolean, nullable=False, default=False)

    # Quebec Operations (for NAFTA/USMCA compliance)
    operates_in_quebec = Column(Boolean, nullable=False, default=False)
    french_language_capable = Column(Boolean, nullable=False, default=False)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    registration_validated = Column(Boolean, nullable=False, default=False)

    # Metadata
    registration_date = Column(TIMESTAMP, nullable=True)
    metadata = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())


class MexicoSecurityIncident(Base):
    """
    Security incident tracking for Mexican freight operations.

    Mexico has significant cargo theft issues, particularly in certain states.
    Track incidents for risk assessment and route planning.
    """
    __tablename__ = "mexico_security_incidents"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    load_id = Column(String, nullable=True, index=True)

    # Incident Details
    incident_type = Column(String, nullable=False)  # theft, hijacking, robbery, vandalism
    incident_date = Column(TIMESTAMP, nullable=False)
    state = Column(String, nullable=False, index=True)  # Mexican state
    municipality = Column(String, nullable=True)
    highway = Column(String, nullable=True)  # Highway where incident occurred

    # Location
    latitude = Column(DECIMAL(10, 7), nullable=True)
    longitude = Column(DECIMAL(10, 7), nullable=True)

    # Impact
    cargo_value_lost_mxn = Column(DECIMAL(15, 2), nullable=True)
    injuries = Column(Boolean, nullable=False, default=False)
    fatalities = Column(Boolean, nullable=False, default=False)

    # Investigation
    police_report_number = Column(String, nullable=True)
    insurance_claim_number = Column(String, nullable=True)
    resolved = Column(Boolean, nullable=False, default=False)

    # Description
    description = Column(Text, nullable=True)
    metadata = Column(JSONB, nullable=True)

    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now())

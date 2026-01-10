"""
Brazil-Specific Data Models

These tables are ONLY used for Brazilian operations.
They don't affect USA or other regions.

Tables:
- brazil_mdfe: MDF-e (Electronic Cargo Manifest) records
- brazil_cte: CT-e (Electronic Transport Document) records
- brazil_ciot: CIOT payment codes
- brazil_sefaz_submissions: SEFAZ API submission logs
"""

from sqlalchemy import Boolean, Column, DateTime, String, Text, DECIMAL, Integer, JSON, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class BrazilMDFe(Base):
    """
    Brazilian MDF-e (Manifesto Eletrônico) records.

    ONLY used for Brazil region companies.
    Stores digital cargo manifests and SEFAZ authorization data.
    """
    __tablename__ = "brazil_mdfe"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    load_id = Column(String, nullable=False, index=True)

    # MDF-e Identification
    mdfe_number = Column(Integer, nullable=False)  # Sequential number
    serie = Column(String, nullable=False, default="1")
    chave_acesso = Column(String, unique=True, nullable=False)  # 44-digit access key

    # SEFAZ Status
    status = Column(String, nullable=False)  # pending, authorized, rejected, cancelled
    sefaz_protocol = Column(String, nullable=True)  # Authorization protocol number
    authorization_date = Column(DateTime, nullable=True)

    # XML Data
    xml_unsigned = Column(Text, nullable=False)  # Original XML
    xml_signed = Column(Text, nullable=True)  # Digitally signed XML
    xml_authorized = Column(Text, nullable=True)  # With SEFAZ authorization

    # Transport Details
    driver_cpf = Column(String, nullable=False)
    vehicle_plate = Column(String, nullable=False)
    uf_start = Column(String, nullable=False)  # Starting state
    uf_end = Column(String, nullable=False)  # Ending state

    # Cargo Details
    total_cargo_value = Column(DECIMAL(15, 2), nullable=False)
    total_weight_kg = Column(DECIMAL(10, 2), nullable=False)

    # Additional Data
    error_message = Column(Text, nullable=True)  # If rejected
    metadata = Column(JSON, nullable=True)  # Additional SEFAZ data

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class BrazilCIOT(Base):
    """
    Brazilian CIOT (Código Identificador da Operação de Transporte) records.

    ONLY used for Brazil region companies.
    Required by Brazilian law to prove minimum freight rate payment.
    """
    __tablename__ = "brazil_ciot"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    load_id = Column(String, nullable=False, index=True)

    # CIOT Identification
    ciot_code = Column(String, unique=True, nullable=False)  # From payment provider
    payment_provider = Column(String, nullable=False)  # Pamcard, Repom, Sem Parar

    # Payment Details
    amount_brl = Column(DECIMAL(15, 2), nullable=False)  # Payment amount in Reais
    payment_date = Column(DateTime, nullable=False)
    payment_status = Column(String, nullable=False)  # pending, completed, failed

    # ANTT Validation
    antt_minimum_rate = Column(DECIMAL(15, 2), nullable=True)  # Minimum required by ANTT
    distance_km = Column(DECIMAL(10, 2), nullable=False)
    cargo_type = Column(String, nullable=True)

    # Driver Details
    driver_cpf = Column(String, nullable=False)
    driver_name = Column(String, nullable=False)

    # Provider Response
    provider_response = Column(JSON, nullable=True)  # Full API response

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class BrazilSEFAZSubmission(Base):
    """
    Brazilian SEFAZ API submission logs.

    ONLY used for Brazil region companies.
    Tracks all interactions with SEFAZ (tax authority) API.
    """
    __tablename__ = "brazil_sefaz_submissions"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)

    # Submission Details
    document_type = Column(String, nullable=False)  # mdfe, cte, nfe
    document_id = Column(String, nullable=False, index=True)  # Links to brazil_mdfe or brazil_cte
    submission_type = Column(String, nullable=False)  # authorization, cancellation, query

    # SEFAZ Response
    status_code = Column(String, nullable=False)  # HTTP status
    sefaz_status = Column(String, nullable=False)  # authorized, rejected, processing
    protocol_number = Column(String, nullable=True)
    response_message = Column(Text, nullable=True)

    # XML Exchange
    request_xml = Column(Text, nullable=False)
    response_xml = Column(Text, nullable=True)

    # Timing
    request_timestamp = Column(DateTime, nullable=False, server_default=func.now())
    response_timestamp = Column(DateTime, nullable=True)
    response_time_ms = Column(Integer, nullable=True)

    # Error Handling
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())


class BrazilCompanyData(Base):
    """
    Brazil-specific company registration data.

    ONLY used for Brazil region companies.
    Stores CNPJ, RNTRC, ANTT, digital certificates, etc.
    """
    __tablename__ = "brazil_company_data"

    id = Column(String, primary_key=True)
    company_id = Column(String, unique=True, nullable=False, index=True)

    # Tax Registration
    cnpj = Column(String, unique=True, nullable=False)  # Corporate Tax ID
    ie_number = Column(String, nullable=True)  # State Tax Registration (per state)

    # Transport Registration
    rntrc = Column(String, unique=True, nullable=False)  # National Road Cargo Transporter
    antt_registration = Column(String, nullable=False)  # Transport Agency

    # Digital Certificate (for XML signing)
    certificate_type = Column(String, nullable=True)  # A1 or A3
    certificate_serial = Column(String, nullable=True)
    certificate_expiry = Column(DateTime, nullable=True)
    certificate_data = Column(Text, nullable=True)  # Encrypted certificate data

    # SEFAZ Configuration
    sefaz_environment = Column(String, nullable=False, default="production")  # production or homologation
    sefaz_uf = Column(String, nullable=False)  # Primary state (UF) for operations

    # Counters (for MDF-e/CT-e numbering)
    last_mdfe_number = Column(Integer, nullable=False, default=0)
    last_cte_number = Column(Integer, nullable=False, default=0)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    registration_validated = Column(Boolean, nullable=False, default=False)

    # Metadata
    registration_date = Column(DateTime, nullable=True)
    metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

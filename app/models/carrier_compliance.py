"""Carrier-level compliance models for FMCSA, ELD auditing, insurance, and registrations."""

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class CompanyInsurance(Base):
    """Company-wide insurance policies (liability, cargo, etc.)."""

    __tablename__ = "company_insurance"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Policy details
    insurance_type = Column(String, nullable=False)  # LIABILITY, CARGO, PHYSICAL_DAMAGE, WORKERS_COMP, UMBRELLA, OTHER
    carrier_name = Column(String, nullable=False)  # Insurance carrier name
    policy_number = Column(String, nullable=False)
    effective_date = Column(Date, nullable=False)
    expiration_date = Column(Date, nullable=False)
    coverage_limit = Column(Numeric(14, 2), nullable=False)
    deductible = Column(Numeric(12, 2), nullable=True)

    # Compliance status calculated from expiration
    status = Column(String, nullable=False, default="COMPLIANT")  # COMPLIANT, EXPIRING, EXPIRED

    # Certificate holder info
    certificate_holder = Column(String, nullable=True)

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company")


class CarrierCredential(Base):
    """Carrier operating credentials (USDOT, MC number, BOC-3, UCR, etc.)."""

    __tablename__ = "carrier_credential"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Credential details
    credential_type = Column(String, nullable=False)  # USDOT, MC_NUMBER, BOC3, UCR, HAZMAT_PERMIT, OTHER
    credential_number = Column(String, nullable=False)
    issuing_authority = Column(String, nullable=True)  # FMCSA, state, etc.
    issue_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)

    # Compliance status
    status = Column(String, nullable=False, default="COMPLIANT")  # COMPLIANT, EXPIRING, EXPIRED

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company")


class VehicleRegistration(Base):
    """Vehicle registration records (IRP cab cards, base plates)."""

    __tablename__ = "vehicle_registration"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    equipment_id = Column(String, nullable=False, index=True)  # References fleet_equipment.id

    # Registration details
    unit_number = Column(String, nullable=False)
    plate_number = Column(String, nullable=False)
    state = Column(String, nullable=False)  # Issuing state
    registration_type = Column(String, nullable=False)  # IRP, BASE_PLATE, TEMPORARY

    # Dates
    effective_date = Column(Date, nullable=False)
    expiration_date = Column(Date, nullable=False)

    # Compliance status
    status = Column(String, nullable=False, default="COMPLIANT")  # COMPLIANT, EXPIRING, EXPIRED

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company")


class ELDAuditItem(Base):
    """ELD audit items for compliance tracking (unidentified driving, missing logs, etc.)."""

    __tablename__ = "eld_audit_item"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Category of audit item
    category = Column(String, nullable=False)  # UNIDENTIFIED_DRIVING, MISSING_LOGS, FORM_MANNER, MALFUNCTION, DATA_TRANSFER

    # Severity
    severity = Column(String, nullable=False, default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL

    # Driver/Equipment context
    driver_id = Column(String, ForeignKey("driver.id"), nullable=True, index=True)
    driver_name = Column(String, nullable=True)  # Denormalized for display
    equipment_id = Column(String, nullable=True, index=True)
    unit_number = Column(String, nullable=True)  # Denormalized for display

    # Event details
    date = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    duration_minutes = Column(Integer, nullable=True)

    # Resolution status
    status = Column(String, nullable=False, default="OPEN")  # OPEN, ACKNOWLEDGED, RESOLVED
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company")
    driver = relationship("Driver")


class CSAScore(Base):
    """CSA BASIC scores from FMCSA SAFER data."""

    __tablename__ = "csa_score"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # BASIC category
    category = Column(String, nullable=False)  # Unsafe Driving, HOS Compliance, Vehicle Maintenance, etc.
    percentile = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)  # Intervention threshold (65 or 80 depending on category)
    status = Column(String, nullable=False, default="OK")  # OK, ALERT, INTERVENTION

    # Source tracking
    last_updated = Column(DateTime, nullable=True)
    data_source = Column(String, nullable=True)  # manual, fmcsa_api, etc.

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company")


class CarrierSAFERSnapshot(Base):
    """Snapshot of carrier SAFER data from FMCSA."""

    __tablename__ = "carrier_safer_snapshot"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # FMCSA identifiers
    usdot_number = Column(String, nullable=False)
    mc_number = Column(String, nullable=True)

    # Company info
    legal_name = Column(String, nullable=False)
    dba_name = Column(String, nullable=True)
    physical_address = Column(String, nullable=True)
    mailing_address = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)

    # Fleet size
    power_units = Column(Integer, nullable=True)
    drivers = Column(Integer, nullable=True)

    # Status
    operating_status = Column(String, nullable=False)  # AUTHORIZED, NOT_AUTHORIZED, OUT_OF_SERVICE
    mcs150_date = Column(Date, nullable=True)
    out_of_service_date = Column(Date, nullable=True)
    carrier_operation = Column(String, nullable=True)  # Interstate, Intrastate
    cargo_carried = Column(String, nullable=True)  # JSON array as string

    # Safety rating
    safety_rating = Column(String, nullable=True)  # SATISFACTORY, CONDITIONAL, UNSATISFACTORY, NONE
    safety_rating_date = Column(Date, nullable=True)

    # Fetch tracking
    last_fetched = Column(DateTime, nullable=True)
    fetch_source = Column(String, nullable=True)  # manual, api, integration

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    company = relationship("Company")

"""Pydantic schemas for carrier-level compliance (insurance, credentials, registrations, ELD audit, CSA)."""

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ==================== COMPLIANCE STATUS ====================

ComplianceStatus = Literal["COMPLIANT", "EXPIRING", "EXPIRED"]
InsuranceType = Literal["LIABILITY", "CARGO", "PHYSICAL_DAMAGE", "WORKERS_COMP", "UMBRELLA", "OTHER"]
CredentialType = Literal["USDOT", "MC_NUMBER", "BOC3", "UCR", "HAZMAT_PERMIT", "OTHER"]
RegistrationType = Literal["IRP", "BASE_PLATE", "TEMPORARY"]
ELDCategory = Literal["UNIDENTIFIED_DRIVING", "MISSING_LOGS", "FORM_MANNER", "MALFUNCTION", "DATA_TRANSFER"]
Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
AuditItemStatus = Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]
CSAStatus = Literal["OK", "ALERT", "INTERVENTION"]
OperatingStatus = Literal["AUTHORIZED", "NOT_AUTHORIZED", "OUT_OF_SERVICE"]
SafetyRating = Literal["SATISFACTORY", "CONDITIONAL", "UNSATISFACTORY", "NONE"]


# ==================== COMPANY INSURANCE ====================


class CompanyInsuranceCreate(BaseModel):
    """Create a new company insurance policy."""
    insurance_type: InsuranceType
    carrier_name: str = Field(..., min_length=1, description="Insurance carrier name")
    policy_number: str = Field(..., min_length=1)
    effective_date: date
    expiration_date: date
    coverage_limit: float = Field(..., gt=0)
    deductible: Optional[float] = None
    certificate_holder: Optional[str] = None
    notes: Optional[str] = None


class CompanyInsuranceUpdate(BaseModel):
    """Update company insurance policy."""
    insurance_type: Optional[InsuranceType] = None
    carrier_name: Optional[str] = None
    policy_number: Optional[str] = None
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None
    coverage_limit: Optional[float] = None
    deductible: Optional[float] = None
    certificate_holder: Optional[str] = None
    notes: Optional[str] = None


class CompanyInsuranceResponse(BaseModel):
    """Company insurance policy response."""
    id: str
    insurance_type: str
    carrier_name: str
    policy_number: str
    effective_date: date
    expiration_date: date
    coverage_limit: float
    deductible: Optional[float] = None
    status: ComplianceStatus
    certificate_holder: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ==================== CARRIER CREDENTIALS ====================


class CarrierCredentialCreate(BaseModel):
    """Create a new carrier credential."""
    credential_type: CredentialType
    credential_number: str = Field(..., min_length=1)
    issuing_authority: Optional[str] = None
    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None
    notes: Optional[str] = None


class CarrierCredentialUpdate(BaseModel):
    """Update carrier credential."""
    credential_type: Optional[CredentialType] = None
    credential_number: Optional[str] = None
    issuing_authority: Optional[str] = None
    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None
    notes: Optional[str] = None


class CarrierCredentialResponse(BaseModel):
    """Carrier credential response."""
    id: str
    credential_type: str
    credential_number: str
    issuing_authority: Optional[str] = None
    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None
    status: ComplianceStatus
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ==================== VEHICLE REGISTRATION ====================


class VehicleRegistrationCreate(BaseModel):
    """Create a new vehicle registration."""
    equipment_id: str
    unit_number: str
    plate_number: str
    state: str = Field(..., min_length=2, max_length=2)
    registration_type: RegistrationType
    effective_date: date
    expiration_date: date
    notes: Optional[str] = None


class VehicleRegistrationUpdate(BaseModel):
    """Update vehicle registration."""
    plate_number: Optional[str] = None
    state: Optional[str] = None
    registration_type: Optional[RegistrationType] = None
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None
    notes: Optional[str] = None


class VehicleRegistrationResponse(BaseModel):
    """Vehicle registration response."""
    id: str
    equipment_id: str
    unit_number: str
    plate_number: str
    state: str
    registration_type: str
    effective_date: date
    expiration_date: date
    status: ComplianceStatus
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ==================== ELD AUDIT ITEMS ====================


class ELDAuditItemCreate(BaseModel):
    """Create a new ELD audit item."""
    category: ELDCategory
    severity: Severity = "MEDIUM"
    driver_id: Optional[str] = None
    driver_name: Optional[str] = None
    equipment_id: Optional[str] = None
    unit_number: Optional[str] = None
    date: date
    description: str
    duration_minutes: Optional[int] = None


class ELDAuditItemUpdate(BaseModel):
    """Update ELD audit item."""
    severity: Optional[Severity] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    status: Optional[AuditItemStatus] = None


class ELDAuditItemResolve(BaseModel):
    """Resolve an ELD audit item."""
    resolved_by: Optional[str] = None


class ELDAuditItemResponse(BaseModel):
    """ELD audit item response."""
    id: str
    category: str
    severity: str
    driver_id: Optional[str] = None
    driver_name: Optional[str] = None
    equipment_id: Optional[str] = None
    unit_number: Optional[str] = None
    date: date
    description: str
    duration_minutes: Optional[int] = None
    status: str
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ELDAuditSummaryResponse(BaseModel):
    """ELD audit summary for the dashboard."""
    unidentified_driving_count: int
    unidentified_driving_minutes: int
    missing_log_count: int
    form_manner_errors: int
    malfunctions: int
    data_transfer_ready: bool
    last_audit_date: Optional[date] = None
    audit_items: List[ELDAuditItemResponse]


# ==================== CSA SCORES ====================


class CSAScoreCreate(BaseModel):
    """Create/update a CSA BASIC score."""
    category: str
    percentile: float = Field(..., ge=0, le=100)
    threshold: float = Field(..., ge=0, le=100)
    status: CSAStatus = "OK"
    data_source: Optional[str] = None


class CSAScoreResponse(BaseModel):
    """CSA BASIC score response."""
    id: str
    category: str
    percentile: float
    threshold: float
    status: str
    last_updated: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ==================== SAFER DATA ====================


class CarrierSAFERDataResponse(BaseModel):
    """Carrier SAFER/SMS data from FMCSA."""
    usdot_number: str
    mc_number: Optional[str] = None
    legal_name: str
    dba_name: Optional[str] = None
    physical_address: Optional[str] = None
    mailing_address: Optional[str] = None
    phone_number: Optional[str] = None
    power_units: Optional[int] = None
    drivers: Optional[int] = None
    mcs150_date: Optional[date] = None
    out_of_service_date: Optional[date] = None
    operating_status: str
    carrier_operation: Optional[str] = None
    cargo_carried: Optional[List[str]] = None
    safety_rating: Optional[str] = None
    safety_rating_date: Optional[date] = None
    csa_scores: Optional[List[CSAScoreResponse]] = None
    last_fetched: Optional[datetime] = None


# ==================== COMPLIANCE SUMMARY ====================


class ComplianceSummary(BaseModel):
    """Compliance item count summary."""
    total: int
    compliant: int
    expiring_soon: int
    expired: int


class CarrierComplianceDashboardResponse(BaseModel):
    """Full carrier compliance dashboard response."""
    safer_data: Optional[CarrierSAFERDataResponse] = None
    eld_audit: Optional[ELDAuditSummaryResponse] = None
    credentials: List[CarrierCredentialResponse]
    insurance_policies: List[CompanyInsuranceResponse]
    vehicle_registrations: List[VehicleRegistrationResponse]
    permit_summary: ComplianceSummary
    insurance_summary: ComplianceSummary
    registration_summary: ComplianceSummary

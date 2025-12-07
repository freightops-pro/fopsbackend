"""Onboarding and DQF models for worker and driver onboarding."""

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class OnboardingStatus(str, enum.Enum):
    """Onboarding workflow status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DocumentCategory(str, enum.Enum):
    """DQF document category."""
    APPLICATION = "application"
    LICENSE = "license"
    MEDICAL = "medical"
    BACKGROUND = "background"
    TRAINING = "training"
    CERTIFICATION = "certification"
    OTHER = "other"


class VerificationStatus(str, enum.Enum):
    """Document verification status."""
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class BackgroundCheckType(str, enum.Enum):
    """Background check types."""
    MVR = "mvr"  # Motor Vehicle Record
    PSP = "psp"  # Pre-Employment Screening Program
    CDL_VERIFICATION = "cdl_verification"
    CLEARINGHOUSE = "clearinghouse"  # FMCSA Drug & Alcohol Clearinghouse
    CRIMINAL_BACKGROUND = "criminal_background"
    EMPLOYMENT_VERIFICATION = "employment_verification"


class BackgroundCheckStatus(str, enum.Enum):
    """Background check status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"


class BackgroundCheckResult(str, enum.Enum):
    """Background check result."""
    PASS = "pass"
    FAIL = "fail"
    REVIEW_REQUIRED = "review_required"


class OnboardingWorkflow(Base):
    """Worker/Driver onboarding workflow tracking."""
    __tablename__ = "onboarding_workflow"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    worker_id = Column(String, ForeignKey("worker.id"), nullable=True, index=True)
    driver_id = Column(String, ForeignKey("driver.id"), nullable=True, index=True)

    # Onboarding details
    worker_type = Column(String(20), nullable=False)  # employee, contractor, driver
    role_type = Column(String(20), nullable=False)  # driver, office, mechanic, etc.
    is_dot_driver = Column(Boolean, nullable=False, default=False)

    # Contact info (before worker/driver created)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    # Onboarding link
    onboarding_token = Column(String, nullable=True, unique=True, index=True)
    token_expires_at = Column(DateTime, nullable=True)
    onboarding_url = Column(String, nullable=True)

    # Status tracking
    status = Column(
        Enum(OnboardingStatus, values_callable=lambda x: [e.value for e in x], native_enum=False),
        nullable=False,
        default=OnboardingStatus.PENDING
    )
    current_step = Column(String(50), nullable=True)
    completed_steps = Column(JSON, nullable=True)  # List of completed step names

    # Background checks (for DOT drivers)
    background_checks_status = Column(JSON, nullable=True)  # Status of MVR, PSP, CDL, Clearinghouse
    background_checks_cost = Column(Numeric(10, 2), nullable=True, default=0)

    # Metadata
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_by = Column(String, ForeignKey("user.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company")
    worker = relationship("Worker")
    driver = relationship("Driver")
    background_checks = relationship("BackgroundCheck", back_populates="onboarding", cascade="all, delete-orphan")


class DQFDocument(Base):
    """Driver Qualification File (DQF) documents."""
    __tablename__ = "dqf_document"

    id = Column(String, primary_key=True)
    driver_id = Column(String, ForeignKey("driver.id"), nullable=False, index=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)

    # Document classification
    document_category = Column(
        Enum(DocumentCategory, values_callable=lambda x: [e.value for e in x], native_enum=False),
        nullable=False
    )
    document_type = Column(String(100), nullable=False)  # cdl, medical_card, mvr, psp, clearinghouse, etc.
    document_name = Column(String, nullable=False)

    # File storage
    file_url = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)
    file_type = Column(String(50), nullable=True)

    # Expiration tracking
    issue_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)
    is_expired = Column(Boolean, nullable=False, default=False)

    # Verification status
    verification_status = Column(
        Enum(VerificationStatus, values_callable=lambda x: [e.value for e in x], native_enum=False),
        nullable=False,
        default=VerificationStatus.PENDING
    )
    verified_by = Column(String, ForeignKey("user.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verification_notes = Column(Text, nullable=True)

    # Metadata
    uploaded_by = Column(String, ForeignKey("user.id"), nullable=True)
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    driver = relationship("Driver")
    company = relationship("Company")


class BackgroundCheck(Base):
    """Background check results and audit trail."""
    __tablename__ = "background_check"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    onboarding_id = Column(String, ForeignKey("onboarding_workflow.id"), nullable=True, index=True)
    driver_id = Column(String, ForeignKey("driver.id"), nullable=True, index=True)

    # Check details
    check_type = Column(
        Enum(BackgroundCheckType, values_callable=lambda x: [e.value for e in x], native_enum=False),
        nullable=False
    )
    provider = Column(String(100), nullable=True)  # e.g., "Foley Services", "HireRight", etc.
    provider_reference_id = Column(String, nullable=True)

    # Subject information
    subject_name = Column(String, nullable=False)
    subject_cdl_number = Column(String, nullable=True)
    subject_cdl_state = Column(String(2), nullable=True)
    subject_dob = Column(Date, nullable=True)

    # Status and results
    status = Column(
        Enum(BackgroundCheckStatus, values_callable=lambda x: [e.value for e in x], native_enum=False),
        nullable=False,
        default=BackgroundCheckStatus.PENDING
    )
    result = Column(
        Enum(BackgroundCheckResult, values_callable=lambda x: [e.value for e in x], native_enum=False),
        nullable=True
    )
    result_data = Column(JSON, nullable=True)  # Full result payload from provider
    result_summary = Column(Text, nullable=True)

    # Flags and violations
    has_violations = Column(Boolean, nullable=True)
    violation_count = Column(Integer, nullable=True, default=0)
    violation_summary = Column(JSON, nullable=True)

    # Billing
    cost = Column(Numeric(10, 2), nullable=True)
    billed_to_company = Column(Boolean, nullable=False, default=True)
    billing_status = Column(String(20), nullable=True, default="pending")  # pending, invoiced, paid

    # Timestamps
    requested_at = Column(DateTime, nullable=False, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    company = relationship("Company")
    onboarding = relationship("OnboardingWorkflow", back_populates="background_checks")
    driver = relationship("Driver")

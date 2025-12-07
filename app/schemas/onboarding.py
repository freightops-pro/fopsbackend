"""Onboarding and DQF schemas."""

from datetime import date, datetime
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, EmailStr, Field


# Enums
OnboardingStatusType = Literal["pending", "in_progress", "completed", "cancelled"]
WorkerTypeType = Literal["employee", "contractor", "driver"]
RoleTypeType = Literal["driver", "office", "mechanic", "dispatcher", "other"]
DocumentCategoryType = Literal["application", "license", "medical", "background", "training", "certification", "other"]
VerificationStatusType = Literal["pending", "verified", "rejected", "expired"]
BackgroundCheckTypeEnum = Literal["mvr", "psp", "cdl_verification", "clearinghouse", "criminal_background", "employment_verification"]
BackgroundCheckStatusEnum = Literal["pending", "in_progress", "completed", "failed", "error"]
BackgroundCheckResultEnum = Literal["pass", "fail", "review_required"]


# ===== Onboarding Workflow =====

class OnboardingWorkflowCreate(BaseModel):
    """Create a new onboarding workflow."""
    worker_type: WorkerTypeType
    role_type: RoleTypeType
    is_dot_driver: bool = False
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    send_onboarding_link: bool = True  # Whether to send onboarding link immediately


class OnboardingWorkflowUpdate(BaseModel):
    """Update onboarding workflow progress."""
    current_step: Optional[str] = None
    completed_steps: Optional[List[str]] = None
    status: Optional[OnboardingStatusType] = None
    background_checks_status: Optional[Dict[str, Any]] = None


class OnboardingWorkflowResponse(BaseModel):
    """Onboarding workflow response."""
    id: str
    company_id: str
    worker_id: Optional[str] = None
    driver_id: Optional[str] = None

    worker_type: str
    role_type: str
    is_dot_driver: bool

    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None

    onboarding_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    onboarding_url: Optional[str] = None

    status: str
    current_step: Optional[str] = None
    completed_steps: Optional[List[str]] = None

    background_checks_status: Optional[Dict[str, Any]] = None
    background_checks_cost: Optional[float] = None

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OnboardingLinkResponse(BaseModel):
    """Response containing onboarding link."""
    onboarding_id: str
    onboarding_url: str
    token: str
    expires_at: datetime
    email_sent: bool


# ===== DQF Documents =====

class DQFDocumentCreate(BaseModel):
    """Create a DQF document."""
    driver_id: str
    document_category: DocumentCategoryType
    document_type: str
    document_name: str
    file_url: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None


class DQFDocumentUpdate(BaseModel):
    """Update DQF document."""
    document_name: Optional[str] = None
    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None
    verification_status: Optional[VerificationStatusType] = None
    verification_notes: Optional[str] = None


class DQFDocumentResponse(BaseModel):
    """DQF document response."""
    id: str
    driver_id: str
    company_id: str

    document_category: str
    document_type: str
    document_name: str

    file_url: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None

    issue_date: Optional[date] = None
    expiration_date: Optional[date] = None
    is_expired: bool

    verification_status: str
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None

    uploaded_by: Optional[str] = None
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DQFSummaryResponse(BaseModel):
    """DQF summary for a driver."""
    driver_id: str
    driver_name: str
    total_documents: int
    verified_documents: int
    pending_documents: int
    expired_documents: int
    expiring_soon_count: int  # Expiring within 30 days
    compliance_percentage: float
    documents_by_category: Dict[str, int]
    upcoming_expirations: List[DQFDocumentResponse]


# ===== Background Checks =====

class BackgroundCheckRequest(BaseModel):
    """Request a background check."""
    onboarding_id: Optional[str] = None
    driver_id: Optional[str] = None
    check_type: BackgroundCheckTypeEnum
    subject_name: str
    subject_cdl_number: Optional[str] = None
    subject_cdl_state: Optional[str] = None
    subject_dob: Optional[date] = None


class BackgroundCheckResponse(BaseModel):
    """Background check response."""
    id: str
    company_id: str
    onboarding_id: Optional[str] = None
    driver_id: Optional[str] = None

    check_type: str
    provider: Optional[str] = None
    provider_reference_id: Optional[str] = None

    subject_name: str
    subject_cdl_number: Optional[str] = None
    subject_cdl_state: Optional[str] = None
    subject_dob: Optional[date] = None

    status: str
    result: Optional[str] = None
    result_summary: Optional[str] = None

    has_violations: Optional[bool] = None
    violation_count: Optional[int] = None
    violation_summary: Optional[Dict[str, Any]] = None

    cost: Optional[float] = None
    billed_to_company: bool
    billing_status: Optional[str] = None

    requested_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BackgroundCheckBatchRequest(BaseModel):
    """Request multiple background checks for a driver."""
    onboarding_id: Optional[str] = None
    driver_id: Optional[str] = None
    check_types: List[BackgroundCheckTypeEnum]
    subject_name: str
    subject_cdl_number: Optional[str] = None
    subject_cdl_state: Optional[str] = None
    subject_dob: Optional[date] = None


class BackgroundCheckBatchResponse(BaseModel):
    """Batch background check response."""
    onboarding_id: Optional[str] = None
    driver_id: Optional[str] = None
    checks_requested: int
    checks_initiated: List[BackgroundCheckResponse]
    total_estimated_cost: float
    billing_company_id: str


# ===== Onboarding Progress =====

class OnboardingStepUpdate(BaseModel):
    """Update progress on an onboarding step."""
    step_name: str
    is_completed: bool
    step_data: Optional[Dict[str, Any]] = None


class OnboardingCompleteRequest(BaseModel):
    """Complete onboarding and create worker/driver."""
    worker_data: Optional[Dict[str, Any]] = None  # Worker profile data
    driver_data: Optional[Dict[str, Any]] = None  # Driver profile data
    payroll_data: Optional[Dict[str, Any]] = None  # Payroll configuration
    create_user_account: bool = True  # Create app access


class OnboardingCompleteResponse(BaseModel):
    """Response after completing onboarding."""
    onboarding_id: str
    worker_id: Optional[str] = None
    driver_id: Optional[str] = None
    user_id: Optional[str] = None
    temporary_password: Optional[str] = None
    message: str


# ===== Background Check Providers =====

class BackgroundCheckCostEstimate(BaseModel):
    """Cost estimate for background checks."""
    check_type: BackgroundCheckTypeEnum
    provider: str
    estimated_cost: float
    estimated_turnaround_days: int


class BackgroundCheckProvidersResponse(BaseModel):
    """Available background check providers and pricing."""
    providers: List[Dict[str, Any]]
    cost_estimates: List[BackgroundCheckCostEstimate]
    total_estimated_cost_for_dot_driver: float  # MVR + PSP + CDL + Clearinghouse

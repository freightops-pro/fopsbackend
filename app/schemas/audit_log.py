"""
Audit Log Schemas for API requests/responses.
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """Response schema for a single audit log entry."""
    id: str
    timestamp: datetime
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    company_id: Optional[str] = None
    event_type: str
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    metadata: Optional[dict] = Field(None, alias="extra_data")
    error_message: Optional[str] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class AuditLogFilter(BaseModel):
    """Filter parameters for querying audit logs."""
    event_type: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    status: Optional[Literal["success", "failure", "blocked"]] = None
    resource_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    search: Optional[str] = None  # Search in action/email


class AuditLogListResponse(BaseModel):
    """Paginated list of audit logs."""
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditLogSummary(BaseModel):
    """Summary statistics for audit logs dashboard."""
    total_events: int
    success_count: int
    failure_count: int
    blocked_count: int
    login_success_count: int
    login_failure_count: int
    recent_security_events: int  # Last 24 hours
    top_event_types: List[dict]  # [{event_type: str, count: int}]


class LoginAttemptResponse(BaseModel):
    """Response schema for login attempt records."""
    id: str
    identifier: str
    attempt_type: str
    timestamp: datetime
    success: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    failure_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class LoginAttemptListResponse(BaseModel):
    """Paginated list of login attempts."""
    items: List[LoginAttemptResponse]
    total: int
    page: int
    page_size: int


# Event type constants for reference
EVENT_TYPES = [
    "auth.login_success",
    "auth.login_failure",
    "auth.logout",
    "auth.password_change",
    "auth.password_reset",
    "auth.email_verification_sent",
    "auth.email_verified",
    "account.locked",
    "account.unlocked",
    "account.created",
    "account.updated",
    "account.deleted",
    "permission.denied",
    "data.pii_accessed",
    "data.pii_modified",
    "security.suspicious_activity",
    "invitation.created",
    "invitation.accepted",
    "invitation.cancelled",
    "invitation.expired",
    "role.assigned",
    "role.removed",
    "settings.updated",
]

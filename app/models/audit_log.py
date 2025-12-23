"""
Audit Log Model for Security Event Tracking.

Logs all security-relevant events for compliance:
- Authentication events (login, logout, failed attempts)
- Authorization events (permission denied)
- Data access (sensitive data viewed/modified)
- Account changes (password, email, profile)
"""

from sqlalchemy import Column, DateTime, Index, JSON, String, Text, func

from app.models.base import Base


class AuditLog(Base):
    """
    Security audit log for SOC 2 / PCI compliance.

    All security-relevant events are logged here with:
    - Who performed the action
    - What action was performed
    - When it occurred
    - Where (IP address, user agent)
    - Additional context (metadata)
    """
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True)

    # When
    timestamp = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    # Who
    user_id = Column(String, nullable=True, index=True)  # Null for failed logins
    user_email = Column(String, nullable=True)
    company_id = Column(String, nullable=True, index=True)

    # What
    event_type = Column(String, nullable=False, index=True)
    # Event types:
    # - auth.login_success, auth.login_failure, auth.logout
    # - auth.password_change, auth.password_reset
    # - auth.email_verification_sent, auth.email_verified
    # - account.locked, account.unlocked
    # - account.created, account.updated, account.deleted
    # - permission.denied
    # - data.pii_accessed, data.pii_modified
    # - security.suspicious_activity

    action = Column(String, nullable=False)  # Human-readable action
    resource_type = Column(String, nullable=True)  # user, driver, load, etc.
    resource_id = Column(String, nullable=True)

    # Where
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    request_id = Column(String, nullable=True)  # For request tracing

    # Status
    status = Column(String, nullable=False, default="success")  # success, failure, blocked

    # Additional context
    extra_data = Column("metadata", JSON, nullable=True)  # Named 'metadata' in DB, 'extra_data' in Python
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_audit_company_timestamp", "company_id", "timestamp"),
        Index("idx_audit_user_timestamp", "user_id", "timestamp"),
        Index("idx_audit_event_timestamp", "event_type", "timestamp"),
    )


class LoginAttempt(Base):
    """
    Tracks login attempts for rate limiting and lockout.

    Separate from audit log for faster queries on active lockouts.
    """
    __tablename__ = "login_attempts"

    id = Column(String, primary_key=True)
    identifier = Column(String, nullable=False, index=True)  # Email or IP
    attempt_type = Column(String, nullable=False)  # email, ip
    timestamp = Column(DateTime, nullable=False, server_default=func.now())
    success = Column(String, nullable=False, default="false")
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    failure_reason = Column(String, nullable=True)  # invalid_password, account_locked, etc.

    __table_args__ = (
        Index("idx_login_attempts_identifier_time", "identifier", "timestamp"),
    )

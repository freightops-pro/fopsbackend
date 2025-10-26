"""
Audit Log Model for Security and Compliance
"""
from sqlalchemy import Column, String, DateTime, Text, JSON, Index
from sqlalchemy.sql import func
from app.config.db import Base
import uuid

class AuditLog(Base):
    """
    Audit log model for tracking all security-relevant activities
    """
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    
    # User and company identification
    company_id = Column(String, index=True, nullable=True)
    user_id = Column(String, index=True, nullable=True)
    session_id = Column(String, index=True, nullable=True)
    
    # Request information
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    request_method = Column(String, nullable=True)
    request_path = Column(String, nullable=True)
    
    # Action details
    action = Column(String, nullable=False, index=True)  # LOGIN, LOGOUT, CREATE, UPDATE, DELETE, VIEW, etc.
    resource_type = Column(String, nullable=True, index=True)  # user, load, driver, invoice, etc.
    resource_id = Column(String, nullable=True, index=True)
    
    # Change tracking
    changes = Column(JSON, nullable=True)  # Before/after values for updates
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    # Status and result
    status = Column(String, nullable=False, index=True)  # success, failure, error
    error_message = Column(Text, nullable=True)
    
    # Additional context
    metadata_json = Column(JSON, nullable=True)  # Additional context data
    risk_level = Column(String, nullable=True, index=True)  # low, medium, high, critical
    
    # Compliance fields
    compliance_category = Column(String, nullable=True, index=True)  # auth, data_access, financial, etc.
    retention_period = Column(String, nullable=True)  # 1_year, 7_years, permanent
    
    # Create indexes for performance
    __table_args__ = (
        Index('idx_audit_company_timestamp', 'company_id', 'timestamp'),
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_action_timestamp', 'action', 'timestamp'),
        Index('idx_audit_resource_timestamp', 'resource_type', 'resource_id', 'timestamp'),
        Index('idx_audit_status_timestamp', 'status', 'timestamp'),
        Index('idx_audit_risk_timestamp', 'risk_level', 'timestamp'),
        Index('idx_audit_compliance_timestamp', 'compliance_category', 'timestamp'),
    )

class SecurityEvent(Base):
    """
    Security event model for critical security events
    """
    __tablename__ = "security_events"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Event identification
    event_type = Column(String, nullable=False, index=True)  # FAILED_LOGIN, SUSPICIOUS_ACTIVITY, etc.
    severity = Column(String, nullable=False, index=True)  # low, medium, high, critical
    
    # User and company identification
    company_id = Column(String, index=True, nullable=True)
    user_id = Column(String, index=True, nullable=True)
    
    # Request information
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Event details
    description = Column(Text, nullable=False)
    details_json = Column(JSON, nullable=True)
    
    # Response actions
    action_taken = Column(String, nullable=True)  # blocked, alerted, logged, etc.
    resolved = Column(String, default='false')  # true, false
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)
    
    # Create indexes for performance
    __table_args__ = (
        Index('idx_security_type_timestamp', 'event_type', 'timestamp'),
        Index('idx_security_severity_timestamp', 'severity', 'timestamp'),
        Index('idx_security_company_timestamp', 'company_id', 'timestamp'),
        Index('idx_security_resolved', 'resolved', 'timestamp'),
    )

class APIAccessLog(Base):
    """
    API access log for tracking API usage and potential abuse
    """
    __tablename__ = "api_access_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Request identification
    request_id = Column(String, index=True, nullable=True)
    api_key_id = Column(String, index=True, nullable=True)
    
    # User and company identification
    company_id = Column(String, index=True, nullable=True)
    user_id = Column(String, index=True, nullable=True)
    
    # Request details
    method = Column(String, nullable=False)
    endpoint = Column(String, nullable=False, index=True)
    query_params = Column(JSON, nullable=True)
    request_size = Column(String, nullable=True)
    
    # Response details
    status_code = Column(String, nullable=False, index=True)
    response_size = Column(String, nullable=True)
    response_time_ms = Column(String, nullable=True)
    
    # Client information
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Rate limiting information
    rate_limit_hit = Column(String, nullable=True)
    rate_limit_remaining = Column(String, nullable=True)
    
    # Create indexes for performance
    __table_args__ = (
        Index('idx_api_company_timestamp', 'company_id', 'timestamp'),
        Index('idx_api_endpoint_timestamp', 'endpoint', 'timestamp'),
        Index('idx_api_status_timestamp', 'status_code', 'timestamp'),
        Index('idx_api_key_timestamp', 'api_key_id', 'timestamp'),
    )

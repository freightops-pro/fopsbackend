from sqlalchemy import Column, String, Boolean, DateTime, JSON, Text, Integer, Numeric, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.config.db import Base
import enum
import uuid

class PortAuthType(str, enum.Enum):
    """Authentication types supported by port APIs"""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    BASIC_AUTH = "basic_auth"
    CLIENT_CERT = "client_cert"
    JWT = "jwt"

class PortService(str, enum.Enum):
    """Services available from port APIs"""
    VESSEL_SCHEDULING = "vessel_scheduling"
    CONTAINER_TRACKING = "container_tracking"
    DOCUMENT_UPLOAD = "document_upload"
    GATE_OPERATIONS = "gate_operations"
    BERTH_AVAILABILITY = "berth_availability"

class PortAddonPricing(str, enum.Enum):
    """Pricing models for port credentials add-on"""
    PAY_PER_REQUEST = "pay_per_request"
    UNLIMITED_MONTHLY = "unlimited_monthly"

class Port(Base):
    """Registry of major US container ports"""
    __tablename__ = "ports"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    port_code = Column(String(10), unique=True, nullable=False, index=True)
    port_name = Column(String(255), nullable=False)
    unlocode = Column(String(5), unique=True, nullable=False, index=True)
    region = Column(String(50))  # West Coast, East Coast, Gulf Coast
    state = Column(String(2))  # CA, NY, TX, etc.
    
    # API Configuration
    api_endpoint = Column(String(500), nullable=False)
    api_version = Column(String(20), default="1.0")
    auth_type = Column(SQLEnum(PortAuthType), nullable=False)
    
    # Service Configuration
    services_supported = Column(JSON)  # List of PortService values
    rate_limits = Column(JSON)  # {"requests_per_minute": 100, "burst_capacity": 50}
    
    # Compliance & Requirements
    compliance_standards = Column(JSON)  # {"twic_required": true, "ctpat_certified": false}
    documentation_requirements = Column(JSON)
    
    # Status
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    credentials = relationship("PortCredential", back_populates="port", cascade="all, delete-orphan")
    audit_logs = relationship("PortAuditLog", back_populates="port")
    health_checks = relationship("PortHealthCheck", back_populates="port")

class PortCredential(Base):
    """Company-specific encrypted port credentials"""
    __tablename__ = "port_credentials"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    port_id = Column(String(36), ForeignKey("ports.id"), nullable=False)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    
    # Encrypted credential storage (Fernet encrypted JSON)
    encrypted_credentials = Column(Text, nullable=False)
    credential_type = Column(String(50), nullable=False)
    
    # Rotation & Validation
    expires_at = Column(DateTime, nullable=True)
    last_validated = Column(DateTime, nullable=True)
    validation_status = Column(String(20), default="pending")  # pending, valid, invalid, expired
    rotation_required = Column(Boolean, default=False)
    rotation_scheduled_at = Column(DateTime, nullable=True)
    
    # Health tracking
    consecutive_failures = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Audit
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    port = relationship("Port", back_populates="credentials")
    company = relationship("Companies")
    creator = relationship("Users")
    
    __table_args__ = (
        Index('ix_port_credentials_company_port', 'company_id', 'port_id'),
    )

class CompanyPortAddon(Base):
    """Tracks port credential add-on subscription per company"""
    __tablename__ = "company_port_addons"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), unique=True, nullable=False)
    
    # Pricing Model
    pricing_model = Column(SQLEnum(PortAddonPricing), nullable=False)
    
    # Monthly Subscription Details
    monthly_price = Column(Numeric(10, 2), nullable=True)  # $99.00
    subscription_start = Column(DateTime, nullable=True)
    subscription_end = Column(DateTime, nullable=True)
    auto_renew = Column(Boolean, default=True)
    
    # Pay-Per-Request Tracking
    current_month = Column(String(7))  # "2024-01" for billing period
    current_month_requests = Column(Integer, default=0)
    current_month_cost = Column(Numeric(10, 2), default=0)
    
    # Optimization
    auto_optimize = Column(Boolean, default=False)  # Auto-switch to best pricing
    last_optimization_check = Column(DateTime, nullable=True)
    
    # Billing
    stripe_subscription_id = Column(String(255), nullable=True)  # For monthly
    next_billing_date = Column(DateTime, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("Companies")

class PortAPIUsage(Base):
    """Tracks individual API calls for billing and analytics"""
    __tablename__ = "port_api_usage"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    port_code = Column(String(10), nullable=False, index=True)
    
    # Operation details
    operation = Column(String(50), nullable=False)  # track_container, vessel_schedule, etc.
    operation_cost = Column(Numeric(10, 2), nullable=False)
    
    # Request details
    request_params = Column(JSON, nullable=True)  # Sanitized parameters
    response_time_ms = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False)  # success, failure, timeout
    error_message = Column(Text, nullable=True)
    
    # Billing
    billing_month = Column(String(7), nullable=False, index=True)  # "2024-01"
    billed = Column(Boolean, default=False)
    
    # Metadata
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)
    
    __table_args__ = (
        Index('ix_port_api_usage_billing', 'company_id', 'billing_month'),
    )

class PortAuditLog(Base):
    """Comprehensive audit trail for port operations"""
    __tablename__ = "port_audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    port_id = Column(String(36), ForeignKey("ports.id"), nullable=False)
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    credential_id = Column(String(36), ForeignKey("port_credentials.id"), nullable=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    # Action details
    action_type = Column(String(50), nullable=False, index=True)
    action_status = Column(String(20), nullable=False)
    
    # Request/Response
    request_data = Column(JSON, nullable=True)
    response_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Security context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, server_default=func.now(), index=True)
    
    # Relationships
    port = relationship("Port", back_populates="audit_logs")

class PortHealthCheck(Base):
    """Health monitoring for port API endpoints"""
    __tablename__ = "port_health_checks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    port_id = Column(String(36), ForeignKey("ports.id"), nullable=False)
    
    # Health status
    status = Column(String(20), nullable=False)  # healthy, degraded, unavailable
    response_time_ms = Column(Integer, nullable=True)
    
    # Failure tracking
    consecutive_failures = Column(Integer, default=0)
    last_success_at = Column(DateTime, nullable=True)
    last_failure_at = Column(DateTime, nullable=True)
    failure_reason = Column(Text, nullable=True)
    
    # Failover
    failover_active = Column(Boolean, default=False)
    failover_endpoint = Column(String(500), nullable=True)
    
    # Timestamp
    checked_at = Column(DateTime, server_default=func.now(), index=True)
    
    # Relationships
    port = relationship("Port", back_populates="health_checks")










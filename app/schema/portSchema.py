from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
from app.models.port import PortAddonPricing

# Request Schemas

class EnablePortAddonRequest(BaseModel):
    """Request to enable port credentials add-on"""
    pricing_model: PortAddonPricing
    auto_optimize: bool = False

class SwitchPricingRequest(BaseModel):
    """Request to switch pricing model"""
    new_model: PortAddonPricing

class PortCredentialCreateRequest(BaseModel):
    """Request to create port credentials"""
    port_id: str
    credential_type: str
    credentials: Dict[str, Any]
    expires_at: Optional[datetime] = None

class TrackContainerRequest(BaseModel):
    """Request to track container"""
    port_code: str
    container_number: str = Field(..., pattern=r'^[A-Z]{4}[0-9]{7}$', description="Standard container number format")

class VesselScheduleRequest(BaseModel):
    """Request for vessel schedule"""
    port_code: str
    vessel_id: Optional[str] = None
    date_range: Optional[Dict[str, str]] = None

class DocumentUploadRequest(BaseModel):
    """Request to upload document"""
    port_code: str
    document_type: str
    file_data: bytes
    metadata: Dict[str, Any] = {}

class GateStatusRequest(BaseModel):
    """Request for gate status"""
    port_code: str

class BerthAvailabilityRequest(BaseModel):
    """Request for berth availability"""
    port_code: str
    vessel_size: str = Field(..., pattern=r'^(small|medium|large|ultra_large)$')
    arrival_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')

# Response Schemas

class PortResponse(BaseModel):
    """Port configuration response"""
    id: str
    port_code: str
    port_name: str
    unlocode: str
    region: Optional[str] = None
    state: Optional[str] = None
    services_supported: Optional[List[str]] = None
    auth_type: str
    rate_limits: Optional[Dict[str, Any]] = None
    compliance_standards: Optional[Dict[str, Any]] = None

class PortCredentialResponse(BaseModel):
    """Port credential response"""
    id: str
    port_id: str
    credential_type: str
    expires_at: Optional[datetime] = None
    validation_status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class CompanyPortAddonResponse(BaseModel):
    """Company port add-on response"""
    id: str
    pricing_model: str
    monthly_price: Optional[Decimal] = None
    subscription_start: Optional[datetime] = None
    subscription_end: Optional[datetime] = None
    current_month_requests: int
    current_month_cost: Decimal
    auto_optimize: bool
    is_active: bool

class PortAddonStatusResponse(BaseModel):
    """Port add-on status with usage stats"""
    enabled: bool
    current_model: Optional[str] = None
    current_month: Optional[Dict[str, Any]] = None
    monthly_stats: Optional[Dict[str, Any]] = None
    averages: Optional[Dict[str, Any]] = None
    recommendation: Optional[Dict[str, Any]] = None

class ContainerTrackingResponse(BaseModel):
    """Container tracking response"""
    container_number: str
    status: str
    location: str
    last_movement: str
    terminal: Optional[str] = None
    vessel: Optional[str] = None
    holds: List[str] = []
    estimated_gate_time: Optional[str] = None
    weight: Optional[str] = None
    seal_number: Optional[str] = None
    customs_status: Optional[str] = None
    usage_cost: float

class VesselScheduleResponse(BaseModel):
    """Vessel schedule response"""
    vessels: List[Dict[str, Any]]
    port_code: str
    timestamp: str
    usage_cost: float

class DocumentUploadResponse(BaseModel):
    """Document upload response"""
    document_id: str
    status: str
    upload_timestamp: str
    reference_number: Optional[str] = None
    validation_errors: List[str] = []
    usage_cost: float

class GateStatusResponse(BaseModel):
    """Gate status response"""
    gates: List[Dict[str, Any]]
    last_updated: str
    average_wait_time: int
    total_queue: int
    usage_cost: float

class BerthAvailabilityResponse(BaseModel):
    """Berth availability response"""
    berths: List[Dict[str, Any]]
    vessel_size: str
    arrival_date: str
    usage_cost: float

class PortHealthResponse(BaseModel):
    """Port health check response"""
    port_code: str
    status: str
    response_time_ms: int
    timestamp: str
    error: Optional[str] = None

# Error Response Schemas

class PortErrorResponse(BaseModel):
    """Standard port API error response"""
    error: str
    message: str
    port_code: Optional[str] = None
    operation: Optional[str] = None
    timestamp: str

class PortAddonRequiredResponse(BaseModel):
    """Response when port add-on is required"""
    error: str
    message: str
    pricing: Dict[str, str]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

# Internal Models (not exposed via API)

class PortCredentialInternal(BaseModel):
    """Internal credential model with encrypted data"""
    id: str
    port_id: str
    company_id: str
    encrypted_credentials: str
    credential_type: str
    expires_at: Optional[datetime] = None
    validation_status: str
    consecutive_failures: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

class PortUsageRecord(BaseModel):
    """Internal usage record model"""
    id: str
    company_id: str
    port_code: str
    operation: str
    operation_cost: Decimal
    status: str
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    timestamp: datetime

# Validation helpers

class PortCredentialValidator:
    """Validates port credential structure"""
    
    @staticmethod
    def validate_api_key_credentials(credentials: Dict[str, Any]) -> bool:
        """Validate API key credentials"""
        return "api_key" in credentials
    
    @staticmethod
    def validate_oauth2_credentials(credentials: Dict[str, Any]) -> bool:
        """Validate OAuth2 credentials"""
        required = ["client_id", "client_secret", "token_url"]
        return all(field in credentials for field in required)
    
    @staticmethod
    def validate_jwt_credentials(credentials: Dict[str, Any]) -> bool:
        """Validate JWT credentials"""
        required = ["private_key", "issuer", "audience"]
        return all(field in credentials for field in required)
    
    @staticmethod
    def validate_client_cert_credentials(credentials: Dict[str, Any]) -> bool:
        """Validate client certificate credentials"""
        required = ["certificate_path", "private_key_path"]
        return all(field in credentials for field in required)
    
    @staticmethod
    def validate_basic_auth_credentials(credentials: Dict[str, Any]) -> bool:
        """Validate basic auth credentials"""
        required = ["username", "password"]
        return all(field in credentials for field in required)

# Utility functions

def format_container_number(container_number: str) -> str:
    """Format container number to standard format"""
    # Remove any spaces or special characters
    cleaned = ''.join(c for c in container_number.upper() if c.isalnum())
    
    # Validate format: 4 letters + 7 digits
    if len(cleaned) == 11 and cleaned[:4].isalpha() and cleaned[4:].isdigit():
        return f"{cleaned[:4]}{cleaned[4:]}"
    
    raise ValueError(f"Invalid container number format: {container_number}")

def calculate_operation_cost(operation: str) -> Decimal:
    """Calculate cost for operation"""
    costs = {
        "track_container": Decimal("0.50"),
        "vessel_schedule": Decimal("1.00"),
        "gate_status": Decimal("1.50"),
        "document_upload": Decimal("2.00"),
        "berth_availability": Decimal("0.75")
    }
    return costs.get(operation, Decimal("0.75"))

def format_port_code(port_code: str) -> str:
    """Format port code to standard format"""
    return port_code.upper().strip()

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional

from app.config.db import get_db
from app.services.port_credential_service import PortCredentialService
from app.services.port_billing_service import PortBillingService
from app.services.port_management_service import PortManagementService
from app.schema.portSchema import *
from app.routes.user import get_current_user
from app.models.port import PortAddonPricing, CompanyPortAddon
from app.config.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ports", tags=["Port Credentials"])

def get_current_company_id(current_user: dict = Depends(get_current_user)) -> str:
    """Extract company ID from current user"""
    company_id = current_user.get("companyId")
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not associated with company"
        )
    return company_id

def require_port_addon(
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Ensure company has enabled port credentials add-on"""
    addon = db.query(CompanyPortAddon).filter(
        CompanyPortAddon.company_id == company_id,
        CompanyPortAddon.is_active == True
    ).first()
    
    if not addon:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "Port Credentials add-on required",
                "message": "Enable port credentials in Settings → Integrations",
                "pricing": {
                    "pay_per_request": "$0.50-$2.00 per request",
                    "unlimited": "$99/month unlimited"
                }
            }
        )

# Port Registry Endpoints

@router.get("/available", response_model=List[PortResponse])
def list_available_ports(db: Session = Depends(get_db)):
    """List all available ports (no auth required for discovery)"""
    service = PortManagementService(db)
    return service.list_ports()

@router.get("/addon/status", response_model=PortAddonStatusResponse)
def get_addon_status(
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get port add-on status and usage"""
    billing_service = PortBillingService(db)
    stats = billing_service.get_usage_stats(company_id, months=3)
    return PortAddonStatusResponse(**stats)

# Add-on Management

@router.post("/addon/enable", response_model=CompanyPortAddonResponse)
def enable_port_addon(
    request: EnablePortAddonRequest,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Enable port credentials add-on"""
    billing_service = PortBillingService(db)
    addon = billing_service.enable_port_addon(
        company_id=company_id,
        pricing_model=request.pricing_model,
        auto_optimize=request.auto_optimize
    )
    return CompanyPortAddonResponse(
        id=addon.id,
        pricing_model=addon.pricing_model.value,
        monthly_price=addon.monthly_price,
        subscription_start=addon.subscription_start,
        subscription_end=addon.subscription_end,
        current_month_requests=addon.current_month_requests,
        current_month_cost=addon.current_month_cost,
        auto_optimize=addon.auto_optimize,
        is_active=addon.is_active
    )

@router.post("/addon/switch-pricing", response_model=CompanyPortAddonResponse)
def switch_pricing_model(
    request: SwitchPricingRequest,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
    _=Depends(require_port_addon)
):
    """Switch between pay-per-request and unlimited"""
    billing_service = PortBillingService(db)
    addon = billing_service.switch_pricing_model(company_id, request.new_model)
    return CompanyPortAddonResponse(
        id=addon.id,
        pricing_model=addon.pricing_model.value,
        monthly_price=addon.monthly_price,
        subscription_start=addon.subscription_start,
        subscription_end=addon.subscription_end,
        current_month_requests=addon.current_month_requests,
        current_month_cost=addon.current_month_cost,
        auto_optimize=addon.auto_optimize,
        is_active=addon.is_active
    )

# Credential Management

@router.post("/credentials", response_model=PortCredentialResponse)
def create_credential(
    request: PortCredentialCreateRequest,
    current_user: dict = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
    _=Depends(require_port_addon)
):
    """Store encrypted credentials for a port"""
    service = PortCredentialService(db)
    credential = service.create_credential(
        port_id=request.port_id,
        company_id=company_id,
        credentials=request.credentials,
        credential_type=request.credential_type,
        user_id=current_user.get("userId"),
        expires_at=request.expires_at
    )
    return PortCredentialResponse(
        id=credential.id,
        port_id=credential.port_id,
        credential_type=credential.credential_type,
        expires_at=credential.expires_at,
        validation_status=credential.validation_status,
        is_active=credential.is_active,
        created_at=credential.created_at,
        updated_at=credential.updated_at
    )

@router.get("/credentials", response_model=List[PortCredentialResponse])
def list_credentials(
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
    _=Depends(require_port_addon)
):
    """List all port credentials for company"""
    service = PortCredentialService(db)
    credentials = service.get_company_credentials(company_id=company_id)
    
    return [
        PortCredentialResponse(
            id=cred.id,
            port_id=cred.port_id,
            credential_type=cred.credential_type,
            expires_at=cred.expires_at,
            validation_status=cred.validation_status,
            is_active=cred.is_active,
            created_at=cred.created_at,
            updated_at=cred.updated_at
        )
        for cred in credentials
    ]

@router.post("/credentials/{credential_id}/validate")
def validate_credential(
    credential_id: str,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
    _=Depends(require_port_addon)
):
    """Validate port credentials"""
    service = PortCredentialService(db)
    is_valid = service.validate_credential(credential_id)
    
    return {
        "credential_id": credential_id,
        "valid": is_valid,
        "timestamp": "2024-01-15T10:00:00Z"  # TODO: Use actual timestamp
    }

# Port Operations (with usage tracking)

@router.post("/operations/track-container", response_model=ContainerTrackingResponse)
async def track_container(
    request: TrackContainerRequest,
    current_user: dict = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
    _=Depends(require_port_addon)
):
    """Track container at port (billable operation)"""
    
    # Execute port operation
    management_service = PortManagementService(db)
    result = await management_service.execute_port_operation(
        company_id=company_id,
        port_code=request.port_code,
        operation="track_container",
        container_number=request.container_number
    )
    
    if result["status"] == "success":
        container_data = result["result"]
        usage_cost = calculate_operation_cost("track_container")
        
        return ContainerTrackingResponse(
            container_number=container_data["container_number"],
            status=container_data["status"],
            location=container_data["location"],
            last_movement=container_data["last_movement"],
            terminal=container_data.get("terminal"),
            vessel=container_data.get("vessel"),
            holds=container_data.get("holds", []),
            estimated_gate_time=container_data.get("estimated_gate_time"),
            weight=container_data.get("weight"),
            seal_number=container_data.get("seal_number"),
            customs_status=container_data.get("customs_status"),
            usage_cost=float(usage_cost)
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["result"]["error"]
        )

@router.post("/operations/vessel-schedule", response_model=VesselScheduleResponse)
async def get_vessel_schedule(
    request: VesselScheduleRequest,
    current_user: dict = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
    _=Depends(require_port_addon)
):
    """Get vessel schedule (billable operation)"""
    
    # Execute port operation
    management_service = PortManagementService(db)
    result = await management_service.execute_port_operation(
        company_id=company_id,
        port_code=request.port_code,
        operation="vessel_schedule",
        vessel_id=request.vessel_id
    )
    
    if result["status"] == "success":
        vessels = result["result"]
        usage_cost = calculate_operation_cost("vessel_schedule")
        
        return VesselScheduleResponse(
            vessels=vessels,
            port_code=request.port_code,
            timestamp=result["timestamp"],
            usage_cost=float(usage_cost)
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["result"]["error"]
        )

@router.post("/operations/gate-status", response_model=GateStatusResponse)
async def get_gate_status(
    request: GateStatusRequest,
    current_user: dict = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
    _=Depends(require_port_addon)
):
    """Get gate status (billable operation)"""
    
    # Execute port operation
    management_service = PortManagementService(db)
    result = await management_service.execute_port_operation(
        company_id=company_id,
        port_code=request.port_code,
        operation="gate_status"
    )
    
    if result["status"] == "success":
        gate_data = result["result"]
        usage_cost = calculate_operation_cost("gate_status")
        
        return GateStatusResponse(
            gates=gate_data["gates"],
            last_updated=gate_data["last_updated"],
            average_wait_time=gate_data["average_wait_time"],
            total_queue=gate_data["total_queue"],
            usage_cost=float(usage_cost)
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["result"]["error"]
        )

@router.post("/operations/document-upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: DocumentUploadRequest,
    current_user: dict = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
    _=Depends(require_port_addon)
):
    """Upload document (billable operation)"""
    
    # Execute port operation
    management_service = PortManagementService(db)
    result = await management_service.execute_port_operation(
        company_id=company_id,
        port_code=request.port_code,
        operation="document_upload",
        document_type=request.document_type,
        file_data=request.file_data,
        metadata=request.metadata
    )
    
    if result["status"] == "success":
        doc_data = result["result"]
        usage_cost = calculate_operation_cost("document_upload")
        
        return DocumentUploadResponse(
            document_id=doc_data["document_id"],
            status=doc_data["status"],
            upload_timestamp=doc_data["upload_timestamp"],
            reference_number=doc_data.get("reference_number"),
            validation_errors=doc_data.get("validation_errors", []),
            usage_cost=float(usage_cost)
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["result"]["error"]
        )

@router.post("/operations/berth-availability", response_model=BerthAvailabilityResponse)
async def check_berth_availability(
    request: BerthAvailabilityRequest,
    current_user: dict = Depends(get_current_user),
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
    _=Depends(require_port_addon)
):
    """Check berth availability (billable operation)"""
    
    # Execute port operation
    management_service = PortManagementService(db)
    result = await management_service.execute_port_operation(
        company_id=company_id,
        port_code=request.port_code,
        operation="berth_availability",
        vessel_size=request.vessel_size,
        arrival_date=request.arrival_date
    )
    
    if result["status"] == "success":
        berth_data = result["result"]
        usage_cost = calculate_operation_cost("berth_availability")
        
        return BerthAvailabilityResponse(
            berths=berth_data,
            vessel_size=request.vessel_size,
            arrival_date=request.arrival_date,
            usage_cost=float(usage_cost)
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["result"]["error"]
        )

# Health Check

@router.get("/health/{port_code}", response_model=PortHealthResponse)
async def health_check_port(
    port_code: str,
    company_id: str = Depends(get_current_company_id),
    db: Session = Depends(get_db),
    _=Depends(require_port_addon)
):
    """Check port API health"""
    
    management_service = PortManagementService(db)
    health_result = await management_service.health_check_port(port_code, company_id)
    
    return PortHealthResponse(
        port_code=port_code,
        status=health_result["status"],
        response_time_ms=health_result.get("response_time_ms", 0),
        timestamp=health_result["timestamp"],
        error=health_result.get("error")
    )










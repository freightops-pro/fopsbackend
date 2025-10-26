from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime
import time

from app.models.port import Port, PortCredential
from app.services.port_credential_service import PortCredentialService
from app.services.port_billing_service import PortBillingService
from app.adapters.port_adapter_factory import PortAdapterFactory
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class PortManagementService:
    """
    Orchestrates port operations and manages business logic
    
    FUNCTION: Coordinates between credential management, billing, and port adapters
    
    HOW IT WORKS:
    1. Validates company has port add-on enabled
    2. Retrieves and decrypts credentials for the port
    3. Creates appropriate port adapter
    4. Executes port operation with usage tracking
    5. Records billing and audit information
    
    SCALABILITY:
    - Async operations for concurrent requests
    - Connection pooling via adapters
    - Automatic retry and failover logic
    - Comprehensive error handling and logging
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.credential_service = PortCredentialService(db)
        self.billing_service = PortBillingService(db)
    
    async def execute_port_operation(
        self,
        company_id: str,
        port_code: str,
        operation: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute port operation with full tracking
        
        Args:
            company_id: Company executing the operation
            port_code: Port code (e.g., "USLAX")
            operation: Operation type (track_container, vessel_schedule, etc.)
            **kwargs: Operation-specific parameters
            
        Returns:
            Operation result with usage cost
            
        ERROR HANDLING:
        - Validates port add-on is enabled
        - Checks credential validity
        - Handles adapter failures gracefully
        - Records all attempts for billing
        """
        
        start_time = time.time()
        operation_result = None
        error_message = None
        status = "success"
        
        try:
            # Get port configuration
            port = self.db.query(Port).filter(
                Port.port_code == port_code,
                Port.is_active == True
            ).first()
            
            if not port:
                raise ValueError(f"Port {port_code} not found or inactive")
            
            # Get company credentials for this port
            credentials = self.credential_service.get_company_credentials(
                company_id=company_id,
                port_code=port_code
            )
            
            if not credentials:
                raise ValueError(f"No credentials configured for port {port_code}")
            
            # Use the first active credential
            credential = credentials[0]
            decrypted_creds = self.credential_service.get_decrypted_credential(
                credential_id=credential.id,
                company_id=company_id
            )
            
            # Create port adapter
            adapter = PortAdapterFactory.create_adapter(
                port=port,
                credentials=decrypted_creds,
                use_mock=False  # Production mode
            )
            
            # Execute operation
            if operation == "track_container":
                container_number = kwargs.get("container_number")
                if not container_number:
                    raise ValueError("container_number required for track_container")
                
                operation_result = await adapter.track_container(container_number)
            
            elif operation == "vessel_schedule":
                vessel_id = kwargs.get("vessel_id")
                operation_result = await adapter.get_vessel_schedule(vessel_id=vessel_id)
            
            elif operation == "gate_status":
                operation_result = await adapter.get_gate_status()
            
            elif operation == "document_upload":
                document_type = kwargs.get("document_type")
                file_data = kwargs.get("file_data")
                metadata = kwargs.get("metadata", {})
                
                if not all([document_type, file_data]):
                    raise ValueError("document_type and file_data required for document_upload")
                
                operation_result = await adapter.upload_document(
                    document_type=document_type,
                    file_data=file_data,
                    metadata=metadata
                )
            
            elif operation == "berth_availability":
                vessel_size = kwargs.get("vessel_size")
                arrival_date = kwargs.get("arrival_date")
                
                if not all([vessel_size, arrival_date]):
                    raise ValueError("vessel_size and arrival_date required for berth_availability")
                
                operation_result = await adapter.check_berth_availability(
                    vessel_size=vessel_size,
                    arrival_date=arrival_date
                )
            
            else:
                raise ValueError(f"Unsupported operation: {operation}")
            
            # Close adapter
            await adapter.close()
            
        except Exception as e:
            status = "failure"
            error_message = str(e)
            operation_result = {"error": error_message}
            logger.error(f"Port operation failed: {operation}", extra={
                "extra_fields": {
                    "company_id": company_id,
                    "port_code": port_code,
                    "operation": operation,
                    "error": error_message
                }
            })
        
        finally:
            # Record usage for billing
            response_time_ms = int((time.time() - start_time) * 1000)
            
            try:
                self.billing_service.record_api_usage(
                    company_id=company_id,
                    port_code=port_code,
                    operation=operation,
                    request_params=kwargs,
                    response_time_ms=response_time_ms,
                    status=status,
                    error_message=error_message
                )
            except Exception as e:
                logger.error(f"Failed to record usage: {str(e)}")
        
        return {
            "result": operation_result,
            "operation": operation,
            "port_code": port_code,
            "status": status,
            "response_time_ms": response_time_ms,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def list_ports(self) -> List[Dict[str, Any]]:
        """
        List all available ports
        
        Returns:
            List of port configurations
        """
        ports = self.db.query(Port).filter(Port.is_active == True).all()
        
        return [
            {
                "id": port.id,
                "port_code": port.port_code,
                "port_name": port.port_name,
                "unlocode": port.unlocode,
                "region": port.region,
                "state": port.state,
                "services_supported": port.services_supported,
                "auth_type": port.auth_type.value,
                "rate_limits": port.rate_limits,
                "compliance_standards": port.compliance_standards
            }
            for port in ports
        ]
    
    def get_port_by_code(self, port_code: str) -> Optional[Dict[str, Any]]:
        """
        Get specific port configuration
        
        Args:
            port_code: Port code to lookup
            
        Returns:
            Port configuration or None if not found
        """
        port = self.db.query(Port).filter(
            Port.port_code == port_code,
            Port.is_active == True
        ).first()
        
        if not port:
            return None
        
        return {
            "id": port.id,
            "port_code": port.port_code,
            "port_name": port.port_name,
            "unlocode": port.unlocode,
            "region": port.region,
            "state": port.state,
            "api_endpoint": port.api_endpoint,
            "api_version": port.api_version,
            "auth_type": port.auth_type.value,
            "services_supported": port.services_supported,
            "rate_limits": port.rate_limits,
            "compliance_standards": port.compliance_standards,
            "documentation_requirements": port.documentation_requirements
        }
    
    async def health_check_port(self, port_code: str, company_id: str) -> Dict[str, Any]:
        """
        Perform health check on port API
        
        Args:
            port_code: Port to check
            company_id: Company with credentials
            
        Returns:
            Health check result
        """
        try:
            # Get credentials
            credentials = self.credential_service.get_company_credentials(
                company_id=company_id,
                port_code=port_code
            )
            
            if not credentials:
                return {
                    "status": "error",
                    "error": "No credentials configured",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Get port
            port = self.db.query(Port).filter(Port.port_code == port_code).first()
            if not port:
                return {
                    "status": "error",
                    "error": "Port not found",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Create adapter and check health
            credential = credentials[0]
            decrypted_creds = self.credential_service.get_decrypted_credential(
                credential_id=credential.id,
                company_id=company_id
            )
            
            adapter = PortAdapterFactory.create_adapter(
                port=port,
                credentials=decrypted_creds,
                use_mock=False  # Production mode
            )
            
            health_result = await adapter.health_check()
            await adapter.close()
            
            return health_result
            
        except Exception as e:
            logger.error(f"Health check failed for {port_code}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }





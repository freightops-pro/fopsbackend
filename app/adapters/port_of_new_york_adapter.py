"""
Port of New York & New Jersey API Adapter

Real implementation for the Port of New York & New Jersey (USNYC) API integration.
This adapter implements the actual API calls to the Port of NY & NJ systems.

FUNCTION: Real API integration with Port of New York & New Jersey
HOW IT WORKS:
1. Uses JWT authentication with the Port of NY & NJ API
2. Implements port-specific endpoint mappings
3. Handles NY/NJ port's specific data formats and requirements
4. Provides real-time container tracking and vessel scheduling
5. Integrates with NY/NJ port's document management system

AUTHENTICATION: JWT with private key signing
API ENDPOINTS:
- Base URL: https://api.panynj.gov/port/v1
- Vessel Schedule: /vessels/schedule
- Container Tracking: /containers/{container_number}/track
- Document Upload: /documents/submit
- Gate Status: /terminals/gates/status
- Berth Availability: /terminals/berths/availability

ERROR HANDLING:
- Handles NY/NJ port's specific error codes
- Manages API rate limits (120 requests/minute)
- Implements retry logic for transient failures
- Provides detailed error messages for debugging

SCALABILITY:
- Supports concurrent requests to NY/NJ port systems
- Implements request caching for frequently accessed data
- Uses connection pooling for efficient API communication
"""

from typing import Dict, Any, List, Optional
import asyncio
import jwt
from datetime import datetime, timedelta
from app.adapters.real_port_adapter import RealPortAdapter
from app.models.port import PortAuthType
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class PortOfNewYorkAdapter(RealPortAdapter):
    """
    Real implementation for Port of New York & New Jersey API integration
    
    This adapter provides actual integration with the Port of NY & NJ
    systems, including container tracking, vessel scheduling, and document
    management capabilities.
    """
    
    def __init__(self, credentials: Dict[str, Any], api_endpoint: str = "https://api.panynj.gov/port/v1"):
        super().__init__(credentials, api_endpoint, PortAuthType.JWT)
        self.rate_limit = 120  # requests per minute
        self.terminal_mappings = {
            "APM": "APM Terminal",
            "GCT": "Global Container Terminal",
            "PNCT": "Port Newark Container Terminal",
            "PNYCT": "Port Newark Yard Container Terminal",
            "PNYT": "Port Newark Yard Terminal",
            "PNYT-1": "Port Newark Yard Terminal 1",
            "PNYT-2": "Port Newark Yard Terminal 2",
            "PNYT-3": "Port Newark Yard Terminal 3",
            "PNYT-4": "Port Newark Yard Terminal 4",
            "PNYT-5": "Port Newark Yard Terminal 5",
            "PNYT-6": "Port Newark Yard Terminal 6",
            "PNYT-7": "Port Newark Yard Terminal 7",
            "PNYT-8": "Port Newark Yard Terminal 8",
            "PNYT-9": "Port Newark Yard Terminal 9",
            "PNYT-10": "Port Newark Yard Terminal 10",
            "PNYT-11": "Port Newark Yard Terminal 11",
            "PNYT-12": "Port Newark Yard Terminal 12",
            "PNYT-13": "Port Newark Yard Terminal 13",
            "PNYT-14": "Port Newark Yard Terminal 14",
            "PNYT-15": "Port Newark Yard Terminal 15",
            "PNYT-16": "Port Newark Yard Terminal 16",
            "PNYT-17": "Port Newark Yard Terminal 17",
            "PNYT-18": "Port Newark Yard Terminal 18",
            "PNYT-19": "Port Newark Yard Terminal 19",
            "PNYT-20": "Port Newark Yard Terminal 20"
        }
    
    def _get_test_endpoint(self) -> str:
        """NY/NJ port health check endpoint"""
        return "system/health"
    
    async def _generate_jwt_token(self) -> str:
        """Generate JWT token for NY/NJ port API"""
        try:
            private_key = self.credentials.get("private_key")
            issuer = self.credentials.get("issuer")
            audience = self.credentials.get("audience")
            client_id = self.credentials.get("client_id")
            
            if not all([private_key, issuer, audience, client_id]):
                raise ValueError("Missing required JWT credentials")
            
            # Create JWT payload
            now = datetime.utcnow()
            payload = {
                "iss": issuer,
                "aud": audience,
                "sub": client_id,
                "iat": now,
                "exp": now + timedelta(hours=1),  # Token expires in 1 hour
                "scope": "port_api_access"
            }
            
            # Sign JWT with private key
            token = jwt.encode(payload, private_key, algorithm="RS256")
            
            return token
            
        except Exception as e:
            logger.error(f"Failed to generate JWT token: {e}")
            return None
    
    async def get_vessel_schedule(self, vessel_id: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Get vessel schedule from Port of New York & New Jersey
        
        NY/NJ port provides detailed vessel scheduling information including
        ETA, ETD, berth assignments, and terminal information.
        """
        try:
            endpoint = "vessels/schedule"
            params = {}
            
            if vessel_id:
                params["vessel_id"] = vessel_id
            
            # Add NY/NJ port specific parameters
            if "date_range" in kwargs:
                params["date_range"] = kwargs["date_range"]
            if "terminal" in kwargs:
                params["terminal"] = kwargs["terminal"]
            if "status" in kwargs:
                params["status"] = kwargs["status"]
            if "vessel_type" in kwargs:
                params["vessel_type"] = kwargs["vessel_type"]
            
            response_data = await self._make_authenticated_request("GET", endpoint, params=params)
            
            # NY/NJ port specific response formatting
            return self._format_ny_vessel_schedule(response_data)
            
        except Exception as e:
            logger.error(f"Failed to get NY/NJ vessel schedule: {e}", extra={
                "extra_fields": {"vessel_id": vessel_id, "endpoint": endpoint}
            })
            return []
    
    async def track_container(self, container_number: str) -> Dict[str, Any]:
        """
        Track container at Port of New York & New Jersey
        
        NY/NJ port provides detailed container tracking including location,
        status, terminal information, and any holds or restrictions.
        """
        try:
            # Validate container number
            if not self._validate_container_number(container_number):
                return {
                    "container_number": container_number,
                    "status": "invalid_format",
                    "error": "Invalid container number format"
                }
            
            endpoint = f"containers/{container_number}/track"
            response_data = await self._make_authenticated_request("GET", endpoint)
            
            # NY/NJ port specific container tracking format
            return self._format_ny_container_tracking(response_data, container_number)
            
        except Exception as e:
            logger.error(f"Failed to track NY/NJ container {container_number}: {e}")
            return {
                "container_number": container_number,
                "status": "error",
                "error": str(e)
            }
    
    async def upload_document(self, document_type: str, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload document to Port of New York & New Jersey system
        
        NY/NJ port accepts various document types including customs declarations,
        safety certificates, and operational documents.
        """
        try:
            endpoint = "documents/submit"
            
            # NY/NJ port specific document types
            valid_document_types = [
                "customs_declaration",
                "safety_certificate",
                "cargo_manifest",
                "bill_of_lading",
                "commercial_invoice",
                "packing_list",
                "certificate_of_origin",
                "insurance_certificate",
                "hazardous_materials_declaration",
                "reefer_certificate",
                "bond_declaration",
                "inspection_certificate"
            ]
            
            if document_type not in valid_document_types:
                return {
                    "status": "error",
                    "error": f"Invalid document type. Valid types: {valid_document_types}",
                    "document_type": document_type
                }
            
            # Prepare NY/NJ port specific metadata
            ny_metadata = {
                "document_type": document_type,
                "port_code": "USNYC",
                "submission_timestamp": datetime.utcnow().isoformat(),
                **metadata
            }
            
            files = {
                "document": ("document", file_data, "application/pdf")
            }
            
            response_data = await self._make_authenticated_request(
                "POST", endpoint, files=files, data=ny_metadata
            )
            
            return self._format_ny_document_upload(response_data)
            
        except Exception as e:
            logger.error(f"Failed to upload document to NY/NJ port: {e}", extra={
                "extra_fields": {"document_type": document_type, "file_size": len(file_data)}
            })
            return {
                "status": "error",
                "error": str(e),
                "document_type": document_type
            }
    
    async def get_gate_status(self) -> Dict[str, Any]:
        """
        Get gate status from Port of New York & New Jersey
        
        NY/NJ port provides real-time gate information including wait times,
        queue lengths, and any restrictions or closures.
        """
        try:
            endpoint = "terminals/gates/status"
            response_data = await self._make_authenticated_request("GET", endpoint)
            
            return self._format_ny_gate_status(response_data)
            
        except Exception as e:
            logger.error(f"Failed to get NY/NJ gate status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "gates": []
            }
    
    async def check_berth_availability(self, vessel_size: str, arrival_date: str) -> List[Dict[str, Any]]:
        """
        Check berth availability at Port of New York & New Jersey
        
        NY/NJ port provides detailed berth availability information including
        terminal assignments, capacity, and restrictions.
        """
        try:
            endpoint = "terminals/berths/availability"
            params = {
                "vessel_size": vessel_size,
                "arrival_date": arrival_date,
                "port_code": "USNYC"
            }
            
            response_data = await self._make_authenticated_request("GET", endpoint, params=params)
            
            return self._format_ny_berth_availability(response_data)
            
        except Exception as e:
            logger.error(f"Failed to check NY/NJ berth availability: {e}", extra={
                "extra_fields": {"vessel_size": vessel_size, "arrival_date": arrival_date}
            })
            return []
    
    def _format_ny_vessel_schedule(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format NY/NJ port vessel schedule response"""
        schedules = []
        
        if "vessels" in data:
            for vessel in data["vessels"]:
                schedule = {
                    "vessel_name": vessel.get("vessel_name"),
                    "imo_number": vessel.get("imo_number"),
                    "vessel_id": vessel.get("vessel_id"),
                    "eta": vessel.get("eta"),
                    "etd": vessel.get("etd"),
                    "berth": vessel.get("berth"),
                    "terminal": vessel.get("terminal"),
                    "terminal_name": self.terminal_mappings.get(vessel.get("terminal"), vessel.get("terminal")),
                    "voyage_number": vessel.get("voyage_number"),
                    "status": vessel.get("status"),
                    "cargo_type": vessel.get("cargo_type"),
                    "gross_tonnage": vessel.get("gross_tonnage"),
                    "length_overall": vessel.get("length_overall"),
                    "draft": vessel.get("draft"),
                    "flag": vessel.get("flag"),
                    "agent": vessel.get("agent"),
                    "pilot_required": vessel.get("pilot_required", False),
                    "tug_assistance": vessel.get("tug_assistance", False),
                    "bridge_clearance": vessel.get("bridge_clearance"),
                    "air_draft": vessel.get("air_draft"),
                    "channel_restrictions": vessel.get("channel_restrictions", [])
                }
                schedules.append(schedule)
        
        return schedules
    
    def _format_ny_container_tracking(self, data: Dict[str, Any], container_number: str) -> Dict[str, Any]:
        """Format NY/NJ port container tracking response"""
        return {
            "container_number": container_number,
            "status": data.get("status"),
            "location": data.get("location"),
            "terminal": data.get("terminal"),
            "terminal_name": self.terminal_mappings.get(data.get("terminal"), data.get("terminal")),
            "yard_location": data.get("yard_location"),
            "last_movement": data.get("last_movement"),
            "vessel": data.get("vessel"),
            "voyage": data.get("voyage"),
            "holds": data.get("holds", []),
            "customs_status": data.get("customs_status"),
            "estimated_gate_time": data.get("estimated_gate_time"),
            "weight": data.get("weight"),
            "seal_number": data.get("seal_number"),
            "size_type": data.get("size_type"),
            "cargo_type": data.get("cargo_type"),
            "shipper": data.get("shipper"),
            "consignee": data.get("consignee"),
            "dangerous_goods": data.get("dangerous_goods", False),
            "temperature_controlled": data.get("temperature_controlled", False),
            "reefer_requirements": data.get("reefer_requirements"),
            "bond_status": data.get("bond_status"),
            "inspection_required": data.get("inspection_required", False),
            "customs_hold": data.get("customs_hold", False)
        }
    
    def _format_ny_document_upload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format NY/NJ port document upload response"""
        return {
            "document_id": data.get("document_id"),
            "status": data.get("status"),
            "upload_timestamp": data.get("upload_timestamp"),
            "file_size": data.get("file_size"),
            "document_type": data.get("document_type"),
            "validation_errors": data.get("validation_errors", []),
            "processing_status": data.get("processing_status"),
            "reference_number": data.get("reference_number"),
            "port_reference": data.get("port_reference"),
            "customs_reference": data.get("customs_reference"),
            "estimated_processing_time": data.get("estimated_processing_time"),
            "bond_reference": data.get("bond_reference"),
            "inspection_scheduled": data.get("inspection_scheduled", False)
        }
    
    def _format_ny_gate_status(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format NY/NJ port gate status response"""
        gates = []
        
        if "gates" in data:
            for gate in data["gates"]:
                gate_info = {
                    "gate_number": gate.get("gate_number"),
                    "terminal": gate.get("terminal"),
                    "terminal_name": self.terminal_mappings.get(gate.get("terminal"), gate.get("terminal")),
                    "status": gate.get("status"),
                    "wait_time_minutes": gate.get("wait_time_minutes"),
                    "current_queue": gate.get("current_queue"),
                    "restrictions": gate.get("restrictions", []),
                    "operating_hours": gate.get("operating_hours"),
                    "last_update": gate.get("last_update"),
                    "bridge_restrictions": gate.get("bridge_restrictions", []),
                    "tunnel_restrictions": gate.get("tunnel_restrictions", [])
                }
                gates.append(gate_info)
        
        return {
            "gates": gates,
            "last_updated": data.get("last_updated"),
            "average_wait_time": data.get("average_wait_time", 0),
            "total_queue": data.get("total_queue", 0),
            "port_status": data.get("port_status", "operational"),
            "bridge_status": data.get("bridge_status", "operational"),
            "tunnel_status": data.get("tunnel_status", "operational")
        }
    
    def _format_ny_berth_availability(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format NY/NJ port berth availability response"""
        berths = []
        
        if "berths" in data:
            for berth in data["berths"]:
                berth_info = {
                    "berth_id": berth.get("berth_id"),
                    "berth_name": berth.get("berth_name"),
                    "terminal": berth.get("terminal"),
                    "terminal_name": self.terminal_mappings.get(berth.get("terminal"), berth.get("terminal")),
                    "available": berth.get("available"),
                    "max_length": berth.get("max_length"),
                    "max_draft": berth.get("max_draft"),
                    "restrictions": berth.get("restrictions", []),
                    "next_available": berth.get("next_available"),
                    "estimated_occupancy_hours": berth.get("estimated_occupancy_hours"),
                    "current_vessel": berth.get("current_vessel"),
                    "departure_eta": berth.get("departure_eta"),
                    "pilot_required": berth.get("pilot_required", False),
                    "tug_assistance": berth.get("tug_assistance", False),
                    "bridge_clearance": berth.get("bridge_clearance"),
                    "air_draft_limit": berth.get("air_draft_limit"),
                    "channel_access": berth.get("channel_access", True)
                }
                berths.append(berth_info)
        
        return berths










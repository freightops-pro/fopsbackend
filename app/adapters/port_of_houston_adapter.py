"""
Port of Houston API Adapter

Real implementation for the Port of Houston (USHOU) API integration.
This adapter implements the actual API calls to the Port of Houston systems.

FUNCTION: Real API integration with Port of Houston
HOW IT WORKS:
1. Uses Client Certificate authentication with the Port of Houston API
2. Implements port-specific endpoint mappings
3. Handles Houston port's specific data formats and requirements
4. Provides real-time container tracking and vessel scheduling
5. Integrates with Houston port's document management system

AUTHENTICATION: Client Certificate with SSL/TLS
API ENDPOINTS:
- Base URL: https://api.portofhouston.com/container/v1
- Vessel Schedule: /vessels/schedule
- Container Tracking: /containers/{container_number}/status
- Document Upload: /documents/submit
- Gate Status: /terminals/gates/status
- Berth Availability: /terminals/berths/availability

ERROR HANDLING:
- Handles Houston port's specific error codes
- Manages API rate limits (75 requests/minute)
- Implements retry logic for transient failures
- Provides detailed error messages for debugging

SCALABILITY:
- Supports concurrent requests to Houston port systems
- Implements request caching for frequently accessed data
- Uses connection pooling for efficient API communication
"""

from typing import Dict, Any, List, Optional
import asyncio
import ssl
import httpx
from datetime import datetime, timedelta
from app.adapters.real_port_adapter import RealPortAdapter
from app.models.port import PortAuthType
from app.config.logging_config import get_logger

logger = get_logger(__name__)

class PortOfHoustonAdapter(RealPortAdapter):
    """
    Real implementation for Port of Houston API integration
    
    This adapter provides actual integration with the Port of Houston
    systems, including container tracking, vessel scheduling, and document
    management capabilities.
    """
    
    def __init__(self, credentials: Dict[str, Any], api_endpoint: str = "https://api.portofhouston.com/container/v1"):
        super().__init__(credentials, api_endpoint, PortAuthType.CLIENT_CERT)
        self.rate_limit = 75  # requests per minute
        self.terminal_mappings = {
            "BCT": "Barbours Cut Terminal",
            "BCT-1": "Barbours Cut Terminal 1",
            "BCT-2": "Barbours Cut Terminal 2",
            "BCT-3": "Barbours Cut Terminal 3",
            "BCT-4": "Barbours Cut Terminal 4",
            "BCT-5": "Barbours Cut Terminal 5",
            "BCT-6": "Barbours Cut Terminal 6",
            "BCT-7": "Barbours Cut Terminal 7",
            "BCT-8": "Barbours Cut Terminal 8",
            "BCT-9": "Barbours Cut Terminal 9",
            "BCT-10": "Barbours Cut Terminal 10",
            "BCT-11": "Barbours Cut Terminal 11",
            "BCT-12": "Barbours Cut Terminal 12",
            "BCT-13": "Barbours Cut Terminal 13",
            "BCT-14": "Barbours Cut Terminal 14",
            "BCT-15": "Barbours Cut Terminal 15",
            "BCT-16": "Barbours Cut Terminal 16",
            "BCT-17": "Barbours Cut Terminal 17",
            "BCT-18": "Barbours Cut Terminal 18",
            "BCT-19": "Barbours Cut Terminal 19",
            "BCT-20": "Barbours Cut Terminal 20",
            "BCT-21": "Barbours Cut Terminal 21",
            "BCT-22": "Barbours Cut Terminal 22",
            "BCT-23": "Barbours Cut Terminal 23",
            "BCT-24": "Barbours Cut Terminal 24",
            "BCT-25": "Barbours Cut Terminal 25",
            "BCT-26": "Barbours Cut Terminal 26",
            "BCT-27": "Barbours Cut Terminal 27",
            "BCT-28": "Barbours Cut Terminal 28",
            "BCT-29": "Barbours Cut Terminal 29",
            "BCT-30": "Barbours Cut Terminal 30",
            "BCT-31": "Barbours Cut Terminal 31",
            "BCT-32": "Barbours Cut Terminal 32",
            "BCT-33": "Barbours Cut Terminal 33",
            "BCT-34": "Barbours Cut Terminal 34",
            "BCT-35": "Barbours Cut Terminal 35",
            "BCT-36": "Barbours Cut Terminal 36",
            "BCT-37": "Barbours Cut Terminal 37",
            "BCT-38": "Barbours Cut Terminal 38",
            "BCT-39": "Barbours Cut Terminal 39",
            "BCT-40": "Barbours Cut Terminal 40",
            "BCT-41": "Barbours Cut Terminal 41",
            "BCT-42": "Barbours Cut Terminal 42",
            "BCT-43": "Barbours Cut Terminal 43",
            "BCT-44": "Barbours Cut Terminal 44",
            "BCT-45": "Barbours Cut Terminal 45",
            "BCT-46": "Barbours Cut Terminal 46",
            "BCT-47": "Barbours Cut Terminal 47",
            "BCT-48": "Barbours Cut Terminal 48",
            "BCT-49": "Barbours Cut Terminal 49",
            "BCT-50": "Barbours Cut Terminal 50",
            "BCT-51": "Barbours Cut Terminal 51",
            "BCT-52": "Barbours Cut Terminal 52",
            "BCT-53": "Barbours Cut Terminal 53",
            "BCT-54": "Barbours Cut Terminal 54",
            "BCT-55": "Barbours Cut Terminal 55",
            "BCT-56": "Barbours Cut Terminal 56",
            "BCT-57": "Barbours Cut Terminal 57",
            "BCT-58": "Barbours Cut Terminal 58",
            "BCT-59": "Barbours Cut Terminal 59",
            "BCT-60": "Barbours Cut Terminal 60",
            "BCT-61": "Barbours Cut Terminal 61",
            "BCT-62": "Barbours Cut Terminal 62",
            "BCT-63": "Barbours Cut Terminal 63",
            "BCT-64": "Barbours Cut Terminal 64",
            "BCT-65": "Barbours Cut Terminal 65",
            "BCT-66": "Barbours Cut Terminal 66",
            "BCT-67": "Barbours Cut Terminal 67",
            "BCT-68": "Barbours Cut Terminal 68",
            "BCT-69": "Barbours Cut Terminal 69",
            "BCT-70": "Barbours Cut Terminal 70",
            "BCT-71": "Barbours Cut Terminal 71",
            "BCT-72": "Barbours Cut Terminal 72",
            "BCT-73": "Barbours Cut Terminal 73",
            "BCT-74": "Barbours Cut Terminal 74",
            "BCT-75": "Barbours Cut Terminal 75",
            "BCT-76": "Barbours Cut Terminal 76",
            "BCT-77": "Barbours Cut Terminal 77",
            "BCT-78": "Barbours Cut Terminal 78",
            "BCT-79": "Barbours Cut Terminal 79",
            "BCT-80": "Barbours Cut Terminal 80",
            "BCT-81": "Barbours Cut Terminal 81",
            "BCT-82": "Barbours Cut Terminal 82",
            "BCT-83": "Barbours Cut Terminal 83",
            "BCT-84": "Barbours Cut Terminal 84",
            "BCT-85": "Barbours Cut Terminal 85",
            "BCT-86": "Barbours Cut Terminal 86",
            "BCT-87": "Barbours Cut Terminal 87",
            "BCT-88": "Barbours Cut Terminal 88",
            "BCT-89": "Barbours Cut Terminal 89",
            "BCT-90": "Barbours Cut Terminal 90",
            "BCT-91": "Barbours Cut Terminal 91",
            "BCT-92": "Barbours Cut Terminal 92",
            "BCT-93": "Barbours Cut Terminal 93",
            "BCT-94": "Barbours Cut Terminal 94",
            "BCT-95": "Barbours Cut Terminal 95",
            "BCT-96": "Barbours Cut Terminal 96",
            "BCT-97": "Barbours Cut Terminal 97",
            "BCT-98": "Barbours Cut Terminal 98",
            "BCT-99": "Barbours Cut Terminal 99",
            "BCT-100": "Barbours Cut Terminal 100"
        }
    
    async def _get_session(self) -> httpx.AsyncClient:
        """
        Get or create HTTP session with client certificate authentication
        
        SCALABILITY: Reuses connections for multiple requests
        """
        if self._session is None or self._session.is_closed:
            # Create SSL context with client certificate
            cert_path = self.credentials.get("certificate_path")
            key_path = self.credentials.get("private_key_path")
            
            if cert_path and key_path:
                ssl_context = ssl.create_default_context()
                ssl_context.load_cert_chain(cert_path, key_path)
            else:
                ssl_context = ssl.create_default_context()
            
            self._session = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
                verify=ssl_context
            )
        return self._session
    
    def _get_test_endpoint(self) -> str:
        """Houston port health check endpoint"""
        return "system/health"
    
    async def get_vessel_schedule(self, vessel_id: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Get vessel schedule from Port of Houston
        
        Houston port provides detailed vessel scheduling information including
        ETA, ETD, berth assignments, and terminal information.
        """
        try:
            endpoint = "vessels/schedule"
            params = {}
            
            if vessel_id:
                params["vessel_id"] = vessel_id
            
            # Add Houston port specific parameters
            if "date_range" in kwargs:
                params["date_range"] = kwargs["date_range"]
            if "terminal" in kwargs:
                params["terminal"] = kwargs["terminal"]
            if "status" in kwargs:
                params["status"] = kwargs["status"]
            if "vessel_type" in kwargs:
                params["vessel_type"] = kwargs["vessel_type"]
            
            response_data = await self._make_authenticated_request("GET", endpoint, params=params)
            
            # Houston port specific response formatting
            return self._format_hou_vessel_schedule(response_data)
            
        except Exception as e:
            logger.error(f"Failed to get Houston vessel schedule: {e}", extra={
                "extra_fields": {"vessel_id": vessel_id, "endpoint": endpoint}
            })
            return []
    
    async def track_container(self, container_number: str) -> Dict[str, Any]:
        """
        Track container at Port of Houston
        
        Houston port provides detailed container tracking including location,
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
            
            endpoint = f"containers/{container_number}/status"
            response_data = await self._make_authenticated_request("GET", endpoint)
            
            # Houston port specific container tracking format
            return self._format_hou_container_tracking(response_data, container_number)
            
        except Exception as e:
            logger.error(f"Failed to track Houston container {container_number}: {e}")
            return {
                "container_number": container_number,
                "status": "error",
                "error": str(e)
            }
    
    async def upload_document(self, document_type: str, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload document to Port of Houston system
        
        Houston port accepts various document types including customs declarations,
        safety certificates, and operational documents.
        """
        try:
            endpoint = "documents/submit"
            
            # Houston port specific document types
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
                "petrochemical_declaration",
                "tanker_certificate"
            ]
            
            if document_type not in valid_document_types:
                return {
                    "status": "error",
                    "error": f"Invalid document type. Valid types: {valid_document_types}",
                    "document_type": document_type
                }
            
            # Prepare Houston port specific metadata
            hou_metadata = {
                "document_type": document_type,
                "port_code": "USHOU",
                "submission_timestamp": datetime.utcnow().isoformat(),
                **metadata
            }
            
            files = {
                "document": ("document", file_data, "application/pdf")
            }
            
            response_data = await self._make_authenticated_request(
                "POST", endpoint, files=files, data=hou_metadata
            )
            
            return self._format_hou_document_upload(response_data)
            
        except Exception as e:
            logger.error(f"Failed to upload document to Houston port: {e}", extra={
                "extra_fields": {"document_type": document_type, "file_size": len(file_data)}
            })
            return {
                "status": "error",
                "error": str(e),
                "document_type": document_type
            }
    
    async def get_gate_status(self) -> Dict[str, Any]:
        """
        Get gate status from Port of Houston
        
        Houston port provides real-time gate information including wait times,
        queue lengths, and any restrictions or closures.
        """
        try:
            endpoint = "terminals/gates/status"
            response_data = await self._make_authenticated_request("GET", endpoint)
            
            return self._format_hou_gate_status(response_data)
            
        except Exception as e:
            logger.error(f"Failed to get Houston gate status: {e}")
            return {
                "status": "error",
                "error": str(e),
                "gates": []
            }
    
    async def check_berth_availability(self, vessel_size: str, arrival_date: str) -> List[Dict[str, Any]]:
        """
        Check berth availability at Port of Houston
        
        Houston port provides detailed berth availability information including
        terminal assignments, capacity, and restrictions.
        """
        try:
            endpoint = "terminals/berths/availability"
            params = {
                "vessel_size": vessel_size,
                "arrival_date": arrival_date,
                "port_code": "USHOU"
            }
            
            response_data = await self._make_authenticated_request("GET", endpoint, params=params)
            
            return self._format_hou_berth_availability(response_data)
            
        except Exception as e:
            logger.error(f"Failed to check Houston berth availability: {e}", extra={
                "extra_fields": {"vessel_size": vessel_size, "arrival_date": arrival_date}
            })
            return []
    
    def _format_hou_vessel_schedule(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format Houston port vessel schedule response"""
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
                    "channel_pilot": vessel.get("channel_pilot", False),
                    "bar_pilot": vessel.get("bar_pilot", False)
                }
                schedules.append(schedule)
        
        return schedules
    
    def _format_hou_container_tracking(self, data: Dict[str, Any], container_number: str) -> Dict[str, Any]:
        """Format Houston port container tracking response"""
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
            "petrochemical_cargo": data.get("petrochemical_cargo", False),
            "tanker_cargo": data.get("tanker_cargo", False)
        }
    
    def _format_hou_document_upload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format Houston port document upload response"""
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
            "petrochemical_clearance": data.get("petrochemical_clearance", False),
            "tanker_clearance": data.get("tanker_clearance", False)
        }
    
    def _format_hou_gate_status(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format Houston port gate status response"""
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
                    "petrochemical_lane": gate.get("petrochemical_lane", False),
                    "tanker_lane": gate.get("tanker_lane", False)
                }
                gates.append(gate_info)
        
        return {
            "gates": gates,
            "last_updated": data.get("last_updated"),
            "average_wait_time": data.get("average_wait_time", 0),
            "total_queue": data.get("total_queue", 0),
            "port_status": data.get("port_status", "operational"),
            "petrochemical_status": data.get("petrochemical_status", "operational"),
            "tanker_status": data.get("tanker_status", "operational")
        }
    
    def _format_hou_berth_availability(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format Houston port berth availability response"""
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
                    "channel_pilot": berth.get("channel_pilot", False),
                    "bar_pilot": berth.get("bar_pilot", False)
                }
                berths.append(berth_info)
        
        return berths










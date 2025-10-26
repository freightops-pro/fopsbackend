from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime, timedelta
from app.adapters.base_port_adapter import BasePortAdapter
from app.models.port import PortAuthType

class MockPortAdapter(BasePortAdapter):
    """
    Mock port adapter for testing and development
    
    Simulates realistic port API responses without requiring actual credentials
    """
    
    def __init__(self, credentials: Dict[str, Any], api_endpoint: str, auth_type: PortAuthType = PortAuthType.API_KEY):
        super().__init__(credentials, api_endpoint, auth_type)
        self._simulate_delays = True
    
    async def authenticate(self) -> bool:
        """Simulate authentication"""
        if self._simulate_delays:
            await asyncio.sleep(0.1)  # Simulate network delay
        
        # Simulate authentication based on auth type
        if self.auth_type == PortAuthType.API_KEY:
            return self.credentials.get("api_key") is not None
        elif self.auth_type == PortAuthType.OAUTH2:
            return self.credentials.get("client_id") is not None
        elif self.auth_type == PortAuthType.BASIC_AUTH:
            return self.credentials.get("username") is not None
        elif self.auth_type == PortAuthType.JWT:
            return self.credentials.get("private_key") is not None
        elif self.auth_type == PortAuthType.CLIENT_CERT:
            return self.credentials.get("certificate_path") is not None
        
        return False
    
    async def validate_credentials(self) -> bool:
        """Simulate credential validation"""
        if self._simulate_delays:
            await asyncio.sleep(0.05)
        
        # Simulate validation by checking if we can "authenticate"
        return await self.authenticate()
    
    async def get_vessel_schedule(self, vessel_id: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        """Return mock vessel schedule"""
        if self._simulate_delays:
            await asyncio.sleep(0.2)
        
        mock_schedules = [
            {
                "vessel_name": "COSCO SHIPPING UNIVERSE",
                "imo_number": "9154683",
                "vessel_id": "COSCO001",
                "eta": (datetime.utcnow() + timedelta(days=2)).isoformat(),
                "etd": (datetime.utcnow() + timedelta(days=3)).isoformat(),
                "berth": "A-5",
                "terminal": "Terminal 1",
                "voyage_number": "001E",
                "status": "inbound",
                "cargo_type": "container"
            },
            {
                "vessel_name": "EVER GIVEN",
                "imo_number": "9811000",
                "vessel_id": "EVER001",
                "eta": (datetime.utcnow() + timedelta(days=5)).isoformat(),
                "etd": (datetime.utcnow() + timedelta(days=6)).isoformat(),
                "berth": "B-12",
                "terminal": "Terminal 2",
                "voyage_number": "002W",
                "status": "inbound",
                "cargo_type": "container"
            },
            {
                "vessel_name": "MSC OSCAR",
                "imo_number": "9454436",
                "vessel_id": "MSC001",
                "eta": (datetime.utcnow() + timedelta(hours=6)).isoformat(),
                "etd": (datetime.utcnow() + timedelta(days=1)).isoformat(),
                "berth": "C-8",
                "terminal": "Terminal 3",
                "voyage_number": "003E",
                "status": "docked",
                "cargo_type": "container"
            }
        ]
        
        # Filter by vessel_id if provided
        if vessel_id:
            return [schedule for schedule in mock_schedules if schedule.get("vessel_id") == vessel_id]
        
        return mock_schedules
    
    async def track_container(self, container_number: str) -> Dict[str, Any]:
        """Return mock container tracking"""
        if self._simulate_delays:
            await asyncio.sleep(0.15)
        
        # Simulate different container statuses
        statuses = ["in_port", "loaded", "discharged", "at_gate", "in_transit"]
        locations = ["Yard Block A-12", "Gate 3", "Berth A-5", "Terminal 2", "Customs Hold"]
        
        import random
        status = random.choice(statuses)
        location = random.choice(locations)
        
        return {
            "container_number": container_number,
            "status": status,
            "location": location,
            "last_movement": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "terminal": "Terminal 1",
            "vessel": "COSCO SHIPPING UNIVERSE" if status == "loaded" else None,
            "holds": [],
            "estimated_gate_time": (datetime.utcnow() + timedelta(hours=4)).isoformat() if status == "at_gate" else None,
            "weight": "25,000 kg",
            "seal_number": "SEAL123456",
            "customs_status": "cleared"
        }
    
    async def upload_document(self, document_type: str, file_data: bytes, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate document upload"""
        if self._simulate_delays:
            await asyncio.sleep(0.3)
        
        # Simulate document processing
        import uuid
        document_id = str(uuid.uuid4())
        
        return {
            "document_id": document_id,
            "status": "accepted",
            "upload_timestamp": datetime.utcnow().isoformat(),
            "file_size": len(file_data),
            "document_type": document_type,
            "validation_errors": [],
            "processing_status": "completed",
            "reference_number": f"DOC-{document_id[:8].upper()}"
        }
    
    async def get_gate_status(self) -> Dict[str, Any]:
        """Get mock gate status"""
        if self._simulate_delays:
            await asyncio.sleep(0.1)
        
        return {
            "gates": [
                {
                    "gate_number": "Gate 1",
                    "status": "open",
                    "wait_time_minutes": 15,
                    "current_queue": 12,
                    "restrictions": []
                },
                {
                    "gate_number": "Gate 2",
                    "status": "open",
                    "wait_time_minutes": 8,
                    "current_queue": 5,
                    "restrictions": []
                },
                {
                    "gate_number": "Gate 3",
                    "status": "closed",
                    "wait_time_minutes": None,
                    "current_queue": 0,
                    "restrictions": ["maintenance"]
                },
                {
                    "gate_number": "Gate 4",
                    "status": "restricted",
                    "wait_time_minutes": 45,
                    "current_queue": 25,
                    "restrictions": ["oversized_vehicles_only"]
                }
            ],
            "last_updated": datetime.utcnow().isoformat(),
            "average_wait_time": 20,
            "total_queue": 42
        }
    
    async def check_berth_availability(self, vessel_size: str, arrival_date: str) -> List[Dict[str, Any]]:
        """Check mock berth availability"""
        if self._simulate_delays:
            await asyncio.sleep(0.12)
        
        # Simulate berth availability based on vessel size
        berths = []
        
        if vessel_size in ["small", "medium"]:
            berths.extend([
                {
                    "berth_id": "A-1",
                    "berth_name": "Berth A-1",
                    "terminal": "Terminal 1",
                    "available": True,
                    "max_length": 300,
                    "max_draft": 12,
                    "restrictions": [],
                    "next_available": arrival_date,
                    "estimated_occupancy_hours": 24
                },
                {
                    "berth_id": "B-5",
                    "berth_name": "Berth B-5",
                    "terminal": "Terminal 2",
                    "available": True,
                    "max_length": 250,
                    "max_draft": 10,
                    "restrictions": ["daylight_only"],
                    "next_available": arrival_date,
                    "estimated_occupancy_hours": 18
                }
            ])
        
        if vessel_size in ["large", "ultra_large"]:
            berths.extend([
                {
                    "berth_id": "C-10",
                    "berth_name": "Berth C-10",
                    "terminal": "Terminal 3",
                    "available": True,
                    "max_length": 400,
                    "max_draft": 16,
                    "restrictions": [],
                    "next_available": arrival_date,
                    "estimated_occupancy_hours": 36
                },
                {
                    "berth_id": "D-15",
                    "berth_name": "Berth D-15",
                    "terminal": "Terminal 4",
                    "available": False,
                    "max_length": 500,
                    "max_draft": 18,
                    "restrictions": ["ultra_large_vessels_only"],
                    "next_available": (datetime.fromisoformat(arrival_date) + timedelta(days=2)).isoformat(),
                    "estimated_occupancy_hours": 48
                }
            ])
        
        return berths










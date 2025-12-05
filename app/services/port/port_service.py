import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.load import Load
from app.models.port import ContainerTracking, ContainerTrackingEvent, Port, PortIntegration
from app.schemas.port import ContainerTrackingResponse
from app.services.port.adapters.base_adapter import PortAdapter, PortAdapterError
from app.services.port.adapters.apm_terminals_adapter import APMTerminalsAdapter
from app.services.port.adapters.la_lb_adapter import LALBAdapter
from app.services.port.adapters.ny_nj_adapter import NYNJAdapter
from app.services.port.adapters.port_houston_adapter import PortHoustonAdapter
from app.services.port.adapters.port_virginia_adapter import PortVirginiaAdapter
from app.services.port.adapters.savannah_adapter import SavannahAdapter


class PortService:
    """Service for port operations and container tracking."""

    # Map port codes to adapter classes
    PORT_ADAPTER_MAP = {
        "USHOU": PortHoustonAdapter,  # Port Houston
        "USORF": PortVirginiaAdapter,  # Port of Virginia (Norfolk)
        "USSAV": SavannahAdapter,  # Savannah
        "USLAX": LALBAdapter,  # Los Angeles
        "USLGB": LALBAdapter,  # Long Beach
        "USNYC": NYNJAdapter,  # New York
        "USEWR": NYNJAdapter,  # Newark
        # APM Terminals
        "USMOB": APMTerminalsAdapter,  # APM Terminals Mobile (Alabama)
        "USEWN": APMTerminalsAdapter,  # APM Terminals Elizabeth (New Jersey)
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    def _get_adapter_class(self, port_code: str) -> Optional[type[PortAdapter]]:
        """Get adapter class for a port code."""
        return self.PORT_ADAPTER_MAP.get(port_code.upper())

    async def _get_port_integration(
        self, company_id: str, port_code: str
    ) -> Optional[PortIntegration]:
        """Get active port integration for company and port."""
        # First, find the port
        port_result = await self.db.execute(
            select(Port).where(Port.port_code == port_code.upper(), Port.is_active == "true")
        )
        port = port_result.scalar_one_or_none()
        if not port:
            return None

        # Then find active integration
        integration_result = await self.db.execute(
            select(PortIntegration).where(
                PortIntegration.company_id == company_id,
                PortIntegration.port_id == port.id,
                PortIntegration.status == "active",
            )
        )
        return integration_result.scalar_one_or_none()

    async def _create_adapter(
        self, port_code: str, integration: Optional[PortIntegration] = None
    ) -> Optional[PortAdapter]:
        """Create adapter instance for a port."""
        adapter_class = self._get_adapter_class(port_code)
        if not adapter_class:
            return None

        credentials = integration.credentials_json if integration else None
        config = integration.config_json if integration else None

        return adapter_class(credentials=credentials, config=config)

    async def track_container(
        self,
        company_id: str,
        container_number: str,
        port_code: str,
        load_id: Optional[str] = None,
    ) -> ContainerTrackingResponse:
        """
        Track a container and store tracking data.
        
        Args:
            company_id: Company ID
            container_number: Container number
            port_code: Port code (UN/LOCODE)
            load_id: Optional load ID to link tracking
            
        Returns:
            ContainerTrackingResponse with current status
        """
        # Get or create port integration
        integration = await self._get_port_integration(company_id, port_code)

        # Create adapter
        adapter = await self._create_adapter(port_code, integration)
        if not adapter:
            raise PortAdapterError(f"No adapter available for port code: {port_code}")

        # Track container
        tracking_response = await adapter.track_container(container_number, port_code)

        # Store tracking data
        await self._store_tracking_data(
            company_id=company_id,
            container_number=container_number,
            port_code=port_code,
            load_id=load_id,
            tracking_response=tracking_response,
            integration=integration,
        )

        return tracking_response

    async def _store_tracking_data(
        self,
        company_id: str,
        container_number: str,
        port_code: str,
        load_id: Optional[str],
        tracking_response: ContainerTrackingResponse,
        integration: Optional[PortIntegration],
    ) -> ContainerTracking:
        """Store container tracking data in database."""
        # Check if tracking record exists
        result = await self.db.execute(
            select(ContainerTracking).where(
                ContainerTracking.company_id == company_id,
                ContainerTracking.container_number == container_number,
                ContainerTracking.port_code == port_code.upper(),
            )
        )
        existing = result.scalar_one_or_none()

        # Prepare tracking data
        tracking_data = {
            "container_number": container_number,
            "port_code": port_code.upper(),
            "terminal": tracking_response.terminal,
            "status": tracking_response.status,
            "location": tracking_response.location.model_dump() if tracking_response.location else None,
            "vessel": tracking_response.vessel.model_dump() if tracking_response.vessel else None,
            "dates": tracking_response.dates.model_dump() if tracking_response.dates else None,
            "container_details": tracking_response.container_details.model_dump()
            if tracking_response.container_details
            else None,
            "holds": tracking_response.holds,
            "charges": tracking_response.charges.model_dump() if tracking_response.charges else None,
            "last_updated_at": datetime.utcnow(),
        }

        if existing:
            # Update existing record
            for key, value in tracking_data.items():
                setattr(existing, key, value)
            if load_id:
                existing.load_id = load_id
            if integration:
                existing.port_integration_id = integration.id
            tracking_record = existing
        else:
            # Create new record
            tracking_record = ContainerTracking(
                id=str(uuid.uuid4()),
                company_id=company_id,
                load_id=load_id,
                port_integration_id=integration.id if integration else None,
                **tracking_data,
            )
            self.db.add(tracking_record)

        # Get events from adapter and store them
        if integration:
            adapter = await self._create_adapter(port_code, integration)
            if adapter:
                try:
                    events = await adapter.get_container_events(container_number, port_code)
                    await self._store_events(tracking_record.id, events)
                except Exception:
                    # Don't fail if events can't be retrieved
                    pass

        await self.db.commit()
        await self.db.refresh(tracking_record)
        return tracking_record

    async def _store_events(self, tracking_id: str, events: List[dict]) -> None:
        """Store container tracking events."""
        for event_data in events:
            # Check if event already exists
            result = await self.db.execute(
                select(ContainerTrackingEvent).where(
                    ContainerTrackingEvent.container_tracking_id == tracking_id,
                    ContainerTrackingEvent.event_type == event_data.get("event_type"),
                    ContainerTrackingEvent.event_timestamp == event_data.get("timestamp"),
                )
            )
            existing = result.scalar_one_or_none()

            if not existing:
                event = ContainerTrackingEvent(
                    id=str(uuid.uuid4()),
                    container_tracking_id=tracking_id,
                    event_type=event_data.get("event_type", "UNKNOWN"),
                    event_timestamp=event_data.get("timestamp") or datetime.utcnow(),
                    location=event_data.get("location"),
                    description=event_data.get("description"),
                    event_metadata=event_data.get("metadata"),
                )
                self.db.add(event)

        await self.db.commit()

    async def get_container_tracking_history(
        self, company_id: str, container_number: str, port_code: Optional[str] = None
    ) -> List[ContainerTracking]:
        """Get container tracking history."""
        query = select(ContainerTracking).where(
            ContainerTracking.company_id == company_id,
            ContainerTracking.container_number == container_number,
        )
        if port_code:
            query = query.where(ContainerTracking.port_code == port_code.upper())

        result = await self.db.execute(query.order_by(ContainerTracking.created_at.desc()))
        return list(result.scalars().all())

    async def get_load_container_tracking(self, company_id: str, load_id: str) -> Optional[ContainerTracking]:
        """Get container tracking for a specific load."""
        result = await self.db.execute(
            select(ContainerTracking).where(
                ContainerTracking.company_id == company_id,
                ContainerTracking.load_id == load_id,
            )
        )
        return result.scalar_one_or_none()

    async def cleanup_completed_load_tracking(self, company_id: str, load_id: str) -> None:
        """Clean up tracking data for a completed load."""
        # Get all tracking records for this load
        result = await self.db.execute(
            select(ContainerTracking).where(
                ContainerTracking.company_id == company_id,
                ContainerTracking.load_id == load_id,
            )
        )
        tracking_records = result.scalars().all()

        for tracking in tracking_records:
            # Delete associated events
            await self.db.execute(
                delete(ContainerTrackingEvent).where(
                    ContainerTrackingEvent.container_tracking_id == tracking.id
                )
            )
            # Delete tracking record
            await self.db.execute(
                delete(ContainerTracking).where(ContainerTracking.id == tracking.id)
            )

        await self.db.commit()

    async def list_available_ports(self) -> List[Port]:
        """List all available ports (active and inactive)."""
        result = await self.db.execute(select(Port).order_by(Port.port_name))
        return list(result.scalars().all())

    async def get_company_port_integrations(self, company_id: str) -> List[PortIntegration]:
        """Get all port integrations for a company."""
        result = await self.db.execute(
            select(PortIntegration)
            .where(PortIntegration.company_id == company_id)
            .order_by(PortIntegration.created_at.desc())
        )
        return list(result.scalars().all())

    # ==================== VESSEL OPERATIONS ====================

    async def get_vessel_schedule(
        self,
        company_id: str,
        port_code: str,
        vessel_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get vessel schedule for a port."""
        integration = await self._get_port_integration(company_id, port_code)
        adapter = await self._create_adapter(port_code, integration)
        if not adapter:
            raise PortAdapterError(f"No adapter available for port code: {port_code}")

        # Check if adapter supports vessel schedules
        if not hasattr(adapter, "get_vessel_schedule"):
            raise PortAdapterError(f"Port {port_code} does not support vessel schedules")

        return await adapter.get_vessel_schedule(vessel_name=vessel_name)

    async def get_active_vessel_visits(
        self,
        company_id: str,
        port_code: str,
    ) -> List[Dict[str, Any]]:
        """Get active vessel visits at a port."""
        integration = await self._get_port_integration(company_id, port_code)
        adapter = await self._create_adapter(port_code, integration)
        if not adapter:
            raise PortAdapterError(f"No adapter available for port code: {port_code}")

        if not hasattr(adapter, "get_active_vessel_visits"):
            raise PortAdapterError(f"Port {port_code} does not support active vessel visits")

        return await adapter.get_active_vessel_visits()

    # ==================== APPOINTMENT OPERATIONS ====================

    async def get_gate_appointments(
        self,
        company_id: str,
        port_code: str,
        container_number: Optional[str] = None,
        appointment_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get gate appointments."""
        integration = await self._get_port_integration(company_id, port_code)
        adapter = await self._create_adapter(port_code, integration)
        if not adapter:
            raise PortAdapterError(f"No adapter available for port code: {port_code}")

        if not hasattr(adapter, "get_gate_appointments"):
            raise PortAdapterError(f"Port {port_code} does not support gate appointments")

        return await adapter.get_gate_appointments(
            container_number=container_number,
            appointment_date=appointment_date,
        )

    async def create_gate_appointment(
        self,
        company_id: str,
        port_code: str,
        container_number: str,
        transaction_type: str,
        appointment_time: datetime,
        trucking_company: str,
        driver_license: Optional[str] = None,
        truck_license: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a gate appointment. Requires tenant's own port credentials."""
        integration = await self._get_port_integration(company_id, port_code)
        if not integration:
            raise PortAdapterError(
                f"Port integration required for creating appointments at {port_code}. "
                "Please configure your port credentials."
            )

        adapter = await self._create_adapter(port_code, integration)
        if not adapter:
            raise PortAdapterError(f"No adapter available for port code: {port_code}")

        if not hasattr(adapter, "create_gate_appointment"):
            raise PortAdapterError(f"Port {port_code} does not support creating appointments")

        return await adapter.create_gate_appointment(
            container_number=container_number,
            transaction_type=transaction_type,
            appointment_time=appointment_time,
            trucking_company=trucking_company,
            driver_license=driver_license,
            truck_license=truck_license,
        )

    async def cancel_gate_appointment(
        self,
        company_id: str,
        port_code: str,
        appointment_id: str,
    ) -> Dict[str, Any]:
        """Cancel a gate appointment."""
        integration = await self._get_port_integration(company_id, port_code)
        if not integration:
            raise PortAdapterError(
                f"Port integration required for canceling appointments at {port_code}. "
                "Please configure your port credentials."
            )

        adapter = await self._create_adapter(port_code, integration)
        if not adapter:
            raise PortAdapterError(f"No adapter available for port code: {port_code}")

        if not hasattr(adapter, "cancel_gate_appointment"):
            raise PortAdapterError(f"Port {port_code} does not support canceling appointments")

        return await adapter.cancel_gate_appointment(appointment_id=appointment_id)

    # ==================== GATE/TRUCK OPERATIONS ====================

    async def get_gate_transactions(
        self,
        company_id: str,
        port_code: str,
        container_number: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get gate transaction history."""
        integration = await self._get_port_integration(company_id, port_code)
        adapter = await self._create_adapter(port_code, integration)
        if not adapter:
            raise PortAdapterError(f"No adapter available for port code: {port_code}")

        if not hasattr(adapter, "get_gate_transactions"):
            raise PortAdapterError(f"Port {port_code} does not support gate transactions")

        return await adapter.get_gate_transactions(
            container_number=container_number,
            since=since,
        )

    async def get_truck_visits(
        self,
        company_id: str,
        port_code: str,
        truck_license: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get truck visit information."""
        integration = await self._get_port_integration(company_id, port_code)
        adapter = await self._create_adapter(port_code, integration)
        if not adapter:
            raise PortAdapterError(f"No adapter available for port code: {port_code}")

        if not hasattr(adapter, "get_truck_visits"):
            raise PortAdapterError(f"Port {port_code} does not support truck visits")

        return await adapter.get_truck_visits(
            truck_license=truck_license,
            since=since,
        )

    # ==================== BOOKING/ORDER OPERATIONS ====================

    async def get_bookings(
        self,
        company_id: str,
        port_code: str,
        booking_number: Optional[str] = None,
        vessel_visit: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get booking information."""
        integration = await self._get_port_integration(company_id, port_code)
        adapter = await self._create_adapter(port_code, integration)
        if not adapter:
            raise PortAdapterError(f"No adapter available for port code: {port_code}")

        if not hasattr(adapter, "get_bookings"):
            raise PortAdapterError(f"Port {port_code} does not support bookings")

        return await adapter.get_bookings(
            booking_number=booking_number,
            vessel_visit=vessel_visit,
        )

    async def get_service_orders(
        self,
        company_id: str,
        port_code: str,
        container_number: Optional[str] = None,
        order_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get service orders."""
        integration = await self._get_port_integration(company_id, port_code)
        adapter = await self._create_adapter(port_code, integration)
        if not adapter:
            raise PortAdapterError(f"No adapter available for port code: {port_code}")

        if not hasattr(adapter, "get_service_orders"):
            raise PortAdapterError(f"Port {port_code} does not support service orders")

        return await adapter.get_service_orders(
            container_number=container_number,
            order_type=order_type,
        )

    # ==================== BILLING OPERATIONS ====================

    async def get_billable_events(
        self,
        company_id: str,
        port_code: str,
        container_number: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get billable events for containers."""
        integration = await self._get_port_integration(company_id, port_code)
        adapter = await self._create_adapter(port_code, integration)
        if not adapter:
            raise PortAdapterError(f"No adapter available for port code: {port_code}")

        if not hasattr(adapter, "get_billable_events"):
            raise PortAdapterError(f"Port {port_code} does not support billable events")

        return await adapter.get_billable_events(
            container_number=container_number,
            since=since,
        )


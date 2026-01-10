from __future__ import annotations

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.load import Load, LoadStop
from app.models.load_accessorial import LoadAccessorial
from app.models.accounting import Customer
from app.models.fuel import FuelTransaction
from app.schemas.load import LoadCreate, LoadResponse, LoadExpense, LoadProfitSummary
from app.services.event_dispatcher import emit_event, EventType

logger = logging.getLogger(__name__)


class LoadService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _find_or_create_customer(
        self, company_id: str, customer_name: str
    ) -> Tuple[Optional[Customer], bool]:
        """
        Find existing customer by name or create a new one.
        Returns tuple of (customer, was_created).
        """
        if not customer_name or not customer_name.strip():
            return None, False

        # Search for existing customer (case-insensitive)
        result = await self.db.execute(
            select(Customer).where(
                Customer.company_id == company_id,
                Customer.name.ilike(customer_name.strip())
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            return existing, False

        # Create new customer
        new_customer = Customer(
            id=str(uuid.uuid4()),
            company_id=company_id,
            name=customer_name.strip(),
            payment_terms="Net 30",
            credit_limit=0,
            status="active",
        )
        self.db.add(new_customer)
        await self.db.flush()
        return new_customer, True

    async def list_loads(self, company_id: str, status_filter: Optional[str] = None) -> List[Load]:
        # Debug: count total loads in database
        total_count_result = await self.db.execute(select(func.count(Load.id)))
        total_count = total_count_result.scalar() or 0

        # Debug: get distinct company_ids in loads table
        distinct_companies_result = await self.db.execute(
            select(Load.company_id).distinct().limit(10)
        )
        distinct_companies = [row[0] for row in distinct_companies_result.fetchall()]

        logger.info(
            f"[LoadService.list_loads] company_id={company_id}, "
            f"total_loads_in_db={total_count}, "
            f"distinct_company_ids={distinct_companies}, "
            f"status_filter={status_filter}"
        )

        query = (
            select(Load)
            .options(selectinload(Load.stops), selectinload(Load.accessorials))
            .where(Load.company_id == company_id)
        )

        if status_filter:
            query = query.where(Load.status == status_filter)

        query = query.order_by(Load.created_at.desc())

        result = await self.db.execute(query)
        loads = list(result.scalars().all())
        logger.info(f"[LoadService.list_loads] Returning {len(loads)} loads for company {company_id}")
        return loads

    async def list_driver_loads(
        self, company_id: str, driver_id: str, status_filter: Optional[str] = None
    ) -> List[Load]:
        """Get loads assigned to a specific driver, optionally filtered by status."""
        query = select(Load).where(
            Load.company_id == company_id,
            Load.driver_id == driver_id,
        )

        if status_filter:
            if status_filter == "current":
                # Active loads: in_transit, at_pickup, at_delivery, loading, unloading
                query = query.where(
                    Load.status.in_(["in_transit", "at_pickup", "at_delivery", "loading", "unloading", "dispatched"])
                )
            elif status_filter == "past":
                # Completed or cancelled loads
                query = query.where(Load.status.in_(["delivered", "completed", "cancelled"]))
            elif status_filter == "future":
                # Assigned but not yet started
                query = query.where(Load.status.in_(["draft", "booked", "confirmed", "assigned"]))
            else:
                # Direct status filter
                query = query.where(Load.status == status_filter)

        result = await self.db.execute(query.order_by(Load.created_at.desc()))
        return list(result.scalars().all())

    async def get_driver_active_load(self, company_id: str, driver_id: str) -> Optional[Load]:
        """Get the current active load for a driver (in_transit or at stop)."""
        result = await self.db.execute(
            select(Load).where(
                Load.company_id == company_id,
                Load.driver_id == driver_id,
                Load.status.in_(["in_transit", "at_pickup", "at_delivery", "loading", "unloading"]),
            ).order_by(Load.updated_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_load(self, company_id: str, load_id: str) -> Load:
        result = await self.db.execute(
            select(Load)
            .options(selectinload(Load.stops), selectinload(Load.accessorials))
            .where(Load.company_id == company_id, Load.id == load_id)
        )
        load = result.scalar_one_or_none()
        if not load:
            raise ValueError("Load not found")
        return load

    async def create_load(
        self, company_id: str, payload: LoadCreate, auto_create_customer: bool = True
    ) -> Tuple[Load, Optional[str]]:
        """
        Create a new load. If auto_create_customer is True and customer doesn't exist,
        creates a new customer record.

        Returns tuple of (load, new_customer_name) where new_customer_name is set
        if a new customer was auto-created.
        """
        new_customer_name = None
        customer_id = None

        # Auto-create customer if needed
        if auto_create_customer and payload.customer_name:
            customer, was_created = await self._find_or_create_customer(
                company_id, payload.customer_name
            )
            if customer:
                customer_id = customer.id
                if was_created:
                    new_customer_name = customer.name

        load = Load(
            id=str(uuid.uuid4()),
            company_id=company_id,
            customer_name=payload.customer_name,
            load_type=payload.load_type,
            commodity=payload.commodity,
            base_rate=payload.base_rate,
            notes=payload.notes,
            container_number=payload.container_number,
            container_size=payload.container_size,
            container_type=payload.container_type,
            vessel_name=payload.vessel_name,
            voyage_number=payload.voyage_number,
            origin_port_code=payload.origin_port_code,
            destination_port_code=payload.destination_port_code,
            drayage_appointment=payload.drayage_appointment,
            customs_hold=payload.customs_hold,
            customs_reference=payload.customs_reference,
            preferred_driver_ids=payload.preferred_driver_ids,
            preferred_truck_ids=payload.preferred_truck_ids,
            required_skills=payload.required_skills,
            status="draft",
        )

        metadata_payload = {}
        if customer_id:
            metadata_payload["customer_id"] = customer_id
        if payload.customer_profile:
            metadata_payload["customer_profile"] = payload.customer_profile.model_dump(exclude_none=True)
        if payload.billing_details:
            metadata_payload["billing_details"] = payload.billing_details.model_dump(exclude_none=True)

        if metadata_payload:
            load.metadata_json = metadata_payload

        self.db.add(load)
        await self.db.flush()

        # Create load stops
        for index, stop_payload in enumerate(payload.stops):
            stop = LoadStop(
                id=str(uuid.uuid4()),
                load_id=load.id,
                sequence=index + 1,
                stop_type=stop_payload.stop_type,
                location_name=stop_payload.location_name,
                address=stop_payload.address,
                city=stop_payload.city,
                state=stop_payload.state,
                postal_code=stop_payload.postal_code,
                scheduled_at=stop_payload.scheduled_at,
                instructions=stop_payload.instructions,
                metadata_json=stop_payload.metadata,
                distance_miles=stop_payload.distance_miles,
                fuel_estimate_gallons=stop_payload.fuel_estimate_gallons,
                dwell_minutes_estimate=stop_payload.dwell_minutes_estimate,
            )
            self.db.add(stop)

        # Create accessorial charges
        if payload.accessorials:
            for accessorial in payload.accessorials:
                acc_charge = LoadAccessorial(
                    id=str(uuid.uuid4()),
                    load_id=load.id,
                    charge_type=accessorial.type,
                    description=accessorial.description or accessorial.type,
                    amount=Decimal(str(accessorial.amount)),
                    quantity=Decimal("1.0"),
                )
                self.db.add(acc_charge)

        await self.db.commit()
        await self.db.refresh(load)
        return load, new_customer_name

    async def update_load(self, company_id: str, load_id: str, payload: LoadCreate) -> Load:
        load = await self.get_load(company_id, load_id)

        load.customer_name = payload.customer_name
        load.load_type = payload.load_type
        load.commodity = payload.commodity
        load.base_rate = payload.base_rate
        load.notes = payload.notes
        load.container_number = payload.container_number
        load.container_size = payload.container_size
        load.container_type = payload.container_type
        load.vessel_name = payload.vessel_name
        load.voyage_number = payload.voyage_number
        load.origin_port_code = payload.origin_port_code
        load.destination_port_code = payload.destination_port_code
        load.drayage_appointment = payload.drayage_appointment
        load.customs_hold = payload.customs_hold
        load.customs_reference = payload.customs_reference
        load.preferred_driver_ids = payload.preferred_driver_ids
        load.preferred_truck_ids = payload.preferred_truck_ids
        load.required_skills = payload.required_skills

        metadata_payload = load.metadata_json or {}
        if payload.customer_profile:
            metadata_payload["customer_profile"] = payload.customer_profile.model_dump(exclude_none=True)
        elif "customer_profile" in metadata_payload:
            metadata_payload.pop("customer_profile")
        if payload.billing_details:
            metadata_payload["billing_details"] = payload.billing_details.model_dump(exclude_none=True)
        elif "billing_details" in metadata_payload:
            metadata_payload.pop("billing_details")
        if payload.accessorials:
            metadata_payload["accessorials"] = [item.model_dump(exclude_none=True) for item in payload.accessorials]
        elif "accessorials" in metadata_payload:
            metadata_payload.pop("accessorials")

        load.metadata_json = metadata_payload or None

        await self.db.execute(delete(LoadStop).where(LoadStop.load_id == load.id))

        for index, stop_payload in enumerate(payload.stops):
            stop = LoadStop(
                id=str(uuid.uuid4()),
                load_id=load.id,
                sequence=index + 1,
                stop_type=stop_payload.stop_type,
                location_name=stop_payload.location_name,
                address=stop_payload.address,
                city=stop_payload.city,
                state=stop_payload.state,
                postal_code=stop_payload.postal_code,
                scheduled_at=stop_payload.scheduled_at,
                instructions=stop_payload.instructions,
                metadata_json=stop_payload.metadata,
                distance_miles=stop_payload.distance_miles,
                fuel_estimate_gallons=stop_payload.fuel_estimate_gallons,
                dwell_minutes_estimate=stop_payload.dwell_minutes_estimate,
            )
            self.db.add(stop)

        await self.db.commit()
        await self.db.refresh(load)
        
        # Trigger cleanup of container tracking if load is completed
        if load.status == "completed":
            await self._cleanup_container_tracking(company_id, load_id)
        
        return load

    async def update_stop_schedule(
        self,
        company_id: str,
        load_id: str,
        stop_id: str,
        scheduled_at: datetime,
    ) -> Load:
        """Update a load stop's scheduled time."""
        load = await self.get_load(company_id, load_id)
        
        # Find the stop
        stop = None
        for s in load.stops:
            if s.id == stop_id:
                stop = s
                break
        
        if not stop:
            raise ValueError("Stop not found")
        
        stop.scheduled_at = scheduled_at
        await self.db.commit()
        await self.db.refresh(load)
        return load

    async def assign_load(
        self,
        company_id: str,
        load_id: str,
        driver_id: Optional[str] = None,
        truck_id: Optional[str] = None,
    ) -> Load:
        """Assign or reassign a load to a driver and/or truck."""
        load = await self.get_load(company_id, load_id)

        # Store previous assignment for notification purposes
        metadata = load.metadata_json or {}
        previous_driver_id = metadata.get("assigned_driver_id")

        # Update assignment
        if driver_id:
            metadata["assigned_driver_id"] = driver_id
            load.driver_id = driver_id  # Set on model for driver app queries
        if truck_id:
            metadata["assigned_truck_id"] = truck_id
            load.truck_id = truck_id  # Set on model for queries

        load.metadata_json = metadata

        # Update status if assigning
        if driver_id and load.status == "draft":
            load.status = "TRUCK_ASSIGNED"

        await self.db.commit()
        await self.db.refresh(load)

        # Emit events for real-time updates (cleaner event-driven approach)
        load_info = {
            "load_id": load_id,
            "reference_number": load.reference_number,
            "origin": load.origin_city,
            "destination": load.destination_city,
            "status": load.status,
            "pickup_date": str(load.pickup_date) if load.pickup_date else None,
            "driver_id": driver_id,
            "truck_id": truck_id,
        }

        # Notify previous driver if they were unassigned
        if previous_driver_id and previous_driver_id != driver_id:
            await emit_event(
                EventType.LOAD_UNASSIGNED,
                load_info,
                company_id=company_id,
                target_driver_id=previous_driver_id,
            )

        # Notify new driver of assignment
        if driver_id and driver_id != previous_driver_id:
            await emit_event(
                EventType.LOAD_ASSIGNED,
                load_info,
                company_id=company_id,
                target_driver_id=driver_id,
            )

        # Trigger cleanup of container tracking if load is completed
        if load.status == "completed":
            await self._cleanup_container_tracking(company_id, load_id)

        return load

    async def _cleanup_container_tracking(self, company_id: str, load_id: str) -> None:
        """Clean up container tracking data for a completed load."""
        from app.services.port.port_service import PortService

        port_service = PortService(self.db)
        await port_service.cleanup_completed_load_tracking(company_id, load_id)

    async def create_port_appointment(
        self,
        company_id: str,
        load_id: str,
        appointment_time: datetime,
        transaction_type: str,
        trucking_company: str,
        driver_license: Optional[str] = None,
        truck_license: Optional[str] = None,
    ) -> Load:
        """
        Create a port appointment (ePass) for a load.

        The load must have a container_number and origin_port_code set.
        The appointment is created via the port's API and the result is stored
        on the load (port_appointment_id, port_appointment_number, port_entry_code, etc.)

        Args:
            company_id: Company ID
            load_id: Load ID
            appointment_time: Requested appointment time
            transaction_type: PUI=Pick Up Import, DOE=Drop Off Export, etc.
            trucking_company: SCAC code or trucking company name
            driver_license: Optional driver license for gate entry
            truck_license: Optional truck license plate

        Returns:
            Updated Load with port appointment information

        Raises:
            ValueError: If load doesn't have required container/port info
        """
        from app.services.port.port_service import PortService

        load = await self.get_load(company_id, load_id)

        # Validate load has container info
        if not load.container_number:
            raise ValueError("Load must have a container number to create a port appointment")
        if not load.origin_port_code:
            raise ValueError("Load must have an origin port code to create a port appointment")

        # Create the port service and appointment
        port_service = PortService(self.db)

        try:
            result = await port_service.create_gate_appointment(
                company_id=company_id,
                port_code=load.origin_port_code,
                container_number=load.container_number,
                transaction_type=transaction_type,
                appointment_time=appointment_time,
                trucking_company=trucking_company,
                driver_license=driver_license,
                truck_license=truck_license,
            )

            # Update load with appointment info
            load.port_appointment_id = result.get("appointment_id")
            load.port_appointment_number = result.get("appointment_number")
            load.port_entry_code = result.get("entry_code")
            load.port_appointment_time = appointment_time
            load.port_appointment_gate = result.get("gate")
            load.port_appointment_terminal = result.get("terminal")
            load.port_appointment_status = result.get("status") or "SCHEDULED"

            await self.db.commit()
            await self.db.refresh(load)

            return load

        except Exception as e:
            raise ValueError(f"Failed to create port appointment: {str(e)}")

    async def cancel_port_appointment(self, company_id: str, load_id: str) -> Load:
        """
        Cancel a port appointment for a load.

        Args:
            company_id: Company ID
            load_id: Load ID

        Returns:
            Updated Load with cleared appointment information
        """
        from app.services.port.port_service import PortService

        load = await self.get_load(company_id, load_id)

        if not load.port_appointment_id:
            raise ValueError("Load does not have a port appointment to cancel")
        if not load.origin_port_code:
            raise ValueError("Load must have an origin port code")

        port_service = PortService(self.db)

        try:
            await port_service.cancel_gate_appointment(
                company_id=company_id,
                port_code=load.origin_port_code,
                appointment_id=load.port_appointment_id,
            )

            # Clear appointment info
            load.port_appointment_status = "CANCELLED"

            await self.db.commit()
            await self.db.refresh(load)

            return load

        except Exception as e:
            raise ValueError(f"Failed to cancel port appointment: {str(e)}")

    async def get_load_expenses(self, company_id: str, load_id: str) -> List[LoadExpense]:
        """
        Get all expenses matched to a load.

        Currently fetches fuel transactions matched to this load.
        Can be extended to include detention, accessorials, etc.
        """
        # Fetch fuel transactions for this load
        result = await self.db.execute(
            select(FuelTransaction).where(
                FuelTransaction.company_id == company_id,
                FuelTransaction.load_id == load_id,
            ).order_by(FuelTransaction.transaction_date.desc())
        )
        fuel_txns = list(result.scalars().all())

        expenses: List[LoadExpense] = []

        for txn in fuel_txns:
            cost = float(txn.cost) if isinstance(txn.cost, Decimal) else txn.cost
            gallons = float(txn.gallons) if isinstance(txn.gallons, Decimal) else txn.gallons

            expenses.append(LoadExpense(
                id=txn.id,
                entry_type="FUEL",
                description=f"Fuel at {txn.location or 'Unknown'}" if txn.location else "Fuel purchase",
                amount=cost,
                quantity=gallons,
                unit="gallons",
                recorded_at=datetime.combine(txn.transaction_date, datetime.min.time()) if txn.transaction_date else datetime.now(),
            ))

        return expenses

    def compute_profit_summary(self, base_rate: float, expenses: List[LoadExpense]) -> LoadProfitSummary:
        """Compute profit summary from base rate and expenses."""
        total_expenses = sum(e.amount for e in expenses)
        gross_profit = base_rate - total_expenses
        profit_margin = (gross_profit / base_rate * 100) if base_rate > 0 else 0.0

        return LoadProfitSummary(
            total_expenses=total_expenses,
            gross_profit=gross_profit,
            profit_margin=profit_margin,
        )

    async def get_load_with_expenses(self, company_id: str, load_id: str) -> Dict[str, Any]:
        """
        Get a load with computed expenses and profit summary.
        Returns a dict suitable for LoadResponse model.
        """
        load = await self.get_load(company_id, load_id)
        expenses = await self.get_load_expenses(company_id, load_id)
        base_rate = float(load.base_rate) if isinstance(load.base_rate, Decimal) else load.base_rate
        profit_summary = self.compute_profit_summary(base_rate, expenses)

        # Convert to dict and add expenses
        load_dict = {
            "id": load.id,
            "customer_name": load.customer_name,
            "load_type": load.load_type,
            "commodity": load.commodity,
            "base_rate": base_rate,
            "status": load.status,
            "notes": load.notes,
            "container_number": load.container_number,
            "container_size": load.container_size,
            "container_type": load.container_type,
            "vessel_name": load.vessel_name,
            "voyage_number": load.voyage_number,
            "origin_port_code": load.origin_port_code,
            "destination_port_code": load.destination_port_code,
            "drayage_appointment": load.drayage_appointment,
            "customs_hold": load.customs_hold,
            "customs_reference": load.customs_reference,
            "port_appointment_id": load.port_appointment_id,
            "port_appointment_number": load.port_appointment_number,
            "port_entry_code": load.port_entry_code,
            "port_appointment_time": load.port_appointment_time,
            "port_appointment_gate": load.port_appointment_gate,
            "port_appointment_status": load.port_appointment_status,
            "port_appointment_terminal": load.port_appointment_terminal,
            "driver_id": load.driver_id,
            "truck_id": load.truck_id,
            "last_known_lat": load.last_known_lat,
            "last_known_lng": load.last_known_lng,
            "last_location_update": load.last_location_update,
            "pickup_arrival_lat": load.pickup_arrival_lat,
            "pickup_arrival_lng": load.pickup_arrival_lng,
            "pickup_arrival_time": load.pickup_arrival_time,
            "delivery_arrival_lat": load.delivery_arrival_lat,
            "delivery_arrival_lng": load.delivery_arrival_lng,
            "delivery_arrival_time": load.delivery_arrival_time,
            "metadata_json": load.metadata_json,
            "created_at": load.created_at,
            "updated_at": load.updated_at,
            "stops": load.stops,
            "expenses": expenses,
            "profit_summary": profit_summary,
        }

        return load_dict

    async def list_loads_with_expenses(self, company_id: str, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all loads with computed expenses and profit summaries."""
        loads = await self.list_loads(company_id, status_filter=status_filter)

        if not loads:
            return []

        # Batch fetch all fuel transactions for this company in one query
        load_ids = [load.id for load in loads]
        fuel_result = await self.db.execute(
            select(FuelTransaction).where(
                FuelTransaction.company_id == company_id,
                FuelTransaction.load_id.in_(load_ids),
            ).order_by(FuelTransaction.transaction_date.desc())
        )
        all_fuel_txns = list(fuel_result.scalars().all())

        # Group fuel transactions by load_id
        fuel_by_load: Dict[str, List[FuelTransaction]] = {}
        for txn in all_fuel_txns:
            if txn.load_id:
                if txn.load_id not in fuel_by_load:
                    fuel_by_load[txn.load_id] = []
                fuel_by_load[txn.load_id].append(txn)

        result = []
        for load in loads:
            # Convert fuel transactions to LoadExpense objects
            expenses: List[LoadExpense] = []
            for txn in fuel_by_load.get(load.id, []):
                cost = float(txn.cost) if isinstance(txn.cost, Decimal) else txn.cost
                gallons = float(txn.gallons) if isinstance(txn.gallons, Decimal) else txn.gallons
                expenses.append(LoadExpense(
                    id=txn.id,
                    entry_type="FUEL",
                    description=f"Fuel at {txn.location or 'Unknown'}" if txn.location else "Fuel purchase",
                    amount=cost,
                    quantity=gallons,
                    unit="gallons",
                    recorded_at=datetime.combine(txn.transaction_date, datetime.min.time()) if txn.transaction_date else datetime.now(),
                ))

            base_rate = float(load.base_rate) if isinstance(load.base_rate, Decimal) else load.base_rate
            profit_summary = self.compute_profit_summary(base_rate, expenses)

            load_dict = {
                "id": load.id,
                "customer_name": load.customer_name,
                "load_type": load.load_type,
                "commodity": load.commodity,
                "base_rate": base_rate,
                "status": load.status,
                "notes": load.notes,
                "container_number": load.container_number,
                "container_size": load.container_size,
                "container_type": load.container_type,
                "vessel_name": load.vessel_name,
                "voyage_number": load.voyage_number,
                "origin_port_code": load.origin_port_code,
                "destination_port_code": load.destination_port_code,
                "drayage_appointment": load.drayage_appointment,
                "customs_hold": load.customs_hold,
                "customs_reference": load.customs_reference,
                "port_appointment_id": load.port_appointment_id,
                "port_appointment_number": load.port_appointment_number,
                "port_entry_code": load.port_entry_code,
                "port_appointment_time": load.port_appointment_time,
                "port_appointment_gate": load.port_appointment_gate,
                "port_appointment_status": load.port_appointment_status,
                "port_appointment_terminal": load.port_appointment_terminal,
                "driver_id": load.driver_id,
                "truck_id": load.truck_id,
                "last_known_lat": load.last_known_lat,
                "last_known_lng": load.last_known_lng,
                "last_location_update": load.last_location_update,
                "pickup_arrival_lat": load.pickup_arrival_lat,
                "pickup_arrival_lng": load.pickup_arrival_lng,
                "pickup_arrival_time": load.pickup_arrival_time,
                "delivery_arrival_lat": load.delivery_arrival_lat,
                "delivery_arrival_lng": load.delivery_arrival_lng,
                "delivery_arrival_time": load.delivery_arrival_time,
                "metadata_json": load.metadata_json,
                "created_at": load.created_at,
                "updated_at": load.updated_at,
                "stops": load.stops,
                "expenses": expenses,
                "profit_summary": profit_summary,
            }
            result.append(load_dict)

        return result

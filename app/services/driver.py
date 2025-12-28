from __future__ import annotations

import logging
import os
import secrets
import string
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password

logger = logging.getLogger(__name__)
from app.models.driver import Driver, DriverDocument, DriverIncident, DriverTraining
from app.models.user import User
from app.models.worker import Worker, WorkerType, WorkerRole, WorkerStatus
from app.services.email import EmailService
from app.services.event_dispatcher import emit_event, EventType
from app.schemas.driver import (
    AssignEquipmentRequest,
    AvailableEquipmentResponse,
    DriverComplianceProfileResponse,
    DriverComplianceResponse,
    DriverComplianceSummaryResponse,
    DriverComplianceUpdateRequest,
    DriverCreate,
    DriverCreateResponse,
    DriverDocumentAttachmentResponse,
    DriverDocumentResponse,
    DriverEquipmentInfo,
    DriverIncidentCreate,
    DriverIncidentResponse,
    DriverProfileUpdate,
    DriverResponse,
    DriverTrainingCreate,
    DriverTrainingResponse,
    EquipmentBasicInfo,
    FuelCardBasicInfo,
    GeneratePasswordResponse,
    UserAccessActionResponse,
    UserAccessInfo,
)


class DriverService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_compliance(self, company_id: str) -> List[DriverComplianceResponse]:
        result = await self.db.execute(
            select(Driver)
            .where(Driver.company_id == company_id)
            .options(selectinload(Driver.incidents), selectinload(Driver.training_records))
        )
        drivers = list(result.scalars().all())

        if not drivers:
            return []

        # Batch fetch all documents for all drivers in one query
        driver_ids = [driver.id for driver in drivers]
        docs_result = await self.db.execute(
            select(DriverDocument).where(DriverDocument.driver_id.in_(driver_ids))
        )
        all_docs = list(docs_result.scalars().all())

        # Group documents by driver_id
        docs_by_driver: Dict[str, List[DriverDocument]] = {}
        for doc in all_docs:
            if doc.driver_id not in docs_by_driver:
                docs_by_driver[doc.driver_id] = []
            docs_by_driver[doc.driver_id].append(doc)

        responses: List[DriverComplianceResponse] = []
        for driver in drivers:
            driver_docs = docs_by_driver.get(driver.id, [])
            responses.append(
                DriverComplianceResponse(
                    driver=DriverResponse.model_validate(driver),
                    incidents=[
                        DriverIncidentResponse.model_validate(incident) for incident in driver.incidents
                    ],
                    training=[
                        DriverTrainingResponse.model_validate(record) for record in driver.training_records
                    ],
                    documents=[
                        DriverDocumentResponse.model_validate(document)
                        for document in driver_docs
                    ],
                )
            )
        return responses

    async def list_profiles(self, company_id: str) -> List[DriverComplianceProfileResponse]:
        result = await self.db.execute(
            select(Driver)
            .where(Driver.company_id == company_id)
            .options(selectinload(Driver.incidents), selectinload(Driver.training_records))
        )
        drivers = result.scalars().all()
        return [await self._build_profile(driver) for driver in drivers]

    async def get_driver(self, company_id: str, driver_id: str) -> Optional[Driver]:
        """Get a single driver by ID."""
        result = await self.db.execute(
            select(Driver).where(Driver.company_id == company_id, Driver.id == driver_id)
        )
        return result.scalar_one_or_none()

    async def get_driver_profile(self, company_id: str, driver_id: str) -> Dict[str, Any]:
        """Get driver profile with equipment info for mobile app."""
        from app.models.equipment import Equipment
        from app.models.load import Load

        driver = await self.get_driver(company_id, driver_id)
        if not driver:
            raise ValueError("Driver not found")

        # Get assigned truck
        truck_result = await self.db.execute(
            select(Equipment).where(
                Equipment.company_id == company_id,
                Equipment.driver_id == driver_id,
                Equipment.equipment_type == "truck",
            )
        )
        truck = truck_result.scalar_one_or_none()

        # Get today's stats
        from datetime import date

        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())

        # Count loads completed today
        completed_today_result = await self.db.execute(
            select(Load).where(
                Load.company_id == company_id,
                Load.driver_id == driver_id,
                Load.status.in_(["delivered", "completed"]),
                Load.updated_at >= start_of_day,
            )
        )
        completed_today = len(list(completed_today_result.scalars().all()))

        # Get total miles from today's completed loads
        miles_result = await self.db.execute(
            select(Load).where(
                Load.company_id == company_id,
                Load.driver_id == driver_id,
                Load.updated_at >= start_of_day,
            )
        )
        loads_today = list(miles_result.scalars().all())
        miles_today = sum(load.total_miles or 0 for load in loads_today)

        # Calculate on-time delivery rate from last 30 days
        thirty_days_ago = datetime.combine(today - timedelta(days=30), datetime.min.time())
        on_time_result = await self.db.execute(
            select(Load).where(
                Load.company_id == company_id,
                Load.driver_id == driver_id,
                Load.status.in_(["delivered", "completed"]),
                Load.updated_at >= thirty_days_ago,
            )
        )
        recent_loads = list(on_time_result.scalars().all())

        # Calculate on-time rate based on scheduled vs actual delivery
        on_time_count = 0
        total_with_schedule = 0

        for load in recent_loads:
            # Check if load has scheduled delivery info
            if hasattr(load, 'stops') and load.stops:
                delivery_stops = [s for s in load.stops if s.stop_type in ('delivery', 'drop')]
                for stop in delivery_stops:
                    if stop.scheduled_at and stop.completed_at:
                        total_with_schedule += 1
                        # On-time if completed within 2 hours of scheduled time
                        if stop.completed_at <= stop.scheduled_at + timedelta(hours=2):
                            on_time_count += 1
                        break  # Only count the primary delivery stop

        # Calculate rate (default to 100% if no deliveries with schedules)
        if total_with_schedule > 0:
            on_time_rate = round((on_time_count / total_with_schedule) * 100)
        else:
            # Fallback: Use load metadata or default based on completed loads
            on_time_rate = 95 if len(recent_loads) > 0 else 100

        return {
            "driver_id": driver.id,
            "first_name": driver.first_name,
            "last_name": driver.last_name,
            "full_name": f"{driver.first_name} {driver.last_name}",
            "email": driver.email,
            "phone": driver.phone,
            "truck_number": truck.unit_number if truck else None,
            "truck_id": truck.id if truck else None,
            "total_completed_loads": driver.total_completed_loads or 0,
            "compliance_score": driver.compliance_score,
            "average_rating": driver.average_rating,
            "stats": {
                "loads_completed_today": completed_today,
                "miles_driven_today": miles_today,
                "on_time_rate": on_time_rate,
                "on_time_loads": on_time_count,
                "total_tracked_loads": total_with_schedule,
            },
        }

    async def update_compliance(
        self,
        company_id: str,
        driver_id: str,
        payload: DriverComplianceUpdateRequest,
    ) -> DriverComplianceProfileResponse:
        # Eagerly load relationships to avoid lazy loading issues
        result = await self.db.execute(
            select(Driver)
            .where(Driver.company_id == company_id, Driver.id == driver_id)
            .options(selectinload(Driver.incidents), selectinload(Driver.training_records))
        )
        driver = result.scalar_one_or_none()
        if not driver:
            raise ValueError("Driver not found")

        if payload.cdl_expiration is not None:
            driver.cdl_expiration = payload.cdl_expiration
        if payload.medical_card_expiration is not None:
            driver.medical_card_expiration = payload.medical_card_expiration

        metadata = self._ensure_metadata(driver.profile_metadata)
        if payload.last_mvr_check is not None:
            metadata["last_mvr_check"] = payload.last_mvr_check.isoformat()
        if payload.last_drug_test is not None:
            metadata["last_drug_test"] = payload.last_drug_test.isoformat()
        if payload.clearinghouse_status is not None:
            metadata["clearinghouse_status"] = payload.clearinghouse_status
        if payload.safety_rating is not None:
            metadata["safety_rating"] = payload.safety_rating
        if payload.violations is not None:
            metadata["violations"] = payload.violations

        driver.profile_metadata = metadata

        await self.db.commit()
        await self.db.refresh(driver)
        return await self._build_profile(driver)

    async def log_incident(
        self,
        company_id: str,
        driver_id: str,
        payload: DriverIncidentCreate,
    ) -> DriverIncidentResponse:
        driver = await self._get_driver(company_id, driver_id)
        incident = DriverIncident(
            id=str(uuid.uuid4()),
            driver_id=driver.id,
            occurred_at=payload.occurred_at,
            incident_type=payload.incident_type,
            severity=payload.severity,
            description=payload.description,
        )
        self.db.add(incident)
        await self.db.commit()
        await self.db.refresh(incident)
        return DriverIncidentResponse.model_validate(incident)

    async def log_training(
        self,
        company_id: str,
        driver_id: str,
        payload: DriverTrainingCreate,
    ) -> DriverTrainingResponse:
        driver = await self._get_driver(company_id, driver_id)
        training = DriverTraining(
            id=str(uuid.uuid4()),
            driver_id=driver.id,
            course_name=payload.course_name,
            completed_at=payload.completed_at,
            expires_at=payload.expires_at,
            instructor=payload.instructor,
            notes=payload.notes,
        )
        self.db.add(training)
        await self.db.commit()
        await self.db.refresh(training)
        return DriverTrainingResponse.model_validate(training)

    async def upload_document(
        self,
        company_id: str,
        driver_id: str,
        document_type: str,
        file_url: str,
    ) -> DriverDocumentResponse:
        await self._get_driver(company_id, driver_id)
        document = DriverDocument(
            id=str(uuid.uuid4()),
            driver_id=driver_id,
            document_type=document_type,
            file_url=file_url,
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        return DriverDocumentResponse.model_validate(document)

    async def _list_documents(self, driver_id: str) -> List[DriverDocument]:
        result = await self.db.execute(select(DriverDocument).where(DriverDocument.driver_id == driver_id))
        return result.scalars().all()

    async def _get_driver(self, company_id: str, driver_id: str) -> Driver:
        result = await self.db.execute(
            select(Driver).where(Driver.company_id == company_id, Driver.id == driver_id)
        )
        driver = result.scalar_one_or_none()
        if not driver:
            raise ValueError("Driver not found")
        return driver

    async def _build_profile(self, driver: Driver) -> DriverComplianceProfileResponse:
        metadata = self._ensure_metadata(driver.profile_metadata)
        profile = DriverComplianceProfileResponse(
            id=driver.id,
            company_id=driver.company_id,
            driver_number=metadata.get("driver_number"),
            first_name=driver.first_name,
            last_name=driver.last_name,
            middle_initial=metadata.get("middle_initial"),
            email=driver.email,
            phone_number=driver.phone,
            status=metadata.get("status", "ACTIVE"),
            home_address=metadata.get("home_address"),
            license_number=driver.cdl_number,
            license_state=metadata.get("license_state"),
            license_class=metadata.get("license_class"),
            license_expiration=metadata.get("license_expiration")
            if metadata.get("license_expiration")
            else driver.cdl_expiration,
            medical_card_expiration=driver.medical_card_expiration,
            endorsements=metadata.get("endorsements"),
            created_at=driver.created_at,
            updated_at=driver.updated_at,
            compliance=self._build_compliance_summary(driver, metadata),
            incidents=[DriverIncidentResponse.model_validate(incident) for incident in driver.incidents],
            training=[DriverTrainingResponse.model_validate(record) for record in driver.training_records],
            documents=[self._to_document_attachment(document) for document in await self._list_documents(driver.id)],
        )
        return profile

    def _build_compliance_summary(
        self,
        driver: Driver,
        metadata: Dict[str, Any],
    ) -> DriverComplianceSummaryResponse:
        return DriverComplianceSummaryResponse(
            cdl_expiration=driver.cdl_expiration,
            medical_card_expiration=driver.medical_card_expiration,
            last_mvr_check=self._parse_datetime(metadata.get("last_mvr_check")),
            last_drug_test=self._parse_datetime(metadata.get("last_drug_test")),
            clearinghouse_status=metadata.get("clearinghouse_status"),
            safety_rating=metadata.get("safety_rating"),
            violations=self._parse_int(metadata.get("violations")),
        )

    def _ensure_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if metadata is None:
            return {}
        if isinstance(metadata, dict):
            return metadata
        return dict(metadata)

    def _to_document_attachment(self, document: DriverDocument) -> DriverDocumentAttachmentResponse:
        file_name = document.file_url.rsplit("/", 1)[-1] if document.file_url else document.id
        return DriverDocumentAttachmentResponse(
            id=document.id,
            file_name=file_name,
            url=document.file_url,
            uploaded_at=document.uploaded_at,
            uploaded_by=None,
        )

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None

    def _parse_int(self, value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _generate_temporary_password(self, length: int = 12) -> str:
        """Generate a secure temporary password."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    async def create_driver(self, company_id: str, payload: DriverCreate) -> DriverCreateResponse:
        """Create a driver record and optionally a user account for app access."""
        driver_id = str(uuid.uuid4())

        # Build driver metadata
        metadata: Dict[str, Any] = {
            "driver_type": payload.driverType,
            "middle_initial": payload.middleInitial,
            "ssn": payload.ssn,
            "dob": payload.dob.isoformat(),
            "home_address": payload.homeAddress,
            "emergency_contact": payload.emergencyContact,
            "license_number": payload.licenseNumber,
            "license_state": payload.licenseState,
            "license_class": payload.licenseClass,
            "license_issue": payload.licenseIssue.isoformat(),
            "license_expiration": payload.licenseExpiry.isoformat(),
            "endorsements": payload.endorsements.model_dump(),
            "payroll_type": payload.payrollType,
            "pay_rate": payload.payRate,
            "deposit_type": payload.depositType,
            "bank_name": payload.bankName,
            "routing_number": payload.routingNumber,
            "account_number": payload.accountNumber,
            "notes": payload.notes,
            "status": "ACTIVE",
        }

        # Create Worker record first (drivers are workers in the payroll system)
        worker_id = str(uuid.uuid4())
        worker_type = WorkerType.CONTRACTOR if payload.payrollType == "1099" else WorkerType.EMPLOYEE
        worker = Worker(
            id=worker_id,
            company_id=company_id,
            type=worker_type,
            role=WorkerRole.DRIVER,
            first_name=payload.firstName,
            last_name=payload.lastName,
            email=payload.email.lower() if payload.email else None,
            phone=payload.phoneNumber,
            status=WorkerStatus.ACTIVE,
        )
        self.db.add(worker)
        await self.db.flush()  # Flush to get the worker ID

        # Create driver record linked to worker
        driver = Driver(
            id=driver_id,
            company_id=company_id,
            worker_id=worker_id,  # Link to worker record
            first_name=payload.firstName,
            last_name=payload.lastName,
            email=payload.email.lower() if payload.email else None,
            phone=payload.phoneNumber,
            cdl_number=payload.licenseNumber,
            cdl_expiration=payload.licenseExpiry,
            profile_metadata=metadata,
        )

        user_id = None
        temporary_password = None

        # Create user account if requested and email is provided
        if payload.createAppAccess and payload.email:
            email_lower = payload.email.lower()
            # Check if user already exists
            existing_user = await self.db.execute(select(User).where(User.email == email_lower))
            if existing_user.scalar_one_or_none():
                raise ValueError(f"User with email {email_lower} already exists")

            # Generate temporary password
            temporary_password = self._generate_temporary_password()

            # Create user account
            user = User(
                id=str(uuid.uuid4()),
                email=email_lower,
                hashed_password=hash_password(temporary_password),
                first_name=payload.firstName,
                last_name=payload.lastName,
                company_id=company_id,
                role="driver",
                is_active=True,
                must_change_password=True,  # Force password change on first login
            )
            self.db.add(user)
            await self.db.flush()
        

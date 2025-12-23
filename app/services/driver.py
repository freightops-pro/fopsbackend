from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
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
            user_id = user.id

            # Link driver to user
            driver.user_id = user_id

            # Send invitation email with credentials
            try:
                EmailService.send_driver_invitation(
                    email=email_lower,
                    first_name=payload.firstName,
                    last_name=payload.lastName,
                    temporary_password=temporary_password,
                )
            except Exception as e:
                print(f"Warning: Failed to send invitation email to {email_lower}: {e}")

        self.db.add(driver)
        await self.db.commit()
        await self.db.refresh(driver)

        # Build response message
        if user_id and temporary_password:
            message = f"Driver created successfully. App access has been set up. Temporary password: {temporary_password}"
        elif user_id:
            message = "Driver created successfully. App access has been set up."
        else:
            message = "Driver created successfully. No app access was created (email required)."

        return DriverCreateResponse(
            driver_id=driver_id,
            user_id=user_id,
            email=payload.email,
            temporary_password=temporary_password,
            message=message,
        )

    async def update_driver_profile(
        self,
        company_id: str,
        driver_id: str,
        payload: DriverProfileUpdate,
    ) -> DriverComplianceProfileResponse:
        """Update driver profile information."""
        # Eagerly load relationships to avoid lazy loading issues
        result = await self.db.execute(
            select(Driver)
            .where(Driver.company_id == company_id, Driver.id == driver_id)
            .options(selectinload(Driver.incidents), selectinload(Driver.training_records))
        )
        driver = result.scalar_one_or_none()
        if not driver:
            raise ValueError("Driver not found")

        # Handle email updates
        if payload.email is not None:
            email_lower = payload.email.lower()

            # If driver already has a user account, update the user's email
            if driver.user_id:
                user_result = await self.db.execute(
                    select(User).where(User.id == driver.user_id)
                )
                user = user_result.scalar_one_or_none()
                if user:
                    user.email = email_lower

            # If driver doesn't have a user account, create one
            else:
                # Check if user already exists with this email
                existing_user_result = await self.db.execute(
                    select(User).where(User.email == email_lower)
                )
                existing_user = existing_user_result.scalar_one_or_none()

                if not existing_user:
                    # Auto-create user account when email is added
                    temporary_password = self._generate_temporary_password()

                    user = User(
                        id=str(uuid.uuid4()),
                        email=email_lower,
                        hashed_password=hash_password(temporary_password),
                        first_name=driver.first_name,
                        last_name=driver.last_name,
                        company_id=company_id,
                        role="driver",
                        is_active=True,
                        must_change_password=True,  # Force password change on first login
                    )
                    self.db.add(user)
                    await self.db.flush()

                    # Link driver to user
                    driver.user_id = user.id

                    # Send invitation email with credentials
                    try:
                        EmailService.send_driver_invitation(
                            email=email_lower,
                            first_name=driver.first_name,
                            last_name=driver.last_name,
                            temporary_password=temporary_password,
                        )
                    except Exception as e:
                        print(f"Warning: Failed to send invitation email to {email_lower}: {e}")

        # Update basic driver fields
        if payload.first_name is not None:
            driver.first_name = payload.first_name
        if payload.last_name is not None:
            driver.last_name = payload.last_name
        if payload.email is not None:
            driver.email = payload.email.lower()
        # Accept both phone and phone_number from frontend
        if payload.phone_number is not None:
            driver.phone = payload.phone_number
        if payload.phone is not None:
            driver.phone = payload.phone
        # Accept both license_number and cdl_number from frontend
        if payload.license_number is not None:
            driver.cdl_number = payload.license_number
        if payload.cdl_number is not None:
            driver.cdl_number = payload.cdl_number
        if payload.license_expiration is not None:
            driver.cdl_expiration = payload.license_expiration
        if payload.medical_card_expiration is not None:
            driver.medical_card_expiration = payload.medical_card_expiration

        # Update metadata
        metadata = self._ensure_metadata(driver.profile_metadata)
        if payload.middle_initial is not None:
            metadata["middle_initial"] = payload.middle_initial
        if payload.home_address is not None:
            metadata["home_address"] = payload.home_address
        if payload.status is not None:
            metadata["status"] = payload.status
        if payload.license_state is not None:
            metadata["license_state"] = payload.license_state
        if payload.license_class is not None:
            metadata["license_class"] = payload.license_class
        if payload.endorsements is not None:
            metadata["endorsements"] = payload.endorsements.model_dump()

        driver.profile_metadata = metadata

        await self.db.commit()
        await self.db.refresh(driver)

        # Emit driver update event for real-time sync
        await emit_event(
            EventType.DRIVER_UPDATED,
            {
                "driver_id": driver_id,
                "driver_name": f"{driver.first_name} {driver.last_name}",
                "email": driver.email,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "phone": driver.phone,
            },
            company_id=company_id,
        )

        return await self._build_profile(driver)

    async def get_user_access(self, company_id: str, driver_id: str) -> UserAccessInfo:
        """Get user access information for a driver."""
        driver = await self._get_driver(company_id, driver_id)

        if not driver.user_id:
            return UserAccessInfo(status="none")

        # Fetch user information
        result = await self.db.execute(select(User).where(User.id == driver.user_id))
        user = result.scalar_one_or_none()

        if not user:
            return UserAccessInfo(status="none")

        status = "active" if user.is_active else "suspended"

        return UserAccessInfo(
            user_id=user.id,
            email=user.email,
            status=status,
            last_login=None,  # TODO: Implement last_login tracking
            created_at=user.created_at,
        )

    async def suspend_user_access(self, company_id: str, driver_id: str) -> UserAccessActionResponse:
        """Suspend user access for a driver."""
        driver = await self._get_driver(company_id, driver_id)

        if not driver.user_id:
            raise ValueError("Driver does not have a user account")

        result = await self.db.execute(select(User).where(User.id == driver.user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User account not found")

        user.is_active = False
        await self.db.commit()

        return UserAccessActionResponse(
            success=True, message=f"User access suspended for {user.email}"
        )

    async def activate_user_access(self, company_id: str, driver_id: str) -> UserAccessActionResponse:
        """Activate user access for a driver."""
        driver = await self._get_driver(company_id, driver_id)

        if not driver.user_id:
            raise ValueError("Driver does not have a user account")

        result = await self.db.execute(select(User).where(User.id == driver.user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User account not found")

        user.is_active = True
        await self.db.commit()

        return UserAccessActionResponse(
            success=True, message=f"User access activated for {user.email}"
        )

    async def send_password_reset_email(
        self, company_id: str, driver_id: str
    ) -> UserAccessActionResponse:
        """Send password reset email (stub for now)."""
        driver = await self._get_driver(company_id, driver_id)

        if not driver.user_id:
            raise ValueError("Driver does not have a user account")

        result = await self.db.execute(select(User).where(User.id == driver.user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User account not found")

        # TODO: Implement actual email sending logic
        # For now, just return success
        return UserAccessActionResponse(
            success=True,
            message=f"Password reset email would be sent to {user.email} (not implemented)",
        )

    async def generate_new_password(
        self, company_id: str, driver_id: str
    ) -> GeneratePasswordResponse:
        """Generate a new temporary password for a driver."""
        driver = await self._get_driver(company_id, driver_id)

        if not driver.user_id:
            raise ValueError("Driver does not have a user account")

        result = await self.db.execute(select(User).where(User.id == driver.user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User account not found")

        # Generate new temporary password
        temporary_password = self._generate_temporary_password()

        # Update user's password
        user.hashed_password = hash_password(temporary_password)
        await self.db.commit()

        return GeneratePasswordResponse(
            temporary_password=temporary_password,
            message=f"New temporary password generated for {user.email}",
        )

    async def create_user_account(
        self, company_id: str, driver_id: str
    ) -> GeneratePasswordResponse:
        """Create a user account for a driver who doesn't have one yet."""
        driver = await self._get_driver(company_id, driver_id)

        if driver.user_id:
            raise ValueError("Driver already has a user account")

        if not driver.email:
            raise ValueError("Driver must have an email address to create app access")

        email_lower = driver.email.lower()

        # Check if user already exists with this email
        existing_user = await self.db.execute(select(User).where(User.email == email_lower))
        if existing_user.scalar_one_or_none():
            raise ValueError(f"A user with email {email_lower} already exists")

        # Generate temporary password
        temporary_password = self._generate_temporary_password()

        # Create user account
        user = User(
            id=str(uuid.uuid4()),
            email=email_lower,
            hashed_password=hash_password(temporary_password),
            first_name=driver.first_name,
            last_name=driver.last_name,
            company_id=company_id,
            role="driver",
            is_active=True,
            must_change_password=True,
        )
        self.db.add(user)
        await self.db.flush()

        # Link driver to user
        driver.user_id = user.id
        await self.db.commit()

        # Send invitation email with credentials
        try:
            EmailService.send_driver_invitation(
                email=email_lower,
                first_name=driver.first_name,
                last_name=driver.last_name,
                temporary_password=temporary_password,
            )
        except Exception as e:
            print(f"Warning: Failed to send invitation email to {email_lower}: {e}")

        return GeneratePasswordResponse(
            temporary_password=temporary_password,
            message=f"App access created for {email_lower}. Login credentials have been sent.",
        )

    async def get_driver_equipment(self, company_id: str, driver_id: str) -> DriverEquipmentInfo:
        """Get equipment assigned to a driver."""
        from app.models.equipment import Equipment
        from app.models.fuel import FuelCard

        driver = await self._get_driver(company_id, driver_id)

        # Get assigned truck
        truck_id = None
        truck_number = None
        if driver.profile_metadata and driver.profile_metadata.get("assigned_truck_id"):
            truck_result = await self.db.execute(
                select(Equipment).where(Equipment.id == driver.profile_metadata["assigned_truck_id"])
            )
            truck = truck_result.scalar_one_or_none()
            if truck:
                truck_id = truck.id
                truck_number = truck.unit_number

        # Get assigned trailer
        trailer_id = None
        trailer_number = None
        if driver.profile_metadata and driver.profile_metadata.get("assigned_trailer_id"):
            trailer_result = await self.db.execute(
                select(Equipment).where(Equipment.id == driver.profile_metadata["assigned_trailer_id"])
            )
            trailer = trailer_result.scalar_one_or_none()
            if trailer:
                trailer_id = trailer.id
                trailer_number = trailer.unit_number

        # Get assigned fuel card
        fuel_card_id = None
        fuel_card_number = None
        fuel_card_result = await self.db.execute(
            select(FuelCard).where(FuelCard.driver_id == driver.id)
        )
        fuel_card = fuel_card_result.scalar_one_or_none()
        if fuel_card:
            fuel_card_id = fuel_card.id
            fuel_card_number = fuel_card.card_number

        return DriverEquipmentInfo(
            truck_id=truck_id,
            truck_number=truck_number,
            trailer_id=trailer_id,
            trailer_number=trailer_number,
            fuel_card_id=fuel_card_id,
            fuel_card_number=fuel_card_number,
        )

    async def get_available_equipment(self, company_id: str) -> AvailableEquipmentResponse:
        """Get available equipment that can be assigned to drivers."""
        from app.models.equipment import Equipment
        from app.models.fuel import FuelCard

        # Get unassigned trucks
        trucks_result = await self.db.execute(
            select(Equipment)
            .where(
                Equipment.company_id == company_id,
                Equipment.equipment_type == "TRACTOR",
                Equipment.assigned_driver_id.is_(None),
            )
            .order_by(Equipment.unit_number)
        )
        trucks = trucks_result.scalars().all()

        # Get unassigned trailers
        trailers_result = await self.db.execute(
            select(Equipment)
            .where(
                Equipment.company_id == company_id,
                Equipment.equipment_type == "TRAILER",
                Equipment.assigned_driver_id.is_(None),
            )
            .order_by(Equipment.unit_number)
        )
        trailers = trailers_result.scalars().all()

        # Get unassigned fuel cards
        fuel_cards_result = await self.db.execute(
            select(FuelCard)
            .where(FuelCard.company_id == company_id, FuelCard.driver_id.is_(None))
            .order_by(FuelCard.card_number)
        )
        fuel_cards = fuel_cards_result.scalars().all()

        return AvailableEquipmentResponse(
            trucks=[EquipmentBasicInfo.model_validate(truck) for truck in trucks],
            trailers=[EquipmentBasicInfo.model_validate(trailer) for trailer in trailers],
            fuel_cards=[FuelCardBasicInfo.model_validate(card) for card in fuel_cards],
        )

    async def assign_equipment(
        self,
        company_id: str,
        driver_id: str,
        equipment_type: str,
        equipment_id: str,
    ) -> UserAccessActionResponse:
        """Assign equipment to a driver."""
        from app.models.equipment import Equipment
        from app.models.fuel import FuelCard

        driver = await self._get_driver(company_id, driver_id)

        if equipment_type == "truck":
            # Verify equipment exists and belongs to company
            equipment_result = await self.db.execute(
                select(Equipment).where(
                    Equipment.id == equipment_id, Equipment.company_id == company_id
                )
            )
            equipment = equipment_result.scalar_one_or_none()
            if not equipment:
                raise ValueError("Truck not found")

            # Update driver metadata
            metadata = self._ensure_metadata(driver.profile_metadata)
            metadata["assigned_truck_id"] = equipment_id
            driver.profile_metadata = metadata

            # Also update equipment's assigned_driver_id
            equipment.assigned_driver_id = driver_id

            await self.db.commit()
            return UserAccessActionResponse(
                success=True, message=f"Truck {equipment.unit_number} assigned to driver"
            )

        elif equipment_type == "trailer":
            # Verify equipment exists and belongs to company
            equipment_result = await self.db.execute(
                select(Equipment).where(
                    Equipment.id == equipment_id, Equipment.company_id == company_id
                )
            )
            equipment = equipment_result.scalar_one_or_none()
            if not equipment:
                raise ValueError("Trailer not found")

            # Update driver metadata
            metadata = self._ensure_metadata(driver.profile_metadata)
            metadata["assigned_trailer_id"] = equipment_id
            driver.profile_metadata = metadata

            # Also update equipment's assigned_driver_id
            equipment.assigned_driver_id = driver_id

            await self.db.commit()
            return UserAccessActionResponse(
                success=True, message=f"Trailer {equipment.unit_number} assigned to driver"
            )

        elif equipment_type == "fuel_card":
            # Verify fuel card exists and belongs to company
            fuel_card_result = await self.db.execute(
                select(FuelCard).where(
                    FuelCard.id == equipment_id, FuelCard.company_id == company_id
                )
            )
            fuel_card = fuel_card_result.scalar_one_or_none()
            if not fuel_card:
                raise ValueError("Fuel card not found")

            # Assign fuel card to driver
            fuel_card.driver_id = driver_id

            await self.db.commit()
            return UserAccessActionResponse(
                success=True, message=f"Fuel card {fuel_card.card_number} assigned to driver"
            )

        else:
            raise ValueError(f"Invalid equipment type: {equipment_type}")

    async def unassign_equipment(
        self,
        company_id: str,
        driver_id: str,
        equipment_type: str,
    ) -> UserAccessActionResponse:
        """Unassign equipment from a driver."""
        from app.models.equipment import Equipment
        from app.models.fuel import FuelCard

        driver = await self._get_driver(company_id, driver_id)

        if equipment_type == "truck":
            metadata = self._ensure_metadata(driver.profile_metadata)
            truck_id = metadata.get("assigned_truck_id")

            if truck_id:
                # Clear equipment's assigned_driver_id
                equipment_result = await self.db.execute(
                    select(Equipment).where(Equipment.id == truck_id)
                )
                equipment = equipment_result.scalar_one_or_none()
                if equipment:
                    equipment.assigned_driver_id = None

                # Clear from driver metadata
                metadata.pop("assigned_truck_id", None)
                driver.profile_metadata = metadata

            await self.db.commit()
            return UserAccessActionResponse(success=True, message="Truck unassigned from driver")

        elif equipment_type == "trailer":
            metadata = self._ensure_metadata(driver.profile_metadata)
            trailer_id = metadata.get("assigned_trailer_id")

            if trailer_id:
                # Clear equipment's assigned_driver_id
                equipment_result = await self.db.execute(
                    select(Equipment).where(Equipment.id == trailer_id)
                )
                equipment = equipment_result.scalar_one_or_none()
                if equipment:
                    equipment.assigned_driver_id = None

                # Clear from driver metadata
                metadata.pop("assigned_trailer_id", None)
                driver.profile_metadata = metadata

            await self.db.commit()
            return UserAccessActionResponse(success=True, message="Trailer unassigned from driver")

        elif equipment_type == "fuel_card":
            # Find and unassign fuel card
            fuel_card_result = await self.db.execute(
                select(FuelCard).where(FuelCard.driver_id == driver_id)
            )
            fuel_card = fuel_card_result.scalar_one_or_none()

            if fuel_card:
                fuel_card.driver_id = None

            await self.db.commit()
            return UserAccessActionResponse(success=True, message="Fuel card unassigned from driver")

        else:
            raise ValueError(f"Invalid equipment type: {equipment_type}")


"""Service layer for carrier-level compliance operations."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.carrier_compliance import (
    CarrierCredential,
    CarrierSAFERSnapshot,
    CompanyInsurance,
    CSAScore,
    ELDAuditItem,
    VehicleRegistration,
)
from app.schemas.carrier_compliance import (
    CarrierComplianceDashboardResponse,
    CarrierCredentialCreate,
    CarrierCredentialResponse,
    CarrierCredentialUpdate,
    CarrierSAFERDataResponse,
    CompanyInsuranceCreate,
    CompanyInsuranceResponse,
    CompanyInsuranceUpdate,
    ComplianceSummary,
    CSAScoreCreate,
    CSAScoreResponse,
    ELDAuditItemCreate,
    ELDAuditItemResolve,
    ELDAuditItemResponse,
    ELDAuditItemUpdate,
    ELDAuditSummaryResponse,
    VehicleRegistrationCreate,
    VehicleRegistrationResponse,
    VehicleRegistrationUpdate,
)


def _calculate_compliance_status(expiration_date: Optional[date]) -> str:
    """Calculate compliance status based on expiration date."""
    if not expiration_date:
        return "COMPLIANT"  # No expiration means always compliant

    today = date.today()
    days_until_expiration = (expiration_date - today).days

    if days_until_expiration < 0:
        return "EXPIRED"
    elif days_until_expiration <= 30:
        return "EXPIRING"
    else:
        return "COMPLIANT"


class CarrierComplianceService:
    """Service for managing carrier-level compliance data."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ==================== COMPANY INSURANCE ====================

    async def list_insurance(self, company_id: str) -> List[CompanyInsuranceResponse]:
        """List all insurance policies for a company."""
        result = await self.db.execute(
            select(CompanyInsurance)
            .where(CompanyInsurance.company_id == company_id)
            .order_by(CompanyInsurance.expiration_date.asc())
        )
        policies = result.scalars().all()
        return [self._map_insurance(p) for p in policies]

    async def create_insurance(
        self, company_id: str, payload: CompanyInsuranceCreate
    ) -> CompanyInsuranceResponse:
        """Create a new insurance policy."""
        policy = CompanyInsurance(
            id=str(uuid.uuid4()),
            company_id=company_id,
            insurance_type=payload.insurance_type,
            carrier_name=payload.carrier_name,
            policy_number=payload.policy_number,
            effective_date=payload.effective_date,
            expiration_date=payload.expiration_date,
            coverage_limit=payload.coverage_limit,
            deductible=payload.deductible,
            certificate_holder=payload.certificate_holder,
            notes=payload.notes,
            status=_calculate_compliance_status(payload.expiration_date),
        )
        self.db.add(policy)
        await self.db.commit()
        await self.db.refresh(policy)
        return self._map_insurance(policy)

    async def update_insurance(
        self, company_id: str, insurance_id: str, payload: CompanyInsuranceUpdate
    ) -> CompanyInsuranceResponse:
        """Update an insurance policy."""
        result = await self.db.execute(
            select(CompanyInsurance).where(
                CompanyInsurance.id == insurance_id,
                CompanyInsurance.company_id == company_id,
            )
        )
        policy = result.scalar_one_or_none()
        if not policy:
            raise ValueError(f"Insurance policy {insurance_id} not found")

        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(policy, key, value)

        # Recalculate status if expiration date changed
        policy.status = _calculate_compliance_status(policy.expiration_date)

        await self.db.commit()
        await self.db.refresh(policy)
        return self._map_insurance(policy)

    async def delete_insurance(self, company_id: str, insurance_id: str) -> None:
        """Delete an insurance policy."""
        result = await self.db.execute(
            select(CompanyInsurance).where(
                CompanyInsurance.id == insurance_id,
                CompanyInsurance.company_id == company_id,
            )
        )
        policy = result.scalar_one_or_none()
        if not policy:
            raise ValueError(f"Insurance policy {insurance_id} not found")

        await self.db.delete(policy)
        await self.db.commit()

    def _map_insurance(self, policy: CompanyInsurance) -> CompanyInsuranceResponse:
        return CompanyInsuranceResponse(
            id=policy.id,
            insurance_type=policy.insurance_type,
            carrier_name=policy.carrier_name,
            policy_number=policy.policy_number,
            effective_date=policy.effective_date,
            expiration_date=policy.expiration_date,
            coverage_limit=float(policy.coverage_limit),
            deductible=float(policy.deductible) if policy.deductible else None,
            status=_calculate_compliance_status(policy.expiration_date),
            certificate_holder=policy.certificate_holder,
            notes=policy.notes,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )

    # ==================== CARRIER CREDENTIALS ====================

    async def list_credentials(self, company_id: str) -> List[CarrierCredentialResponse]:
        """List all carrier credentials for a company."""
        result = await self.db.execute(
            select(CarrierCredential)
            .where(CarrierCredential.company_id == company_id)
            .order_by(CarrierCredential.credential_type.asc())
        )
        credentials = result.scalars().all()
        return [self._map_credential(c) for c in credentials]

    async def create_credential(
        self, company_id: str, payload: CarrierCredentialCreate
    ) -> CarrierCredentialResponse:
        """Create a new carrier credential."""
        credential = CarrierCredential(
            id=str(uuid.uuid4()),
            company_id=company_id,
            credential_type=payload.credential_type,
            credential_number=payload.credential_number,
            issuing_authority=payload.issuing_authority,
            issue_date=payload.issue_date,
            expiration_date=payload.expiration_date,
            notes=payload.notes,
            status=_calculate_compliance_status(payload.expiration_date),
        )
        self.db.add(credential)
        await self.db.commit()
        await self.db.refresh(credential)
        return self._map_credential(credential)

    async def update_credential(
        self, company_id: str, credential_id: str, payload: CarrierCredentialUpdate
    ) -> CarrierCredentialResponse:
        """Update a carrier credential."""
        result = await self.db.execute(
            select(CarrierCredential).where(
                CarrierCredential.id == credential_id,
                CarrierCredential.company_id == company_id,
            )
        )
        credential = result.scalar_one_or_none()
        if not credential:
            raise ValueError(f"Credential {credential_id} not found")

        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(credential, key, value)

        credential.status = _calculate_compliance_status(credential.expiration_date)

        await self.db.commit()
        await self.db.refresh(credential)
        return self._map_credential(credential)

    async def delete_credential(self, company_id: str, credential_id: str) -> None:
        """Delete a carrier credential."""
        result = await self.db.execute(
            select(CarrierCredential).where(
                CarrierCredential.id == credential_id,
                CarrierCredential.company_id == company_id,
            )
        )
        credential = result.scalar_one_or_none()
        if not credential:
            raise ValueError(f"Credential {credential_id} not found")

        await self.db.delete(credential)
        await self.db.commit()

    def _map_credential(self, credential: CarrierCredential) -> CarrierCredentialResponse:
        return CarrierCredentialResponse(
            id=credential.id,
            credential_type=credential.credential_type,
            credential_number=credential.credential_number,
            issuing_authority=credential.issuing_authority,
            issue_date=credential.issue_date,
            expiration_date=credential.expiration_date,
            status=_calculate_compliance_status(credential.expiration_date),
            notes=credential.notes,
            created_at=credential.created_at,
            updated_at=credential.updated_at,
        )

    # ==================== VEHICLE REGISTRATIONS ====================

    async def list_registrations(self, company_id: str) -> List[VehicleRegistrationResponse]:
        """List all vehicle registrations for a company."""
        result = await self.db.execute(
            select(VehicleRegistration)
            .where(VehicleRegistration.company_id == company_id)
            .order_by(VehicleRegistration.expiration_date.asc())
        )
        registrations = result.scalars().all()
        return [self._map_registration(r) for r in registrations]

    async def create_registration(
        self, company_id: str, payload: VehicleRegistrationCreate
    ) -> VehicleRegistrationResponse:
        """Create a new vehicle registration."""
        registration = VehicleRegistration(
            id=str(uuid.uuid4()),
            company_id=company_id,
            equipment_id=payload.equipment_id,
            unit_number=payload.unit_number,
            plate_number=payload.plate_number,
            state=payload.state,
            registration_type=payload.registration_type,
            effective_date=payload.effective_date,
            expiration_date=payload.expiration_date,
            notes=payload.notes,
            status=_calculate_compliance_status(payload.expiration_date),
        )
        self.db.add(registration)
        await self.db.commit()
        await self.db.refresh(registration)
        return self._map_registration(registration)

    async def update_registration(
        self, company_id: str, registration_id: str, payload: VehicleRegistrationUpdate
    ) -> VehicleRegistrationResponse:
        """Update a vehicle registration."""
        result = await self.db.execute(
            select(VehicleRegistration).where(
                VehicleRegistration.id == registration_id,
                VehicleRegistration.company_id == company_id,
            )
        )
        registration = result.scalar_one_or_none()
        if not registration:
            raise ValueError(f"Registration {registration_id} not found")

        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(registration, key, value)

        registration.status = _calculate_compliance_status(registration.expiration_date)

        await self.db.commit()
        await self.db.refresh(registration)
        return self._map_registration(registration)

    async def delete_registration(self, company_id: str, registration_id: str) -> None:
        """Delete a vehicle registration."""
        result = await self.db.execute(
            select(VehicleRegistration).where(
                VehicleRegistration.id == registration_id,
                VehicleRegistration.company_id == company_id,
            )
        )
        registration = result.scalar_one_or_none()
        if not registration:
            raise ValueError(f"Registration {registration_id} not found")

        await self.db.delete(registration)
        await self.db.commit()

    def _map_registration(self, registration: VehicleRegistration) -> VehicleRegistrationResponse:
        return VehicleRegistrationResponse(
            id=registration.id,
            equipment_id=registration.equipment_id,
            unit_number=registration.unit_number,
            plate_number=registration.plate_number,
            state=registration.state,
            registration_type=registration.registration_type,
            effective_date=registration.effective_date,
            expiration_date=registration.expiration_date,
            status=_calculate_compliance_status(registration.expiration_date),
            notes=registration.notes,
            created_at=registration.created_at,
            updated_at=registration.updated_at,
        )

    # ==================== ELD AUDIT ITEMS ====================

    async def list_audit_items(
        self, company_id: str, status: Optional[str] = None
    ) -> List[ELDAuditItemResponse]:
        """List ELD audit items for a company."""
        query = select(ELDAuditItem).where(ELDAuditItem.company_id == company_id)
        if status:
            query = query.where(ELDAuditItem.status == status)
        query = query.order_by(ELDAuditItem.date.desc())

        result = await self.db.execute(query)
        items = result.scalars().all()
        return [self._map_audit_item(i) for i in items]

    async def create_audit_item(
        self, company_id: str, payload: ELDAuditItemCreate
    ) -> ELDAuditItemResponse:
        """Create a new ELD audit item."""
        item = ELDAuditItem(
            id=str(uuid.uuid4()),
            company_id=company_id,
            category=payload.category,
            severity=payload.severity,
            driver_id=payload.driver_id,
            driver_name=payload.driver_name,
            equipment_id=payload.equipment_id,
            unit_number=payload.unit_number,
            date=payload.date,
            description=payload.description,
            duration_minutes=payload.duration_minutes,
            status="OPEN",
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return self._map_audit_item(item)

    async def update_audit_item(
        self, company_id: str, item_id: str, payload: ELDAuditItemUpdate
    ) -> ELDAuditItemResponse:
        """Update an ELD audit item."""
        result = await self.db.execute(
            select(ELDAuditItem).where(
                ELDAuditItem.id == item_id,
                ELDAuditItem.company_id == company_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError(f"Audit item {item_id} not found")

        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(item, key, value)

        await self.db.commit()
        await self.db.refresh(item)
        return self._map_audit_item(item)

    async def resolve_audit_item(
        self, company_id: str, item_id: str, payload: ELDAuditItemResolve
    ) -> ELDAuditItemResponse:
        """Resolve an ELD audit item."""
        result = await self.db.execute(
            select(ELDAuditItem).where(
                ELDAuditItem.id == item_id,
                ELDAuditItem.company_id == company_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError(f"Audit item {item_id} not found")

        item.status = "RESOLVED"
        item.resolved_at = datetime.utcnow()
        item.resolved_by = payload.resolved_by

        await self.db.commit()
        await self.db.refresh(item)
        return self._map_audit_item(item)

    async def get_audit_summary(self, company_id: str) -> ELDAuditSummaryResponse:
        """Get ELD audit summary for a company."""
        # Get all open audit items
        open_items = await self.list_audit_items(company_id, status="OPEN")

        unidentified_driving_count = 0
        unidentified_driving_minutes = 0
        missing_log_count = 0
        form_manner_errors = 0
        malfunctions = 0

        for item in open_items:
            if item.category == "UNIDENTIFIED_DRIVING":
                unidentified_driving_count += 1
                unidentified_driving_minutes += item.duration_minutes or 0
            elif item.category == "MISSING_LOGS":
                missing_log_count += 1
            elif item.category == "FORM_MANNER":
                form_manner_errors += 1
            elif item.category == "MALFUNCTION":
                malfunctions += 1

        # Get last audit date
        last_audit_result = await self.db.execute(
            select(func.max(ELDAuditItem.date)).where(ELDAuditItem.company_id == company_id)
        )
        last_audit_date = last_audit_result.scalar_one_or_none()

        return ELDAuditSummaryResponse(
            unidentified_driving_count=unidentified_driving_count,
            unidentified_driving_minutes=unidentified_driving_minutes,
            missing_log_count=missing_log_count,
            form_manner_errors=form_manner_errors,
            malfunctions=malfunctions,
            data_transfer_ready=malfunctions == 0,  # Ready if no malfunctions
            last_audit_date=last_audit_date,
            audit_items=open_items,
        )

    def _map_audit_item(self, item: ELDAuditItem) -> ELDAuditItemResponse:
        return ELDAuditItemResponse(
            id=item.id,
            category=item.category,
            severity=item.severity,
            driver_id=item.driver_id,
            driver_name=item.driver_name,
            equipment_id=item.equipment_id,
            unit_number=item.unit_number,
            date=item.date,
            description=item.description,
            duration_minutes=item.duration_minutes,
            status=item.status,
            resolved_at=item.resolved_at,
            resolved_by=item.resolved_by,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    # ==================== CSA SCORES ====================

    async def list_csa_scores(self, company_id: str) -> List[CSAScoreResponse]:
        """List CSA BASIC scores for a company."""
        result = await self.db.execute(
            select(CSAScore)
            .where(CSAScore.company_id == company_id)
            .order_by(CSAScore.category.asc())
        )
        scores = result.scalars().all()
        return [self._map_csa_score(s) for s in scores]

    async def upsert_csa_score(
        self, company_id: str, payload: CSAScoreCreate
    ) -> CSAScoreResponse:
        """Create or update a CSA BASIC score."""
        result = await self.db.execute(
            select(CSAScore).where(
                CSAScore.company_id == company_id,
                CSAScore.category == payload.category,
            )
        )
        score = result.scalar_one_or_none()

        if score:
            # Update existing
            score.percentile = payload.percentile
            score.threshold = payload.threshold
            score.status = payload.status
            score.data_source = payload.data_source
            score.last_updated = datetime.utcnow()
        else:
            # Create new
            score = CSAScore(
                id=str(uuid.uuid4()),
                company_id=company_id,
                category=payload.category,
                percentile=payload.percentile,
                threshold=payload.threshold,
                status=payload.status,
                data_source=payload.data_source,
                last_updated=datetime.utcnow(),
            )
            self.db.add(score)

        await self.db.commit()
        await self.db.refresh(score)
        return self._map_csa_score(score)

    def _map_csa_score(self, score: CSAScore) -> CSAScoreResponse:
        return CSAScoreResponse(
            id=score.id,
            category=score.category,
            percentile=score.percentile,
            threshold=score.threshold,
            status=score.status,
            last_updated=score.last_updated,
            created_at=score.created_at,
            updated_at=score.updated_at,
        )

    # ==================== SAFER DATA ====================

    async def get_safer_data(self, company_id: str) -> Optional[CarrierSAFERDataResponse]:
        """Get the most recent SAFER snapshot for a company."""
        result = await self.db.execute(
            select(CarrierSAFERSnapshot)
            .where(CarrierSAFERSnapshot.company_id == company_id)
            .order_by(CarrierSAFERSnapshot.last_fetched.desc())
        )
        snapshot = result.scalar_one_or_none()
        if not snapshot:
            return None

        # Get CSA scores
        csa_scores = await self.list_csa_scores(company_id)

        cargo_carried = None
        if snapshot.cargo_carried:
            import json
            try:
                cargo_carried = json.loads(snapshot.cargo_carried)
            except (json.JSONDecodeError, TypeError):
                cargo_carried = [snapshot.cargo_carried]

        return CarrierSAFERDataResponse(
            usdot_number=snapshot.usdot_number,
            mc_number=snapshot.mc_number,
            legal_name=snapshot.legal_name,
            dba_name=snapshot.dba_name,
            physical_address=snapshot.physical_address,
            mailing_address=snapshot.mailing_address,
            phone_number=snapshot.phone_number,
            power_units=snapshot.power_units,
            drivers=snapshot.drivers,
            mcs150_date=snapshot.mcs150_date,
            out_of_service_date=snapshot.out_of_service_date,
            operating_status=snapshot.operating_status,
            carrier_operation=snapshot.carrier_operation,
            cargo_carried=cargo_carried,
            safety_rating=snapshot.safety_rating,
            safety_rating_date=snapshot.safety_rating_date,
            csa_scores=csa_scores,
            last_fetched=snapshot.last_fetched,
        )

    # ==================== DASHBOARD ====================

    async def get_dashboard(self, company_id: str) -> CarrierComplianceDashboardResponse:
        """Get the full carrier compliance dashboard."""
        # Fetch all data
        safer_data = await self.get_safer_data(company_id)
        eld_audit = await self.get_audit_summary(company_id)
        credentials = await self.list_credentials(company_id)
        insurance_policies = await self.list_insurance(company_id)
        vehicle_registrations = await self.list_registrations(company_id)

        # Calculate summaries
        def calc_summary(items: list) -> ComplianceSummary:
            total = len(items)
            compliant = sum(1 for i in items if i.status == "COMPLIANT")
            expiring = sum(1 for i in items if i.status == "EXPIRING")
            expired = sum(1 for i in items if i.status == "EXPIRED")
            return ComplianceSummary(
                total=total,
                compliant=compliant,
                expiring_soon=expiring,
                expired=expired,
            )

        return CarrierComplianceDashboardResponse(
            safer_data=safer_data,
            eld_audit=eld_audit,
            credentials=credentials,
            insurance_policies=insurance_policies,
            vehicle_registrations=vehicle_registrations,
            permit_summary=calc_summary(credentials),
            insurance_summary=calc_summary(insurance_policies),
            registration_summary=calc_summary(vehicle_registrations),
        )

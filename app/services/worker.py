"""Worker service - handles worker CRUD operations."""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import and_, cast, select, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver import Driver
from app.models.worker import (
    Deduction,
    PayRule,
    Worker,
    WorkerDocument,
    PayrollSettlement,
    WorkerType,
    WorkerRole,
    WorkerStatus,
)
from app.models.equipment import Equipment
from app.schemas.worker import (
    DeductionCreate,
    DeductionResponse,
    PayRuleCreate,
    PayRuleResponse,
    WorkerCreate,
    WorkerDocumentCreate,
    WorkerDocumentResponse,
    WorkerProfileResponse,
    WorkerResponse,
    WorkerUpdate,
    SettlementResponse,
)


class WorkerService:
    """Service for worker management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_workers(
        self,
        company_id: str,
        worker_type: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[WorkerResponse]:
        """List workers with optional filters."""
        query = select(Worker).where(Worker.company_id == company_id)

        if worker_type:
            # Validate enum value exists, then compare with lowercase string (PostgreSQL stores lowercase)
            WorkerType[worker_type.upper()]  # Raises KeyError if invalid
            query = query.where(cast(Worker.type, String) == worker_type.lower())
        if role:
            WorkerRole[role.upper()]  # Raises KeyError if invalid
            query = query.where(cast(Worker.role, String) == role.lower())
        if status:
            WorkerStatus[status.upper()]  # Raises KeyError if invalid
            query = query.where(cast(Worker.status, String) == status.lower())

        result = await self.db.execute(query)
        workers = result.scalars().all()

        return [WorkerResponse.model_validate(w) for w in workers]

    async def get_worker(self, company_id: str, worker_id: str) -> Optional[WorkerResponse]:
        """Get worker by ID."""
        result = await self.db.execute(
            select(Worker).where(
                and_(
                    Worker.id == worker_id,
                    Worker.company_id == company_id,
                )
            )
        )
        worker = result.scalar_one_or_none()

        if not worker:
            return None

        return WorkerResponse.model_validate(worker)

    async def get_worker_profile(self, company_id: str, worker_id: str) -> Optional[WorkerProfileResponse]:
        """Get detailed worker profile with documents, pay rules, deductions, and settlements."""
        result = await self.db.execute(
            select(Worker).where(
                and_(
                    Worker.id == worker_id,
                    Worker.company_id == company_id,
                )
            )
        )
        worker = result.scalar_one_or_none()

        if not worker:
            return None

        # Get documents
        docs_result = await self.db.execute(
            select(WorkerDocument).where(WorkerDocument.worker_id == worker_id)
        )
        documents = docs_result.scalars().all()

        # Get pay rules
        rules_result = await self.db.execute(
            select(PayRule).where(PayRule.worker_id == worker_id)
        )
        pay_rules = rules_result.scalars().all()

        # Get deductions
        deductions_result = await self.db.execute(
            select(Deduction).where(Deduction.worker_id == worker_id)
        )
        deductions = deductions_result.scalars().all()

        # Get owned equipment count
        equipment_result = await self.db.execute(
            select(Equipment).where(Equipment.owner_id == worker_id)
        )
        owned_equipment_count = len(equipment_result.scalars().all())

        # Get recent settlements
        settlements_result = await self.db.execute(
            select(PayrollSettlement)
            .where(PayrollSettlement.worker_id == worker_id)
            .order_by(PayrollSettlement.created_at.desc())
            .limit(10)
        )
        recent_settlements = settlements_result.scalars().all()

        return WorkerProfileResponse(
            **WorkerResponse.model_validate(worker).model_dump(),
            documents=[WorkerDocumentResponse.model_validate(d) for d in documents],
            pay_rules=[PayRuleResponse.model_validate(r) for r in pay_rules],
            deductions=[DeductionResponse.model_validate(d) for d in deductions],
            owned_equipment_count=owned_equipment_count,
            recent_settlements=[SettlementResponse.model_validate(s) for s in recent_settlements],
        )

    async def create_worker(self, company_id: str, payload: WorkerCreate) -> WorkerResponse:
        """Create a new worker and corresponding functional role record if applicable."""
        # Convert string type/role to enums
        worker_type = WorkerType[payload.type.upper()] if payload.type else WorkerType.EMPLOYEE
        worker_role = WorkerRole[payload.role.upper()] if payload.role else WorkerRole.OTHER

        worker = Worker(
            id=str(uuid.uuid4()),
            company_id=company_id,
            type=worker_type,
            role=worker_role,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            tax_id=payload.tax_id,  # TODO: Encrypt in production
            bank_info=payload.bank_info,
            pay_default=payload.pay_default,
            hire_date=payload.hire_date,
            status=WorkerStatus.ACTIVE,
        )

        self.db.add(worker)
        await self.db.flush()  # Flush to get the worker ID

        # If role is driver, create corresponding Driver record
        if payload.role.lower() == "driver":
            driver = Driver(
                id=str(uuid.uuid4()),
                company_id=company_id,
                worker_id=worker.id,
                first_name=payload.first_name,
                last_name=payload.last_name,
                email=payload.email,
                phone=payload.phone,
            )
            self.db.add(driver)

        await self.db.commit()
        await self.db.refresh(worker)

        return WorkerResponse.model_validate(worker)

    async def update_worker(
        self,
        company_id: str,
        worker_id: str,
        payload: WorkerUpdate,
    ) -> Optional[WorkerResponse]:
        """Update worker."""
        result = await self.db.execute(
            select(Worker).where(
                and_(
                    Worker.id == worker_id,
                    Worker.company_id == company_id,
                )
            )
        )
        worker = result.scalar_one_or_none()

        if not worker:
            return None

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(worker, field, value)

        await self.db.commit()
        await self.db.refresh(worker)

        return WorkerResponse.model_validate(worker)

    async def add_document(
        self,
        company_id: str,
        worker_id: str,
        payload: WorkerDocumentCreate,
        uploaded_by: str,
    ) -> WorkerDocumentResponse:
        """Add document to worker."""
        # Verify worker exists
        await self.get_worker(company_id, worker_id)

        document = WorkerDocument(
            id=str(uuid.uuid4()),
            worker_id=worker_id,
            doc_type=payload.doc_type,
            file_url=payload.file_url,
            expires_at=payload.expires_at,
            uploaded_by=uploaded_by,
        )

        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        return WorkerDocumentResponse.model_validate(document)

    async def create_pay_rule(
        self,
        company_id: str,
        worker_id: str,
        payload: PayRuleCreate,
    ) -> PayRuleResponse:
        """Create pay rule for worker."""
        # Verify worker exists
        await self.get_worker(company_id, worker_id)

        pay_rule = PayRule(
            id=str(uuid.uuid4()),
            worker_id=worker_id,
            company_id=company_id,
            rule_type=payload.rule_type,
            rate=payload.rate,
            additional=payload.additional,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
        )

        self.db.add(pay_rule)
        await self.db.commit()
        await self.db.refresh(pay_rule)

        return PayRuleResponse.model_validate(pay_rule)

    async def get_pay_rules(self, company_id: str, worker_id: str) -> List[PayRuleResponse]:
        """Get pay rules for worker."""
        # Verify worker exists
        await self.get_worker(company_id, worker_id)

        result = await self.db.execute(
            select(PayRule).where(PayRule.worker_id == worker_id)
        )
        pay_rules = result.scalars().all()

        return [PayRuleResponse.model_validate(r) for r in pay_rules]

    async def create_deduction(
        self,
        company_id: str,
        worker_id: str,
        payload: DeductionCreate,
    ) -> DeductionResponse:
        """Create deduction for worker."""
        # Verify worker exists
        await self.get_worker(company_id, worker_id)

        deduction = Deduction(
            id=str(uuid.uuid4()),
            worker_id=worker_id,
            type=payload.type,
            amount=payload.amount,
            percentage=payload.percentage,
            frequency=payload.frequency,
            meta=payload.meta,
            is_active="true",
        )

        self.db.add(deduction)
        await self.db.commit()
        await self.db.refresh(deduction)

        return DeductionResponse.model_validate(deduction)

    async def get_deductions(self, company_id: str, worker_id: str) -> List[DeductionResponse]:
        """Get deductions for worker."""
        # Verify worker exists
        await self.get_worker(company_id, worker_id)

        result = await self.db.execute(
            select(Deduction).where(Deduction.worker_id == worker_id)
        )
        deductions = result.scalars().all()

        return [DeductionResponse.model_validate(d) for d in deductions]

    async def backfill_workers_for_drivers(self, company_id: str) -> dict:
        """Create Worker records for existing drivers who don't have them."""
        # Find drivers without worker_id
        driver_query = (
            select(Driver)
            .where(Driver.company_id == company_id)
            .where(Driver.worker_id == None)
        )
        driver_result = await self.db.execute(driver_query)
        drivers = driver_result.scalars().all()

        created_count = 0
        for driver in drivers:
            # Create a Worker record for the driver
            worker = Worker(
                id=str(uuid.uuid4()),
                company_id=company_id,
                type=WorkerType.EMPLOYEE,  # Default to employee
                role=WorkerRole.DRIVER,
                first_name=driver.first_name,
                last_name=driver.last_name,
                email=driver.email,
                phone=driver.phone,
                status=WorkerStatus.ACTIVE,
            )
            self.db.add(worker)
            await self.db.flush()

            # Link the driver to the worker
            driver.worker_id = worker.id
            created_count += 1

        await self.db.commit()

        return {
            "created_count": created_count,
            "message": f"Created {created_count} worker records for existing drivers",
        }

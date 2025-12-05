"""HQ Admin Portal service layer."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import create_access_token, hash_password, verify_password
from app.models.company import Company
from app.models.hq_employee import HQEmployee, HQRole
from app.models.hq_tenant import HQTenant, TenantStatus, SubscriptionTier
from app.models.hq_contract import HQContract, ContractStatus, ContractType
from app.models.hq_quote import HQQuote, QuoteStatus
from app.models.hq_credit import HQCredit, CreditType, CreditStatus
from app.models.hq_payout import HQPayout, PayoutStatus
from app.models.hq_system_module import HQSystemModule, ModuleStatus
from app.schemas.hq import (
    HQLoginRequest,
    HQSessionUser,
    HQAuthSessionResponse,
    HQEmployeeCreate,
    HQEmployeeUpdate,
    HQTenantCreate,
    HQTenantUpdate,
    HQContractCreate,
    HQContractUpdate,
    HQQuoteCreate,
    HQQuoteUpdate,
    HQCreditCreate,
    HQCreditReject,
    HQPayoutCreate,
    HQSystemModuleUpdate,
    HQDashboardMetrics,
)


class HQAuthService:
    """Authentication service for HQ admin portal."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def authenticate(self, payload: HQLoginRequest) -> Tuple[HQEmployee, str]:
        """Authenticate HQ employee with email, employee number, and password."""
        result = await self.db.execute(
            select(HQEmployee).where(
                and_(
                    HQEmployee.email == payload.email.lower(),
                    HQEmployee.employee_number == payload.employee_number.upper(),
                )
            )
        )
        employee = result.scalar_one_or_none()

        if not employee or not verify_password(payload.password, employee.hashed_password):
            raise ValueError("Invalid credentials")
        if not employee.is_active:
            raise ValueError("Account disabled")

        # Update last login
        employee.last_login_at = datetime.utcnow()
        await self.db.commit()

        access_token = create_access_token({"sub": employee.id, "type": "hq"})
        return employee, access_token

    async def build_session(self, employee: HQEmployee, token: str | None = None) -> HQAuthSessionResponse:
        """Build session response for HQ employee."""
        session_user = HQSessionUser(
            id=employee.id,
            email=employee.email,
            employee_number=employee.employee_number,
            first_name=employee.first_name,
            last_name=employee.last_name,
            role=employee.role.value if isinstance(employee.role, HQRole) else employee.role,
            department=employee.department,
        )
        return HQAuthSessionResponse(user=session_user, access_token=token)

    async def get_employee_by_id(self, employee_id: str) -> Optional[HQEmployee]:
        """Get HQ employee by ID."""
        return await self.db.get(HQEmployee, employee_id)


class HQEmployeeService:
    """Service for managing HQ employees."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_employees(self) -> List[HQEmployee]:
        """List all HQ employees."""
        result = await self.db.execute(
            select(HQEmployee).order_by(HQEmployee.employee_number)
        )
        return list(result.scalars().all())

    async def get_employee(self, employee_id: str) -> Optional[HQEmployee]:
        """Get employee by ID."""
        return await self.db.get(HQEmployee, employee_id)

    async def create_employee(self, payload: HQEmployeeCreate) -> HQEmployee:
        """Create a new HQ employee."""
        # Check for existing email
        result = await self.db.execute(
            select(HQEmployee).where(HQEmployee.email == payload.email.lower())
        )
        if result.scalar_one_or_none():
            raise ValueError("Email already in use")

        # Check for existing employee number
        result = await self.db.execute(
            select(HQEmployee).where(HQEmployee.employee_number == payload.employee_number.upper())
        )
        if result.scalar_one_or_none():
            raise ValueError("Employee number already in use")

        employee = HQEmployee(
            id=str(uuid.uuid4()),
            employee_number=payload.employee_number.upper(),
            email=payload.email.lower(),
            hashed_password=hash_password(payload.password),
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            role=HQRole(payload.role),
            department=payload.department,
            phone=payload.phone,
        )
        self.db.add(employee)
        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def update_employee(self, employee_id: str, payload: HQEmployeeUpdate) -> HQEmployee:
        """Update an HQ employee."""
        employee = await self.db.get(HQEmployee, employee_id)
        if not employee:
            raise ValueError("Employee not found")

        if payload.first_name is not None:
            employee.first_name = payload.first_name.strip()
        if payload.last_name is not None:
            employee.last_name = payload.last_name.strip()
        if payload.role is not None:
            employee.role = HQRole(payload.role)
        if payload.department is not None:
            employee.department = payload.department
        if payload.phone is not None:
            employee.phone = payload.phone
        if payload.is_active is not None:
            employee.is_active = payload.is_active

        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def delete_employee(self, employee_id: str) -> None:
        """Delete an HQ employee."""
        employee = await self.db.get(HQEmployee, employee_id)
        if not employee:
            raise ValueError("Employee not found")
        await self.db.delete(employee)
        await self.db.commit()


class HQTenantService:
    """Service for managing tenants."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_tenants(self, status: Optional[str] = None) -> List[HQTenant]:
        """List all tenants with optional status filter."""
        query = select(HQTenant).options(selectinload(HQTenant.company))
        if status:
            query = query.where(HQTenant.status == TenantStatus(status))
        query = query.order_by(HQTenant.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_tenant(self, tenant_id: str) -> Optional[HQTenant]:
        """Get tenant by ID with company data."""
        result = await self.db.execute(
            select(HQTenant)
            .options(selectinload(HQTenant.company))
            .where(HQTenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def create_tenant(self, payload: HQTenantCreate) -> HQTenant:
        """Create a new tenant record for an existing company."""
        # Check company exists
        company = await self.db.get(Company, payload.company_id)
        if not company:
            raise ValueError("Company not found")

        # Check no existing tenant for this company
        result = await self.db.execute(
            select(HQTenant).where(HQTenant.company_id == payload.company_id)
        )
        if result.scalar_one_or_none():
            raise ValueError("Tenant already exists for this company")

        tenant = HQTenant(
            id=str(uuid.uuid4()),
            company_id=payload.company_id,
            status=TenantStatus.TRIAL,
            subscription_tier=SubscriptionTier(payload.subscription_tier),
            monthly_rate=payload.monthly_rate,
            billing_email=payload.billing_email,
            notes=payload.notes,
        )
        self.db.add(tenant)
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def update_tenant(self, tenant_id: str, payload: HQTenantUpdate) -> HQTenant:
        """Update a tenant."""
        tenant = await self.db.get(HQTenant, tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")

        if payload.status is not None:
            tenant.status = TenantStatus(payload.status)
        if payload.subscription_tier is not None:
            tenant.subscription_tier = SubscriptionTier(payload.subscription_tier)
        if payload.monthly_rate is not None:
            tenant.monthly_rate = payload.monthly_rate
        if payload.billing_email is not None:
            tenant.billing_email = payload.billing_email
        if payload.notes is not None:
            tenant.notes = payload.notes
        if payload.assigned_sales_rep_id is not None:
            tenant.assigned_sales_rep_id = payload.assigned_sales_rep_id

        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def suspend_tenant(self, tenant_id: str) -> HQTenant:
        """Suspend a tenant."""
        tenant = await self.db.get(HQTenant, tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        tenant.status = TenantStatus.SUSPENDED
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def activate_tenant(self, tenant_id: str) -> HQTenant:
        """Activate a tenant."""
        tenant = await self.db.get(HQTenant, tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")
        tenant.status = TenantStatus.ACTIVE
        tenant.subscription_started_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant


class HQContractService:
    """Service for managing contracts."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._counter = 0

    async def _generate_contract_number(self) -> str:
        """Generate unique contract number."""
        result = await self.db.execute(select(func.count(HQContract.id)))
        count = result.scalar() or 0
        return f"CTR-{datetime.utcnow().year}-{str(count + 1).zfill(5)}"

    async def list_contracts(self, tenant_id: Optional[str] = None) -> List[HQContract]:
        """List contracts with optional tenant filter."""
        query = select(HQContract)
        if tenant_id:
            query = query.where(HQContract.tenant_id == tenant_id)
        query = query.order_by(HQContract.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_contract(self, contract_id: str) -> Optional[HQContract]:
        """Get contract by ID."""
        return await self.db.get(HQContract, contract_id)

    async def create_contract(self, payload: HQContractCreate, created_by_id: str) -> HQContract:
        """Create a new contract."""
        contract_number = await self._generate_contract_number()

        contract = HQContract(
            id=str(uuid.uuid4()),
            tenant_id=payload.tenant_id,
            contract_number=contract_number,
            contract_type=ContractType(payload.contract_type),
            status=ContractStatus.DRAFT,
            title=payload.title,
            description=payload.description,
            monthly_value=payload.monthly_value,
            annual_value=payload.annual_value or (payload.monthly_value * 12),
            setup_fee=payload.setup_fee,
            start_date=payload.start_date,
            end_date=payload.end_date,
            auto_renew=payload.auto_renew,
            notice_period_days=payload.notice_period_days,
            custom_terms=payload.custom_terms,
            created_by_id=created_by_id,
        )
        self.db.add(contract)
        await self.db.commit()
        await self.db.refresh(contract)
        return contract

    async def update_contract(self, contract_id: str, payload: HQContractUpdate) -> HQContract:
        """Update a contract."""
        contract = await self.db.get(HQContract, contract_id)
        if not contract:
            raise ValueError("Contract not found")

        if payload.title is not None:
            contract.title = payload.title
        if payload.status is not None:
            contract.status = ContractStatus(payload.status)
        if payload.description is not None:
            contract.description = payload.description
        if payload.monthly_value is not None:
            contract.monthly_value = payload.monthly_value
        if payload.annual_value is not None:
            contract.annual_value = payload.annual_value
        if payload.setup_fee is not None:
            contract.setup_fee = payload.setup_fee
        if payload.start_date is not None:
            contract.start_date = payload.start_date
        if payload.end_date is not None:
            contract.end_date = payload.end_date
        if payload.custom_terms is not None:
            contract.custom_terms = payload.custom_terms

        await self.db.commit()
        await self.db.refresh(contract)
        return contract

    async def approve_contract(self, contract_id: str, approved_by_id: str) -> HQContract:
        """Approve a contract."""
        contract = await self.db.get(HQContract, contract_id)
        if not contract:
            raise ValueError("Contract not found")
        contract.status = ContractStatus.ACTIVE
        contract.approved_by_id = approved_by_id
        contract.approved_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(contract)
        return contract


class HQQuoteService:
    """Service for managing quotes."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _generate_quote_number(self) -> str:
        """Generate unique quote number."""
        result = await self.db.execute(select(func.count(HQQuote.id)))
        count = result.scalar() or 0
        return f"QTE-{datetime.utcnow().year}-{str(count + 1).zfill(5)}"

    async def list_quotes(self, tenant_id: Optional[str] = None) -> List[HQQuote]:
        """List quotes with optional tenant filter."""
        query = select(HQQuote)
        if tenant_id:
            query = query.where(HQQuote.tenant_id == tenant_id)
        query = query.order_by(HQQuote.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_quote(self, quote_id: str) -> Optional[HQQuote]:
        """Get quote by ID."""
        return await self.db.get(HQQuote, quote_id)

    async def create_quote(self, payload: HQQuoteCreate, created_by_id: str) -> HQQuote:
        """Create a new quote."""
        quote_number = await self._generate_quote_number()

        quote = HQQuote(
            id=str(uuid.uuid4()),
            tenant_id=payload.tenant_id,
            quote_number=quote_number,
            status=QuoteStatus.DRAFT,
            title=payload.title,
            description=payload.description,
            tier=payload.tier,
            contact_name=payload.contact_name,
            contact_email=payload.contact_email,
            contact_company=payload.contact_company,
            contact_phone=payload.contact_phone,
            base_monthly_rate=payload.base_monthly_rate,
            discount_percent=payload.discount_percent,
            discount_amount=payload.discount_amount,
            final_monthly_rate=payload.final_monthly_rate,
            setup_fee=payload.setup_fee,
            addons=payload.addons,
            valid_until=payload.valid_until,
            created_by_id=created_by_id,
        )
        self.db.add(quote)
        await self.db.commit()
        await self.db.refresh(quote)
        return quote

    async def send_quote(self, quote_id: str) -> HQQuote:
        """Mark quote as sent."""
        quote = await self.db.get(HQQuote, quote_id)
        if not quote:
            raise ValueError("Quote not found")
        quote.status = QuoteStatus.SENT
        quote.sent_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(quote)
        return quote

    async def update_quote(self, quote_id: str, payload: HQQuoteUpdate) -> HQQuote:
        """Update a quote."""
        quote = await self.db.get(HQQuote, quote_id)
        if not quote:
            raise ValueError("Quote not found")

        for field in ["title", "description", "tier", "base_monthly_rate",
                      "discount_percent", "discount_amount", "final_monthly_rate",
                      "setup_fee", "addons", "valid_until"]:
            value = getattr(payload, field, None)
            if value is not None:
                setattr(quote, field, value)
        if payload.status is not None:
            quote.status = QuoteStatus(payload.status)

        await self.db.commit()
        await self.db.refresh(quote)
        return quote


class HQCreditService:
    """Service for managing credits."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_credits(self, tenant_id: Optional[str] = None, status: Optional[str] = None) -> List[HQCredit]:
        """List credits with optional filters."""
        query = select(HQCredit)
        if tenant_id:
            query = query.where(HQCredit.tenant_id == tenant_id)
        if status:
            query = query.where(HQCredit.status == CreditStatus(status))
        query = query.order_by(HQCredit.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_credit(self, credit_id: str) -> Optional[HQCredit]:
        """Get credit by ID."""
        return await self.db.get(HQCredit, credit_id)

    async def create_credit(self, payload: HQCreditCreate, requested_by_id: str) -> HQCredit:
        """Create a new credit request."""
        credit = HQCredit(
            id=str(uuid.uuid4()),
            tenant_id=payload.tenant_id,
            credit_type=CreditType(payload.credit_type),
            status=CreditStatus.PENDING,
            amount=payload.amount,
            remaining_amount=payload.amount,
            reason=payload.reason,
            internal_notes=payload.internal_notes,
            expires_at=payload.expires_at,
            requested_by_id=requested_by_id,
        )
        self.db.add(credit)
        await self.db.commit()
        await self.db.refresh(credit)
        return credit

    async def approve_credit(self, credit_id: str, approved_by_id: str) -> HQCredit:
        """Approve a credit."""
        credit = await self.db.get(HQCredit, credit_id)
        if not credit:
            raise ValueError("Credit not found")
        if credit.status != CreditStatus.PENDING:
            raise ValueError("Credit is not pending")
        credit.status = CreditStatus.APPROVED
        credit.approved_by_id = approved_by_id
        credit.approved_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(credit)
        return credit

    async def reject_credit(self, credit_id: str, rejected_by_id: str, payload: HQCreditReject) -> HQCredit:
        """Reject a credit."""
        credit = await self.db.get(HQCredit, credit_id)
        if not credit:
            raise ValueError("Credit not found")
        if credit.status != CreditStatus.PENDING:
            raise ValueError("Credit is not pending")
        credit.status = CreditStatus.REJECTED
        credit.rejected_by_id = rejected_by_id
        credit.rejected_at = datetime.utcnow()
        credit.rejection_reason = payload.rejection_reason
        await self.db.commit()
        await self.db.refresh(credit)
        return credit

    async def apply_credit(self, credit_id: str, invoice_id: Optional[str] = None) -> HQCredit:
        """Apply a credit."""
        credit = await self.db.get(HQCredit, credit_id)
        if not credit:
            raise ValueError("Credit not found")
        if credit.status != CreditStatus.APPROVED:
            raise ValueError("Credit must be approved before applying")
        credit.status = CreditStatus.APPLIED
        credit.applied_at = datetime.utcnow()
        credit.applied_to_invoice_id = invoice_id
        credit.remaining_amount = Decimal("0")
        await self.db.commit()
        await self.db.refresh(credit)
        return credit


class HQPayoutService:
    """Service for managing payouts."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_payouts(self, tenant_id: Optional[str] = None, status: Optional[str] = None) -> List[HQPayout]:
        """List payouts with optional filters."""
        query = select(HQPayout)
        if tenant_id:
            query = query.where(HQPayout.tenant_id == tenant_id)
        if status:
            query = query.where(HQPayout.status == PayoutStatus(status))
        query = query.order_by(HQPayout.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_payout(self, payout_id: str) -> Optional[HQPayout]:
        """Get payout by ID."""
        return await self.db.get(HQPayout, payout_id)

    async def create_payout(self, payload: HQPayoutCreate, initiated_by_id: str) -> HQPayout:
        """Create a new payout."""
        payout = HQPayout(
            id=str(uuid.uuid4()),
            tenant_id=payload.tenant_id,
            status=PayoutStatus.PENDING,
            amount=payload.amount,
            currency=payload.currency,
            description=payload.description,
            period_start=payload.period_start,
            period_end=payload.period_end,
            initiated_by_id=initiated_by_id,
            initiated_at=datetime.utcnow(),
        )
        self.db.add(payout)
        await self.db.commit()
        await self.db.refresh(payout)
        return payout

    async def cancel_payout(self, payout_id: str) -> HQPayout:
        """Cancel a pending payout."""
        payout = await self.db.get(HQPayout, payout_id)
        if not payout:
            raise ValueError("Payout not found")
        if payout.status != PayoutStatus.PENDING:
            raise ValueError("Only pending payouts can be cancelled")
        payout.status = PayoutStatus.CANCELLED
        await self.db.commit()
        await self.db.refresh(payout)
        return payout


class HQSystemModuleService:
    """Service for managing system modules."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_modules(self) -> List[HQSystemModule]:
        """List all system modules."""
        result = await self.db.execute(
            select(HQSystemModule).order_by(HQSystemModule.key)
        )
        return list(result.scalars().all())

    async def get_module(self, module_key: str) -> Optional[HQSystemModule]:
        """Get module by key."""
        result = await self.db.execute(
            select(HQSystemModule).where(HQSystemModule.key == module_key)
        )
        return result.scalar_one_or_none()

    async def update_module(self, module_key: str, payload: HQSystemModuleUpdate, updated_by_id: str) -> HQSystemModule:
        """Update a system module."""
        module = await self.get_module(module_key)
        if not module:
            raise ValueError("Module not found")

        if payload.status is not None:
            module.status = ModuleStatus(payload.status)
        if payload.maintenance_message is not None:
            module.maintenance_message = payload.maintenance_message
        if payload.maintenance_end_time is not None:
            module.maintenance_end_time = payload.maintenance_end_time

        module.last_updated_by_id = updated_by_id
        module.last_updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(module)
        return module

    async def set_maintenance(self, module_key: str, updated_by_id: str) -> HQSystemModule:
        """Put module in maintenance mode."""
        module = await self.get_module(module_key)
        if not module:
            raise ValueError("Module not found")
        module.status = ModuleStatus.MAINTENANCE
        module.last_updated_by_id = updated_by_id
        module.last_updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(module)
        return module

    async def activate_module(self, module_key: str, updated_by_id: str) -> HQSystemModule:
        """Activate a module."""
        module = await self.get_module(module_key)
        if not module:
            raise ValueError("Module not found")
        module.status = ModuleStatus.ACTIVE
        module.maintenance_message = None
        module.maintenance_end_time = None
        module.last_updated_by_id = updated_by_id
        module.last_updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(module)
        return module


class HQDashboardService:
    """Service for dashboard metrics."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_metrics(self) -> HQDashboardMetrics:
        """Get dashboard metrics."""
        # Active tenants
        active_result = await self.db.execute(
            select(func.count(HQTenant.id)).where(HQTenant.status == TenantStatus.ACTIVE)
        )
        active_tenants = active_result.scalar() or 0

        # Trial tenants
        trial_result = await self.db.execute(
            select(func.count(HQTenant.id)).where(HQTenant.status == TenantStatus.TRIAL)
        )
        trial_tenants = trial_result.scalar() or 0

        # MRR (sum of active tenant monthly rates)
        mrr_result = await self.db.execute(
            select(func.coalesce(func.sum(HQTenant.monthly_rate), 0)).where(
                HQTenant.status == TenantStatus.ACTIVE
            )
        )
        mrr = Decimal(str(mrr_result.scalar() or 0))

        # ARR
        arr = mrr * 12

        # Pending payouts
        pending_payouts_result = await self.db.execute(
            select(
                func.count(HQPayout.id),
                func.coalesce(func.sum(HQPayout.amount), 0)
            ).where(HQPayout.status == PayoutStatus.PENDING)
        )
        pending_row = pending_payouts_result.one()
        pending_payouts_count = pending_row[0] or 0
        pending_payouts_amount = Decimal(str(pending_row[1] or 0))

        # Pending credits
        pending_credits_result = await self.db.execute(
            select(func.count(HQCredit.id)).where(HQCredit.status == CreditStatus.PENDING)
        )
        pending_credits_count = pending_credits_result.scalar() or 0

        # Expiring contracts (next 30 days)
        from datetime import timedelta
        expiring_result = await self.db.execute(
            select(func.count(HQContract.id)).where(
                and_(
                    HQContract.status == ContractStatus.ACTIVE,
                    HQContract.end_date <= datetime.utcnow() + timedelta(days=30),
                    HQContract.end_date >= datetime.utcnow(),
                )
            )
        )
        expiring_contracts_count = expiring_result.scalar() or 0

        return HQDashboardMetrics(
            active_tenants=active_tenants,
            trial_tenants=trial_tenants,
            mrr=mrr,
            arr=arr,
            churn_rate=Decimal("0"),  # Would need historical data
            ltv=Decimal("0"),  # Would need historical data
            pending_payouts_amount=pending_payouts_amount,
            pending_payouts_count=pending_payouts_count,
            pending_credits_count=pending_credits_count,
            expiring_contracts_count=expiring_contracts_count,
        )

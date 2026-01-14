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
from app.core.password_policy import validate_password
from app.models.company import Company
from app.models.user import User
from app.models.hq_employee import HQEmployee, HQRole
from app.models.hq_tenant import HQTenant, TenantStatus, SubscriptionTier
from app.models.hq_contract import HQContract, ContractStatus, ContractType
from app.models.hq_quote import HQQuote, QuoteStatus
from app.models.hq_credit import HQCredit, CreditType, CreditStatus
from app.models.hq_payout import HQPayout, PayoutStatus
from app.models.hq_system_module import HQSystemModule, ModuleStatus
from app.models.hq_banking import HQFraudAlert, HQBankingAuditLog, FraudAlertSeverity, FraudAlertStatus, BankingAuditAction
from app.models.banking import BankingCustomer, BankingAccount, BankingCard
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
    HQBankingCompanyResponse,
    HQFraudAlertResponse,
    HQBankingAuditLogResponse,
    HQBankingOverviewStats,
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
        # Validate password strength
        is_valid, errors = validate_password(payload.password, payload.email)
        if not is_valid:
            raise ValueError(f"Password does not meet requirements: {'; '.join(errors)}")

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
            title=payload.title,
            phone=payload.phone,
            hire_date=payload.hire_date,
            salary=payload.salary,
            emergency_contact=payload.emergency_contact,
            emergency_phone=payload.emergency_phone,
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
        if payload.title is not None:
            employee.title = payload.title
        if payload.phone is not None:
            employee.phone = payload.phone
        if payload.hire_date is not None:
            employee.hire_date = payload.hire_date
        if payload.salary is not None:
            employee.salary = payload.salary
        if payload.emergency_contact is not None:
            employee.emergency_contact = payload.emergency_contact
        if payload.emergency_phone is not None:
            employee.emergency_phone = payload.emergency_phone
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

    # ========================================================================
    # Master Spec Module 4: Affiliate & Sales - Referral Code Generation
    # ========================================================================

    async def generate_referral_code(self, employee_id: str, custom_code: Optional[str] = None) -> dict:
        """
        Generate a unique referral code for a sales agent or affiliate.

        Master Spec Module 4: Referral codes enable tracking of:
        - Which agent/affiliate referred a tenant
        - Commission calculations for successful conversions
        - Performance metrics per agent
        """
        import random
        import string

        employee = await self.db.get(HQEmployee, employee_id)
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")

        # Check if already has a referral code
        if employee.referral_code:
            return {
                "success": False,
                "message": "Employee already has a referral code",
                "referralCode": employee.referral_code,
                "generatedAt": employee.referral_code_generated_at.isoformat() if employee.referral_code_generated_at else None
            }

        # Generate referral code
        if custom_code:
            # Validate custom code format (alphanumeric, 6-12 chars, uppercase)
            if not custom_code.isalnum():
                raise ValueError("Custom code must be alphanumeric")
            if len(custom_code) < 6 or len(custom_code) > 12:
                raise ValueError("Custom code must be 6-12 characters")

            referral_code = custom_code.upper()

            # Check if custom code already exists
            result = await self.db.execute(
                select(HQEmployee).where(HQEmployee.referral_code == referral_code)
            )
            if result.scalar_one_or_none():
                raise ValueError(f"Referral code {referral_code} already in use")
        else:
            # Auto-generate: FirstLast + 4 random chars
            # Example: JOHNSMITH1A2B
            first_clean = ''.join(c for c in employee.first_name.upper() if c.isalnum())[:6]
            last_clean = ''.join(c for c in employee.last_name.upper() if c.isalnum())[:6]

            # Try to generate unique code (max 10 attempts)
            for attempt in range(10):
                random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                referral_code = f"{first_clean}{last_clean}{random_suffix}"[:12]

                # Check uniqueness
                result = await self.db.execute(
                    select(HQEmployee).where(HQEmployee.referral_code == referral_code)
                )
                if not result.scalar_one_or_none():
                    break
            else:
                raise ValueError("Failed to generate unique referral code after 10 attempts")

        # Save referral code
        employee.referral_code = referral_code
        employee.referral_code_generated_at = datetime.utcnow()

        await self.db.commit()

        return {
            "success": True,
            "employeeId": employee_id,
            "referralCode": referral_code,
            "generatedAt": employee.referral_code_generated_at.isoformat(),
            "referralUrl": f"https://app.freightops.io/signup?ref={referral_code}"
        }

    async def get_referral_stats(self, employee_id: str) -> dict:
        """
        Get referral statistics for a sales agent or affiliate.

        Master Spec Module 4: Shows performance metrics including:
        - Total referrals (lifetime_referrals)
        - Total commission earned (lifetime_commission_earned)
        - Active tenants from referrals
        - Pending commission payouts
        """
        from app.models.hq_tenant import HQTenant
        from app.models.hq_commission import HQCommissionPayout
        from decimal import Decimal

        employee = await self.db.get(HQEmployee, employee_id)
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")

        if not employee.referral_code:
            raise ValueError("Employee does not have a referral code")

        # Get active tenants referred by this agent
        result = await self.db.execute(
            select(HQTenant)
            .where(HQTenant.referred_by_agent_id == employee_id)
            .where(HQTenant.status.in_(["ACTIVE", "TRIAL"]))
        )
        active_tenants = result.scalars().all()

        # Calculate total MRR from referred tenants
        total_referred_mrr = sum(
            tenant.mrr_amount or Decimal("0.00")
            for tenant in active_tenants
        )

        # Get pending commission payouts
        result = await self.db.execute(
            select(HQCommissionPayout)
            .where(HQCommissionPayout.agent_id == employee_id)
            .where(HQCommissionPayout.status == "PENDING")
        )
        pending_payouts = result.scalars().all()

        pending_commission = sum(
            payout.commission_amount or Decimal("0.00")
            for payout in pending_payouts
        )

        return {
            "success": True,
            "employeeId": employee_id,
            "referralCode": employee.referral_code,
            "stats": {
                "lifetimeReferrals": employee.lifetime_referrals or 0,
                "lifetimeCommissionEarned": float(employee.lifetime_commission_earned or Decimal("0.00")),
                "activeReferredTenants": len(active_tenants),
                "totalReferredMrr": float(total_referred_mrr),
                "pendingCommission": float(pending_commission),
                "commissionRates": {
                    "mrr": float(employee.commission_rate_mrr or Decimal("0.00")),
                    "setup": float(employee.commission_rate_setup or Decimal("0.00")),
                    "fintech": float(employee.commission_rate_fintech or Decimal("0.00"))
                }
            }
        }

    async def update_commission_rates(
        self,
        employee_id: str,
        mrr_rate: Optional[Decimal] = None,
        setup_rate: Optional[Decimal] = None,
        fintech_rate: Optional[Decimal] = None
    ) -> dict:
        """
        Update commission rates for a sales agent or affiliate.

        Master Spec Module 4: Commission rates are percentages (e.g., 0.1000 = 10%)
        - mrr_rate: Commission on monthly recurring revenue
        - setup_rate: Commission on setup fees
        - fintech_rate: Commission on fintech revenue (banking/payroll)
        """
        employee = await self.db.get(HQEmployee, employee_id)
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")

        updated_fields = []

        if mrr_rate is not None:
            if mrr_rate < Decimal("0.0") or mrr_rate > Decimal("1.0"):
                raise ValueError("MRR rate must be between 0.0 and 1.0 (0% to 100%)")
            employee.commission_rate_mrr = mrr_rate
            updated_fields.append("commission_rate_mrr")

        if setup_rate is not None:
            if setup_rate < Decimal("0.0") or setup_rate > Decimal("1.0"):
                raise ValueError("Setup rate must be between 0.0 and 1.0 (0% to 100%)")
            employee.commission_rate_setup = setup_rate
            updated_fields.append("commission_rate_setup")

        if fintech_rate is not None:
            if fintech_rate < Decimal("0.0") or fintech_rate > Decimal("1.0"):
                raise ValueError("Fintech rate must be between 0.0 and 1.0 (0% to 100%)")
            employee.commission_rate_fintech = fintech_rate
            updated_fields.append("commission_rate_fintech")

        await self.db.commit()

        return {
            "success": True,
            "employeeId": employee_id,
            "updatedFields": updated_fields,
            "commissionRates": {
                "mrr": float(employee.commission_rate_mrr or Decimal("0.00")),
                "setup": float(employee.commission_rate_setup or Decimal("0.00")),
                "fintech": float(employee.commission_rate_fintech or Decimal("0.00"))
            }
        }


class HQTenantService:
    """Service for managing tenants."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_tenants(self, status: Optional[str] = None) -> List[HQTenant]:
        """List all tenants with optional status filter."""
        query = select(HQTenant).options(
            selectinload(HQTenant.company).selectinload(Company.users)
        )
        if status:
            query = query.where(HQTenant.status == TenantStatus(status))
        query = query.order_by(HQTenant.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_tenant(self, tenant_id: str) -> Optional[HQTenant]:
        """Get tenant by ID with company data."""
        result = await self.db.execute(
            select(HQTenant)
            .options(selectinload(HQTenant.company).selectinload(Company.users))
            .where(HQTenant.id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def create_tenant(self, payload: HQTenantCreate) -> HQTenant:
        """Create a new tenant with company from frontend form data."""
        # Generate email from company name if not provided
        company_email = payload.primary_contact_email
        if not company_email:
            # Create a placeholder email
            slug = payload.company_name.lower().replace(" ", "-").replace(".", "")[:30]
            company_email = f"{slug}@placeholder.fops.io"

        # Check if company with same DOT number exists
        if payload.dot_number:
            result = await self.db.execute(
                select(Company).where(Company.dotNumber == payload.dot_number)
            )
            if result.scalar_one_or_none():
                raise ValueError(f"Company with DOT number {payload.dot_number} already exists")

        # Check if company with same MC number exists
        if payload.mc_number:
            result = await self.db.execute(
                select(Company).where(Company.mcNumber == payload.mc_number)
            )
            if result.scalar_one_or_none():
                raise ValueError(f"Company with MC number {payload.mc_number} already exists")

        # Create Company record
        company_id = str(uuid.uuid4())
        company = Company(
            id=company_id,
            name=payload.company_name,
            legal_name=payload.legal_name,
            email=company_email,
            phone=payload.primary_contact_phone,
            dotNumber=payload.dot_number,
            mcNumber=payload.mc_number,
            tax_id=payload.tax_id,
            primaryContactName=payload.primary_contact_name,
            subscriptionPlan="pro",
            isActive=True,
        )
        self.db.add(company)

        # Parse subscription start date
        sub_started = None
        if payload.subscription_start_date:
            try:
                sub_started = datetime.fromisoformat(payload.subscription_start_date.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        # Create HQTenant record
        tenant = HQTenant(
            id=str(uuid.uuid4()),
            company_id=company_id,
            status=TenantStatus.TRIAL,
            subscription_tier=SubscriptionTier(payload.subscription_tier),
            monthly_rate=payload.monthly_fee,
            setup_fee=payload.setup_fee or Decimal("0"),
            billing_email=payload.billing_email or company_email,
            subscription_started_at=sub_started,
            notes=payload.notes,
        )
        self.db.add(tenant)

        await self.db.commit()

        # Reload with relationships
        result = await self.db.execute(
            select(HQTenant)
            .options(selectinload(HQTenant.company).selectinload(Company.users))
            .where(HQTenant.id == tenant.id)
        )
        return result.scalar_one()

    async def update_tenant(self, tenant_id: str, payload: HQTenantUpdate) -> HQTenant:
        """Update a tenant."""
        tenant = await self.db.get(HQTenant, tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")

        if payload.status is not None:
            tenant.status = TenantStatus(payload.status)
        if payload.subscription_tier is not None:
            tenant.subscription_tier = SubscriptionTier(payload.subscription_tier)
        if payload.monthly_fee is not None:
            tenant.monthly_rate = payload.monthly_fee
        if payload.setup_fee is not None:
            tenant.setup_fee = payload.setup_fee
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

    # ========================================================================
    # Master Spec Module 2: MRR Calculation & Financial Metrics
    # ========================================================================

    async def calculate_mrr(self, tenant_id: str) -> dict:
        """
        Calculate Monthly Recurring Revenue for a tenant.

        Master Spec Module 2: MRR calculation includes:
        - Base subscription MRR from HQSubscription
        - Fintech revenue estimate (banking + payroll)
        - Add-on services revenue
        - Usage-based revenue (if applicable)
        """
        from app.models.hq_subscription import HQSubscription
        from decimal import Decimal

        # Get tenant
        tenant = await self.db.get(HQTenant, tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        # Initialize MRR components
        subscription_mrr = Decimal("0.00")
        fintech_mrr = Decimal("0.00")
        addon_mrr = Decimal("0.00")
        total_mrr = Decimal("0.00")

        # 1. Base Subscription MRR
        result = await self.db.execute(
            select(HQSubscription)
            .where(HQSubscription.tenant_id == tenant_id)
            .where(HQSubscription.status.in_(["active", "trialing"]))
        )
        subscription = result.scalar_one_or_none()

        if subscription:
            # Use monthly_rate from subscription
            subscription_mrr = subscription.monthly_rate or Decimal("0.00")

        # 2. Fintech Revenue Estimate
        # Banking: Estimate based on deposit volume * take rate
        if tenant.banking_status == "ACCOUNT_OPENED" and tenant.total_deposits_mtd:
            # Example: 0.25% take rate on deposits
            banking_take_rate = tenant.fintech_take_rate or Decimal("0.0025")
            fintech_mrr += (tenant.total_deposits_mtd * banking_take_rate)

        # Payroll: Estimate based on active employees
        if tenant.payroll_status == "ACTIVE" and tenant.active_employees_paid:
            # Example: $5 per employee per month
            payroll_per_employee = Decimal("5.00")
            fintech_mrr += (Decimal(str(tenant.active_employees_paid)) * payroll_per_employee)

        # 3. Total MRR
        total_mrr = subscription_mrr + fintech_mrr + addon_mrr

        # 4. Update tenant MRR field
        tenant.mrr_amount = total_mrr
        await self.db.commit()

        # 5. Calculate additional metrics
        # Annual Contract Value (ACV)
        acv = total_mrr * Decimal("12")

        # Lifetime Value (simple estimate: MRR * expected lifetime months)
        expected_lifetime_months = Decimal("36")  # 3 years average
        ltv_estimate = total_mrr * expected_lifetime_months

        return {
            "success": True,
            "tenantId": tenant_id,
            "mrr": {
                "subscriptionMrr": float(subscription_mrr),
                "fintechMrr": float(fintech_mrr),
                "addonMrr": float(addon_mrr),
                "totalMrr": float(total_mrr)
            },
            "metrics": {
                "acv": float(acv),
                "ltvEstimate": float(ltv_estimate),
                "activeEmployees": int(tenant.active_employees_paid) if tenant.active_employees_paid else 0,
                "depositsMtd": float(tenant.total_deposits_mtd) if tenant.total_deposits_mtd else 0.0
            },
            "calculatedAt": datetime.utcnow().isoformat()
        }

    async def calculate_all_tenant_mrr(self, limit: int = 100) -> dict:
        """
        Batch calculate MRR for all active tenants.

        Master Spec Module 2: Run this periodically (e.g., nightly) to update
        all tenant MRR values for reporting and churn prediction.
        """
        from app.models.hq_tenant import TenantStatus

        # Get active tenants
        result = await self.db.execute(
            select(HQTenant)
            .where(HQTenant.status.in_([TenantStatus.ACTIVE, TenantStatus.TRIAL]))
            .limit(limit)
        )
        tenants = result.scalars().all()

        calculated_count = 0
        errors = []
        total_platform_mrr = Decimal("0.00")

        for tenant in tenants:
            try:
                result = await self.calculate_mrr(tenant.id)
                calculated_count += 1
                total_platform_mrr += Decimal(str(result["mrr"]["totalMrr"]))
            except Exception as e:
                errors.append({
                    "tenantId": tenant.id,
                    "companyName": tenant.company.name if tenant.company else "Unknown",
                    "error": str(e)
                })

        return {
            "success": True,
            "totalCalculated": calculated_count,
            "totalPlatformMrr": float(total_platform_mrr),
            "errors": errors
        }

    async def update_fintech_metrics(
        self,
        tenant_id: str,
        deposits_mtd: Optional[Decimal] = None,
        active_employees: Optional[int] = None
    ) -> dict:
        """
        Update fintech metrics for MRR calculation.

        Master Spec Module 3: This endpoint is called by webhook handlers when:
        - Synctera reports new deposits (banking)
        - CheckHQ reports active payroll employees
        """
        tenant = await self.db.get(HQTenant, tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        updated_fields = []

        if deposits_mtd is not None:
            tenant.total_deposits_mtd = deposits_mtd
            updated_fields.append("total_deposits_mtd")

        if active_employees is not None:
            tenant.active_employees_paid = Decimal(str(active_employees))
            updated_fields.append("active_employees_paid")

        await self.db.commit()

        # Recalculate MRR with new data
        mrr_result = await self.calculate_mrr(tenant_id)

        return {
            "success": True,
            "tenantId": tenant_id,
            "updatedFields": updated_fields,
            "newMrr": mrr_result["mrr"]["totalMrr"]
        }


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
        from datetime import timedelta
        from app.models.company import Company
        from app.models.billing import Subscription

        # Total tenants (companies)
        total_result = await self.db.execute(select(func.count(Company.id)))
        total_tenants = total_result.scalar() or 0

        # Active tenants (isActive = True)
        active_result = await self.db.execute(
            select(func.count(Company.id)).where(Company.isActive == True)
        )
        active_tenants = active_result.scalar() or 0

        # Trial tenants (subscriptionPlan = 'free' or 'starter')
        trial_result = await self.db.execute(
            select(func.count(Company.id)).where(
                and_(Company.isActive == True, Company.subscriptionPlan.in_(["free", "starter"]))
            )
        )
        trial_tenants = trial_result.scalar() or 0

        # Churned tenants (isActive = False)
        churned_result = await self.db.execute(
            select(func.count(Company.id)).where(Company.isActive == False)
        )
        churned_tenants = churned_result.scalar() or 0

        # MRR (sum from Subscription table for active companies)
        try:
            mrr_result = await self.db.execute(
                select(func.coalesce(func.sum(Subscription.total_monthly_cost), 0))
                .select_from(Subscription)
                .join(Company, Company.id == Subscription.company_id)
                .where(Company.isActive == True)
            )
            mrr = Decimal(str(mrr_result.scalar() or 0))
        except Exception:
            mrr = Decimal("0")

        # ARR
        arr = mrr * 12

        # Initialize HQ-specific metrics (may not exist yet)
        pending_payouts_count = 0
        pending_payouts_amount = Decimal("0")
        open_contracts = 0
        expiring_contracts = 0
        pending_quotes = 0
        total_credits_outstanding = Decimal("0")
        hq_employee_count = 0

        # Try to get HQ-specific metrics (tables may not exist)
        try:
            pending_payouts_result = await self.db.execute(
                select(
                    func.count(HQPayout.id),
                    func.coalesce(func.sum(HQPayout.amount), 0)
                ).where(HQPayout.status == PayoutStatus.PENDING)
            )
            pending_row = pending_payouts_result.one()
            pending_payouts_count = pending_row[0] or 0
            pending_payouts_amount = Decimal(str(pending_row[1] or 0))
        except Exception:
            pass

        try:
            open_contracts_result = await self.db.execute(
                select(func.count(HQContract.id)).where(HQContract.status == ContractStatus.ACTIVE)
            )
            open_contracts = open_contracts_result.scalar() or 0

            expiring_result = await self.db.execute(
                select(func.count(HQContract.id)).where(
                    and_(
                        HQContract.status == ContractStatus.ACTIVE,
                        HQContract.end_date <= datetime.utcnow() + timedelta(days=30),
                        HQContract.end_date >= datetime.utcnow(),
                    )
                )
            )
            expiring_contracts = expiring_result.scalar() or 0
        except Exception:
            pass

        try:
            pending_quotes_result = await self.db.execute(
                select(func.count(HQQuote.id)).where(
                    HQQuote.status.in_([QuoteStatus.DRAFT, QuoteStatus.SENT])
                )
            )
            pending_quotes = pending_quotes_result.scalar() or 0
        except Exception:
            pass

        try:
            credits_result = await self.db.execute(
                select(func.coalesce(func.sum(HQCredit.remaining_amount), 0)).where(
                    HQCredit.status == CreditStatus.APPROVED
                )
            )
            total_credits_outstanding = Decimal(str(credits_result.scalar() or 0))
        except Exception:
            pass

        try:
            employee_result = await self.db.execute(
                select(func.count(HQEmployee.id)).where(HQEmployee.is_active == True)
            )
            hq_employee_count = employee_result.scalar() or 0
        except Exception:
            pass

        return HQDashboardMetrics(
            total_tenants=total_tenants,
            active_tenants=active_tenants,
            trial_tenants=trial_tenants,
            churned_tenants=churned_tenants,
            mrr=mrr,
            arr=arr,
            mrr_growth=Decimal("0"),  # Would need historical data
            pending_payouts=pending_payouts_count,
            pending_payout_amount=pending_payouts_amount,
            open_contracts=open_contracts,
            expiring_contracts=expiring_contracts,
            pending_quotes=pending_quotes,
            total_credits_outstanding=total_credits_outstanding,
            hq_employee_count=hq_employee_count,
        )


class HQBankingService:
    """Service for HQ banking admin operations (Synctera integration)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_overview_stats(self) -> HQBankingOverviewStats:
        """Get banking overview statistics for HQ dashboard."""
        # Total companies with banking
        total_result = await self.db.execute(
            select(func.count(BankingCustomer.id))
        )
        total_companies = total_result.scalar() or 0

        # Active companies
        active_result = await self.db.execute(
            select(func.count(BankingCustomer.id)).where(
                BankingCustomer.status == "active"
            )
        )
        active_companies = active_result.scalar() or 0

        # Frozen companies
        frozen_result = await self.db.execute(
            select(func.count(BankingCustomer.id)).where(
                BankingCustomer.status == "frozen"
            )
        )
        frozen_companies = frozen_result.scalar() or 0

        # Pending KYB
        pending_kyb_result = await self.db.execute(
            select(func.count(BankingCustomer.id)).where(
                BankingCustomer.kyb_status.in_(["pending", "pending_review"])
            )
        )
        pending_kyb = pending_kyb_result.scalar() or 0

        # Total balance across all accounts
        balance_result = await self.db.execute(
            select(func.coalesce(func.sum(BankingAccount.available_balance), 0))
        )
        total_balance = Decimal(str(balance_result.scalar() or 0))

        # Pending fraud alerts
        pending_alerts_result = await self.db.execute(
            select(func.count(HQFraudAlert.id)).where(
                HQFraudAlert.status == FraudAlertStatus.PENDING.value
            )
        )
        pending_fraud_alerts = pending_alerts_result.scalar() or 0

        # Fraud alerts today
        from datetime import date
        today_alerts_result = await self.db.execute(
            select(func.count(HQFraudAlert.id)).where(
                func.date(HQFraudAlert.created_at) == date.today()
            )
        )
        fraud_alerts_today = today_alerts_result.scalar() or 0

        return HQBankingOverviewStats(
            total_companies=total_companies,
            active_companies=active_companies,
            frozen_companies=frozen_companies,
            pending_kyb=pending_kyb,
            total_balance=total_balance,
            pending_fraud_alerts=pending_fraud_alerts,
            fraud_alerts_today=fraud_alerts_today,
        )

    async def list_companies(self, status: Optional[str] = None) -> List[HQBankingCompanyResponse]:
        """List companies with banking status."""
        query = select(BankingCustomer).options(selectinload(BankingCustomer.accounts))
        if status:
            query = query.where(BankingCustomer.status == status)
        query = query.order_by(BankingCustomer.created_at.desc())

        result = await self.db.execute(query)
        customers = result.scalars().all()

        responses = []
        for customer in customers:
            # Get company info
            company = await self.db.get(Company, customer.company_id)

            # Count accounts and cards
            account_count = len(customer.accounts) if customer.accounts else 0
            card_count = 0
            total_balance = Decimal("0")
            available_balance = Decimal("0")

            for account in (customer.accounts or []):
                total_balance += account.balance or Decimal("0")
                available_balance += account.available_balance or Decimal("0")
                # Count cards
                cards_result = await self.db.execute(
                    select(func.count(BankingCard.id)).where(BankingCard.account_id == account.id)
                )
                card_count += cards_result.scalar() or 0

            # Count fraud alerts for this company
            alerts_result = await self.db.execute(
                select(func.count(HQFraudAlert.id)).where(
                    and_(
                        HQFraudAlert.company_id == customer.company_id,
                        HQFraudAlert.status == FraudAlertStatus.PENDING.value
                    )
                )
            )
            fraud_alert_count = alerts_result.scalar() or 0

            responses.append(HQBankingCompanyResponse(
                id=customer.id,
                tenant_id=customer.company_id,
                company_name=company.name if company else "Unknown",
                status=customer.status or "pending",
                kyb_status=customer.kyb_status or "not_started",
                synctera_business_id=customer.synctera_business_id,
                synctera_customer_id=customer.external_id,
                account_count=account_count,
                card_count=card_count,
                total_balance=total_balance,
                available_balance=available_balance,
                fraud_alert_count=fraud_alert_count,
                last_activity_at=customer.updated_at,
                created_at=customer.created_at,
                updated_at=customer.updated_at,
            ))

        return responses

    async def freeze_company(self, company_id: str, employee_id: str, ip_address: Optional[str] = None) -> None:
        """Freeze a company's banking access."""
        result = await self.db.execute(
            select(BankingCustomer).where(BankingCustomer.company_id == company_id)
        )
        customer = result.scalar_one_or_none()
        if not customer:
            raise ValueError("Banking customer not found")

        customer.status = "frozen"
        await self._log_action(
            company_id=company_id,
            action=BankingAuditAction.ACCOUNT_FROZEN.value,
            description=f"Account frozen by HQ admin",
            employee_id=employee_id,
            ip_address=ip_address,
        )
        await self.db.commit()

    async def unfreeze_company(self, company_id: str, employee_id: str, ip_address: Optional[str] = None) -> None:
        """Unfreeze a company's banking access."""
        result = await self.db.execute(
            select(BankingCustomer).where(BankingCustomer.company_id == company_id)
        )
        customer = result.scalar_one_or_none()
        if not customer:
            raise ValueError("Banking customer not found")

        customer.status = "active"
        await self._log_action(
            company_id=company_id,
            action=BankingAuditAction.ACCOUNT_UNFROZEN.value,
            description=f"Account unfrozen by HQ admin",
            employee_id=employee_id,
            ip_address=ip_address,
        )
        await self.db.commit()

    async def list_fraud_alerts(self, status: Optional[str] = None) -> List[HQFraudAlertResponse]:
        """List fraud alerts."""
        query = select(HQFraudAlert)
        if status:
            query = query.where(HQFraudAlert.status == status)
        query = query.order_by(HQFraudAlert.created_at.desc())

        result = await self.db.execute(query)
        alerts = result.scalars().all()

        responses = []
        for alert in alerts:
            company = await self.db.get(Company, alert.company_id)
            responses.append(HQFraudAlertResponse(
                id=alert.id,
                company_id=alert.company_id,
                company_name=company.name if company else "Unknown",
                alert_type=alert.alert_type,
                amount=alert.amount,
                description=alert.description,
                severity=alert.severity,
                status=alert.status,
                transaction_id=alert.transaction_id,
                card_id=alert.card_id,
                account_id=alert.account_id,
                synctera_alert_id=alert.synctera_alert_id,
                resolved_by=alert.resolved_by,
                resolved_at=alert.resolved_at,
                resolution_notes=alert.resolution_notes,
                created_at=alert.created_at,
                updated_at=alert.updated_at,
            ))

        return responses

    async def approve_fraud_alert(
        self, alert_id: str, employee_id: str, notes: Optional[str] = None, ip_address: Optional[str] = None
    ) -> HQFraudAlert:
        """Approve a fraud alert (allow the transaction)."""
        alert = await self.db.get(HQFraudAlert, alert_id)
        if not alert:
            raise ValueError("Fraud alert not found")
        if alert.status != FraudAlertStatus.PENDING.value:
            raise ValueError("Alert is not pending")

        alert.status = FraudAlertStatus.APPROVED.value
        alert.resolved_by = employee_id
        alert.resolved_at = datetime.utcnow()
        alert.resolution_notes = notes

        await self._log_action(
            company_id=alert.company_id,
            action=BankingAuditAction.FRAUD_APPROVED.value,
            description=f"Fraud alert approved: {alert.alert_type}",
            employee_id=employee_id,
            ip_address=ip_address,
            action_metadata={"alert_id": alert_id, "amount": str(alert.amount)},
        )
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def block_fraud_alert(
        self, alert_id: str, employee_id: str, notes: Optional[str] = None, ip_address: Optional[str] = None
    ) -> HQFraudAlert:
        """Block a fraud alert (reject the transaction)."""
        alert = await self.db.get(HQFraudAlert, alert_id)
        if not alert:
            raise ValueError("Fraud alert not found")
        if alert.status != FraudAlertStatus.PENDING.value:
            raise ValueError("Alert is not pending")

        alert.status = FraudAlertStatus.BLOCKED.value
        alert.resolved_by = employee_id
        alert.resolved_at = datetime.utcnow()
        alert.resolution_notes = notes

        await self._log_action(
            company_id=alert.company_id,
            action=BankingAuditAction.FRAUD_BLOCKED.value,
            description=f"Fraud alert blocked: {alert.alert_type}",
            employee_id=employee_id,
            ip_address=ip_address,
            action_metadata={"alert_id": alert_id, "amount": str(alert.amount)},
        )
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def list_audit_logs(self, limit: int = 100) -> List[HQBankingAuditLogResponse]:
        """List banking audit logs."""
        query = (
            select(HQBankingAuditLog)
            .options(selectinload(HQBankingAuditLog.performer))
            .order_by(HQBankingAuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        logs = result.scalars().all()

        responses = []
        for log in logs:
            company_name = None
            if log.company_id:
                company = await self.db.get(Company, log.company_id)
                company_name = company.name if company else None

            performer_name = f"{log.performer.first_name} {log.performer.last_name}" if log.performer else "Unknown"

            responses.append(HQBankingAuditLogResponse(
                id=log.id,
                company_id=log.company_id,
                company_name=company_name,
                action=log.action,
                description=log.description,
                performed_by=log.performed_by,
                performed_by_name=performer_name,
                ip_address=log.ip_address,
                action_metadata=log.action_metadata,
                created_at=log.created_at,
            ))

        return responses

    async def _log_action(
        self,
        action: str,
        description: str,
        employee_id: str,
        company_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        action_metadata: Optional[dict] = None,
    ) -> None:
        """Log a banking admin action."""
        log = HQBankingAuditLog(
            id=str(uuid.uuid4()),
            company_id=company_id,
            action=action,
            description=description,
            performed_by=employee_id,
            ip_address=ip_address,
            action_metadata=action_metadata,
        )
        self.db.add(log)


# ============================================================================
# Accounting Services
# ============================================================================

class HQCustomerService:
    """Service for managing A/R customers."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _generate_customer_number(self) -> str:
        """Generate unique customer number."""
        from app.models.hq_accounting import HQCustomer
        result = await self.db.execute(select(func.count(HQCustomer.id)))
        count = result.scalar() or 0
        return f"CUST-{str(count + 1).zfill(5)}"

    async def list_customers(self, status: Optional[str] = None) -> list:
        """List all customers."""
        from app.models.hq_accounting import HQCustomer, CustomerStatus
        query = select(HQCustomer)
        if status:
            query = query.where(HQCustomer.status == CustomerStatus(status.upper()))
        query = query.order_by(HQCustomer.name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_customer(self, customer_id: str):
        """Get customer by ID."""
        from app.models.hq_accounting import HQCustomer
        return await self.db.get(HQCustomer, customer_id)

    async def create_customer(self, payload, created_by_id: str = None):
        """Create a new customer."""
        from app.models.hq_accounting import HQCustomer, CustomerStatus, CustomerType

        customer_number = await self._generate_customer_number()

        customer = HQCustomer(
            id=str(uuid.uuid4()),
            customer_number=customer_number,
            tenant_id=payload.tenant_id,
            name=payload.name,
            customer_type=CustomerType(payload.customer_type.upper()),
            status=CustomerStatus.ACTIVE,
            email=payload.email,
            phone=payload.phone,
            billing_address=payload.billing_address,
            billing_city=payload.billing_city,
            billing_state=payload.billing_state,
            billing_zip=payload.billing_zip,
            billing_country=payload.billing_country,
            tax_id=payload.tax_id,
            payment_terms_days=payload.payment_terms_days,
            credit_limit=payload.credit_limit,
            notes=payload.notes,
        )
        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def update_customer(self, customer_id: str, payload):
        """Update a customer."""
        from app.models.hq_accounting import HQCustomer, CustomerStatus, CustomerType

        customer = await self.db.get(HQCustomer, customer_id)
        if not customer:
            raise ValueError("Customer not found")

        if payload.name is not None:
            customer.name = payload.name
        if payload.customer_type is not None:
            customer.customer_type = CustomerType(payload.customer_type.upper())
        if payload.status is not None:
            customer.status = CustomerStatus(payload.status.upper())
        if payload.email is not None:
            customer.email = payload.email
        if payload.phone is not None:
            customer.phone = payload.phone
        if payload.billing_address is not None:
            customer.billing_address = payload.billing_address
        if payload.billing_city is not None:
            customer.billing_city = payload.billing_city
        if payload.billing_state is not None:
            customer.billing_state = payload.billing_state
        if payload.billing_zip is not None:
            customer.billing_zip = payload.billing_zip
        if payload.payment_terms_days is not None:
            customer.payment_terms_days = payload.payment_terms_days
        if payload.credit_limit is not None:
            customer.credit_limit = payload.credit_limit
        if payload.notes is not None:
            customer.notes = payload.notes

        await self.db.commit()
        await self.db.refresh(customer)
        return customer


class HQInvoiceService:
    """Service for managing A/R invoices."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _generate_invoice_number(self) -> str:
        """Generate unique invoice number."""
        from app.models.hq_accounting import HQInvoice
        result = await self.db.execute(select(func.count(HQInvoice.id)))
        count = result.scalar() or 0
        return f"INV-{datetime.utcnow().year}-{str(count + 1).zfill(5)}"

    async def list_invoices(self, customer_id: Optional[str] = None, status: Optional[str] = None) -> list:
        """List all invoices."""
        from app.models.hq_accounting import HQInvoice, InvoiceStatus
        query = select(HQInvoice)
        if customer_id:
            query = query.where(HQInvoice.customer_id == customer_id)
        if status:
            query = query.where(HQInvoice.status == InvoiceStatus(status.upper()))
        query = query.order_by(HQInvoice.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_invoice(self, invoice_id: str):
        """Get invoice by ID."""
        from app.models.hq_accounting import HQInvoice
        return await self.db.get(HQInvoice, invoice_id)

    async def create_invoice(self, payload, created_by_id: str):
        """Create a new invoice."""
        from app.models.hq_accounting import HQInvoice, InvoiceStatus, InvoiceType

        invoice_number = await self._generate_invoice_number()

        # Convert line items to dict
        line_items = [item.model_dump() for item in payload.line_items] if payload.line_items else []

        invoice = HQInvoice(
            id=str(uuid.uuid4()),
            invoice_number=invoice_number,
            customer_id=payload.customer_id,
            tenant_id=payload.tenant_id,
            contract_id=payload.contract_id,
            invoice_type=InvoiceType(payload.invoice_type.upper()),
            status=InvoiceStatus.DRAFT,
            description=payload.description,
            line_items=line_items,
            subtotal=payload.subtotal,
            tax_total=payload.tax_total,
            total=payload.total,
            balance_due=payload.total,
            due_date=payload.due_date,
            notes=payload.notes,
            terms=payload.terms,
            created_by_id=created_by_id,
        )
        self.db.add(invoice)
        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def update_invoice(self, invoice_id: str, payload):
        """Update an invoice."""
        from app.models.hq_accounting import HQInvoice, InvoiceStatus

        invoice = await self.db.get(HQInvoice, invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")

        if payload.status is not None:
            invoice.status = InvoiceStatus(payload.status.upper())
        if payload.description is not None:
            invoice.description = payload.description
        if payload.due_date is not None:
            invoice.due_date = payload.due_date
        if payload.notes is not None:
            invoice.notes = payload.notes

        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def send_invoice(self, invoice_id: str):
        """Send an invoice."""
        from app.models.hq_accounting import HQInvoice, InvoiceStatus

        invoice = await self.db.get(HQInvoice, invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")

        invoice.status = InvoiceStatus.SENT
        invoice.issued_date = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice

    async def record_payment(self, invoice_id: str, amount: Decimal, recorded_by_id: str):
        """Record a payment against an invoice."""
        from app.models.hq_accounting import HQInvoice, HQPayment, InvoiceStatus, PaymentType, PaymentDirection

        invoice = await self.db.get(HQInvoice, invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")

        # Generate payment number
        result = await self.db.execute(select(func.count(HQPayment.id)))
        count = result.scalar() or 0
        payment_number = f"PMT-{datetime.utcnow().year}-{str(count + 1).zfill(5)}"

        # Create payment record
        payment = HQPayment(
            id=str(uuid.uuid4()),
            payment_number=payment_number,
            invoice_id=invoice_id,
            payment_type=PaymentType.ACH,
            direction=PaymentDirection.INCOMING,
            amount=amount,
            payment_date=datetime.utcnow(),
            recorded_by_id=recorded_by_id,
        )
        self.db.add(payment)

        # Update invoice
        invoice.paid_amount = (invoice.paid_amount or Decimal("0")) + amount
        invoice.balance_due = invoice.total - invoice.paid_amount

        if invoice.balance_due <= 0:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_date = datetime.utcnow()
        elif invoice.paid_amount > 0:
            invoice.status = InvoiceStatus.PARTIAL

        await self.db.commit()
        await self.db.refresh(invoice)
        return invoice


class HQVendorService:
    """Service for managing A/P vendors."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _generate_vendor_number(self) -> str:
        """Generate unique vendor number."""
        from app.models.hq_accounting import HQVendor
        result = await self.db.execute(select(func.count(HQVendor.id)))
        count = result.scalar() or 0
        return f"VEND-{str(count + 1).zfill(5)}"

    async def list_vendors(self, status: Optional[str] = None) -> list:
        """List all vendors."""
        from app.models.hq_accounting import HQVendor, VendorStatus
        query = select(HQVendor)
        if status:
            query = query.where(HQVendor.status == VendorStatus(status.upper()))
        query = query.order_by(HQVendor.name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_vendor(self, vendor_id: str):
        """Get vendor by ID."""
        from app.models.hq_accounting import HQVendor
        return await self.db.get(HQVendor, vendor_id)

    async def create_vendor(self, payload):
        """Create a new vendor."""
        from app.models.hq_accounting import HQVendor, VendorStatus, VendorType

        vendor_number = await self._generate_vendor_number()

        vendor = HQVendor(
            id=str(uuid.uuid4()),
            vendor_number=vendor_number,
            name=payload.name,
            vendor_type=VendorType(payload.vendor_type.upper()),
            status=VendorStatus.ACTIVE,
            email=payload.email,
            phone=payload.phone,
            address=payload.address,
            city=payload.city,
            state=payload.state,
            zip_code=payload.zip_code,
            country=payload.country,
            tax_id=payload.tax_id,
            payment_terms_days=payload.payment_terms_days,
            default_expense_account=payload.default_expense_account,
            bank_account_info=payload.bank_account_info,
            notes=payload.notes,
        )
        self.db.add(vendor)
        await self.db.commit()
        await self.db.refresh(vendor)
        return vendor

    async def update_vendor(self, vendor_id: str, payload):
        """Update a vendor."""
        from app.models.hq_accounting import HQVendor, VendorStatus, VendorType

        vendor = await self.db.get(HQVendor, vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")

        if payload.name is not None:
            vendor.name = payload.name
        if payload.vendor_type is not None:
            vendor.vendor_type = VendorType(payload.vendor_type.upper())
        if payload.status is not None:
            vendor.status = VendorStatus(payload.status.upper())
        if payload.email is not None:
            vendor.email = payload.email
        if payload.phone is not None:
            vendor.phone = payload.phone
        if payload.address is not None:
            vendor.address = payload.address
        if payload.city is not None:
            vendor.city = payload.city
        if payload.state is not None:
            vendor.state = payload.state
        if payload.zip_code is not None:
            vendor.zip_code = payload.zip_code
        if payload.payment_terms_days is not None:
            vendor.payment_terms_days = payload.payment_terms_days
        if payload.default_expense_account is not None:
            vendor.default_expense_account = payload.default_expense_account
        if payload.notes is not None:
            vendor.notes = payload.notes

        await self.db.commit()
        await self.db.refresh(vendor)
        return vendor


class HQBillService:
    """Service for managing A/P bills."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _generate_bill_number(self) -> str:
        """Generate unique bill number."""
        from app.models.hq_accounting import HQBill
        result = await self.db.execute(select(func.count(HQBill.id)))
        count = result.scalar() or 0
        return f"BILL-{datetime.utcnow().year}-{str(count + 1).zfill(5)}"

    async def list_bills(self, vendor_id: Optional[str] = None, status: Optional[str] = None) -> list:
        """List all bills."""
        from app.models.hq_accounting import HQBill, BillStatus
        query = select(HQBill)
        if vendor_id:
            query = query.where(HQBill.vendor_id == vendor_id)
        if status:
            query = query.where(HQBill.status == BillStatus(status.upper()))
        query = query.order_by(HQBill.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_bill(self, bill_id: str):
        """Get bill by ID."""
        from app.models.hq_accounting import HQBill
        return await self.db.get(HQBill, bill_id)

    async def create_bill(self, payload, created_by_id: str):
        """Create a new bill."""
        from app.models.hq_accounting import HQBill, BillStatus, BillType

        bill_number = await self._generate_bill_number()

        # Convert line items to dict
        line_items = [item.model_dump() for item in payload.line_items] if payload.line_items else []

        bill = HQBill(
            id=str(uuid.uuid4()),
            bill_number=bill_number,
            vendor_id=payload.vendor_id,
            vendor_invoice_number=payload.vendor_invoice_number,
            bill_type=BillType(payload.bill_type.upper()),
            status=BillStatus.DRAFT,
            description=payload.description,
            line_items=line_items,
            subtotal=payload.subtotal,
            tax_total=payload.tax_total,
            total=payload.total,
            balance_due=payload.total,
            bill_date=payload.bill_date,
            due_date=payload.due_date,
            notes=payload.notes,
            created_by_id=created_by_id,
        )
        self.db.add(bill)
        await self.db.commit()
        await self.db.refresh(bill)
        return bill

    async def approve_bill(self, bill_id: str, approved_by_id: str):
        """Approve a bill for payment."""
        from app.models.hq_accounting import HQBill, BillStatus

        bill = await self.db.get(HQBill, bill_id)
        if not bill:
            raise ValueError("Bill not found")
        if bill.status not in [BillStatus.DRAFT, BillStatus.PENDING_APPROVAL]:
            raise ValueError("Bill cannot be approved in current status")

        bill.status = BillStatus.APPROVED
        bill.approved_by_id = approved_by_id
        bill.approved_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(bill)
        return bill

    async def pay_bill(self, bill_id: str, amount: Decimal, recorded_by_id: str):
        """Record a payment for a bill."""
        from app.models.hq_accounting import HQBill, HQPayment, BillStatus, PaymentType, PaymentDirection

        bill = await self.db.get(HQBill, bill_id)
        if not bill:
            raise ValueError("Bill not found")

        # Generate payment number
        result = await self.db.execute(select(func.count(HQPayment.id)))
        count = result.scalar() or 0
        payment_number = f"PMT-{datetime.utcnow().year}-{str(count + 1).zfill(5)}"

        # Create payment record
        payment = HQPayment(
            id=str(uuid.uuid4()),
            payment_number=payment_number,
            bill_id=bill_id,
            payment_type=PaymentType.ACH,
            direction=PaymentDirection.OUTGOING,
            amount=amount,
            payment_date=datetime.utcnow(),
            recorded_by_id=recorded_by_id,
        )
        self.db.add(payment)

        # Update bill
        bill.paid_amount = (bill.paid_amount or Decimal("0")) + amount
        bill.balance_due = bill.total - bill.paid_amount

        if bill.balance_due <= 0:
            bill.status = BillStatus.PAID
            bill.paid_date = datetime.utcnow()
        elif bill.paid_amount > 0:
            bill.status = BillStatus.PARTIAL

        await self.db.commit()
        await self.db.refresh(bill)
        return bill


class HQAccountingDashboardService:
    """Service for accounting dashboard metrics."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_dashboard(self):
        """Get accounting dashboard metrics."""
        from app.models.hq_accounting import HQInvoice, HQBill, InvoiceStatus, BillStatus
        from app.schemas.hq import HQAccountingDashboard
        from datetime import timedelta

        now = datetime.utcnow()

        # A/R Metrics
        ar_result = await self.db.execute(
            select(
                func.coalesce(func.sum(HQInvoice.balance_due), 0),
            ).where(
                HQInvoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.VIEWED, InvoiceStatus.PARTIAL, InvoiceStatus.OVERDUE])
            )
        )
        total_outstanding_ar = Decimal(str(ar_result.scalar() or 0))

        # Count pending invoices
        pending_invoices_result = await self.db.execute(
            select(func.count(HQInvoice.id)).where(HQInvoice.status == InvoiceStatus.DRAFT)
        )
        pending_invoices_count = pending_invoices_result.scalar() or 0

        # Count overdue invoices
        overdue_invoices_result = await self.db.execute(
            select(func.count(HQInvoice.id)).where(HQInvoice.status == InvoiceStatus.OVERDUE)
        )
        overdue_invoices_count = overdue_invoices_result.scalar() or 0

        # A/P Metrics
        ap_result = await self.db.execute(
            select(
                func.coalesce(func.sum(HQBill.balance_due), 0),
            ).where(
                HQBill.status.in_([BillStatus.APPROVED, BillStatus.PARTIAL, BillStatus.OVERDUE])
            )
        )
        total_outstanding_ap = Decimal(str(ap_result.scalar() or 0))

        # Count pending bills
        pending_bills_result = await self.db.execute(
            select(func.count(HQBill.id)).where(HQBill.status.in_([BillStatus.DRAFT, BillStatus.PENDING_APPROVAL]))
        )
        pending_bills_count = pending_bills_result.scalar() or 0

        # Count overdue bills
        overdue_bills_result = await self.db.execute(
            select(func.count(HQBill.id)).where(HQBill.status == BillStatus.OVERDUE)
        )
        overdue_bills_count = overdue_bills_result.scalar() or 0

        return HQAccountingDashboard(
            total_outstanding_ar=total_outstanding_ar,
            ar_current=Decimal("0"),
            ar_30_days=Decimal("0"),
            ar_60_days=Decimal("0"),
            ar_90_plus_days=Decimal("0"),
            pending_invoices_count=pending_invoices_count,
            overdue_invoices_count=overdue_invoices_count,
            total_outstanding_ap=total_outstanding_ap,
            ap_current=Decimal("0"),
            ap_30_days=Decimal("0"),
            ap_60_days=Decimal("0"),
            ap_90_plus_days=Decimal("0"),
            pending_bills_count=pending_bills_count,
            overdue_bills_count=overdue_bills_count,
            expected_collections_30_days=Decimal("0"),
            expected_payments_30_days=Decimal("0"),
        )

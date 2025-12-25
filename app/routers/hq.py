"""HQ Admin Portal router."""

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.config import get_settings
from app.core.security import decode_access_token
from app.models.hq_employee import HQEmployee
from app.schemas.hq import (
    HQLoginRequest,
    HQTokenResponse,
    HQAuthSessionResponse,
    HQEmployeeCreate,
    HQEmployeeUpdate,
    HQEmployeeResponse,
    HQTenantCreate,
    HQTenantUpdate,
    HQTenantResponse,
    HQContractCreate,
    HQContractUpdate,
    HQContractResponse,
    HQQuoteCreate,
    HQQuoteUpdate,
    HQQuoteResponse,
    HQQuoteSend,
    HQCreditCreate,
    HQCreditReject,
    HQCreditResponse,
    HQPayoutCreate,
    HQPayoutResponse,
    HQSystemModuleUpdate,
    HQSystemModuleResponse,
    HQDashboardMetrics,
    HQBankingCompanyResponse,
    HQFraudAlertResponse,
    HQBankingAuditLogResponse,
    HQBankingOverviewStats,
    HQFraudAlertResolve,
    # General Ledger schemas
    HQChartOfAccountsCreate,
    HQChartOfAccountsUpdate,
    HQChartOfAccountsResponse,
    HQJournalEntryCreate,
    HQJournalEntryResponse,
    HQAccountBalance,
    HQProfitLossReport,
    HQBalanceSheetReport,
    HQTenantProfitMargin,
    HQAIUsageLogRequest,
    HQAICostsByTenant,
    HQGLDashboard,
    # CRM schemas
    HQLeadCreate,
    HQLeadUpdate,
    HQLeadResponse,
    HQLeadConvert,
    HQLeadImportRequest,
    HQLeadImportResponse,
    HQOpportunityCreate,
    HQOpportunityUpdate,
    HQOpportunityResponse,
    HQOpportunityConvert,
    HQPipelineSummary,
    HQSalesRepCommissionCreate,
    HQSalesRepCommissionUpdate,
    HQSalesRepCommissionResponse,
    HQCommissionRecordResponse,
    HQCommissionPaymentResponse,
    HQCommissionPaymentApprove,
    HQSalesRepEarnings,
    HQSalesRepAccountSummary,
)
from app.services.hq import (
    HQAuthService,
    HQEmployeeService,
    HQTenantService,
    HQContractService,
    HQQuoteService,
    HQCreditService,
    HQPayoutService,
    HQSystemModuleService,
    HQDashboardService,
    HQBankingService,
)

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

HQ_AUTH_COOKIE_NAME = "freightops_hq_token"

hq_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/hq/auth/login", auto_error=False)


# ============================================================================
# Authentication Dependencies
# ============================================================================

async def get_current_hq_employee(
    request: Request,
    token: Annotated[str | None, Depends(hq_oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> HQEmployee:
    """Get current authenticated HQ employee."""
    cookie_token = request.cookies.get(HQ_AUTH_COOKIE_NAME)
    credentials_token = cookie_token or token

    if not credentials_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(credentials_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Verify this is an HQ token
    if payload.get("type") != "hq":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    employee_id = payload.get("sub")
    if not employee_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    employee = await db.get(HQEmployee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Employee not found")
    if not employee.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    return employee


def require_hq_role(*allowed_roles: str):
    """
    Dependency that requires the HQ employee to have one of the specified roles.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(employee = Depends(require_hq_role("SUPER_ADMIN", "ADMIN"))):
            ...
    """
    from app.models.hq_employee import HQRole

    async def dependency(
        request: Request,
        token: Annotated[str | None, Depends(hq_oauth2_scheme)],
        db: AsyncSession = Depends(get_db),
    ) -> HQEmployee:
        employee = await get_current_hq_employee(request, token, db)

        # Convert role enum to string for comparison
        employee_role = employee.role.value if isinstance(employee.role, HQRole) else employee.role

        if employee_role not in allowed_roles:
            logger.warning(
                f"HQ Role denied: employee={employee.email}, role={employee_role}, required={allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}"
            )

        return employee

    return dependency


def require_hq_admin():
    """Shortcut for requiring SUPER_ADMIN or ADMIN role."""
    return require_hq_role("SUPER_ADMIN", "ADMIN")


def require_hq_super_admin():
    """Shortcut for requiring SUPER_ADMIN role only."""
    return require_hq_role("SUPER_ADMIN")


def require_hq_permission(*required_permissions: str):
    """
    Dependency that requires specific HQ permissions.

    Usage:
        @router.get("/gl/accounts")
        async def list_accounts(employee = Depends(require_hq_permission("view_gl"))):
            ...
    """
    from app.models.hq_employee import HQRole, HQPermission, has_hq_permission

    async def dependency(
        request: Request,
        token: Annotated[str | None, Depends(hq_oauth2_scheme)],
        db: AsyncSession = Depends(get_db),
    ) -> HQEmployee:
        employee = await get_current_hq_employee(request, token, db)

        # Check if employee has any of the required permissions
        for perm_str in required_permissions:
            try:
                permission = HQPermission(perm_str)
                if has_hq_permission(employee.role, permission):
                    return employee
            except ValueError:
                continue

        logger.warning(
            f"HQ Permission denied: employee={employee.email}, role={employee.role.value}, required={required_permissions}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )

    return dependency


def set_hq_auth_cookie(response: Response, token: str) -> None:
    """Set HQ authentication cookie with secure settings."""
    response.set_cookie(
        key=HQ_AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.environment != "development",  # HTTPS only in production
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
        domain=None,
    )


def clear_hq_auth_cookie(response: Response) -> None:
    """Clear HQ authentication cookie."""
    response.delete_cookie(HQ_AUTH_COOKIE_NAME, path="/")


# ============================================================================
# Auth Endpoints
# ============================================================================

@router.post("/auth/login", response_model=HQAuthSessionResponse)
async def hq_login(
    payload: HQLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> HQAuthSessionResponse:
    """Login to HQ admin portal with email, employee number, and password."""
    service = HQAuthService(db)
    try:
        employee, token = await service.authenticate(payload)
        set_hq_auth_cookie(response, token)
        return await service.build_session(employee, token=token)
    except ValueError as exc:
        logger.warning(f"HQ login failed: {str(exc)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.get("/auth/session", response_model=HQAuthSessionResponse)
async def hq_session(
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQAuthSessionResponse:
    """Get current HQ session."""
    service = HQAuthService(db)
    return await service.build_session(current_employee)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def hq_logout(response: Response) -> None:
    """Logout from HQ admin portal."""
    clear_hq_auth_cookie(response)


# ============================================================================
# Dashboard Endpoints
# ============================================================================

@router.get("/dashboard/metrics", response_model=HQDashboardMetrics)
async def get_dashboard_metrics(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQDashboardMetrics:
    """Get HQ dashboard metrics."""
    service = HQDashboardService(db)
    return await service.get_metrics()


@router.get("/dashboard/recent-tenants", response_model=List[HQTenantResponse])
async def get_recent_tenants(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQTenantResponse]:
    """Get recently created tenants."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.company import Company

    result = await db.execute(
        select(Company)
        .options(
            selectinload(Company.users),
            selectinload(Company.subscription),
        )
        .order_by(Company.createdAt.desc())
        .limit(5)
    )
    companies = result.scalars().all()
    return [_build_tenant_response_from_company(c) for c in companies]


@router.get("/dashboard/expiring-contracts", response_model=List[HQContractResponse])
async def get_expiring_contracts(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQContractResponse]:
    """Get contracts expiring within 30 days."""
    from sqlalchemy import select, and_
    from sqlalchemy.orm import selectinload
    from datetime import datetime, timedelta
    from app.models.hq_contract import HQContract, ContractStatus
    from app.models.hq_tenant import HQTenant

    thirty_days = datetime.utcnow() + timedelta(days=30)
    result = await db.execute(
        select(HQContract)
        .options(selectinload(HQContract.tenant).selectinload(HQTenant.company))
        .where(
            and_(
                HQContract.status == ContractStatus.ACTIVE,
                HQContract.end_date <= thirty_days
            )
        )
        .order_by(HQContract.end_date.asc())
        .limit(5)
    )
    contracts = result.scalars().all()

    responses = []
    for c in contracts:
        data = {
            "id": c.id,
            "tenant_id": c.tenant_id,
            "tenant_name": c.tenant.company.name if c.tenant and c.tenant.company else None,
            "contract_number": c.contract_number,
            "title": c.title,
            "contract_type": c.contract_type.value if hasattr(c.contract_type, 'value') else c.contract_type,
            "status": c.status.value if hasattr(c.status, 'value') else c.status,
            "description": c.description,
            "monthly_value": c.monthly_value,
            "annual_value": c.annual_value,
            "setup_fee": c.setup_fee or 0,
            "start_date": c.start_date,
            "end_date": c.end_date,
            "auto_renew": c.auto_renew or "false",
            "notice_period_days": c.notice_period_days or "30",
            "custom_terms": c.custom_terms,
            "signed_by_customer": c.signed_by_customer,
            "signed_by_hq": c.signed_by_hq,
            "signed_at": c.signed_at,
            "created_by_id": c.created_by_id,
            "approved_by_id": c.approved_by_id,
            "approved_at": c.approved_at,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
        responses.append(HQContractResponse.model_validate(data))
    return responses


# ============================================================================
# Employee Endpoints
# ============================================================================

@router.get("/employees", response_model=List[HQEmployeeResponse])
async def list_employees(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQEmployeeResponse]:
    """List all HQ employees."""
    service = HQEmployeeService(db)
    employees = await service.list_employees()
    return [HQEmployeeResponse.model_validate(e, from_attributes=True) for e in employees]


@router.post("/employees", response_model=HQEmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: HQEmployeeCreate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQEmployeeResponse:
    """Create a new HQ employee."""
    service = HQEmployeeService(db)
    try:
        employee = await service.create_employee(payload)
        return HQEmployeeResponse.model_validate(employee, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/employees/{employee_id}", response_model=HQEmployeeResponse)
async def get_employee(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQEmployeeResponse:
    """Get HQ employee by ID."""
    service = HQEmployeeService(db)
    employee = await service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return HQEmployeeResponse.model_validate(employee, from_attributes=True)


@router.patch("/employees/{employee_id}", response_model=HQEmployeeResponse)
async def update_employee(
    employee_id: str,
    payload: HQEmployeeUpdate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQEmployeeResponse:
    """Update an HQ employee."""
    service = HQEmployeeService(db)
    try:
        employee = await service.update_employee(employee_id, payload)
        return HQEmployeeResponse.model_validate(employee, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_employee(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete an HQ employee."""
    service = HQEmployeeService(db)
    try:
        await service.delete_employee(employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ============================================================================
# Tenant Endpoints - Query Company table directly
# ============================================================================

def _build_tenant_response_from_company(company) -> HQTenantResponse:
    """Build HQTenantResponse directly from Company model."""
    from app.schemas.hq import AddressResponse
    users = company.users if hasattr(company, 'users') and company.users else []
    total_users = len(users)
    active_users = sum(1 for u in users if getattr(u, "is_active", True))

    # Build address if company has address fields
    address = None
    if company.address_line1 or company.city:
        address = AddressResponse(
            street=company.address_line1,
            city=company.city,
            state=company.state,
            zip=company.zip_code,
        )

    # Map subscription plan to tier
    plan_to_tier = {"free": "starter", "starter": "starter", "pro": "professional", "enterprise": "enterprise"}
    tier = plan_to_tier.get(company.subscriptionPlan, "professional")

    # Status based on isActive
    status = "active" if company.isActive else "suspended"

    # Get Stripe data from subscription relationship
    subscription = getattr(company, 'subscription', None)
    stripe_customer_id = None
    stripe_subscription_id = None
    monthly_fee = 0
    subscription_end_date = None

    if subscription:
        stripe_customer_id = subscription.stripe_customer_id
        stripe_subscription_id = subscription.stripe_subscription_id
        monthly_fee = float(subscription.total_monthly_cost) if subscription.total_monthly_cost else 0
        subscription_end_date = subscription.current_period_end

    return HQTenantResponse(
        id=company.id,
        company_name=company.name,
        legal_name=company.legal_name,
        tax_id=company.tax_id,
        dot_number=company.dotNumber,
        mc_number=company.mcNumber,
        status=status,
        subscription_tier=tier,
        subscription_start_date=company.createdAt,
        subscription_end_date=subscription_end_date,
        monthly_fee=monthly_fee,
        setup_fee=0,
        primary_contact_name=company.primaryContactName,
        primary_contact_email=company.email,
        primary_contact_phone=company.phone,
        billing_email=company.email,
        address=address,
        total_users=total_users,
        active_users=active_users,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        notes=company.description,
        created_at=company.createdAt,
        updated_at=company.updatedAt,
    )


@router.get("/tenants", response_model=List[HQTenantResponse])
async def list_tenants(
    status_filter: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQTenantResponse]:
    """List all tenants (companies) directly."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.company import Company

    query = select(Company).options(
        selectinload(Company.users),
        selectinload(Company.subscription),  # Load Stripe subscription data
    )

    # Filter by status (active/suspended based on isActive)
    if status_filter:
        if status_filter == "active":
            query = query.where(Company.isActive == True)
        elif status_filter == "suspended":
            query = query.where(Company.isActive == False)

    query = query.order_by(Company.createdAt.desc())
    result = await db.execute(query)
    companies = result.scalars().all()

    return [_build_tenant_response_from_company(c) for c in companies]


@router.post("/tenants", response_model=HQTenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: HQTenantCreate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQTenantResponse:
    """Create a new tenant (company) from HQ."""
    import uuid
    from app.models.company import Company

    # Check for existing DOT/MC
    if payload.dot_number:
        from sqlalchemy import select
        result = await db.execute(select(Company).where(Company.dotNumber == payload.dot_number))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Company with DOT {payload.dot_number} already exists")

    if payload.mc_number:
        from sqlalchemy import select
        result = await db.execute(select(Company).where(Company.mcNumber == payload.mc_number))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Company with MC {payload.mc_number} already exists")

    # Map tier to subscription plan
    tier_to_plan = {"starter": "starter", "professional": "pro", "enterprise": "enterprise", "custom": "enterprise"}
    plan = tier_to_plan.get(payload.subscription_tier, "pro")

    company = Company(
        id=str(uuid.uuid4()),
        name=payload.company_name,
        legal_name=payload.legal_name,
        email=payload.primary_contact_email or f"{payload.company_name.lower().replace(' ', '')}@placeholder.fops.io",
        phone=payload.primary_contact_phone,
        dotNumber=payload.dot_number,
        mcNumber=payload.mc_number,
        tax_id=payload.tax_id,
        primaryContactName=payload.primary_contact_name,
        subscriptionPlan=plan,
        isActive=True,
        description=payload.notes,
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)

    return _build_tenant_response_from_company(company)


@router.get("/tenants/{tenant_id}", response_model=HQTenantResponse)
async def get_tenant(
    tenant_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQTenantResponse:
    """Get tenant (company) by ID."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.company import Company

    result = await db.execute(
        select(Company).options(selectinload(Company.users)).where(Company.id == tenant_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return _build_tenant_response_from_company(company)


@router.get("/tenants/{tenant_id}/detail")
async def get_tenant_detail(
    tenant_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed tenant profile with fleet, dispatch, and usage metrics."""
    from decimal import Decimal
    from sqlalchemy import select, func, Integer
    from sqlalchemy.orm import selectinload
    from app.models.company import Company
    from app.schemas.hq import (
        HQTenantDetailResponse,
        TenantFleetMetrics,
        TenantDispatchMetrics,
        TenantUsageMetrics,
        TenantCostBreakdown,
        AddressResponse,
    )

    # Get company with users
    result = await db.execute(
        select(Company).options(selectinload(Company.users)).where(Company.id == tenant_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Fleet metrics
    fleet = TenantFleetMetrics()
    try:
        from app.models.equipment import Equipment
        from app.models.driver import Driver

        # Equipment counts
        eq_result = await db.execute(
            select(
                func.count(Equipment.id).label("total"),
                func.sum(func.cast(Equipment.status == "ACTIVE", Integer)).label("active")
            ).where(Equipment.company_id == tenant_id)
        )
        eq_row = eq_result.first()
        if eq_row:
            fleet.total_trucks = eq_row.total or 0
            fleet.active_trucks = eq_row.active or 0

        # Could separate by equipment_type for tractors vs trailers
        # For now, using same count

        # Driver counts
        dr_result = await db.execute(
            select(func.count(Driver.id)).where(Driver.company_id == tenant_id)
        )
        fleet.total_drivers = dr_result.scalar() or 0
        fleet.active_drivers = fleet.total_drivers  # Assume all active for now
    except Exception:
        pass  # Models may not exist

    # Dispatch metrics
    dispatch = TenantDispatchMetrics()
    try:
        from app.models.load import Load

        load_result = await db.execute(
            select(
                func.count(Load.id).label("total"),
                func.sum(func.cast(Load.status == "delivered", Integer)).label("completed"),
                func.sum(func.cast(Load.status == "in_transit", Integer)).label("in_transit"),
                func.sum(func.cast(Load.status.in_(["draft", "assigned"]), Integer)).label("pending"),
                func.coalesce(func.sum(Load.base_rate), 0).label("revenue")
            ).where(Load.company_id == tenant_id)
        )
        load_row = load_result.first()
        if load_row:
            dispatch.total_loads = load_row.total or 0
            dispatch.completed_loads = load_row.completed or 0
            dispatch.in_transit_loads = load_row.in_transit or 0
            dispatch.pending_loads = load_row.pending or 0
            dispatch.total_revenue = Decimal(str(load_row.revenue or 0))
            if dispatch.total_loads > 0:
                dispatch.avg_load_value = dispatch.total_revenue / dispatch.total_loads
    except Exception:
        pass  # Models may not exist

    # Usage metrics (API calls)
    usage = TenantUsageMetrics()
    try:
        from app.models.ai_usage import AIUsageLog

        usage_result = await db.execute(
            select(
                func.count(AIUsageLog.id).label("total"),
                func.sum(func.cast(AIUsageLog.operation_type == "ocr", Integer)).label("ocr"),
                func.sum(func.cast(AIUsageLog.operation_type == "chat", Integer)).label("chat"),
                func.sum(func.cast(AIUsageLog.operation_type == "audit", Integer)).label("audit"),
                func.coalesce(func.sum(AIUsageLog.tokens_used), 0).label("tokens"),
                func.coalesce(func.sum(AIUsageLog.cost_usd), 0).label("cost")
            ).where(AIUsageLog.company_id == tenant_id)
        )
        usage_row = usage_result.first()
        if usage_row:
            usage.total_api_calls = usage_row.total or 0
            usage.ocr_calls = usage_row.ocr or 0
            usage.chat_calls = usage_row.chat or 0
            usage.audit_calls = usage_row.audit or 0
            usage.tokens_used = usage_row.tokens or 0
            usage.estimated_cost = Decimal(str(usage_row.cost or 0))
    except Exception:
        pass  # Models may not exist

    # Cost breakdown calculation
    # Pricing: Base $299/mo + $10/truck + $5/driver + API usage
    base_sub = Decimal("299")
    truck_rate = Decimal("10")
    driver_rate = Decimal("5")

    cost = TenantCostBreakdown(
        base_subscription=base_sub,
        per_truck_cost=truck_rate * fleet.total_trucks,
        per_driver_cost=driver_rate * fleet.total_drivers,
        api_usage_cost=usage.estimated_cost,
        total_monthly_cost=base_sub + (truck_rate * fleet.total_trucks) + (driver_rate * fleet.total_drivers) + usage.estimated_cost
    )

    # Build base tenant response
    users = company.users if hasattr(company, 'users') and company.users else []
    total_users = len(users)
    active_users = sum(1 for u in users if getattr(u, "is_active", True))

    address = None
    if company.address_line1 or company.city:
        address = AddressResponse(
            street=company.address_line1,
            city=company.city,
            state=company.state,
            zip=company.zip_code,
        )

    plan_to_tier = {"free": "starter", "starter": "starter", "pro": "professional", "enterprise": "enterprise"}
    tier = plan_to_tier.get(company.subscriptionPlan, "professional")
    status_val = "active" if company.isActive else "suspended"

    return HQTenantDetailResponse(
        id=company.id,
        company_name=company.name,
        legal_name=company.legal_name,
        tax_id=company.tax_id,
        dot_number=company.dotNumber,
        mc_number=company.mcNumber,
        status=status_val,
        subscription_tier=tier,
        subscription_start_date=company.createdAt,
        subscription_end_date=None,
        monthly_fee=cost.total_monthly_cost,
        setup_fee=Decimal("0"),
        primary_contact_name=company.primaryContactName,
        primary_contact_email=company.email,
        primary_contact_phone=company.phone,
        billing_email=company.email,
        address=address,
        total_users=total_users,
        active_users=active_users,
        stripe_customer_id=None,
        stripe_subscription_id=None,
        notes=company.description,
        created_at=company.createdAt,
        updated_at=company.updatedAt,
        fleet=fleet,
        dispatch=dispatch,
        usage=usage,
        cost_breakdown=cost,
    )


@router.patch("/tenants/{tenant_id}", response_model=HQTenantResponse)
async def update_tenant(
    tenant_id: str,
    payload: HQTenantUpdate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQTenantResponse:
    """Update a tenant (company)."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.company import Company

    result = await db.execute(
        select(Company).options(selectinload(Company.users)).where(Company.id == tenant_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Update fields if provided
    if payload.subscription_tier:
        tier_to_plan = {"starter": "starter", "professional": "pro", "enterprise": "enterprise", "custom": "enterprise"}
        company.subscriptionPlan = tier_to_plan.get(payload.subscription_tier, "pro")
    if payload.billing_email:
        company.email = payload.billing_email
    if payload.notes is not None:
        company.description = payload.notes
    if payload.status:
        company.isActive = payload.status in ("active", "trial")

    await db.commit()
    await db.refresh(company)
    return _build_tenant_response_from_company(company)


@router.post("/tenants/{tenant_id}/suspend", response_model=HQTenantResponse)
async def suspend_tenant(
    tenant_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQTenantResponse:
    """Suspend a tenant (set company.isActive = False)."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.company import Company

    result = await db.execute(
        select(Company).options(selectinload(Company.users)).where(Company.id == tenant_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    company.isActive = False
    await db.commit()
    await db.refresh(company)
    return _build_tenant_response_from_company(company)


@router.post("/tenants/{tenant_id}/activate", response_model=HQTenantResponse)
async def activate_tenant(
    tenant_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQTenantResponse:
    """Activate a tenant (set company.isActive = True)."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.company import Company

    result = await db.execute(
        select(Company).options(selectinload(Company.users)).where(Company.id == tenant_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    company.isActive = True
    await db.commit()
    await db.refresh(company)
    return _build_tenant_response_from_company(company)


@router.post("/tenants/{tenant_id}/deactivate", response_model=HQTenantResponse)
async def deactivate_tenant(
    tenant_id: str,
    _: HQEmployee = Depends(require_hq_admin()),
    db: AsyncSession = Depends(get_db)
) -> HQTenantResponse:
    """Permanently deactivate a tenant (set status to churned). Requires admin role."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.company import Company

    result = await db.execute(
        select(Company).options(selectinload(Company.users)).where(Company.id == tenant_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    company.isActive = False
    # Set subscription end date to now
    from datetime import datetime
    company.subscription_end_date = datetime.utcnow()
    await db.commit()
    await db.refresh(company)
    return _build_tenant_response_from_company(company)


@router.get("/tenants/{tenant_id}/payments")
async def get_tenant_payments(
    tenant_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> list:
    """Get payment history for a tenant from Stripe invoices."""
    from sqlalchemy import select, desc
    from app.models.company import Company

    # First verify tenant exists
    result = await db.execute(select(Company).where(Company.id == tenant_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Get payments from Stripe invoices
    try:
        from app.models.billing import StripeInvoice
        result = await db.execute(
            select(StripeInvoice)
            .where(StripeInvoice.company_id == tenant_id)
            .order_by(desc(StripeInvoice.invoice_created_at))
        )
        invoices = result.scalars().all()
        return [
            {
                "id": str(inv.id),
                "tenantId": tenant_id,
                "type": "subscription",
                "amount": float(inv.amount_paid) if inv.amount_paid else float(inv.amount_due),
                "description": f"Invoice #{inv.invoice_number}" if inv.invoice_number else "Subscription Payment",
                "stripePaymentIntentId": inv.stripe_invoice_id,
                "status": inv.status,
                "createdAt": inv.invoice_created_at.isoformat() if inv.invoice_created_at else None,
            }
            for inv in invoices
        ]
    except ImportError:
        # Billing model doesn't exist, return empty
        return []


@router.get("/tenants/{tenant_id}/credits")
async def get_tenant_credits(
    tenant_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> list:
    """Get credits for a tenant."""
    from sqlalchemy import select, desc
    from app.models.company import Company

    # First verify tenant exists
    result = await db.execute(select(Company).where(Company.id == tenant_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Get credits from HQ credit service
    service = HQCreditService(db)
    credits = await service.list_credits(tenant_id=tenant_id)
    return [HQCreditResponse.model_validate(c, from_attributes=True) for c in credits]


@router.post("/tenants/{tenant_id}/credits", response_model=HQCreditResponse, status_code=status.HTTP_201_CREATED)
async def add_tenant_credit(
    tenant_id: str,
    payload: HQCreditCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQCreditResponse:
    """Add a credit to a tenant's account."""
    from sqlalchemy import select
    from app.models.company import Company

    # Verify tenant exists
    result = await db.execute(select(Company).where(Company.id == tenant_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Ensure tenant_id is set in payload
    payload_dict = payload.model_dump()
    payload_dict["tenant_id"] = tenant_id

    service = HQCreditService(db)
    credit = await service.create_credit(HQCreditCreate(**payload_dict), current_employee.id)
    return HQCreditResponse.model_validate(credit, from_attributes=True)


@router.get("/tenants/{tenant_id}/addons")
async def get_tenant_addons(
    tenant_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> list:
    """Get add-ons enabled for a tenant."""
    from sqlalchemy import select
    from app.models.company import Company

    # First verify tenant exists
    result = await db.execute(select(Company).where(Company.id == tenant_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Try to get add-ons from company integrations or company settings
    try:
        from app.models.integration import CompanyIntegration, Integration
        from sqlalchemy.orm import selectinload

        # Get integrations for this company that represent add-ons
        addon_keys = ["payroll", "port", "banking", "fuel_cards"]
        result = await db.execute(
            select(CompanyIntegration)
            .options(selectinload(CompanyIntegration.integration))
            .where(CompanyIntegration.company_id == tenant_id)
        )
        integrations = result.scalars().all()

        addons = []
        addon_config = {
            "payroll": {"name": "Payroll Integration", "description": "Enable Check HQ payroll processing", "monthlyFee": 99},
            "container_tracking": {"name": "Container Tracking", "description": "Enable container tracking and visibility for drayage operations", "monthlyFee": 149},
        }

        for key, config in addon_config.items():
            # Check if this integration exists and is active
            matching = [i for i in integrations if i.integration and i.integration.integration_key == key]
            enabled = any(i.status == "active" for i in matching)
            addons.append({
                "key": key,
                "name": config["name"],
                "description": config["description"],
                "enabled": enabled,
                "monthlyFee": config["monthlyFee"],
            })

        return addons
    except ImportError:
        # Return default disabled add-ons
        return [
            {"key": "payroll", "name": "Payroll Integration", "description": "Enable Check HQ payroll processing", "enabled": False, "monthlyFee": 99},
            {"key": "container_tracking", "name": "Container Tracking", "description": "Enable container tracking and visibility for drayage operations", "enabled": False, "monthlyFee": 149},
        ]


@router.patch("/tenants/{tenant_id}/addons/{addon_key}")
async def toggle_tenant_addon(
    tenant_id: str,
    addon_key: str,
    payload: dict,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Enable or disable an add-on for a tenant."""
    from sqlalchemy import select
    from app.models.company import Company

    # Verify tenant exists
    result = await db.execute(select(Company).where(Company.id == tenant_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    enabled = payload.get("enabled", False)

    try:
        from app.models.integration import CompanyIntegration, Integration
        from sqlalchemy.orm import selectinload

        # Find the integration by key
        result = await db.execute(
            select(Integration).where(Integration.integration_key == addon_key)
        )
        integration = result.scalar_one_or_none()

        if not integration:
            # Create the integration if it doesn't exist
            integration = Integration(
                integration_key=addon_key,
                name=addon_key.replace("_", " ").title(),
                integration_type="addon",
                is_active=True,
            )
            db.add(integration)
            await db.flush()

        # Find or create company integration
        result = await db.execute(
            select(CompanyIntegration)
            .where(
                CompanyIntegration.company_id == tenant_id,
                CompanyIntegration.integration_id == integration.id
            )
        )
        company_integration = result.scalar_one_or_none()

        if company_integration:
            company_integration.status = "active" if enabled else "inactive"
        else:
            company_integration = CompanyIntegration(
                company_id=tenant_id,
                integration_id=integration.id,
                status="active" if enabled else "inactive",
            )
            db.add(company_integration)

        await db.commit()

        return {"key": addon_key, "enabled": enabled}

    except ImportError as e:
        logger.error(f"Failed to toggle addon: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Add-on management not available")


# ============================================================================
# Contract Endpoints
# ============================================================================

@router.get("/contracts", response_model=List[HQContractResponse])
async def list_contracts(
    tenant_id: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQContractResponse]:
    """List all contracts."""
    service = HQContractService(db)
    contracts = await service.list_contracts(tenant_id=tenant_id)
    return [HQContractResponse.model_validate(c, from_attributes=True) for c in contracts]


@router.post("/contracts", response_model=HQContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    payload: HQContractCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQContractResponse:
    """Create a new contract."""
    service = HQContractService(db)
    contract = await service.create_contract(payload, current_employee.id)
    return HQContractResponse.model_validate(contract, from_attributes=True)


@router.get("/contracts/{contract_id}", response_model=HQContractResponse)
async def get_contract(
    contract_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQContractResponse:
    """Get contract by ID."""
    service = HQContractService(db)
    contract = await service.get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
    return HQContractResponse.model_validate(contract, from_attributes=True)


@router.patch("/contracts/{contract_id}", response_model=HQContractResponse)
async def update_contract(
    contract_id: str,
    payload: HQContractUpdate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQContractResponse:
    """Update a contract."""
    service = HQContractService(db)
    try:
        contract = await service.update_contract(contract_id, payload)
        return HQContractResponse.model_validate(contract, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/contracts/{contract_id}/approve", response_model=HQContractResponse)
async def approve_contract(
    contract_id: str,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQContractResponse:
    """Approve a contract."""
    service = HQContractService(db)
    try:
        contract = await service.approve_contract(contract_id, current_employee.id)
        return HQContractResponse.model_validate(contract, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ============================================================================
# Quote Endpoints
# ============================================================================

@router.get("/quotes", response_model=List[HQQuoteResponse])
async def list_quotes(
    tenant_id: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQQuoteResponse]:
    """List all quotes."""
    service = HQQuoteService(db)
    quotes = await service.list_quotes(tenant_id=tenant_id)
    return [HQQuoteResponse.model_validate(q, from_attributes=True) for q in quotes]


@router.post("/quotes", response_model=HQQuoteResponse, status_code=status.HTTP_201_CREATED)
async def create_quote(
    payload: HQQuoteCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQQuoteResponse:
    """Create a new quote."""
    service = HQQuoteService(db)
    quote = await service.create_quote(payload, current_employee.id)
    return HQQuoteResponse.model_validate(quote, from_attributes=True)


@router.get("/quotes/{quote_id}", response_model=HQQuoteResponse)
async def get_quote(
    quote_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQQuoteResponse:
    """Get quote by ID."""
    service = HQQuoteService(db)
    quote = await service.get_quote(quote_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found")
    return HQQuoteResponse.model_validate(quote, from_attributes=True)


@router.patch("/quotes/{quote_id}", response_model=HQQuoteResponse)
async def update_quote(
    quote_id: str,
    payload: HQQuoteUpdate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQQuoteResponse:
    """Update a quote."""
    service = HQQuoteService(db)
    try:
        quote = await service.update_quote(quote_id, payload)
        return HQQuoteResponse.model_validate(quote, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/quotes/{quote_id}/send", response_model=HQQuoteResponse)
async def send_quote(
    quote_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQQuoteResponse:
    """Send a quote to customer."""
    service = HQQuoteService(db)
    try:
        quote = await service.send_quote(quote_id)
        return HQQuoteResponse.model_validate(quote, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ============================================================================
# Credit Endpoints
# ============================================================================

@router.get("/credits", response_model=List[HQCreditResponse])
async def list_credits(
    tenant_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQCreditResponse]:
    """List all credits."""
    service = HQCreditService(db)
    credits = await service.list_credits(tenant_id=tenant_id, status=status_filter)
    return [HQCreditResponse.model_validate(c, from_attributes=True) for c in credits]


@router.post("/credits", response_model=HQCreditResponse, status_code=status.HTTP_201_CREATED)
async def create_credit(
    payload: HQCreditCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQCreditResponse:
    """Create a new credit request."""
    service = HQCreditService(db)
    credit = await service.create_credit(payload, current_employee.id)
    return HQCreditResponse.model_validate(credit, from_attributes=True)


@router.get("/credits/{credit_id}", response_model=HQCreditResponse)
async def get_credit(
    credit_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQCreditResponse:
    """Get credit by ID."""
    service = HQCreditService(db)
    credit = await service.get_credit(credit_id)
    if not credit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credit not found")
    return HQCreditResponse.model_validate(credit, from_attributes=True)


@router.post("/credits/{credit_id}/approve", response_model=HQCreditResponse)
async def approve_credit(
    credit_id: str,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQCreditResponse:
    """Approve a credit."""
    service = HQCreditService(db)
    try:
        credit = await service.approve_credit(credit_id, current_employee.id)
        return HQCreditResponse.model_validate(credit, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/credits/{credit_id}/reject", response_model=HQCreditResponse)
async def reject_credit(
    credit_id: str,
    payload: HQCreditReject,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQCreditResponse:
    """Reject a credit."""
    service = HQCreditService(db)
    try:
        credit = await service.reject_credit(credit_id, current_employee.id, payload)
        return HQCreditResponse.model_validate(credit, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/credits/{credit_id}/apply", response_model=HQCreditResponse)
async def apply_credit(
    credit_id: str,
    invoice_id: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQCreditResponse:
    """Apply a credit."""
    service = HQCreditService(db)
    try:
        credit = await service.apply_credit(credit_id, invoice_id)
        return HQCreditResponse.model_validate(credit, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ============================================================================
# Payout Endpoints
# ============================================================================

@router.get("/payouts", response_model=List[HQPayoutResponse])
async def list_payouts(
    tenant_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQPayoutResponse]:
    """List all payouts."""
    service = HQPayoutService(db)
    payouts = await service.list_payouts(tenant_id=tenant_id, status=status_filter)
    return [HQPayoutResponse.model_validate(p, from_attributes=True) for p in payouts]


@router.post("/payouts", response_model=HQPayoutResponse, status_code=status.HTTP_201_CREATED)
async def create_payout(
    payload: HQPayoutCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQPayoutResponse:
    """Create a new payout."""
    service = HQPayoutService(db)
    payout = await service.create_payout(payload, current_employee.id)
    return HQPayoutResponse.model_validate(payout, from_attributes=True)


@router.get("/payouts/{payout_id}", response_model=HQPayoutResponse)
async def get_payout(
    payout_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQPayoutResponse:
    """Get payout by ID."""
    service = HQPayoutService(db)
    payout = await service.get_payout(payout_id)
    if not payout:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payout not found")
    return HQPayoutResponse.model_validate(payout, from_attributes=True)


@router.post("/payouts/{payout_id}/cancel", response_model=HQPayoutResponse)
async def cancel_payout(
    payout_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQPayoutResponse:
    """Cancel a pending payout."""
    service = HQPayoutService(db)
    try:
        payout = await service.cancel_payout(payout_id)
        return HQPayoutResponse.model_validate(payout, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ============================================================================
# System Module Endpoints
# ============================================================================

@router.get("/system/modules", response_model=List[HQSystemModuleResponse])
async def list_modules(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQSystemModuleResponse]:
    """List all system modules."""
    service = HQSystemModuleService(db)
    modules = await service.list_modules()
    return [HQSystemModuleResponse.model_validate(m, from_attributes=True) for m in modules]


@router.patch("/system/modules/{module_key}", response_model=HQSystemModuleResponse)
async def update_module(
    module_key: str,
    payload: HQSystemModuleUpdate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQSystemModuleResponse:
    """Update a system module."""
    service = HQSystemModuleService(db)
    try:
        module = await service.update_module(module_key, payload, current_employee.id)
        return HQSystemModuleResponse.model_validate(module, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/system/modules/{module_key}/maintenance", response_model=HQSystemModuleResponse)
async def set_module_maintenance(
    module_key: str,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQSystemModuleResponse:
    """Put a module in maintenance mode."""
    service = HQSystemModuleService(db)
    try:
        module = await service.set_maintenance(module_key, current_employee.id)
        return HQSystemModuleResponse.model_validate(module, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/system/modules/{module_key}/activate", response_model=HQSystemModuleResponse)
async def activate_module(
    module_key: str,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQSystemModuleResponse:
    """Activate a module."""
    service = HQSystemModuleService(db)
    try:
        module = await service.activate_module(module_key, current_employee.id)
        return HQSystemModuleResponse.model_validate(module, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ============================================================================
# Banking Admin Endpoints (Synctera Integration)
# ============================================================================

@router.get("/banking/stats", response_model=HQBankingOverviewStats)
async def get_banking_stats(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQBankingOverviewStats:
    """Get banking overview statistics for HQ dashboard."""
    service = HQBankingService(db)
    return await service.get_overview_stats()


@router.get("/banking/companies", response_model=List[HQBankingCompanyResponse])
async def list_banking_companies(
    status_filter: Optional[str] = None,
    kyb_status: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQBankingCompanyResponse]:
    """List all companies with banking status."""
    service = HQBankingService(db)
    return await service.list_companies(status=status_filter, kyb_status=kyb_status)


@router.get("/banking/companies/{company_id}", response_model=HQBankingCompanyResponse)
async def get_banking_company(
    company_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQBankingCompanyResponse:
    """Get company banking details."""
    service = HQBankingService(db)
    companies = await service.list_companies()
    for company in companies:
        if company.id == company_id:
            return company
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")


@router.post("/banking/companies/{company_id}/freeze", response_model=HQBankingCompanyResponse)
async def freeze_company_banking(
    company_id: str,
    request: Request,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQBankingCompanyResponse:
    """Freeze a company's banking access."""
    service = HQBankingService(db)
    try:
        ip_address = request.client.host if request.client else None
        return await service.freeze_company(company_id, current_employee.id, ip_address)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/banking/companies/{company_id}/unfreeze", response_model=HQBankingCompanyResponse)
async def unfreeze_company_banking(
    company_id: str,
    request: Request,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQBankingCompanyResponse:
    """Unfreeze a company's banking access."""
    service = HQBankingService(db)
    try:
        ip_address = request.client.host if request.client else None
        return await service.unfreeze_company(company_id, current_employee.id, ip_address)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/banking/fraud-alerts", response_model=List[HQFraudAlertResponse])
async def list_fraud_alerts(
    status_filter: Optional[str] = None,
    severity: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQFraudAlertResponse]:
    """List fraud alerts from Synctera."""
    service = HQBankingService(db)
    return await service.list_fraud_alerts(status=status_filter, severity=severity)


@router.get("/banking/fraud-alerts/{alert_id}", response_model=HQFraudAlertResponse)
async def get_fraud_alert(
    alert_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQFraudAlertResponse:
    """Get fraud alert details."""
    service = HQBankingService(db)
    alerts = await service.list_fraud_alerts()
    for alert in alerts:
        if alert.id == alert_id:
            return alert
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud alert not found")


@router.post("/banking/fraud-alerts/{alert_id}/approve", response_model=HQFraudAlertResponse)
async def approve_fraud_alert(
    alert_id: str,
    payload: Optional[HQFraudAlertResolve] = None,
    request: Request = None,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQFraudAlertResponse:
    """Approve a fraud alert (allow transaction)."""
    service = HQBankingService(db)
    try:
        ip_address = request.client.host if request and request.client else None
        notes = payload.resolution_notes if payload else None
        return await service.approve_fraud_alert(alert_id, current_employee.id, ip_address, notes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/banking/fraud-alerts/{alert_id}/block", response_model=HQFraudAlertResponse)
async def block_fraud_alert(
    alert_id: str,
    payload: Optional[HQFraudAlertResolve] = None,
    request: Request = None,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQFraudAlertResponse:
    """Block a fraud alert (reject transaction)."""
    service = HQBankingService(db)
    try:
        ip_address = request.client.host if request and request.client else None
        notes = payload.resolution_notes if payload else None
        return await service.block_fraud_alert(alert_id, current_employee.id, ip_address, notes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/banking/audit-logs", response_model=List[HQBankingAuditLogResponse])
async def list_banking_audit_logs(
    company_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQBankingAuditLogResponse]:
    """List banking admin audit logs."""
    service = HQBankingService(db)
    return await service.list_audit_logs(company_id=company_id, action=action, limit=limit)


# ============================================================================
# Accounting Endpoints
# ============================================================================

from app.services.hq import (
    HQCustomerService,
    HQInvoiceService,
    HQVendorService,
    HQBillService,
    HQAccountingDashboardService,
)
from app.schemas.hq import (
    HQCustomerCreate,
    HQCustomerUpdate,
    HQCustomerResponse,
    HQInvoiceCreate,
    HQInvoiceUpdate,
    HQInvoiceResponse,
    HQVendorCreate,
    HQVendorUpdate,
    HQVendorResponse,
    HQBillCreate,
    HQBillUpdate,
    HQBillResponse,
    HQAccountingDashboard,
    HQColabChatRequest,
    HQColabChatResponse,
    HQColabInitRequest,
    HQColabInitResponse,
)


@router.get("/accounting/dashboard", response_model=HQAccountingDashboard)
async def get_accounting_dashboard(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQAccountingDashboard:
    """Get accounting dashboard metrics."""
    service = HQAccountingDashboardService(db)
    return await service.get_dashboard()


# Customer (A/R) Endpoints
@router.get("/accounting/customers", response_model=List[HQCustomerResponse])
async def list_customers(
    status_filter: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQCustomerResponse]:
    """List all customers."""
    service = HQCustomerService(db)
    customers = await service.list_customers(status=status_filter)
    return [HQCustomerResponse.model_validate(c, from_attributes=True) for c in customers]


@router.post("/accounting/customers", response_model=HQCustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    payload: HQCustomerCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQCustomerResponse:
    """Create a new customer."""
    service = HQCustomerService(db)
    customer = await service.create_customer(payload, current_employee.id)
    return HQCustomerResponse.model_validate(customer, from_attributes=True)


@router.get("/accounting/customers/{customer_id}", response_model=HQCustomerResponse)
async def get_customer(
    customer_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQCustomerResponse:
    """Get customer by ID."""
    service = HQCustomerService(db)
    customer = await service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return HQCustomerResponse.model_validate(customer, from_attributes=True)


@router.patch("/accounting/customers/{customer_id}", response_model=HQCustomerResponse)
async def update_customer(
    customer_id: str,
    payload: HQCustomerUpdate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQCustomerResponse:
    """Update a customer."""
    service = HQCustomerService(db)
    try:
        customer = await service.update_customer(customer_id, payload)
        return HQCustomerResponse.model_validate(customer, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# Invoice (A/R) Endpoints
@router.get("/accounting/invoices", response_model=List[HQInvoiceResponse])
async def list_invoices(
    customer_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQInvoiceResponse]:
    """List all invoices."""
    service = HQInvoiceService(db)
    invoices = await service.list_invoices(customer_id=customer_id, status=status_filter)
    return [HQInvoiceResponse.model_validate(inv, from_attributes=True) for inv in invoices]


@router.post("/accounting/invoices", response_model=HQInvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: HQInvoiceCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQInvoiceResponse:
    """Create a new invoice."""
    service = HQInvoiceService(db)
    invoice = await service.create_invoice(payload, current_employee.id)
    return HQInvoiceResponse.model_validate(invoice, from_attributes=True)


@router.get("/accounting/invoices/{invoice_id}", response_model=HQInvoiceResponse)
async def get_invoice(
    invoice_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQInvoiceResponse:
    """Get invoice by ID."""
    service = HQInvoiceService(db)
    invoice = await service.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return HQInvoiceResponse.model_validate(invoice, from_attributes=True)


@router.patch("/accounting/invoices/{invoice_id}", response_model=HQInvoiceResponse)
async def update_invoice(
    invoice_id: str,
    payload: HQInvoiceUpdate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQInvoiceResponse:
    """Update an invoice."""
    service = HQInvoiceService(db)
    try:
        invoice = await service.update_invoice(invoice_id, payload)
        return HQInvoiceResponse.model_validate(invoice, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/accounting/invoices/{invoice_id}/send", response_model=HQInvoiceResponse)
async def send_invoice(
    invoice_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQInvoiceResponse:
    """Send an invoice to customer."""
    service = HQInvoiceService(db)
    try:
        invoice = await service.send_invoice(invoice_id)
        return HQInvoiceResponse.model_validate(invoice, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# Vendor (A/P) Endpoints
@router.get("/accounting/vendors", response_model=List[HQVendorResponse])
async def list_vendors(
    status_filter: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQVendorResponse]:
    """List all vendors."""
    service = HQVendorService(db)
    vendors = await service.list_vendors(status=status_filter)
    return [HQVendorResponse.model_validate(v, from_attributes=True) for v in vendors]


@router.post("/accounting/vendors", response_model=HQVendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    payload: HQVendorCreate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQVendorResponse:
    """Create a new vendor."""
    service = HQVendorService(db)
    vendor = await service.create_vendor(payload)
    return HQVendorResponse.model_validate(vendor, from_attributes=True)


@router.get("/accounting/vendors/{vendor_id}", response_model=HQVendorResponse)
async def get_vendor(
    vendor_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQVendorResponse:
    """Get vendor by ID."""
    service = HQVendorService(db)
    vendor = await service.get_vendor(vendor_id)
    if not vendor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")
    return HQVendorResponse.model_validate(vendor, from_attributes=True)


@router.patch("/accounting/vendors/{vendor_id}", response_model=HQVendorResponse)
async def update_vendor(
    vendor_id: str,
    payload: HQVendorUpdate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQVendorResponse:
    """Update a vendor."""
    service = HQVendorService(db)
    try:
        vendor = await service.update_vendor(vendor_id, payload)
        return HQVendorResponse.model_validate(vendor, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# Bill (A/P) Endpoints
@router.get("/accounting/bills", response_model=List[HQBillResponse])
async def list_bills(
    vendor_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQBillResponse]:
    """List all bills."""
    service = HQBillService(db)
    bills = await service.list_bills(vendor_id=vendor_id, status=status_filter)
    return [HQBillResponse.model_validate(b, from_attributes=True) for b in bills]


@router.post("/accounting/bills", response_model=HQBillResponse, status_code=status.HTTP_201_CREATED)
async def create_bill(
    payload: HQBillCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQBillResponse:
    """Create a new bill."""
    service = HQBillService(db)
    bill = await service.create_bill(payload, current_employee.id)
    return HQBillResponse.model_validate(bill, from_attributes=True)


@router.get("/accounting/bills/{bill_id}", response_model=HQBillResponse)
async def get_bill(
    bill_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQBillResponse:
    """Get bill by ID."""
    service = HQBillService(db)
    bill = await service.get_bill(bill_id)
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    return HQBillResponse.model_validate(bill, from_attributes=True)


@router.patch("/accounting/bills/{bill_id}", response_model=HQBillResponse)
async def update_bill(
    bill_id: str,
    payload: HQBillUpdate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQBillResponse:
    """Update a bill."""
    service = HQBillService(db)
    try:
        bill = await service.update_bill(bill_id, payload) if hasattr(service, 'update_bill') else None
        if bill:
            return HQBillResponse.model_validate(bill, from_attributes=True)
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Update not implemented")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/accounting/bills/{bill_id}/approve", response_model=HQBillResponse)
async def approve_bill(
    bill_id: str,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQBillResponse:
    """Approve a bill for payment."""
    service = HQBillService(db)
    try:
        bill = await service.approve_bill(bill_id, current_employee.id)
        return HQBillResponse.model_validate(bill, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ============================================================================
# Colab AI Endpoints
# ============================================================================

from app.services.hq_colab import get_hq_colab_service


@router.post("/colab/init", response_model=HQColabInitResponse)
async def init_colab_chat(
    payload: HQColabInitRequest,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
) -> HQColabInitResponse:
    """Initialize a chat session with an HQ AI agent (Oracle, Sentinel, or Nexus)."""
    service = get_hq_colab_service()
    return await service.init_chat(
        session_id=payload.session_id,
        agent=payload.agent,
        user_id=payload.user_id or current_employee.id,
        user_name=payload.user_name or f"{current_employee.first_name} {current_employee.last_name}",
    )


@router.post("/colab/chat", response_model=HQColabChatResponse)
async def colab_chat(
    payload: HQColabChatRequest,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
) -> HQColabChatResponse:
    """Chat with an HQ AI agent. Uses Llama 4 for intelligent responses."""
    service = get_hq_colab_service()
    return await service.chat(
        session_id=payload.session_id,
        agent=payload.agent,
        message=payload.message,
        user_id=payload.user_id or current_employee.id,
        user_name=payload.user_name or f"{current_employee.first_name} {current_employee.last_name}",
    )


# ============================================================================
# General Ledger Endpoints
# ============================================================================

from datetime import date, datetime
from decimal import Decimal
from app.services.hq_general_ledger import GeneralLedgerManager, LedgerLine, JournalEntryInput
from app.services.hq_chart_of_accounts_seed import seed_chart_of_accounts, get_ai_pricing


# Chart of Accounts Endpoints
@router.get("/gl/accounts", response_model=List[HQChartOfAccountsResponse])
async def list_chart_of_accounts(
    account_type: Optional[str] = None,
    include_inactive: bool = False,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQChartOfAccountsResponse]:
    """List all accounts in the Chart of Accounts."""
    from app.models.hq_general_ledger import AccountType
    gl_manager = GeneralLedgerManager(db)

    type_filter = None
    if account_type:
        try:
            type_filter = AccountType(account_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid account type: {account_type}"
            )

    accounts = await gl_manager.get_chart_of_accounts(
        account_type=type_filter,
        include_inactive=include_inactive
    )
    return [HQChartOfAccountsResponse.model_validate(a, from_attributes=True) for a in accounts]


@router.post("/gl/accounts", response_model=HQChartOfAccountsResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: HQChartOfAccountsCreate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQChartOfAccountsResponse:
    """Create a new account in the Chart of Accounts."""
    from app.models.hq_general_ledger import AccountType, AccountSubtype
    gl_manager = GeneralLedgerManager(db)

    try:
        account_type = AccountType(payload.account_type)
        account_subtype = AccountSubtype(payload.account_subtype) if payload.account_subtype else None

        account = await gl_manager.create_account(
            account_number=payload.account_number,
            account_name=payload.account_name,
            account_type=account_type,
            account_subtype=account_subtype,
            description=payload.description,
            parent_account_id=payload.parent_account_id,
            is_system=payload.is_system,
        )
        await db.commit()
        return HQChartOfAccountsResponse.model_validate(account, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/gl/accounts/{account_id}/balance", response_model=HQAccountBalance)
async def get_account_balance(
    account_id: str,
    as_of_date: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQAccountBalance:
    """Get the balance for a specific account."""
    gl_manager = GeneralLedgerManager(db)

    try:
        date_filter = None
        if as_of_date:
            date_filter = datetime.fromisoformat(as_of_date).date()

        balance = await gl_manager.get_account_balance(account_id, date_filter)
        return HQAccountBalance(
            account_id=balance.account_id,
            account_number=balance.account_number,
            account_name=balance.account_name,
            account_type=balance.account_type.value,
            debit_total=balance.debit_total,
            credit_total=balance.credit_total,
            balance=balance.balance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/gl/seed-accounts")
async def seed_accounts(
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
):
    """Seed the Chart of Accounts with standard SaaS accounts."""
    if current_employee.role not in ["SUPER_ADMIN", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can seed accounts"
        )

    gl_manager = GeneralLedgerManager(db)
    count = await seed_chart_of_accounts(db, gl_manager)
    return {"message": f"Seeded {count} accounts", "count": count}


# Journal Entry Endpoints
@router.post("/gl/journal-entries", response_model=HQJournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    payload: HQJournalEntryCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQJournalEntryResponse:
    """Create a new journal entry."""
    gl_manager = GeneralLedgerManager(db)

    try:
        lines = [
            LedgerLine(
                account_number=line.account_number,
                amount=line.amount,
                is_debit=line.is_debit,
                memo=line.memo,
                tenant_id=line.tenant_id,
            )
            for line in payload.lines
        ]

        entry_input = JournalEntryInput(
            description=payload.description,
            lines=lines,
            transaction_date=payload.transaction_date,
            reference=payload.reference,
            source_type=payload.source_type,
            source_id=payload.source_id,
            tenant_id=payload.tenant_id,
        )

        journal_entry = await gl_manager.create_journal_entry(
            entry=entry_input,
            created_by_id=current_employee.id,
            auto_post=payload.auto_post,
        )
        await db.commit()
        return HQJournalEntryResponse.model_validate(journal_entry, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/gl/journal-entries", response_model=List[HQJournalEntryResponse])
async def list_journal_entries(
    status_filter: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQJournalEntryResponse]:
    """List journal entries with optional filters."""
    from sqlalchemy import select
    from app.models.hq_general_ledger import HQJournalEntry, JournalEntryStatus

    query = select(HQJournalEntry).order_by(HQJournalEntry.transaction_date.desc()).limit(limit)

    if status_filter:
        try:
            status_enum = JournalEntryStatus(status_filter)
            query = query.where(HQJournalEntry.status == status_enum)
        except ValueError:
            pass

    if start_date:
        start = datetime.fromisoformat(start_date)
        query = query.where(HQJournalEntry.transaction_date >= start)

    if end_date:
        end = datetime.fromisoformat(end_date)
        query = query.where(HQJournalEntry.transaction_date <= end)

    result = await db.execute(query)
    entries = result.scalars().all()
    return [HQJournalEntryResponse.model_validate(e, from_attributes=True) for e in entries]


@router.post("/gl/journal-entries/{entry_id}/post", response_model=HQJournalEntryResponse)
async def post_journal_entry(
    entry_id: str,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQJournalEntryResponse:
    """Post a journal entry, making it immutable."""
    gl_manager = GeneralLedgerManager(db)

    try:
        entry = await gl_manager.post_journal_entry(entry_id, current_employee.id)
        await db.commit()
        return HQJournalEntryResponse.model_validate(entry, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/gl/journal-entries/{entry_id}/void", response_model=HQJournalEntryResponse)
async def void_journal_entry(
    entry_id: str,
    reason: Optional[str] = None,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQJournalEntryResponse:
    """Void a journal entry by creating a reversing entry."""
    gl_manager = GeneralLedgerManager(db)

    try:
        entry = await gl_manager.void_journal_entry(entry_id, current_employee.id, reason)
        await db.commit()
        return HQJournalEntryResponse.model_validate(entry, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# Financial Reports Endpoints
@router.get("/gl/reports/profit-loss", response_model=HQProfitLossReport)
async def get_profit_loss_report(
    start_date: str,
    end_date: str,
    tenant_id: Optional[str] = None,
    include_tenant_breakdown: bool = False,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQProfitLossReport:
    """
    Generate a Profit & Loss report.

    This is the query Atlas uses to show the Monthly P&L dashboard.
    """
    gl_manager = GeneralLedgerManager(db)

    try:
        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()

        report = await gl_manager.get_profit_loss_report(
            start_date=start,
            end_date=end,
            tenant_id=tenant_id,
            include_tenant_breakdown=include_tenant_breakdown,
        )

        gross_margin = (report.gross_profit / report.total_revenue * 100) if report.total_revenue > 0 else Decimal("0")

        return HQProfitLossReport(
            period_start=datetime.combine(report.period_start, datetime.min.time()),
            period_end=datetime.combine(report.period_end, datetime.min.time()),
            revenue=report.revenue,
            cost_of_revenue=report.cost_of_revenue,
            expenses=report.expenses,
            total_revenue=report.total_revenue,
            total_cogs=report.total_cogs,
            gross_profit=report.gross_profit,
            gross_margin_percent=gross_margin.quantize(Decimal("0.01")),
            total_expenses=report.total_expenses,
            net_income=report.net_income,
            tenant_breakdown=report.tenant_breakdown,
        )
    except Exception as exc:
        logger.error(f"Error generating P&L report: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/gl/reports/balance-sheet", response_model=HQBalanceSheetReport)
async def get_balance_sheet(
    as_of_date: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQBalanceSheetReport:
    """Generate a Balance Sheet report."""
    gl_manager = GeneralLedgerManager(db)

    try:
        report_date = datetime.fromisoformat(as_of_date).date() if as_of_date else date.today()

        report = await gl_manager.get_balance_sheet(report_date)

        return HQBalanceSheetReport(
            as_of_date=datetime.combine(report.as_of_date, datetime.min.time()),
            assets=report.assets,
            liabilities=report.liabilities,
            equity=report.equity,
            total_assets=report.total_assets,
            total_liabilities=report.total_liabilities,
            total_equity=report.total_equity,
        )
    except Exception as exc:
        logger.error(f"Error generating Balance Sheet: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/gl/reports/tenant-margin/{tenant_id}", response_model=HQTenantProfitMargin)
async def get_tenant_profit_margin(
    tenant_id: str,
    start_date: str,
    end_date: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQTenantProfitMargin:
    """Get profit margin analysis for a specific tenant."""
    gl_manager = GeneralLedgerManager(db)

    try:
        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()

        margin = await gl_manager.get_tenant_profit_margin(tenant_id, start, end)

        return HQTenantProfitMargin(
            tenant_id=margin["tenant_id"],
            tenant_name=margin.get("tenant_name"),
            revenue=margin["revenue"],
            cogs=margin["cogs"],
            gross_profit=margin["gross_profit"],
            gross_margin_percent=margin["gross_margin_percent"],
        )
    except Exception as exc:
        logger.error(f"Error getting tenant margin: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# AI Usage & COGS Endpoints
@router.post("/gl/ai-usage")
async def log_ai_usage(
    payload: HQAIUsageLogRequest,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
):
    """Log AI usage and book COGS automatically."""
    gl_manager = GeneralLedgerManager(db)

    try:
        pricing = get_ai_pricing(payload.model)

        usage_log, journal_entry = await gl_manager.log_ai_usage(
            tenant_id=payload.tenant_id,
            model=payload.model,
            input_tokens=payload.input_tokens,
            output_tokens=payload.output_tokens,
            cost_per_1k_input=pricing["input"],
            cost_per_1k_output=pricing["output"],
        )
        await db.commit()

        return {
            "usage_log_id": usage_log.id,
            "total_tokens": payload.input_tokens + payload.output_tokens,
            "total_cost": float(usage_log.total_cost) if usage_log.total_cost else 0,
            "journal_entry_id": journal_entry.id if journal_entry else None,
        }
    except Exception as exc:
        logger.error(f"Error logging AI usage: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/gl/ai-costs", response_model=List[HQAICostsByTenant])
async def get_ai_costs_by_tenant(
    start_date: str,
    end_date: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQAICostsByTenant]:
    """Get AI costs aggregated by tenant for a period."""
    gl_manager = GeneralLedgerManager(db)

    try:
        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()

        costs = await gl_manager.get_ai_costs_by_tenant(start, end)

        return [
            HQAICostsByTenant(
                tenant_id=c["tenant_id"],
                tenant_name=c.get("tenant_name"),
                request_count=c["request_count"],
                total_tokens=c["total_tokens"],
                total_cost=c["total_cost"],
            )
            for c in costs
        ]
    except Exception as exc:
        logger.error(f"Error getting AI costs: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# GL Dashboard Endpoint
@router.get("/gl/dashboard", response_model=HQGLDashboard)
async def get_gl_dashboard(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQGLDashboard:
    """Get General Ledger dashboard with key financial metrics."""
    from sqlalchemy import select, func
    from app.models.hq_general_ledger import (
        HQChartOfAccounts, HQJournalEntry, HQUsageLog,
        AccountType, JournalEntryStatus, UsageMetricType
    )

    gl_manager = GeneralLedgerManager(db)

    # Get current month dates
    today = date.today()
    month_start = today.replace(day=1)

    try:
        # Balance sheet summary
        balance_sheet = await gl_manager.get_balance_sheet(today)

        # P&L for current month
        pl_report = await gl_manager.get_profit_loss_report(month_start, today)

        # Get specific account balances
        cash_result = await db.execute(
            select(func.sum(HQChartOfAccounts.current_balance))
            .where(HQChartOfAccounts.account_subtype == "cash")
        )
        cash_balance = cash_result.scalar() or Decimal("0")

        ar_result = await db.execute(
            select(func.sum(HQChartOfAccounts.current_balance))
            .where(HQChartOfAccounts.account_subtype == "accounts_receivable")
        )
        ar_balance = ar_result.scalar() or Decimal("0")

        ap_result = await db.execute(
            select(func.sum(HQChartOfAccounts.current_balance))
            .where(HQChartOfAccounts.account_subtype == "accounts_payable")
        )
        ap_balance = ap_result.scalar() or Decimal("0")

        # Account count
        accounts_count = await db.execute(
            select(func.count(HQChartOfAccounts.id))
            .where(HQChartOfAccounts.is_active == True)
        )

        # Posted entries count
        entries_count = await db.execute(
            select(func.count(HQJournalEntry.id))
            .where(HQJournalEntry.status == JournalEntryStatus.POSTED)
        )

        # AI costs MTD
        ai_costs_result = await db.execute(
            select(func.sum(HQUsageLog.total_cost))
            .where(
                HQUsageLog.metric_type == UsageMetricType.AI_TOKENS_USED,
                HQUsageLog.recorded_at >= month_start,
            )
        )
        ai_costs_mtd = ai_costs_result.scalar() or Decimal("0")

        # AI costs by model (simplified)
        ai_by_model = {}

        # Calculate gross margin
        gross_margin = (pl_report.gross_profit / pl_report.total_revenue * 100) if pl_report.total_revenue > 0 else Decimal("0")

        return HQGLDashboard(
            total_assets=balance_sheet.total_assets,
            total_liabilities=balance_sheet.total_liabilities,
            total_equity=balance_sheet.total_equity,
            cash_balance=Decimal(str(cash_balance)),
            accounts_receivable=Decimal(str(ar_balance)),
            accounts_payable=Decimal(str(ap_balance)),
            current_month_revenue=pl_report.total_revenue,
            current_month_cogs=pl_report.total_cogs,
            current_month_gross_profit=pl_report.gross_profit,
            current_month_expenses=pl_report.total_expenses,
            current_month_net_income=pl_report.net_income,
            ai_costs_mtd=Decimal(str(ai_costs_mtd)),
            ai_costs_by_model=ai_by_model,
            gross_margin_percent=gross_margin.quantize(Decimal("0.01")),
            accounts_count=accounts_count.scalar() or 0,
            posted_entries_count=entries_count.scalar() or 0,
        )
    except Exception as exc:
        logger.error(f"Error getting GL dashboard: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ============================================================================
# HR & Payroll Endpoints
# ============================================================================

from app.services.hq_hr import HQHREmployeeService, HQPayrollService
from app.schemas.hq import (
    HQHREmployeeCreate,
    HQHREmployeeUpdate,
    HQHREmployeeResponse,
    HQPayrollRunCreate,
    HQPayrollRunResponse,
    HQPayrollItemResponse,
)


# HR Employee Endpoints
@router.get("/hr/stats")
async def get_hr_stats(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
):
    """Get HR statistics."""
    hr_service = HQHREmployeeService(db)
    payroll_service = HQPayrollService(db)

    hr_stats = await hr_service.get_hr_stats()
    payroll_stats = await payroll_service.get_payroll_stats()

    return {**hr_stats, **payroll_stats}


@router.get("/hr/employees", response_model=List[HQHREmployeeResponse])
async def list_hr_employees(
    status_filter: Optional[str] = None,
    department: Optional[str] = None,
    employment_type: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQHREmployeeResponse]:
    """List all HR employees (payroll employees)."""
    service = HQHREmployeeService(db)
    employees = await service.list_employees(
        status=status_filter,
        department=department,
        employment_type=employment_type,
    )

    result = []
    for emp in employees:
        resp = HQHREmployeeResponse.model_validate(emp, from_attributes=True)
        # Add manager name if available
        if emp.manager:
            resp.manager_name = f"{emp.manager.first_name} {emp.manager.last_name}"
        result.append(resp)
    return result


@router.post("/hr/employees", response_model=HQHREmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_hr_employee(
    payload: HQHREmployeeCreate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQHREmployeeResponse:
    """Create a new HR employee."""
    service = HQHREmployeeService(db)
    try:
        employee = await service.create_employee(payload)
        return HQHREmployeeResponse.model_validate(employee, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/hr/employees/{employee_id}", response_model=HQHREmployeeResponse)
async def get_hr_employee(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQHREmployeeResponse:
    """Get HR employee by ID."""
    service = HQHREmployeeService(db)
    employee = await service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    resp = HQHREmployeeResponse.model_validate(employee, from_attributes=True)
    if employee.manager:
        resp.manager_name = f"{employee.manager.first_name} {employee.manager.last_name}"
    return resp


@router.patch("/hr/employees/{employee_id}", response_model=HQHREmployeeResponse)
async def update_hr_employee(
    employee_id: str,
    payload: HQHREmployeeUpdate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQHREmployeeResponse:
    """Update an HR employee."""
    service = HQHREmployeeService(db)
    try:
        employee = await service.update_employee(employee_id, payload)
        return HQHREmployeeResponse.model_validate(employee, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/hr/employees/{employee_id}/terminate", response_model=HQHREmployeeResponse)
async def terminate_hr_employee(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQHREmployeeResponse:
    """Terminate an HR employee."""
    service = HQHREmployeeService(db)
    try:
        employee = await service.terminate_employee(employee_id)
        return HQHREmployeeResponse.model_validate(employee, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# Payroll Run Endpoints
@router.get("/hr/payroll", response_model=List[HQPayrollRunResponse])
async def list_payroll_runs(
    status_filter: Optional[str] = None,
    limit: int = 50,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQPayrollRunResponse]:
    """List all payroll runs."""
    service = HQPayrollService(db)
    payrolls = await service.list_payroll_runs(status=status_filter, limit=limit)
    return [HQPayrollRunResponse.model_validate(p, from_attributes=True) for p in payrolls]


@router.post("/hr/payroll", response_model=HQPayrollRunResponse, status_code=status.HTTP_201_CREATED)
async def create_payroll_run(
    payload: HQPayrollRunCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQPayrollRunResponse:
    """Create a new payroll run."""
    service = HQPayrollService(db)
    try:
        payroll = await service.create_payroll_run(payload, current_employee.id)
        return HQPayrollRunResponse.model_validate(payroll, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/hr/payroll/{payroll_id}", response_model=HQPayrollRunResponse)
async def get_payroll_run(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQPayrollRunResponse:
    """Get payroll run by ID."""
    service = HQPayrollService(db)
    payroll = await service.get_payroll_run(payroll_id)
    if not payroll:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found")
    return HQPayrollRunResponse.model_validate(payroll, from_attributes=True)


@router.get("/hr/payroll/{payroll_id}/items", response_model=List[HQPayrollItemResponse])
async def get_payroll_items(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQPayrollItemResponse]:
    """Get all items for a payroll run."""
    service = HQPayrollService(db)
    items = await service.get_payroll_items(payroll_id)

    result = []
    for item in items:
        resp = HQPayrollItemResponse(
            id=item.id,
            payroll_run_id=item.payroll_run_id,
            employee_id=item.employee_id,
            employee_name=f"{item.employee.first_name} {item.employee.last_name}" if item.employee else "Unknown",
            gross_pay=item.gross_pay,
            federal_tax=item.federal_tax,
            state_tax=item.state_tax,
            social_security=item.social_security,
            medicare=item.medicare,
            other_deductions=item.other_deductions + item.health_insurance + item.dental_insurance + item.vision_insurance + item.retirement_401k,
            net_pay=item.net_pay,
            hours_worked=item.regular_hours,
            overtime_hours=item.overtime_hours,
            check_paystub_id=item.check_paystub_id,
        )
        result.append(resp)
    return result


@router.post("/hr/payroll/{payroll_id}/submit", response_model=HQPayrollRunResponse)
async def submit_payroll_for_approval(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQPayrollRunResponse:
    """Submit a payroll run for approval."""
    service = HQPayrollService(db)
    try:
        payroll = await service.submit_for_approval(payroll_id)
        return HQPayrollRunResponse.model_validate(payroll, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/hr/payroll/{payroll_id}/approve", response_model=HQPayrollRunResponse)
async def approve_payroll_run(
    payroll_id: str,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQPayrollRunResponse:
    """Approve a payroll run."""
    service = HQPayrollService(db)
    try:
        payroll = await service.approve_payroll(payroll_id, current_employee.id)
        return HQPayrollRunResponse.model_validate(payroll, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/hr/payroll/{payroll_id}/process", response_model=HQPayrollRunResponse)
async def process_payroll_run(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQPayrollRunResponse:
    """Process an approved payroll run."""
    service = HQPayrollService(db)
    try:
        payroll = await service.process_payroll(payroll_id)
        return HQPayrollRunResponse.model_validate(payroll, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/hr/payroll/{payroll_id}/cancel", response_model=HQPayrollRunResponse)
async def cancel_payroll_run(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQPayrollRunResponse:
    """Cancel a payroll run."""
    service = HQPayrollService(db)
    try:
        payroll = await service.cancel_payroll(payroll_id)
        return HQPayrollRunResponse.model_validate(payroll, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ============================================================================
# HR - Check HQ Integration Endpoints
# ============================================================================

@router.post("/hr/employees/{employee_id}/sync-to-check")
async def sync_employee_to_check(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
):
    """Sync an HR employee to Check payroll system."""
    from app.services.check import CheckService

    hr_service = HQHREmployeeService(db)
    employee = await hr_service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    # Get HQ's Check company ID from settings
    check_company_id = settings.check_hq_company_id
    if not check_company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check HQ company not configured"
        )

    check_service = CheckService(company_check_id=check_company_id)

    try:
        # Create employee in Check
        check_data = {
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "email": employee.email,
            "phone": employee.phone,
            "start_date": employee.hire_date.isoformat() if employee.hire_date else None,
            "residence": {
                "line1": employee.address_line1,
                "line2": employee.address_line2,
                "city": employee.city,
                "state": employee.state,
                "postal_code": employee.zip_code,
                "country": "US",
            } if employee.address_line1 else None,
        }

        if employee.check_employee_id:
            # Update existing
            result = await check_service.update_employee(employee.check_employee_id, check_data)
        else:
            # Create new
            result = await check_service.create_employee(check_data)
            employee.check_employee_id = result.get("id")
            await db.commit()

        return {"status": "synced", "check_employee_id": employee.check_employee_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/hr/employees/{employee_id}/check-status")
async def get_employee_check_status(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
):
    """Get Check payroll status for an employee."""
    from app.services.check import CheckService

    hr_service = HQHREmployeeService(db)
    employee = await hr_service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    if not employee.check_employee_id:
        return {"synced": False, "check_employee_id": None, "onboarding_status": None}

    check_company_id = settings.check_hq_company_id
    if not check_company_id:
        return {"synced": False, "check_employee_id": None, "onboarding_status": None}

    check_service = CheckService(company_check_id=check_company_id)

    try:
        check_employee = await check_service.get_employee(employee.check_employee_id)
        return {
            "synced": True,
            "check_employee_id": employee.check_employee_id,
            "onboarding_status": check_employee.get("onboarding", {}).get("status"),
            "payment_method": check_employee.get("payment_method", {}).get("type"),
            "bank_account_linked": check_employee.get("payment_method", {}).get("bank_account") is not None,
        }
    except Exception as e:
        return {"synced": False, "check_employee_id": employee.check_employee_id, "error": str(e)}


@router.get("/hr/employees/{employee_id}/onboarding-link")
async def get_employee_onboarding_link(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
):
    """Get Check onboarding link for an employee."""
    from app.services.check import CheckService

    hr_service = HQHREmployeeService(db)
    employee = await hr_service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    if not employee.check_employee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee not synced to Check")

    check_company_id = settings.check_hq_company_id
    if not check_company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Check HQ company not configured")

    check_service = CheckService(company_check_id=check_company_id)

    try:
        # Get onboarding link from Check
        result = await check_service._request(
            "POST",
            f"/employees/{employee.check_employee_id}/onboarding_link"
        )
        return {"url": result.get("url")}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/hr/employees/{employee_id}/resend-onboarding")
async def resend_employee_onboarding(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
):
    """Resend onboarding email to employee."""
    from app.services.check import CheckService

    hr_service = HQHREmployeeService(db)
    employee = await hr_service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    if not employee.check_employee_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee not synced to Check")

    check_company_id = settings.check_hq_company_id
    if not check_company_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Check HQ company not configured")

    check_service = CheckService(company_check_id=check_company_id)

    try:
        await check_service._request(
            "POST",
            f"/employees/{employee.check_employee_id}/onboarding/resend"
        )
        return {"status": "sent"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ============================================================================
# HR - Onboarding Endpoints
# ============================================================================

@router.get("/hr/onboarding")
async def list_onboarding_employees(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
):
    """List all employees in onboarding status."""
    hr_service = HQHREmployeeService(db)
    employees = await hr_service.list_employees(status="onboarding")

    result = []
    for emp in employees:
        resp = HQHREmployeeResponse.model_validate(emp, from_attributes=True)
        result.append(resp)
    return result


@router.post("/hr/employees/{employee_id}/complete-onboarding")
async def complete_employee_onboarding(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
):
    """Mark employee onboarding as complete and set status to active."""
    from app.models.hq_hr import HREmployeeStatus

    hr_service = HQHREmployeeService(db)
    employee = await hr_service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    if employee.status != HREmployeeStatus.ONBOARDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee is not in onboarding status")

    employee.status = HREmployeeStatus.ACTIVE
    await db.commit()
    await db.refresh(employee)

    return HQHREmployeeResponse.model_validate(employee, from_attributes=True)


# ============================================================================
# CRM - Lead Endpoints
# ============================================================================

@router.get("/leads", response_model=List[HQLeadResponse])
async def list_leads(
    status: Optional[str] = None,
    source: Optional[str] = None,
    current_employee: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """List leads. Sales managers only see their own leads."""
    from app.services.hq_leads import HQLeadService

    lead_service = HQLeadService(db)
    return await lead_service.get_leads(
        current_user_id=current_employee.id,
        current_user_role=current_employee.role,
        status=status,
        source=source,
    )


@router.get("/leads/{lead_id}", response_model=HQLeadResponse)
async def get_lead(
    lead_id: str,
    _: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single lead by ID."""
    from app.services.hq_leads import HQLeadService

    lead_service = HQLeadService(db)
    lead = await lead_service.get_lead(lead_id)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.post("/leads", response_model=HQLeadResponse)
async def create_lead(
    data: HQLeadCreate,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new lead."""
    from app.services.hq_leads import HQLeadService

    lead_service = HQLeadService(db)
    return await lead_service.create_lead(data, current_employee.id)


@router.put("/leads/{lead_id}", response_model=HQLeadResponse)
async def update_lead(
    lead_id: str,
    data: HQLeadUpdate,
    _: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Update a lead."""
    from app.services.hq_leads import HQLeadService

    lead_service = HQLeadService(db)
    lead = await lead_service.update_lead(lead_id, data)
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.post("/leads/{lead_id}/convert", response_model=HQOpportunityResponse)
async def convert_lead_to_opportunity(
    lead_id: str,
    data: HQLeadConvert,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Convert a lead to an opportunity."""
    from app.services.hq_leads import HQLeadService

    lead_service = HQLeadService(db)
    try:
        opportunity = await lead_service.convert_to_opportunity(lead_id, data, current_employee.id)
        if not opportunity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        return opportunity
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/leads/import", response_model=HQLeadImportResponse)
async def import_leads_ai(
    data: HQLeadImportRequest,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """
    Import leads using AI parsing from CSV, spreadsheet, email, or text content.

    The AI will extract company names, contacts, and other lead info automatically.
    Leads can be assigned to a specific sales rep or distributed round-robin.
    """
    from app.services.hq_leads import HQLeadService

    lead_service = HQLeadService(db)
    leads_created, errors = await lead_service.import_leads_from_content(
        content=data.content,
        content_type=data.content_type,
        assign_to_sales_rep_id=data.assign_to_sales_rep_id,
        created_by_id=current_employee.id,
        auto_assign_round_robin=data.auto_assign_round_robin,
    )

    return HQLeadImportResponse(
        leads_created=leads_created,
        errors=errors,
        total_parsed=len(leads_created) + len(errors),
        total_created=len(leads_created),
    )


# ============================================================================
# CRM - Opportunity Endpoints
# ============================================================================

@router.get("/opportunities", response_model=List[HQOpportunityResponse])
async def list_opportunities(
    stage: Optional[str] = None,
    current_employee: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """List opportunities. Sales managers only see their own."""
    from app.services.hq_opportunities import HQOpportunityService

    opp_service = HQOpportunityService(db)
    return await opp_service.get_opportunities(
        current_user_id=current_employee.id,
        current_user_role=current_employee.role,
        stage=stage,
    )


@router.get("/opportunities/pipeline", response_model=List[HQPipelineSummary])
async def get_pipeline_summary(
    current_employee: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get pipeline summary grouped by stage."""
    from app.services.hq_opportunities import HQOpportunityService

    opp_service = HQOpportunityService(db)
    return await opp_service.get_pipeline_summary(
        current_user_id=current_employee.id,
        current_user_role=current_employee.role,
    )


@router.get("/opportunities/{opportunity_id}", response_model=HQOpportunityResponse)
async def get_opportunity(
    opportunity_id: str,
    _: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single opportunity by ID."""
    from app.services.hq_opportunities import HQOpportunityService

    opp_service = HQOpportunityService(db)
    opportunity = await opp_service.get_opportunity(opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return opportunity


@router.post("/opportunities", response_model=HQOpportunityResponse)
async def create_opportunity(
    data: HQOpportunityCreate,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new opportunity."""
    from app.services.hq_opportunities import HQOpportunityService

    opp_service = HQOpportunityService(db)
    return await opp_service.create_opportunity(data, current_employee.id)


@router.put("/opportunities/{opportunity_id}", response_model=HQOpportunityResponse)
async def update_opportunity(
    opportunity_id: str,
    data: HQOpportunityUpdate,
    _: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Update an opportunity."""
    from app.services.hq_opportunities import HQOpportunityService

    opp_service = HQOpportunityService(db)
    opportunity = await opp_service.update_opportunity(opportunity_id, data)
    if not opportunity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return opportunity


@router.post("/opportunities/{opportunity_id}/convert", response_model=HQQuoteResponse)
async def convert_opportunity_to_quote(
    opportunity_id: str,
    data: HQOpportunityConvert,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_quotes")),
    db: AsyncSession = Depends(get_db),
):
    """Convert an opportunity to a quote."""
    from app.services.hq_opportunities import HQOpportunityService

    opp_service = HQOpportunityService(db)
    try:
        quote = await opp_service.convert_to_quote(opportunity_id, data, current_employee.id)
        if not quote:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
        return quote
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============================================================================
# Commission Configuration Endpoints (Admin Only)
# ============================================================================

@router.get("/commission/config", response_model=List[HQSalesRepCommissionResponse])
async def list_commission_configs(
    _: HQEmployee = Depends(require_hq_admin()),
    db: AsyncSession = Depends(get_db),
):
    """List all sales rep commission configurations (Admin only)."""
    from app.services.hq_commission import HQCommissionService

    commission_service = HQCommissionService(db)
    return await commission_service.get_all_commission_configs()


@router.get("/commission/config/{sales_rep_id}", response_model=HQSalesRepCommissionResponse)
async def get_commission_config(
    sales_rep_id: str,
    _: HQEmployee = Depends(require_hq_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Get commission config for a specific sales rep."""
    from app.services.hq_commission import HQCommissionService

    commission_service = HQCommissionService(db)
    config = await commission_service.get_commission_config(sales_rep_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commission config not found")
    return config


@router.post("/commission/config", response_model=HQSalesRepCommissionResponse)
async def create_commission_config(
    data: HQSalesRepCommissionCreate,
    current_employee: HQEmployee = Depends(require_hq_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Create commission config for a sales rep."""
    from app.services.hq_commission import HQCommissionService

    commission_service = HQCommissionService(db)
    try:
        return await commission_service.create_commission_config(data, current_employee.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/commission/config/{sales_rep_id}", response_model=HQSalesRepCommissionResponse)
async def update_commission_config(
    sales_rep_id: str,
    data: HQSalesRepCommissionUpdate,
    current_employee: HQEmployee = Depends(require_hq_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Update commission config for a sales rep."""
    from app.services.hq_commission import HQCommissionService

    commission_service = HQCommissionService(db)
    config = await commission_service.update_commission_config(sales_rep_id, data, current_employee.id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commission config not found")
    return config


# ============================================================================
# Commission Earnings Endpoints
# ============================================================================

@router.get("/commission/earnings", response_model=HQSalesRepEarnings)
async def get_my_earnings(
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """Get earnings dashboard for current sales rep."""
    from app.services.hq_commission import HQCommissionService

    commission_service = HQCommissionService(db)
    earnings = await commission_service.get_sales_rep_earnings(current_employee.id)
    if not earnings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Earnings data not found")
    return earnings


@router.get("/commission/earnings/{sales_rep_id}", response_model=HQSalesRepEarnings)
async def get_sales_rep_earnings(
    sales_rep_id: str,
    _: HQEmployee = Depends(require_hq_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Get earnings dashboard for a specific sales rep (Admin only)."""
    from app.services.hq_commission import HQCommissionService

    commission_service = HQCommissionService(db)
    earnings = await commission_service.get_sales_rep_earnings(sales_rep_id)
    if not earnings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Earnings data not found")
    return earnings


@router.get("/commission/accounts", response_model=List[HQSalesRepAccountSummary])
async def get_my_accounts(
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """Get accounts assigned to current sales rep with MRR breakdown."""
    from app.services.hq_commission import HQCommissionService

    commission_service = HQCommissionService(db)
    return await commission_service.get_sales_rep_accounts(current_employee.id)


@router.get("/commission/accounts/{sales_rep_id}", response_model=List[HQSalesRepAccountSummary])
async def get_sales_rep_accounts(
    sales_rep_id: str,
    _: HQEmployee = Depends(require_hq_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Get accounts for a specific sales rep (Admin only)."""
    from app.services.hq_commission import HQCommissionService

    commission_service = HQCommissionService(db)
    return await commission_service.get_sales_rep_accounts(sales_rep_id)


# ============================================================================
# Commission Records & Payments Endpoints
# ============================================================================

@router.get("/commission/records", response_model=List[HQCommissionRecordResponse])
async def list_commission_records(
    status: Optional[str] = None,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """List commission records. Sales reps see their own, admins see all."""
    from app.services.hq_commission import HQCommissionService
    from app.models.hq_employee import HQRole

    commission_service = HQCommissionService(db)

    # Admins see all, sales reps see their own
    sales_rep_id = None if current_employee.role in [HQRole.SUPER_ADMIN, HQRole.ADMIN] else current_employee.id

    return await commission_service.get_commission_records(
        sales_rep_id=sales_rep_id,
        status=status,
    )


@router.get("/commission/payments", response_model=List[HQCommissionPaymentResponse])
async def list_commission_payments(
    status: Optional[str] = None,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """List commission payments. Sales reps see their own, admins see all."""
    from app.services.hq_commission import HQCommissionService
    from app.models.hq_employee import HQRole

    commission_service = HQCommissionService(db)

    # Admins see all, sales reps see their own
    sales_rep_id = None if current_employee.role in [HQRole.SUPER_ADMIN, HQRole.ADMIN] else current_employee.id

    return await commission_service.get_commission_payments(
        sales_rep_id=sales_rep_id,
        status=status,
    )


@router.post("/commission/payments/{payment_id}/approve", response_model=HQCommissionPaymentResponse)
async def approve_commission_payment(
    payment_id: str,
    data: HQCommissionPaymentApprove,
    current_employee: HQEmployee = Depends(require_hq_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Approve a commission payment (Admin only)."""
    from app.services.hq_commission import HQCommissionService

    commission_service = HQCommissionService(db)
    payment = await commission_service.approve_commission_payment(payment_id, data, current_employee.id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return payment


@router.post("/commission/payments/{payment_id}/mark-paid", response_model=HQCommissionPaymentResponse)
async def mark_commission_payment_paid(
    payment_id: str,
    payment_reference: Optional[str] = None,
    _: HQEmployee = Depends(require_hq_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Mark a commission payment as paid (Admin only)."""
    from app.services.hq_commission import HQCommissionService

    commission_service = HQCommissionService(db)
    payment = await commission_service.mark_payment_paid(payment_id, payment_reference)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return payment

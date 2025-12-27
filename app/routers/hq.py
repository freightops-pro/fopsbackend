"""HQ Admin Portal router."""

import logging
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status, Query
from pydantic import BaseModel
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
    HQCreditCreateForTenant,
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
    HQLeadFMCSAImportRequest,
    HQLeadEnrichRequest,
    HQLeadEnrichResponse,
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
    # Deal schemas
    HQDealCreate,
    HQDealUpdate,
    HQDealResponse,
    HQDealStageSummary,
    HQDealImportRequest,
    HQDealImportResponse,
    HQDealFMCSAImportRequest,
    HQDealActivityCreate,
    HQDealActivityResponse,
    # Subscription schemas
    HQSubscriptionCreate,
    HQSubscriptionUpdate,
    HQSubscriptionResponse,
    HQSubscriptionFromDeal,
    HQMRRSummary,
    HQRateChangeResponse,
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
    from decimal import Decimal
    from app.models.hq_contract import HQContract, ContractStatus
    from app.models.hq_tenant import HQTenant

    try:
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
            # Safely get tenant name
            tenant_name = None
            try:
                if c.tenant and c.tenant.company:
                    tenant_name = c.tenant.company.name
            except Exception:
                pass

            data = {
                "id": c.id,
                "tenant_id": c.tenant_id,
                "tenant_name": tenant_name,
                "contract_number": c.contract_number,
                "title": c.title,
                "contract_type": c.contract_type.value if hasattr(c.contract_type, 'value') else str(c.contract_type),
                "status": c.status.value if hasattr(c.status, 'value') else str(c.status),
                "description": c.description,
                "monthly_value": Decimal(str(c.monthly_value)) if c.monthly_value is not None else Decimal("0"),
                "annual_value": Decimal(str(c.annual_value)) if c.annual_value is not None else None,
                "setup_fee": Decimal(str(c.setup_fee)) if c.setup_fee is not None else Decimal("0"),
                "start_date": c.start_date,
                "end_date": c.end_date,
                "auto_renew": str(c.auto_renew) if c.auto_renew else "false",
                "notice_period_days": str(c.notice_period_days) if c.notice_period_days else "30",
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
    except Exception as e:
        logger.error(f"Error fetching expiring contracts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching expiring contracts: {str(e)}"
        )


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
    payload: HQCreditCreateForTenant,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQCreditResponse:
    """Add a credit to a tenant's account.

    tenant_id comes from URL path, not request body.
    """
    from sqlalchemy import select
    from app.models.company import Company

    # Verify tenant exists
    result = await db.execute(select(Company).where(Company.id == tenant_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Build full payload with tenant_id from URL
    full_payload = HQCreditCreate(
        tenant_id=tenant_id,
        **payload.model_dump()
    )

    service = HQCreditService(db)
    credit = await service.create_credit(full_payload, current_employee.id)
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
# HQ Internal Banking Endpoints (FreightOps HQ's Own Banking)
# Uses the same banking infrastructure as tenants, but for HQ's company
# ============================================================================

from app.services.banking import BankingService
from app.schemas.banking import (
    BankingAccountCreate,
    BankingAccountResponse,
    BankingCardCreate,
    BankingCardResponse,
    BankingCustomerCreate,
    BankingCustomerResponse,
)


def _get_hq_company_id() -> str:
    """Get HQ's company ID from config."""
    if not settings.hq_company_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HQ company ID not configured. Set HQ_COMPANY_ID in environment."
        )
    return settings.hq_company_id


@router.get("/internal-banking/accounts", response_model=List[BankingAccountResponse])
async def list_hq_accounts(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> List[BankingAccountResponse]:
    """List HQ's own bank accounts."""
    company_id = _get_hq_company_id()
    service = BankingService(db)
    return await service.list_accounts(company_id)


@router.post("/internal-banking/accounts", response_model=BankingAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_hq_account(
    payload: BankingAccountCreate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> BankingAccountResponse:
    """Create a new bank account for HQ."""
    company_id = _get_hq_company_id()
    service = BankingService(db)
    return await service.create_account(company_id, payload)


@router.get("/internal-banking/cards")
async def list_hq_cards(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List HQ's cards."""
    from app.models.banking import BankingCard, BankingAccount

    company_id = _get_hq_company_id()
    result = await db.execute(
        select(BankingCard)
        .join(BankingAccount, BankingCard.account_id == BankingAccount.id)
        .where(BankingAccount.company_id == company_id)
        .order_by(BankingCard.created_at.desc())
    )
    cards = result.scalars().all()
    return [BankingCardResponse.model_validate(card).model_dump() for card in cards]


@router.post("/internal-banking/cards", response_model=BankingCardResponse, status_code=status.HTTP_201_CREATED)
async def issue_hq_card(
    payload: BankingCardCreate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> BankingCardResponse:
    """Issue a new card for HQ."""
    service = BankingService(db)
    return await service.issue_card(payload)


@router.get("/internal-banking/transactions")
async def list_hq_transactions(
    account_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List HQ's transactions."""
    from app.models.banking import BankingTransaction, BankingAccount
    from datetime import datetime

    company_id = _get_hq_company_id()

    # Build query
    query = (
        select(BankingTransaction)
        .join(BankingAccount, BankingTransaction.account_id == BankingAccount.id)
        .where(BankingAccount.company_id == company_id)
    )

    if account_id:
        query = query.where(BankingTransaction.account_id == account_id)

    if start_date:
        query = query.where(BankingTransaction.posted_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.where(BankingTransaction.posted_at <= datetime.fromisoformat(end_date))

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    # Get paginated results
    query = query.order_by(BankingTransaction.posted_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    transactions = result.scalars().all()

    return {
        "transactions": [
            {
                "id": t.id,
                "account_id": t.account_id,
                "amount": float(t.amount) if t.amount else 0,
                "currency": t.currency or "USD",
                "description": t.description,
                "category": t.category or "transfer",
                "posted_at": t.posted_at.isoformat() if t.posted_at else None,
                "pending": t.pending if hasattr(t, 'pending') else False,
            }
            for t in transactions
        ],
        "total": total,
    }


@router.post("/internal-banking/transfers/internal", status_code=status.HTTP_201_CREATED)
async def create_hq_internal_transfer(
    payload: Dict[str, Any],
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create an internal transfer between HQ accounts."""
    from app.services.transfer_service import TransferService

    company_id = _get_hq_company_id()
    service = TransferService(db)

    try:
        result = await service.create_internal_transfer(
            company_id=company_id,
            from_account_id=payload["from_account_id"],
            to_account_id=payload["to_account_id"],
            amount=payload["amount"],
            description=payload["description"],
            user_id=current_employee.id,
            scheduled_date=payload.get("scheduled_date"),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/internal-banking/transfers/ach", status_code=status.HTTP_201_CREATED)
async def create_hq_ach_transfer(
    payload: Dict[str, Any],
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create an ACH transfer from HQ account."""
    from app.services.transfer_service import TransferService

    company_id = _get_hq_company_id()
    service = TransferService(db)

    try:
        result = await service.create_ach_transfer(
            company_id=company_id,
            from_account_id=payload["from_account_id"],
            recipient_name=payload.get("recipient_name"),
            recipient_routing_number=payload.get("recipient_routing_number"),
            recipient_account_number=payload.get("recipient_account_number"),
            recipient_account_type=payload.get("recipient_account_type", "checking"),
            amount=payload["amount"],
            description=payload["description"],
            user_id=current_employee.id,
            save_recipient=payload.get("save_recipient", False),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/internal-banking/transfers/wire", status_code=status.HTTP_201_CREATED)
async def create_hq_wire_transfer(
    payload: Dict[str, Any],
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Create a wire transfer from HQ account."""
    from app.services.transfer_service import TransferService

    company_id = _get_hq_company_id()
    service = TransferService(db)

    try:
        result = await service.create_wire_transfer(
            company_id=company_id,
            from_account_id=payload["from_account_id"],
            recipient_name=payload["recipient_name"],
            recipient_routing_number=payload["recipient_routing_number"],
            recipient_account_number=payload["recipient_account_number"],
            recipient_bank_name=payload["recipient_bank_name"],
            amount=payload["amount"],
            description=payload.get("description", ""),
            wire_type=payload.get("wire_type", "domestic"),
            user_id=current_employee.id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/internal-banking/transfers/history")
async def get_hq_transfer_history(
    limit: int = 50,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get HQ's transfer history."""
    from app.services.transfer_service import TransferService

    company_id = _get_hq_company_id()
    service = TransferService(db)
    transfers = await service.get_transfer_history(company_id, limit)
    return {"transfers": transfers}


@router.get("/internal-banking/statements")
async def list_hq_statements(
    account_id: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """List HQ's bank statements."""
    from app.models.banking import BankingStatement, BankingAccount

    company_id = _get_hq_company_id()

    query = (
        select(BankingStatement)
        .join(BankingAccount, BankingStatement.account_id == BankingAccount.id)
        .where(BankingAccount.company_id == company_id)
    )

    if account_id:
        query = query.where(BankingStatement.account_id == account_id)

    query = query.order_by(BankingStatement.period_end.desc())
    result = await db.execute(query)
    statements = result.scalars().all()

    return {
        "statements": [
            {
                "id": s.id,
                "account_id": s.account_id,
                "period_start": s.period_start.isoformat() if s.period_start else None,
                "period_end": s.period_end.isoformat() if s.period_end else None,
                "opening_balance": float(s.opening_balance) if s.opening_balance else 0,
                "closing_balance": float(s.closing_balance) if s.closing_balance else 0,
                "total_credits": float(s.total_credits) if hasattr(s, 'total_credits') and s.total_credits else 0,
                "total_debits": float(s.total_debits) if hasattr(s, 'total_debits') and s.total_debits else 0,
                "transaction_count": s.transaction_count if hasattr(s, 'transaction_count') else 0,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in statements
        ]
    }


@router.get("/internal-banking/statements/{statement_id}/download")
async def download_hq_statement(
    statement_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get download URL for HQ statement."""
    from app.models.banking import BankingStatement, BankingAccount

    company_id = _get_hq_company_id()

    result = await db.execute(
        select(BankingStatement)
        .join(BankingAccount, BankingStatement.account_id == BankingAccount.id)
        .where(BankingStatement.id == statement_id)
        .where(BankingAccount.company_id == company_id)
    )
    statement = result.scalar_one_or_none()

    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found")

    # Return download URL (would be generated from R2/S3 in production)
    return {
        "statement_id": statement.id,
        "download_url": f"/api/hq/internal-banking/statements/{statement_id}/pdf",
        "filename": f"statement_{statement.period_end.strftime('%Y-%m')}.pdf" if statement.period_end else "statement.pdf",
    }


@router.get("/internal-banking/recipients")
async def list_hq_recipients(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List HQ's saved transfer recipients."""
    company_id = _get_hq_company_id()

    result = await db.execute(
        text("""
            SELECT id, name, bank_name, routing_number, account_number, account_type,
                   is_verified, created_at
            FROM banking_recipient
            WHERE company_id = :company_id
            ORDER BY name
        """),
        {"company_id": company_id}
    )
    rows = result.fetchall()

    return [
        {
            "id": row.id,
            "name": row.name,
            "bank_name": row.bank_name,
            "routing_number": row.routing_number,
            "account_number": row.account_number,
            "account_type": row.account_type,
            "is_verified": row.is_verified,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.delete("/internal-banking/recipients/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hq_recipient(
    recipient_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a saved recipient."""
    company_id = _get_hq_company_id()

    result = await db.execute(
        text("""
            DELETE FROM banking_recipient
            WHERE id = :recipient_id AND company_id = :company_id
        """),
        {"recipient_id": recipient_id, "company_id": company_id}
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")


# ============================================================================
# HQ Banking Onboarding Endpoints
# ============================================================================

class HQBankingOnboardingStatusResponse(BaseModel):
    """Response model for HQ banking onboarding status."""
    status: str  # not_started, pending, in_review, approved, rejected, active
    application_id: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class HQBankingApplicationSubmit(BaseModel):
    """Request model for submitting HQ banking application."""
    # Business info
    business_legal_name: str
    business_dba: Optional[str] = None
    business_type: str  # llc, corporation, partnership, sole_proprietorship
    business_ein: str
    business_formation_date: Optional[str] = None
    business_state: Optional[str] = None
    business_phone: Optional[str] = None
    business_website: Optional[str] = None
    business_address: Optional[str] = None
    business_industry: Optional[str] = None

    # Primary applicant
    applicant_first_name: str
    applicant_last_name: str
    applicant_email: str
    applicant_phone: Optional[str] = None
    applicant_title: Optional[str] = None
    applicant_dob: Optional[str] = None
    applicant_ssn: Optional[str] = None
    applicant_address: Optional[str] = None
    applicant_ownership_percent: Optional[float] = None

    # Account choices
    account_types: List[str] = ["checking"]  # checking, savings
    initial_deposit: Optional[float] = None


@router.get("/internal-banking/onboarding/status", response_model=HQBankingOnboardingStatusResponse)
async def get_hq_banking_onboarding_status(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> HQBankingOnboardingStatusResponse:
    """Get HQ banking onboarding/KYB status."""
    from app.models.banking import BankingApplication, BankingAccount

    company_id = _get_hq_company_id()

    # Check if there's already an approved application with active accounts
    accounts_result = await db.execute(
        select(BankingAccount).where(
            BankingAccount.company_id == company_id,
            BankingAccount.status == "active"
        ).limit(1)
    )
    active_account = accounts_result.scalar_one_or_none()

    if active_account:
        return HQBankingOnboardingStatusResponse(
            status="active",
            application_id=None,
            submitted_at=None,
            reviewed_at=None,
            rejection_reason=None
        )

    # Check for existing application
    result = await db.execute(
        select(BankingApplication)
        .where(BankingApplication.company_id == company_id)
        .order_by(BankingApplication.created_at.desc())
        .limit(1)
    )
    application = result.scalar_one_or_none()

    if not application:
        return HQBankingOnboardingStatusResponse(
            status="not_started",
            application_id=None,
            submitted_at=None,
            reviewed_at=None,
            rejection_reason=None
        )

    # Map application status to onboarding status
    status_map = {
        "draft": "pending",
        "submitted": "pending",
        "pending_review": "in_review",
        "approved": "approved",
        "rejected": "rejected",
        "needs_info": "pending",
        "synctera_error": "pending",
    }
    onboarding_status = status_map.get(application.status, "pending")

    return HQBankingOnboardingStatusResponse(
        status=onboarding_status,
        application_id=application.id,
        submitted_at=application.submitted_at,
        reviewed_at=application.reviewed_at,
        rejection_reason=application.rejection_reason
    )


@router.post("/internal-banking/onboarding/apply", status_code=status.HTTP_201_CREATED)
async def submit_hq_banking_application(
    payload: HQBankingApplicationSubmit,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Submit HQ banking application for KYB review."""
    from app.models.banking import BankingApplication, BankingBusiness, BankingPerson
    import uuid
    from datetime import datetime

    company_id = _get_hq_company_id()

    # Check for existing pending application
    existing_result = await db.execute(
        select(BankingApplication)
        .where(
            BankingApplication.company_id == company_id,
            BankingApplication.status.in_(["submitted", "pending_review", "approved"])
        )
        .limit(1)
    )
    existing_app = existing_result.scalar_one_or_none()

    if existing_app:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An application is already in progress or approved"
        )

    # Create the application
    app_id = str(uuid.uuid4())
    reference = f"HQ-{datetime.now().strftime('%Y%m%d')}-{app_id[:8].upper()}"

    application = BankingApplication(
        id=app_id,
        company_id=company_id,
        reference=reference,
        status="submitted",
        account_choices={"types": payload.account_types, "initial_deposit": payload.initial_deposit},
        submitted_at=datetime.utcnow(),
    )
    db.add(application)

    # Create business record
    business_id = str(uuid.uuid4())
    business = BankingBusiness(
        id=business_id,
        application_id=app_id,
        legal_name=payload.business_legal_name,
        dba=payload.business_dba,
        entity_type=payload.business_type,
        ein=payload.business_ein,
        formation_date=datetime.strptime(payload.business_formation_date, "%Y-%m-%d").date() if payload.business_formation_date else None,
        state_of_formation=payload.business_state,
        phone=payload.business_phone,
        website=payload.business_website,
        physical_address=payload.business_address,
        industry_description=payload.business_industry,
    )
    db.add(business)

    # Create primary applicant record
    person_id = str(uuid.uuid4())
    person = BankingPerson(
        id=person_id,
        application_id=app_id,
        person_type="primary",
        first_name=payload.applicant_first_name,
        last_name=payload.applicant_last_name,
        email=payload.applicant_email,
        phone=payload.applicant_phone,
        role=payload.applicant_title,
        dob=datetime.strptime(payload.applicant_dob, "%Y-%m-%d").date() if payload.applicant_dob else None,
        ssn_last4=payload.applicant_ssn[-4:] if payload.applicant_ssn and len(payload.applicant_ssn) >= 4 else None,
        address=payload.applicant_address,
        ownership_pct=payload.applicant_ownership_percent,
    )
    db.add(person)

    # Update application with primary person
    application.primary_person_id = person_id

    await db.commit()

    return {
        "application_id": app_id,
        "reference": reference,
        "status": "submitted",
        "message": "Application submitted successfully. You will be notified once reviewed."
    }


# ============================================================================
# HQ HR & Payroll Endpoints
# ============================================================================

from app.services.hq_hr import HQHREmployeeService, HQPayrollService
from app.schemas.hq import (
    HQHREmployeeCreate,
    HQHREmployeeUpdate,
    HQHREmployeeResponse,
    HQPayrollRunCreate,
    HQPayrollRunResponse,
)


class HQHRStatsResponse(BaseModel):
    """HR statistics response."""
    totalEmployees: int
    activeEmployees: int
    onboarding: int
    totalAnnualSalary: float
    totalPayrolls: int = 0
    pendingApproval: int = 0
    ytdGross: float = 0
    ytdTaxes: float = 0
    ytdNet: float = 0
    lastPayrollDate: Optional[str] = None
    lastPayrollAmount: float = 0

    model_config = {"from_attributes": True}


@router.get("/hr/stats", response_model=HQHRStatsResponse)
async def get_hq_hr_stats(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> HQHRStatsResponse:
    """Get HQ HR and payroll statistics."""
    hr_service = HQHREmployeeService(db)
    payroll_service = HQPayrollService(db)

    hr_stats = await hr_service.get_hr_stats()
    payroll_stats = await payroll_service.get_payroll_stats()

    return HQHRStatsResponse(
        totalEmployees=hr_stats["total_employees"],
        activeEmployees=hr_stats["active_employees"],
        onboarding=hr_stats["onboarding"],
        totalAnnualSalary=hr_stats["total_annual_salary"],
        totalPayrolls=payroll_stats["total_payrolls"],
        pendingApproval=payroll_stats["pending_approval"],
        ytdGross=payroll_stats["ytd_gross"],
        ytdTaxes=payroll_stats["ytd_taxes"],
        ytdNet=payroll_stats["ytd_net"],
        lastPayrollDate=payroll_stats["last_payroll_date"],
        lastPayrollAmount=payroll_stats["last_payroll_amount"],
    )


@router.get("/hr/employees", response_model=List[HQHREmployeeResponse])
async def list_hq_hr_employees(
    status: Optional[str] = None,
    department: Optional[str] = None,
    employment_type: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> List[HQHREmployeeResponse]:
    """List all HQ HR employees."""
    service = HQHREmployeeService(db)
    employees = await service.list_employees(
        status=status,
        department=department,
        employment_type=employment_type,
    )
    return [HQHREmployeeResponse.from_orm_model(e) for e in employees]


@router.get("/hr/employees/{employee_id}", response_model=HQHREmployeeResponse)
async def get_hq_hr_employee(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> HQHREmployeeResponse:
    """Get a specific HQ HR employee."""
    service = HQHREmployeeService(db)
    employee = await service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return HQHREmployeeResponse.from_orm_model(employee)


@router.post("/hr/employees", response_model=HQHREmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_hq_hr_employee(
    payload: HQHREmployeeCreate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> HQHREmployeeResponse:
    """Create a new HQ HR employee."""
    service = HQHREmployeeService(db)
    employee = await service.create_employee(payload)
    return HQHREmployeeResponse.from_orm_model(employee)


@router.patch("/hr/employees/{employee_id}", response_model=HQHREmployeeResponse)
async def update_hq_hr_employee(
    employee_id: str,
    payload: HQHREmployeeUpdate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> HQHREmployeeResponse:
    """Update an HQ HR employee."""
    service = HQHREmployeeService(db)
    try:
        employee = await service.update_employee(employee_id, payload)
        return HQHREmployeeResponse.from_orm_model(employee)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/hr/employees/{employee_id}/terminate", response_model=HQHREmployeeResponse)
async def terminate_hq_hr_employee(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> HQHREmployeeResponse:
    """Terminate an HQ HR employee."""
    service = HQHREmployeeService(db)
    try:
        employee = await service.terminate_employee(employee_id)
        return HQHREmployeeResponse.from_orm_model(employee)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/hr/employees/{employee_id}/sync-to-check")
async def sync_employee_to_check(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Sync an employee to Check HQ payroll."""
    from app.services.check import CheckService

    hr_service = HQHREmployeeService(db)
    employee = await hr_service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    if employee.check_employee_id:
        return {"status": "already_synced", "check_employee_id": employee.check_employee_id}

    # Create employee in Check
    check_service = CheckService()
    try:
        check_employee = await check_service.create_employee({
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "email": employee.email,
            "dob": employee.date_of_birth.isoformat() if employee.date_of_birth else None,
            "address": {
                "line1": employee.address_line1,
                "line2": employee.address_line2,
                "city": employee.city,
                "state": employee.state,
                "postal_code": employee.zip_code,
                "country": "US",
            } if employee.address_line1 else None,
        })

        # Update employee with Check ID
        employee.check_employee_id = check_employee.get("id")
        await db.commit()

        return {"status": "synced", "check_employee_id": employee.check_employee_id}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Check API error: {str(e)}")


@router.get("/hr/employees/{employee_id}/onboarding-link")
async def get_employee_onboarding_link(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get Check onboarding link for an employee."""
    from app.services.check import CheckService

    hr_service = HQHREmployeeService(db)
    employee = await hr_service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    if not employee.check_employee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee must be synced to Check first"
        )

    check_service = CheckService()
    try:
        result = await check_service.get_employee_onboarding_link(employee.check_employee_id)
        return {"onboarding_url": result.get("url"), "expires_at": result.get("expires_at")}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Check API error: {str(e)}")


@router.post("/hr/employees/{employee_id}/complete-onboarding")
async def complete_employee_onboarding(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Mark employee onboarding as complete."""
    from app.models.hq_hr import HREmployeeStatus

    hr_service = HQHREmployeeService(db)
    employee = await hr_service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    employee.status = HREmployeeStatus.ACTIVE
    await db.commit()

    return {"status": "completed", "employee_status": "active"}


# Payroll Endpoints

@router.get("/hr/payroll", response_model=List[HQPayrollRunResponse])
async def list_hq_payroll_runs(
    status_filter: Optional[str] = None,
    limit: int = 50,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> List[HQPayrollRunResponse]:
    """List all HQ payroll runs."""
    service = HQPayrollService(db)
    payrolls = await service.list_payroll_runs(status=status_filter, limit=limit)
    return [HQPayrollRunResponse.from_orm_model(p) for p in payrolls]


@router.get("/hr/payroll/{payroll_id}", response_model=HQPayrollRunResponse)
async def get_hq_payroll_run(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> HQPayrollRunResponse:
    """Get a specific payroll run."""
    service = HQPayrollService(db)
    payroll = await service.get_payroll_run(payroll_id)
    if not payroll:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found")
    return HQPayrollRunResponse.from_orm_model(payroll)


@router.post("/hr/payroll", response_model=HQPayrollRunResponse, status_code=status.HTTP_201_CREATED)
async def create_hq_payroll_run(
    payload: HQPayrollRunCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> HQPayrollRunResponse:
    """Create a new payroll run."""
    service = HQPayrollService(db)
    payroll = await service.create_payroll_run(payload, current_employee.id)
    return HQPayrollRunResponse.from_orm_model(payroll)


@router.post("/hr/payroll/{payroll_id}/submit", response_model=HQPayrollRunResponse)
async def submit_hq_payroll_for_approval(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> HQPayrollRunResponse:
    """Submit a payroll run for approval."""
    service = HQPayrollService(db)
    try:
        payroll = await service.submit_for_approval(payroll_id)
        return HQPayrollRunResponse.from_orm_model(payroll)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/hr/payroll/{payroll_id}/approve", response_model=HQPayrollRunResponse)
async def approve_hq_payroll(
    payroll_id: str,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> HQPayrollRunResponse:
    """Approve a payroll run."""
    service = HQPayrollService(db)
    try:
        payroll = await service.approve_payroll(payroll_id, current_employee.id)
        return HQPayrollRunResponse.from_orm_model(payroll)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/hr/payroll/{payroll_id}/process", response_model=HQPayrollRunResponse)
async def process_hq_payroll(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> HQPayrollRunResponse:
    """Process an approved payroll run."""
    service = HQPayrollService(db)
    try:
        payroll = await service.process_payroll(payroll_id)
        return HQPayrollRunResponse.from_orm_model(payroll)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/hr/payroll/{payroll_id}/cancel", response_model=HQPayrollRunResponse)
async def cancel_hq_payroll(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
) -> HQPayrollRunResponse:
    """Cancel a payroll run."""
    service = HQPayrollService(db)
    try:
        payroll = await service.cancel_payroll(payroll_id)
        return HQPayrollRunResponse.from_orm_model(payroll)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


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
# HQ AI Tasks Endpoints (Proxy to main AI tasks for HQ portal)
# ============================================================================

from app.models.ai_task import AITask
from sqlalchemy import select, or_


@router.get("/ai/tasks")
async def list_hq_ai_tasks(
    status: Optional[str] = None,
    agent_type: Optional[str] = None,
    limit: int = 50,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """
    List AI tasks across all tenants for HQ monitoring.

    Query params:
    - status: Filter by status (comma-separated for multiple, e.g. 'queued,planning,in_progress')
    - agent_type: Filter by agent type
    - limit: Max results (default 50)
    """
    query = select(AITask)

    if status:
        # Support comma-separated status values
        statuses = [s.strip() for s in status.split(",")]
        query = query.where(or_(*[AITask.status == s for s in statuses]))

    if agent_type:
        query = query.where(AITask.agent_type == agent_type)

    query = query.order_by(AITask.created_at.desc()).limit(limit)

    result = await db.execute(query)
    tasks = result.scalars().all()

    return [
        {
            "id": str(task.id),
            "company_id": str(task.company_id) if task.company_id else None,
            "agent_type": task.agent_type,
            "task_description": task.task_description,
            "status": task.status,
            "progress_percent": task.progress_percent,
            "result": task.result,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }
        for task in tasks
    ]


@router.get("/ai/tasks/{task_id}")
async def get_hq_ai_task(
    task_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific AI task by ID for HQ monitoring."""
    result = await db.execute(select(AITask).where(AITask.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": str(task.id),
        "company_id": str(task.company_id) if task.company_id else None,
        "agent_type": task.agent_type,
        "task_description": task.task_description,
        "status": task.status,
        "progress_percent": task.progress_percent,
        "result": task.result,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


# ============================================================================
# HQ Integrations Endpoints
# ============================================================================

from app.models.integration import Integration, CompanyIntegration


@router.get("/integrations/connections")
async def list_hq_integration_connections(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """
    List all HQ-level integration connections.

    HQ has its own integrations separate from tenant integrations,
    primarily for platform-level accounting (QuickBooks for HQ revenue, etc).
    """
    from sqlalchemy.orm import selectinload

    # HQ integrations are stored with company_id = None or a special HQ company ID
    query = (
        select(CompanyIntegration)
        .where(CompanyIntegration.company_id.is_(None))
        .options(selectinload(CompanyIntegration.integration))
    )

    result = await db.execute(query)
    connections = result.scalars().all()

    return [
        {
            "id": str(conn.id),
            "company_id": None,
            "integration_id": str(conn.integration_id),
            "status": conn.status or "not-activated",
            "last_sync_at": conn.last_sync_at.isoformat() if conn.last_sync_at else None,
            "last_success_at": conn.last_success_at.isoformat() if conn.last_success_at else None,
            "last_error_at": conn.last_error_at.isoformat() if conn.last_error_at else None,
            "last_error_message": conn.last_error_message,
            "consecutive_failures": conn.consecutive_failures or 0,
            "auto_sync": conn.auto_sync if hasattr(conn, 'auto_sync') else False,
            "sync_interval_minutes": conn.sync_interval_minutes if hasattr(conn, 'sync_interval_minutes') else 60,
            "activated_at": conn.activated_at.isoformat() if hasattr(conn, 'activated_at') and conn.activated_at else None,
            "created_at": conn.created_at.isoformat() if conn.created_at else None,
            "updated_at": conn.updated_at.isoformat() if conn.updated_at else None,
            "integration": {
                "id": str(conn.integration.id),
                "integration_key": conn.integration.integration_key,
                "display_name": conn.integration.display_name,
                "description": conn.integration.description,
                "integration_type": conn.integration.integration_type,
                "auth_type": conn.integration.auth_type,
                "requires_oauth": conn.integration.requires_oauth,
                "status": conn.status or "not-activated",
            } if conn.integration else None,
        }
        for conn in connections
    ]


@router.get("/integrations/available")
async def list_available_integrations(
    integration_type: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """List all available integrations that can be connected."""
    query = select(Integration).where(Integration.is_active == True)

    if integration_type:
        query = query.where(Integration.integration_type == integration_type)

    result = await db.execute(query)
    integrations = result.scalars().all()

    return [
        {
            "id": str(i.id),
            "integration_key": i.integration_key,
            "display_name": i.display_name,
            "description": i.description,
            "integration_type": i.integration_type,
            "auth_type": i.auth_type,
            "requires_oauth": i.requires_oauth,
            "features": i.features if hasattr(i, 'features') else None,
            "support_email": i.support_email if hasattr(i, 'support_email') else None,
            "status": "not-activated",
        }
        for i in integrations
    ]


@router.get("/integrations/health")
async def get_integration_health(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """
    Get overall health status of all tenant integrations (for monitoring).

    This is an admin view to monitor integration health across all tenants.
    """
    from sqlalchemy.orm import selectinload

    # Get all company integrations with their status
    query = (
        select(CompanyIntegration)
        .options(selectinload(CompanyIntegration.integration))
    )

    result = await db.execute(query)
    connections = result.scalars().all()

    # Calculate statistics
    total = len(connections)
    active = sum(1 for c in connections if c.status == "active")
    error = sum(1 for c in connections if c.status == "error")
    healthy = sum(1 for c in connections if c.status == "active" and (c.consecutive_failures or 0) == 0)
    warning = sum(1 for c in connections if c.status == "active" and 0 < (c.consecutive_failures or 0) < 3)
    critical = sum(1 for c in connections if (c.consecutive_failures or 0) >= 3)

    # Group by integration type
    by_type = {}
    for conn in connections:
        if conn.integration:
            key = conn.integration.integration_key
            if key not in by_type:
                by_type[key] = {
                    "integration_type": conn.integration.integration_type,
                    "integration_key": key,
                    "integration_name": conn.integration.display_name,
                    "total_connections": 0,
                    "active_connections": 0,
                    "error_connections": 0,
                }
            by_type[key]["total_connections"] += 1
            if conn.status == "active":
                by_type[key]["active_connections"] += 1
            if conn.status == "error":
                by_type[key]["error_connections"] += 1

    # Get recent errors
    recent_errors = [
        {
            "id": str(c.id),
            "company_id": str(c.company_id) if c.company_id else None,
            "integration_key": c.integration.integration_key if c.integration else "unknown",
            "integration_name": c.integration.display_name if c.integration else "Unknown",
            "integration_type": c.integration.integration_type if c.integration else "unknown",
            "status": c.status,
            "last_error_at": c.last_error_at.isoformat() if c.last_error_at else None,
            "last_error_message": c.last_error_message,
            "consecutive_failures": c.consecutive_failures or 0,
        }
        for c in connections
        if c.status == "error" or (c.consecutive_failures or 0) > 0
    ][:10]  # Limit to 10 most recent

    return {
        "total_connections": total,
        "active_connections": active,
        "error_connections": error,
        "healthy_connections": healthy,
        "warning_connections": warning,
        "critical_connections": critical,
        "by_type": list(by_type.values()),
        "recent_errors": recent_errors,
    }


# ============================================================================
# HQ QuickBooks Integration Endpoints
# ============================================================================

from app.services.quickbooks.quickbooks_service import QuickBooksService


@router.get("/integrations/quickbooks/{integration_id}/sync/summary")
async def hq_quickbooks_sync_summary(
    integration_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """Get summary of QuickBooks data and sync status for HQ."""
    result = await db.execute(
        select(CompanyIntegration).where(CompanyIntegration.id == integration_id)
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        return await service.get_sync_summary(integration)
    except Exception as e:
        logger.error(f"QuickBooks sync summary error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/integrations/quickbooks/{integration_id}/sync/{entity}")
async def hq_quickbooks_sync_entity(
    integration_id: str,
    entity: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """Sync a specific entity (customers, invoices, vendors, bills) from QuickBooks for HQ."""
    result = await db.execute(
        select(CompanyIntegration).where(CompanyIntegration.id == integration_id)
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        if entity == "customers":
            return await service.sync_customers(integration)
        elif entity == "invoices":
            return await service.sync_invoices(integration)
        elif entity == "vendors":
            return await service.sync_vendors(integration)
        elif entity == "bills":
            return await service.sync_bills(integration)
        elif entity == "full":
            return await service.full_sync(integration)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown entity: {entity}")
    except Exception as e:
        logger.error(f"QuickBooks sync {entity} error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/integrations/quickbooks/{integration_id}/oauth/authorize")
async def hq_quickbooks_oauth_authorize(
    integration_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """Generate QuickBooks OAuth authorization URL for HQ."""
    from app.core.settings import settings

    result = await db.execute(
        select(CompanyIntegration).where(CompanyIntegration.id == integration_id)
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    try:
        # Build OAuth URL
        credentials = integration.credentials or {}
        client_id = credentials.get("client_id")

        if not client_id:
            raise HTTPException(status_code=400, detail="Client ID not configured")

        redirect_uri = f"{settings.get_api_base_url()}/hq/integrations/quickbooks/{integration_id}/oauth/callback"

        # QuickBooks OAuth URL
        auth_url = (
            f"https://appcenter.intuit.com/connect/oauth2"
            f"?client_id={client_id}"
            f"&response_type=code"
            f"&scope=com.intuit.quickbooks.accounting"
            f"&redirect_uri={redirect_uri}"
            f"&state={integration_id}"
        )

        return {"success": True, "authorization_url": auth_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QuickBooks OAuth authorize error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/integrations/quickbooks/{integration_id}/test-connection")
async def hq_quickbooks_test_connection(
    integration_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """Test QuickBooks connection for HQ."""
    result = await db.execute(
        select(CompanyIntegration).where(CompanyIntegration.id == integration_id)
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    try:
        service = QuickBooksService(db)
        return await service.test_connection(integration)
    except Exception as e:
        logger.error(f"QuickBooks connection test error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/integrations/company/{integration_id}")
async def hq_update_integration_connection(
    integration_id: str,
    update_data: dict,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db),
):
    """Update an integration connection (credentials, config) for HQ."""
    result = await db.execute(
        select(CompanyIntegration).where(CompanyIntegration.id == integration_id)
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    try:
        if "credentials" in update_data:
            # Merge with existing credentials
            existing_creds = integration.credentials or {}
            existing_creds.update(update_data["credentials"])
            integration.credentials = existing_creds

        if "config" in update_data:
            existing_config = integration.config or {}
            existing_config.update(update_data["config"])
            integration.config = existing_config

        if "status" in update_data:
            integration.status = update_data["status"]

        if "auto_sync" in update_data:
            integration.auto_sync = update_data["auto_sync"]

        if "sync_interval_minutes" in update_data:
            integration.sync_interval_minutes = update_data["sync_interval_minutes"]

        await db.commit()
        await db.refresh(integration)

        return {"success": True, "message": "Integration updated successfully"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Update integration error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HQ Chat Endpoints (Unified Team + AI Chat)
# ============================================================================

from app.services.hq_chat import HQChatService
from app.schemas.hq import (
    HQChatChannelCreate,
    HQChatChannelResponse,
    HQChatMessageCreate,
    HQChatMessageResponse,
)


async def _get_chat_service(db: AsyncSession = Depends(get_db)) -> HQChatService:
    """Get HQ Chat service instance."""
    return HQChatService(db)


from app.services.hq_presence import HQPresenceService
from app.schemas.presence import PresenceState, PresenceUpdate, SetAwayMessage


async def _get_hq_presence_service(db: AsyncSession = Depends(get_db)) -> HQPresenceService:
    """Get HQ Presence service instance."""
    return HQPresenceService(db)


@router.get("/chat/channels", response_model=List[HQChatChannelResponse])
async def list_chat_channels(
    _: HQEmployee = Depends(get_current_hq_employee),
    service: HQChatService = Depends(_get_chat_service),
) -> List[HQChatChannelResponse]:
    """List all HQ chat channels."""
    # Ensure default channels exist
    await service.ensure_default_channels()
    return await service.list_channels()


@router.post("/chat/channels", response_model=HQChatChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_channel(
    payload: HQChatChannelCreate,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: HQChatService = Depends(_get_chat_service),
) -> HQChatChannelResponse:
    """Create a new chat channel."""
    return await service.create_channel(payload)


@router.get("/chat/channels/{channel_id}", response_model=HQChatChannelResponse)
async def get_chat_channel(
    channel_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: HQChatService = Depends(_get_chat_service),
) -> HQChatChannelResponse:
    """Get a specific chat channel."""
    try:
        return await service.get_channel(channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/chat/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_channel(
    channel_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: HQChatService = Depends(_get_chat_service),
) -> None:
    """Delete a chat channel."""
    try:
        await service.delete_channel(channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/chat/channels/{channel_id}/messages", response_model=List[HQChatMessageResponse])
async def list_chat_messages(
    channel_id: str,
    limit: int = 100,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: HQChatService = Depends(_get_chat_service),
) -> List[HQChatMessageResponse]:
    """Get messages for a chat channel."""
    try:
        await service.get_channel(channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return await service.list_messages(channel_id, limit=limit)


@router.post("/chat/channels/{channel_id}/messages", response_model=List[HQChatMessageResponse], status_code=status.HTTP_201_CREATED)
async def post_chat_message(
    channel_id: str,
    payload: HQChatMessageCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    service: HQChatService = Depends(_get_chat_service),
) -> List[HQChatMessageResponse]:
    """
    Post a message to a chat channel.

    For AI channels, this will also return the AI response.
    Returns a list containing the user message and optionally the AI response.
    """
    author_name = f"{current_employee.first_name} {current_employee.last_name}"

    try:
        user_msg, ai_msg = await service.post_message(
            channel_id=channel_id,
            author_id=current_employee.id,
            author_name=author_name,
            payload=payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    result = [user_msg]
    if ai_msg:
        result.append(ai_msg)

    return result


@router.post("/chat/channels/{channel_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_messages_read(
    channel_id: str,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    service: HQChatService = Depends(_get_chat_service),
) -> None:
    """Mark all messages in a channel as read."""
    await service.mark_messages_read(channel_id, current_employee.id)


@router.get("/chat/employees", response_model=List[dict])
async def list_chat_employees(
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    service: HQChatService = Depends(_get_chat_service),
) -> List[dict]:
    """List all employees available for chat (for starting DMs or group chats)."""
    return await service.list_employees_for_chat(exclude_id=str(current_employee.id))


@router.post("/chat/dm", response_model=HQChatChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_direct_message(
    payload: dict,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    service: HQChatService = Depends(_get_chat_service),
    db: AsyncSession = Depends(get_db),
) -> HQChatChannelResponse:
    """Create or get existing direct message channel with another employee."""
    from sqlalchemy import select

    target_id = payload.get("employeeId") or payload.get("employee_id")
    if not target_id:
        raise HTTPException(status_code=400, detail="employeeId is required")

    # Get target employee's name
    result = await db.execute(
        select(HQEmployee).where(HQEmployee.id == target_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Employee not found")

    return await service.create_direct_message(
        current_employee_id=str(current_employee.id),
        current_employee_name=f"{current_employee.first_name} {current_employee.last_name}",
        target_employee_id=target_id,
        target_employee_name=f"{target.first_name} {target.last_name}"
    )


@router.post("/chat/group", response_model=HQChatChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_group_chat(
    payload: dict,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    service: HQChatService = Depends(_get_chat_service),
    db: AsyncSession = Depends(get_db),
) -> HQChatChannelResponse:
    """Create a new group chat with multiple participants."""
    from sqlalchemy import select

    name = payload.get("name")
    description = payload.get("description")
    participant_ids = payload.get("participantIds") or payload.get("participant_ids") or []

    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not participant_ids:
        raise HTTPException(status_code=400, detail="participantIds is required")

    # Get participant names
    result = await db.execute(
        select(HQEmployee).where(HQEmployee.id.in_(participant_ids))
    )
    employees = result.scalars().all()
    participant_names = {str(e.id): f"{e.first_name} {e.last_name}" for e in employees}

    return await service.create_group_chat(
        creator_id=str(current_employee.id),
        creator_name=f"{current_employee.first_name} {current_employee.last_name}",
        name=name,
        description=description,
        participant_ids=participant_ids,
        participant_names=participant_names
    )


@router.post("/chat/channels/{channel_id}/participants", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_channel_participant(
    channel_id: str,
    payload: dict,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: HQChatService = Depends(_get_chat_service),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a participant to a channel."""
    from sqlalchemy import select

    employee_id = payload.get("employeeId") or payload.get("employee_id")
    if not employee_id:
        raise HTTPException(status_code=400, detail="employeeId is required")

    # Get employee's name
    result = await db.execute(
        select(HQEmployee).where(HQEmployee.id == employee_id)
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    try:
        participant = await service.add_participant(
            channel_id=channel_id,
            employee_id=employee_id,
            employee_name=f"{employee.first_name} {employee.last_name}"
        )
        return participant.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/chat/channels/{channel_id}/participants/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_channel_participant(
    channel_id: str,
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: HQChatService = Depends(_get_chat_service),
) -> None:
    """Remove a participant from a channel."""
    try:
        await service.remove_participant(channel_id, employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/chat/upload", response_model=dict)
async def upload_chat_file(
    file: UploadFile = File(...),
    current_employee: HQEmployee = Depends(get_current_hq_employee),
) -> dict:
    """
    Upload a file for chat attachment using Cloudflare R2.

    Supports images, documents, and other file types.
    Returns the file metadata including the public URL.
    """
    import uuid
    from app.services.storage import StorageService

    # Validate file size (max 25MB)
    max_size = 25 * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 25MB."
        )

    # Validate file type
    allowed_types = {
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain", "text/csv",
    }
    content_type = file.content_type or "application/octet-stream"
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{content_type}' not allowed."
        )

    try:
        # Upload to Cloudflare R2
        storage = StorageService()
        key = await storage.upload_file(
            file_content=content,
            filename=file.filename or "unnamed_file",
            prefix="hq-chat",
            content_type=content_type,
        )

        # Get public URL
        public_url = storage.get_public_url(key)
        if not public_url:
            # Fall back to presigned URL if no public URL configured
            public_url = storage.get_file_url(key, expires_in=86400 * 7)  # 7 days

        # Generate thumbnail URL for images
        thumbnail_url = None
        if content_type.startswith("image/"):
            thumbnail_url = public_url  # Could add image processing for thumbnails

        file_id = str(uuid.uuid4())

        return {
            "id": file_id,
            "filename": file.filename or "unnamed_file",
            "fileType": content_type,
            "fileSize": len(content),
            "url": public_url,
            "thumbnailUrl": thumbnail_url,
            "key": key,  # Store key for potential deletion
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


# ============================================================================
# HQ Presence Endpoints
# ============================================================================

@router.get("/presence", response_model=List[PresenceState])
async def list_all_presence(
    _: HQEmployee = Depends(get_current_hq_employee),
    presence_service: HQPresenceService = Depends(_get_hq_presence_service),
) -> List[PresenceState]:
    """Get presence status for all HQ employees."""
    return await presence_service.get_all_presence()


@router.get("/presence/me", response_model=PresenceState)
async def get_my_presence(
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    presence_service: HQPresenceService = Depends(_get_hq_presence_service),
) -> PresenceState:
    """Get current employee's presence status."""
    state = await presence_service.get_employee_presence(str(current_employee.id))
    if not state:
        # Create initial presence if not exists
        state = await presence_service.set_presence(str(current_employee.id), "online")
    return state


@router.put("/presence", response_model=PresenceState)
async def update_my_presence(
    payload: PresenceUpdate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    presence_service: HQPresenceService = Depends(_get_hq_presence_service),
) -> PresenceState:
    """Update current employee's presence status."""
    return await presence_service.set_presence(
        str(current_employee.id),
        payload.status,
        payload.away_message,
        manual=True,
    )


@router.post("/presence/heartbeat", response_model=PresenceState)
async def presence_heartbeat(
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    presence_service: HQPresenceService = Depends(_get_hq_presence_service),
) -> PresenceState:
    """Send heartbeat to indicate employee activity."""
    state = await presence_service.update_activity(str(current_employee.id))
    if not state:
        state = await presence_service.set_presence(str(current_employee.id), "online")
    return state


@router.put("/presence/away-message", response_model=PresenceState)
async def set_my_away_message(
    payload: SetAwayMessage,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    presence_service: HQPresenceService = Depends(_get_hq_presence_service),
) -> PresenceState:
    """Set or clear away message for current employee."""
    state = await presence_service.set_away_message(
        str(current_employee.id), payload.away_message
    )
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presence not found")
    return state


@router.get("/presence/{employee_id}", response_model=PresenceState)
async def get_employee_presence(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    presence_service: HQPresenceService = Depends(_get_hq_presence_service),
) -> PresenceState:
    """Get presence status for a specific employee."""
    state = await presence_service.get_employee_presence(employee_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Presence not found")
    return state


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


@router.post("/leads/import-fmcsa", response_model=HQLeadImportResponse)
async def import_leads_from_fmcsa(
    data: HQLeadFMCSAImportRequest,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """
    Import leads from FMCSA Motor Carrier Census data.

    Fetches active carriers from government open data based on fleet size and state filters.
    Automatically skips companies that already exist as leads.
    """
    from app.services.hq_leads import HQLeadService

    lead_service = HQLeadService(db)
    leads_created, errors = await lead_service.import_leads_from_fmcsa(
        state=data.state,
        min_trucks=data.min_trucks,
        max_trucks=data.max_trucks,
        limit=data.limit,
        assign_to_sales_rep_id=data.assign_to_sales_rep_id,
        created_by_id=current_employee.id,
        auto_assign_round_robin=data.auto_assign_round_robin,
        authority_days=data.authority_days,
    )

    return HQLeadImportResponse(
        leads_created=leads_created,
        errors=errors,
        total_parsed=len(leads_created) + len(errors),
        total_created=len(leads_created),
    )


@router.post("/leads/enrich", response_model=HQLeadEnrichResponse)
async def enrich_leads_with_ai(
    data: HQLeadEnrichRequest,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """
    Use AI to find and add contact information to leads.

    The AI will search for owner names, emails, phone numbers, and other details
    for the specified leads and update them with found information.
    """
    from app.services.hq_leads import HQLeadService

    lead_service = HQLeadService(db)
    enriched_leads, errors = await lead_service.enrich_leads_batch(data.lead_ids)

    return HQLeadEnrichResponse(
        enriched_leads=enriched_leads,
        errors=errors,
        total_enriched=len(enriched_leads),
    )


@router.post("/leads/{lead_id}/enrich", response_model=HQLeadResponse)
async def enrich_single_lead(
    lead_id: str,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """
    Use AI to find and add contact information to a single lead.
    """
    from app.services.hq_leads import HQLeadService

    lead_service = HQLeadService(db)
    result = await lead_service.enrich_lead_with_ai(lead_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return result


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


# ============================================================================
# AI Approval Queue Endpoints (Level 2 Autonomy)
# ============================================================================

from app.schemas.hq import (
    HQAIActionResponse, HQAIActionApprove, HQAIActionReject,
    HQAIQueueStats, HQAIAutonomyRuleResponse
)


@router.get("/ai-queue", response_model=List[HQAIActionResponse])
async def get_ai_queue(
    action_type: Optional[str] = None,
    current_employee: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get pending AI actions for the approval queue.

    Sales managers see only their assigned actions.
    Admins see all actions.
    """
    from app.services.hq_ai_queue import HQAIQueueService
    from app.models.hq_ai_queue import AIActionType

    queue_service = HQAIQueueService(db)

    # Sales managers only see their assigned actions
    assigned_to = None
    if current_employee.role.value == "SALES_MANAGER":
        assigned_to = current_employee.id

    at = AIActionType(action_type) if action_type else None

    actions = await queue_service.get_pending_actions(
        assigned_to_id=assigned_to,
        action_type=at,
    )

    return [
        HQAIActionResponse(
            id=a.id,
            action_type=a.action_type.value,
            risk_level=a.risk_level.value,
            status=a.status.value,
            agent_name=a.agent_name,
            title=a.title,
            description=a.description,
            draft_content=a.draft_content,
            ai_reasoning=a.ai_reasoning,
            entity_type=a.entity_type,
            entity_id=a.entity_id,
            entity_name=a.entity_name,
            risk_factors=a.risk_factors,
            assigned_to_id=a.assigned_to_id,
            reviewed_by_id=a.reviewed_by_id,
            reviewed_at=a.reviewed_at,
            human_edits=a.human_edits,
            rejection_reason=a.rejection_reason,
            was_edited=a.was_edited,
            created_at=a.created_at,
            expires_at=a.expires_at,
            executed_at=a.executed_at,
        )
        for a in actions
    ]


@router.get("/ai-queue/stats", response_model=HQAIQueueStats)
async def get_ai_queue_stats(
    _: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get AI approval queue statistics."""
    from app.services.hq_ai_queue import HQAIQueueService

    queue_service = HQAIQueueService(db)
    stats = await queue_service.get_queue_stats()
    return HQAIQueueStats(**stats)


@router.get("/ai-queue/{action_id}", response_model=HQAIActionResponse)
async def get_ai_action(
    action_id: str,
    _: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific AI action by ID."""
    from app.services.hq_ai_queue import HQAIQueueService

    queue_service = HQAIQueueService(db)
    action = await queue_service.get_action(action_id)

    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")

    return HQAIActionResponse(
        id=action.id,
        action_type=action.action_type.value,
        risk_level=action.risk_level.value,
        status=action.status.value,
        agent_name=action.agent_name,
        title=action.title,
        description=action.description,
        draft_content=action.draft_content,
        ai_reasoning=action.ai_reasoning,
        entity_type=action.entity_type,
        entity_id=action.entity_id,
        entity_name=action.entity_name,
        risk_factors=action.risk_factors,
        assigned_to_id=action.assigned_to_id,
        reviewed_by_id=action.reviewed_by_id,
        reviewed_at=action.reviewed_at,
        human_edits=action.human_edits,
        rejection_reason=action.rejection_reason,
        was_edited=action.was_edited,
        created_at=action.created_at,
        expires_at=action.expires_at,
        executed_at=action.executed_at,
    )


@router.post("/ai-queue/{action_id}/approve", response_model=HQAIActionResponse)
async def approve_ai_action(
    action_id: str,
    data: HQAIActionApprove,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve an AI action.

    Optionally provide edits to modify the AI's draft before executing.
    The system learns from edits to improve future actions.
    """
    from app.services.hq_ai_queue import HQAIQueueService

    queue_service = HQAIQueueService(db)
    action = await queue_service.approve_action(
        action_id=action_id,
        reviewed_by_id=current_employee.id,
        edits=data.edits,
    )

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found or already processed"
        )

    # Execute the action based on type
    await _execute_approved_action(action, data.edits, db)

    return HQAIActionResponse(
        id=action.id,
        action_type=action.action_type.value,
        risk_level=action.risk_level.value,
        status=action.status.value,
        agent_name=action.agent_name,
        title=action.title,
        description=action.description,
        draft_content=action.draft_content,
        ai_reasoning=action.ai_reasoning,
        entity_type=action.entity_type,
        entity_id=action.entity_id,
        entity_name=action.entity_name,
        risk_factors=action.risk_factors,
        assigned_to_id=action.assigned_to_id,
        reviewed_by_id=action.reviewed_by_id,
        reviewed_at=action.reviewed_at,
        human_edits=action.human_edits,
        rejection_reason=action.rejection_reason,
        was_edited=action.was_edited,
        created_at=action.created_at,
        expires_at=action.expires_at,
        executed_at=action.executed_at,
    )


@router.post("/ai-queue/{action_id}/reject", response_model=HQAIActionResponse)
async def reject_ai_action(
    action_id: str,
    data: HQAIActionReject,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Reject an AI action with a reason."""
    from app.services.hq_ai_queue import HQAIQueueService

    queue_service = HQAIQueueService(db)
    action = await queue_service.reject_action(
        action_id=action_id,
        reviewed_by_id=current_employee.id,
        reason=data.reason,
    )

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found or already processed"
        )

    return HQAIActionResponse(
        id=action.id,
        action_type=action.action_type.value,
        risk_level=action.risk_level.value,
        status=action.status.value,
        agent_name=action.agent_name,
        title=action.title,
        description=action.description,
        draft_content=action.draft_content,
        ai_reasoning=action.ai_reasoning,
        entity_type=action.entity_type,
        entity_id=action.entity_id,
        entity_name=action.entity_name,
        risk_factors=action.risk_factors,
        assigned_to_id=action.assigned_to_id,
        reviewed_by_id=action.reviewed_by_id,
        reviewed_at=action.reviewed_at,
        human_edits=action.human_edits,
        rejection_reason=action.rejection_reason,
        was_edited=action.was_edited,
        created_at=action.created_at,
        expires_at=action.expires_at,
        executed_at=action.executed_at,
    )


async def _execute_approved_action(action, edits: Optional[str], db: AsyncSession):
    """Execute an approved AI action based on its type."""
    from app.models.hq_ai_queue import AIActionType, HQAIAction
    from app.models.hq_lead import HQLead, LeadStatus
    from sqlalchemy import select
    from datetime import datetime

    if action.action_type == AIActionType.LEAD_QUALIFICATION:
        # Update lead with AI analysis
        if action.entity_id:
            result = await db.execute(
                select(HQLead).where(HQLead.id == action.entity_id)
            )
            lead = result.scalar_one_or_none()
            if lead:
                # Determine new status from description
                if "qualified" in action.description.lower():
                    lead.status = LeadStatus.QUALIFIED
                elif "unqualified" in action.description.lower():
                    lead.status = LeadStatus.UNQUALIFIED

                # Add notes (use edits if provided, otherwise draft)
                content = edits or action.draft_content
                if content:
                    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                    if lead.notes:
                        lead.notes = f"{lead.notes}\n\n--- AI Analysis ({timestamp}) ---\n{content}"
                    else:
                        lead.notes = f"--- AI Analysis ({timestamp}) ---\n{content}"

                await db.commit()

    # Add handlers for other action types as needed
    # elif action.action_type == AIActionType.LEAD_OUTREACH:
    #     # Send email, log activity, etc.
    #     pass


# ============================================================================
# Lead Activity & Notes Endpoints
# ============================================================================

from app.schemas.hq import (
    HQLeadActivityResponse, HQNoteCreate, HQNoteUpdate,
    HQFollowUpCreate, HQFollowUpComplete, HQFollowUpSnooze,
    HQCallLogCreate, HQDueFollowUp, HQFollowUpAlerts,
    HQSendEmailRequest, HQEmailTemplateCreate, HQEmailTemplateUpdate,
    HQEmailTemplateResponse, HQRenderTemplateRequest, HQRenderTemplateResponse,
)


@router.get("/leads/{lead_id}/activities", response_model=List[HQLeadActivityResponse])
async def get_lead_activities(
    lead_id: str,
    activity_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    _: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get all activities for a lead."""
    from app.services.hq_lead_activity import HQLeadActivityService
    from app.models.hq_lead_activity import ActivityType

    activity_service = HQLeadActivityService(db)

    activity_types = None
    if activity_type:
        try:
            activity_types = [ActivityType(activity_type)]
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid activity type: {activity_type}")

    activities = await activity_service.get_activities(
        lead_id=lead_id,
        activity_types=activity_types,
        limit=limit,
        offset=offset,
    )

    result = []
    for a in activities:
        resp = HQLeadActivityResponse(
            id=a.id,
            lead_id=a.lead_id,
            activity_type=a.activity_type.value,
            subject=a.subject,
            content=a.content,
            email_from=a.email_from,
            email_to=a.email_to,
            email_cc=a.email_cc,
            email_status=a.email_status,
            email_thread_id=a.email_thread_id,
            follow_up_date=a.follow_up_date,
            follow_up_status=a.follow_up_status.value if a.follow_up_status else None,
            follow_up_completed_at=a.follow_up_completed_at,
            call_duration_seconds=a.call_duration_seconds,
            call_outcome=a.call_outcome,
            is_pinned=a.is_pinned,
            metadata=a.metadata,
            created_by_id=a.created_by_id,
            created_by_name=f"{a.created_by.first_name} {a.created_by.last_name}" if a.created_by else None,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        result.append(resp)

    return result


@router.post("/leads/{lead_id}/notes", response_model=HQLeadActivityResponse)
async def add_lead_note(
    lead_id: str,
    data: HQNoteCreate,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Add a note to a lead."""
    from app.services.hq_lead_activity import HQLeadActivityService

    activity_service = HQLeadActivityService(db)
    activity = await activity_service.add_note(
        lead_id=lead_id,
        content=data.content,
        created_by_id=current_employee.id,
        is_pinned=data.is_pinned,
    )

    return HQLeadActivityResponse(
        id=activity.id,
        lead_id=activity.lead_id,
        activity_type=activity.activity_type.value,
        subject=activity.subject,
        content=activity.content,
        is_pinned=activity.is_pinned,
        created_by_id=activity.created_by_id,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


@router.patch("/leads/activities/{activity_id}", response_model=HQLeadActivityResponse)
async def update_lead_note(
    activity_id: str,
    data: HQNoteUpdate,
    _: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Update a note."""
    from app.services.hq_lead_activity import HQLeadActivityService

    activity_service = HQLeadActivityService(db)
    activity = await activity_service.update_note(
        activity_id=activity_id,
        content=data.content,
        is_pinned=data.is_pinned,
    )

    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found or not a note")

    return HQLeadActivityResponse(
        id=activity.id,
        lead_id=activity.lead_id,
        activity_type=activity.activity_type.value,
        subject=activity.subject,
        content=activity.content,
        is_pinned=activity.is_pinned,
        created_by_id=activity.created_by_id,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


@router.delete("/leads/activities/{activity_id}")
async def delete_lead_activity(
    activity_id: str,
    _: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Delete an activity."""
    from app.services.hq_lead_activity import HQLeadActivityService

    activity_service = HQLeadActivityService(db)
    deleted = await activity_service.delete_activity(activity_id)

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")

    return {"status": "deleted"}


# ============================================================================
# Lead Follow-up Endpoints
# ============================================================================

@router.post("/leads/{lead_id}/follow-ups", response_model=HQLeadActivityResponse)
async def create_lead_follow_up(
    lead_id: str,
    data: HQFollowUpCreate,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Create a follow-up reminder for a lead."""
    from app.services.hq_lead_activity import HQLeadActivityService

    activity_service = HQLeadActivityService(db)
    activity = await activity_service.create_follow_up(
        lead_id=lead_id,
        follow_up_date=data.follow_up_date,
        content=data.content,
        created_by_id=current_employee.id,
        subject=data.subject,
    )

    return HQLeadActivityResponse(
        id=activity.id,
        lead_id=activity.lead_id,
        activity_type=activity.activity_type.value,
        subject=activity.subject,
        content=activity.content,
        follow_up_date=activity.follow_up_date,
        follow_up_status=activity.follow_up_status.value if activity.follow_up_status else None,
        created_by_id=activity.created_by_id,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


@router.post("/leads/follow-ups/{activity_id}/complete", response_model=HQLeadActivityResponse)
async def complete_follow_up(
    activity_id: str,
    data: HQFollowUpComplete,
    _: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Complete a follow-up."""
    from app.services.hq_lead_activity import HQLeadActivityService

    activity_service = HQLeadActivityService(db)
    activity = await activity_service.complete_follow_up(
        activity_id=activity_id,
        notes=data.notes,
    )

    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found")

    return HQLeadActivityResponse(
        id=activity.id,
        lead_id=activity.lead_id,
        activity_type=activity.activity_type.value,
        subject=activity.subject,
        content=activity.content,
        follow_up_date=activity.follow_up_date,
        follow_up_status=activity.follow_up_status.value if activity.follow_up_status else None,
        follow_up_completed_at=activity.follow_up_completed_at,
        created_by_id=activity.created_by_id,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


@router.post("/leads/follow-ups/{activity_id}/snooze", response_model=HQLeadActivityResponse)
async def snooze_follow_up(
    activity_id: str,
    data: HQFollowUpSnooze,
    _: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Snooze a follow-up to a new date."""
    from app.services.hq_lead_activity import HQLeadActivityService

    activity_service = HQLeadActivityService(db)
    activity = await activity_service.snooze_follow_up(
        activity_id=activity_id,
        new_date=data.new_date,
    )

    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow-up not found")

    return HQLeadActivityResponse(
        id=activity.id,
        lead_id=activity.lead_id,
        activity_type=activity.activity_type.value,
        subject=activity.subject,
        content=activity.content,
        follow_up_date=activity.follow_up_date,
        follow_up_status=activity.follow_up_status.value if activity.follow_up_status else None,
        created_by_id=activity.created_by_id,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


@router.get("/leads/follow-ups/alerts", response_model=HQFollowUpAlerts)
async def get_follow_up_alerts(
    current_employee: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get follow-up alerts for the current sales rep."""
    from app.services.hq_lead_activity import HQLeadActivityService
    from app.models.hq_employee import HQRole
    from datetime import datetime

    activity_service = HQLeadActivityService(db)

    # Admin sees all, sales reps see their own
    sales_rep_id = None if current_employee.role in [HQRole.SUPER_ADMIN, HQRole.ADMIN] else current_employee.id

    # Get overdue and due today
    due_follow_ups = await activity_service.get_due_follow_ups(
        sales_rep_id=sales_rep_id,
        include_overdue=True,
    )

    # Get upcoming (next 7 days)
    upcoming = await activity_service.get_upcoming_follow_ups(
        sales_rep_id=sales_rep_id,
        days_ahead=7,
    )

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    overdue = []
    due_today = []

    for f in due_follow_ups:
        days_overdue = (now - f.follow_up_date).days if f.follow_up_date < today_start else 0
        is_overdue = f.follow_up_date < today_start

        item = HQDueFollowUp(
            id=f.id,
            lead_id=f.lead_id,
            lead_company_name=f.lead.company_name if f.lead else "Unknown",
            lead_contact_name=f.lead.contact_name if f.lead else None,
            subject=f.subject,
            content=f.content,
            follow_up_date=f.follow_up_date,
            is_overdue=is_overdue,
            days_overdue=days_overdue,
            created_by_name=f"{f.created_by.first_name} {f.created_by.last_name}" if f.created_by else None,
        )

        if is_overdue:
            overdue.append(item)
        else:
            due_today.append(item)

    upcoming_items = [
        HQDueFollowUp(
            id=f.id,
            lead_id=f.lead_id,
            lead_company_name=f.lead.company_name if f.lead else "Unknown",
            lead_contact_name=f.lead.contact_name if f.lead else None,
            subject=f.subject,
            content=f.content,
            follow_up_date=f.follow_up_date,
            is_overdue=False,
            days_overdue=0,
            created_by_name=f"{f.created_by.first_name} {f.created_by.last_name}" if f.created_by else None,
        )
        for f in upcoming
    ]

    return HQFollowUpAlerts(
        overdue_count=len(overdue),
        due_today_count=len(due_today),
        upcoming_count=len(upcoming_items),
        overdue=overdue,
        due_today=due_today,
        upcoming=upcoming_items,
    )


# ============================================================================
# Lead Call Logging Endpoints
# ============================================================================

@router.post("/leads/{lead_id}/calls", response_model=HQLeadActivityResponse)
async def log_lead_call(
    lead_id: str,
    data: HQCallLogCreate,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Log a phone call with a lead."""
    from app.services.hq_lead_activity import HQLeadActivityService

    activity_service = HQLeadActivityService(db)
    activity = await activity_service.log_call(
        lead_id=lead_id,
        created_by_id=current_employee.id,
        outcome=data.outcome,
        notes=data.notes,
        duration_seconds=data.duration_seconds,
    )

    return HQLeadActivityResponse(
        id=activity.id,
        lead_id=activity.lead_id,
        activity_type=activity.activity_type.value,
        subject=activity.subject,
        content=activity.content,
        call_duration_seconds=activity.call_duration_seconds,
        call_outcome=activity.call_outcome,
        created_by_id=activity.created_by_id,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


# ============================================================================
# Lead Email Endpoints
# ============================================================================

@router.post("/leads/{lead_id}/email", response_model=HQLeadActivityResponse)
async def send_lead_email(
    lead_id: str,
    data: HQSendEmailRequest,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Send an email to a lead."""
    from app.services.hq_email import HQEmailService

    email_service = HQEmailService(db)
    activity, error = await email_service.send_email(
        lead_id=lead_id,
        to_email=data.to_email,
        subject=data.subject,
        body=data.body,
        sent_by_id=current_employee.id,
        cc=data.cc,
        template_id=data.template_id,
    )

    if not activity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error or "Failed to send email")

    return HQLeadActivityResponse(
        id=activity.id,
        lead_id=activity.lead_id,
        activity_type=activity.activity_type.value,
        subject=activity.subject,
        content=activity.content,
        email_from=activity.email_from,
        email_to=activity.email_to,
        email_cc=activity.email_cc,
        email_status=activity.email_status,
        email_thread_id=activity.email_thread_id,
        created_by_id=activity.created_by_id,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
    )


# ============================================================================
# Email Template Endpoints
# ============================================================================

@router.get("/email/templates", response_model=List[HQEmailTemplateResponse])
async def list_email_templates(
    category: Optional[str] = None,
    current_employee: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """List available email templates."""
    from app.services.hq_email import HQEmailService

    email_service = HQEmailService(db)
    templates = await email_service.get_templates(
        category=category,
        include_personal=True,
        user_id=current_employee.id,
    )

    return [HQEmailTemplateResponse.model_validate(t, from_attributes=True) for t in templates]


@router.post("/email/templates", response_model=HQEmailTemplateResponse)
async def create_email_template(
    data: HQEmailTemplateCreate,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Create an email template."""
    from app.services.hq_email import HQEmailService

    email_service = HQEmailService(db)
    template = await email_service.create_template(
        name=data.name,
        subject=data.subject,
        body=data.body,
        created_by_id=current_employee.id,
        category=data.category,
        is_global=data.is_global,
        variables=data.variables,
    )

    return HQEmailTemplateResponse.model_validate(template, from_attributes=True)


@router.post("/email/templates/{template_id}/render", response_model=HQRenderTemplateResponse)
async def render_email_template(
    template_id: str,
    lead_id: str,
    custom_vars: Optional[dict] = None,
    _: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Render an email template with lead data for preview."""
    from app.services.hq_email import HQEmailService

    email_service = HQEmailService(db)
    subject, body, error = await email_service.render_template(
        template_id=template_id,
        lead_id=lead_id,
        custom_vars=custom_vars,
    )

    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    return HQRenderTemplateResponse(subject=subject, body=body)


# ============================================================================
# Deals Endpoints (Unified Sales Pipeline)
# ============================================================================

@router.get("/deals", response_model=List[dict])
async def list_deals(
    stage: Optional[str] = None,
    source: Optional[str] = None,
    current_employee: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """List deals. Sales managers only see their own deals."""
    from app.services.hq_deals import HQDealsService

    deal_service = HQDealsService(db)
    return await deal_service.get_deals(
        current_user_id=current_employee.id,
        current_user_role=current_employee.role,
        stage=stage,
        source=source,
    )


@router.get("/deals/summary", response_model=List[dict])
async def get_deals_summary(
    current_employee: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get pipeline summary with counts and values per stage."""
    from app.services.hq_deals import HQDealsService

    deal_service = HQDealsService(db)
    return await deal_service.get_pipeline_summary(
        current_user_id=current_employee.id,
        current_user_role=current_employee.role,
    )


@router.get("/deals/{deal_id}", response_model=dict)
async def get_deal(
    deal_id: str,
    _: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single deal by ID."""
    from app.services.hq_deals import HQDealsService

    deal_service = HQDealsService(db)
    deal = await deal_service.get_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.post("/deals", response_model=dict)
async def create_deal(
    data: HQDealCreate,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new deal."""
    from app.services.hq_deals import HQDealsService

    deal_service = HQDealsService(db)
    deal_data = data.model_dump(by_alias=False)
    return await deal_service.create_deal(deal_data, current_employee.id)


@router.put("/deals/{deal_id}", response_model=dict)
async def update_deal(
    deal_id: str,
    data: HQDealUpdate,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Update a deal."""
    from app.services.hq_deals import HQDealsService

    deal_service = HQDealsService(db)
    deal_data = data.model_dump(exclude_unset=True, by_alias=False)
    deal = await deal_service.update_deal(deal_id, deal_data, current_employee.id)
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.delete("/deals/{deal_id}")
async def delete_deal(
    deal_id: str,
    _: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Delete a deal."""
    from app.services.hq_deals import HQDealsService

    deal_service = HQDealsService(db)
    deleted = await deal_service.delete_deal(deal_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return {"status": "deleted"}


@router.post("/deals/import", response_model=HQDealImportResponse)
async def import_deals_ai(
    data: HQDealImportRequest,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Import deals using AI parsing from CSV, spreadsheet, email, or text content."""
    from app.services.hq_deals import HQDealsService

    deal_service = HQDealsService(db)
    deals_created, errors = await deal_service.import_deals_from_content(
        content=data.content,
        content_type=data.content_type,
        assign_to_sales_rep_id=data.assign_to_sales_rep_id,
        created_by_id=current_employee.id,
        auto_assign_round_robin=data.auto_assign_round_robin,
    )
    return HQDealImportResponse(
        deals_created=deals_created,
        errors=errors,
        total_parsed=len(deals_created) + len(errors),
        total_created=len(deals_created),
    )


@router.post("/deals/import-fmcsa", response_model=HQDealImportResponse)
async def import_deals_from_fmcsa(
    data: HQDealFMCSAImportRequest,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Import deals from FMCSA Motor Carrier Census data."""
    from app.services.hq_deals import HQDealsService

    deal_service = HQDealsService(db)
    deals_created, errors = await deal_service.import_deals_from_fmcsa(
        state=data.state,
        min_trucks=data.min_trucks,
        max_trucks=data.max_trucks,
        limit=data.limit,
        assign_to_sales_rep_id=data.assign_to_sales_rep_id,
        created_by_id=current_employee.id,
        auto_assign_round_robin=data.auto_assign_round_robin,
        authority_days=data.authority_days,
    )
    return HQDealImportResponse(
        deals_created=deals_created,
        errors=errors,
        total_parsed=len(deals_created) + len(errors),
        total_created=len(deals_created),
    )


@router.post("/deals/{deal_id}/enrich", response_model=dict)
async def enrich_deal(
    deal_id: str,
    _: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Use AI to find and add contact information to a deal."""
    from app.services.hq_deals import HQDealsService

    deal_service = HQDealsService(db)
    result = await deal_service.enrich_deal_with_ai(deal_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return result


@router.get("/deals/{deal_id}/activities", response_model=List[dict])
async def get_deal_activities(
    deal_id: str,
    _: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get activities for a deal."""
    from app.services.hq_deals import HQDealsService

    deal_service = HQDealsService(db)
    return await deal_service.get_activities(deal_id)


@router.post("/deals/{deal_id}/activities", response_model=dict)
async def add_deal_activity(
    deal_id: str,
    data: HQDealActivityCreate,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Add an activity to a deal."""
    from app.services.hq_deals import HQDealsService

    deal_service = HQDealsService(db)
    return await deal_service.add_activity(
        deal_id=deal_id,
        activity_type=data.activity_type,
        description=data.description,
        created_by_id=current_employee.id,
    )


# ============================================================================
# Subscription Endpoints
# ============================================================================

@router.get("/subscriptions", response_model=List[dict])
async def list_subscriptions(
    status: Optional[str] = None,
    _: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """List all subscriptions."""
    from app.services.hq_subscriptions import HQSubscriptionsService

    sub_service = HQSubscriptionsService(db)
    return await sub_service.get_subscriptions(status=status)


@router.get("/subscriptions/summary", response_model=dict)
async def get_subscriptions_summary(
    _: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get MRR summary and subscription statistics."""
    from app.services.hq_subscriptions import HQSubscriptionsService

    sub_service = HQSubscriptionsService(db)
    return await sub_service.get_mrr_summary()


@router.get("/subscriptions/{subscription_id}", response_model=dict)
async def get_subscription(
    subscription_id: str,
    _: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single subscription by ID."""
    from app.services.hq_subscriptions import HQSubscriptionsService

    sub_service = HQSubscriptionsService(db)
    subscription = await sub_service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return subscription


@router.post("/subscriptions", response_model=dict)
async def create_subscription(
    data: HQSubscriptionCreate,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new subscription."""
    from app.services.hq_subscriptions import HQSubscriptionsService

    sub_service = HQSubscriptionsService(db)
    sub_data = data.model_dump(by_alias=False)
    return await sub_service.create_subscription(sub_data, current_employee.id)


@router.post("/subscriptions/from-deal/{deal_id}", response_model=dict)
async def create_subscription_from_deal(
    deal_id: str,
    data: HQSubscriptionFromDeal,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Create a subscription from a won deal."""
    from app.services.hq_subscriptions import HQSubscriptionsService

    sub_service = HQSubscriptionsService(db)
    sub_data = data.model_dump(by_alias=False)
    try:
        subscription = await sub_service.create_subscription_from_deal(deal_id, sub_data, current_employee.id)
        if not subscription:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
        return subscription
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/subscriptions/{subscription_id}", response_model=dict)
async def update_subscription(
    subscription_id: str,
    data: HQSubscriptionUpdate,
    current_employee: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Update a subscription."""
    from app.services.hq_subscriptions import HQSubscriptionsService

    sub_service = HQSubscriptionsService(db)
    sub_data = data.model_dump(exclude_unset=True, by_alias=False)
    subscription = await sub_service.update_subscription(subscription_id, sub_data, current_employee.id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return subscription


@router.post("/subscriptions/{subscription_id}/pause", response_model=dict)
async def pause_subscription(
    subscription_id: str,
    reason: Optional[str] = None,
    _: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Pause a subscription."""
    from app.services.hq_subscriptions import HQSubscriptionsService

    sub_service = HQSubscriptionsService(db)
    subscription = await sub_service.pause_subscription(subscription_id, reason)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return subscription


@router.post("/subscriptions/{subscription_id}/resume", response_model=dict)
async def resume_subscription(
    subscription_id: str,
    _: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused subscription."""
    from app.services.hq_subscriptions import HQSubscriptionsService

    sub_service = HQSubscriptionsService(db)
    subscription = await sub_service.resume_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return subscription


@router.post("/subscriptions/{subscription_id}/cancel", response_model=dict)
async def cancel_subscription(
    subscription_id: str,
    reason: Optional[str] = None,
    _: HQEmployee = Depends(require_hq_permission("manage_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a subscription."""
    from app.services.hq_subscriptions import HQSubscriptionsService

    sub_service = HQSubscriptionsService(db)
    subscription = await sub_service.cancel_subscription(subscription_id, reason)
    if not subscription:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return subscription


@router.get("/subscriptions/{subscription_id}/rate-changes", response_model=List[dict])
async def get_subscription_rate_changes(
    subscription_id: str,
    _: HQEmployee = Depends(require_hq_permission("view_tenants")),
    db: AsyncSession = Depends(get_db),
):
    """Get rate change history for a subscription."""
    from app.services.hq_subscriptions import HQSubscriptionsService

    sub_service = HQSubscriptionsService(db)
    return await sub_service.get_rate_changes(subscription_id)


# ============================================================================
# WebSocket Endpoint for HQ Real-time Chat
# ============================================================================

from fastapi import WebSocket, WebSocketDisconnect
from app.services.hq_websocket_manager import hq_manager


async def _get_hq_employee_from_ws_token(token: str, db: AsyncSession) -> Optional[HQEmployee]:
    """Authenticate HQ employee from WebSocket token."""
    from sqlalchemy import select

    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    # Verify this is an HQ token
    if payload.get("type") != "hq":
        return None

    employee_id = payload.get("sub")
    if not employee_id:
        return None

    result = await db.execute(
        select(HQEmployee).where(HQEmployee.id == employee_id, HQEmployee.is_active == True)
    )
    return result.scalar_one_or_none()


@router.websocket("/ws")
async def hq_websocket_endpoint(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for HQ real-time chat updates.

    Clients connect with token as query parameter:
    ws://host/api/hq/ws?token=<hq_access_token>

    Message Types (Client -> Server):
    - ping: Keep-alive
    - subscribe_channel: Subscribe to a channel's messages
    - unsubscribe_channel: Unsubscribe from a channel
    - chat_message: Send a message to a channel (also posts via REST)
    - typing: Typing indicator

    Message Types (Server -> Client):
    - pong: Response to ping
    - system_message: System notifications
    - chat_message / message_received: New chat message
    - channel_created: New channel created
    - channel_deleted: Channel deleted
    - presence_update: Employee online/offline status
    - typing: Typing indicator from other employees
    - error: Error message
    """
    employee = None
    try:
        # Accept the WebSocket connection first
        await websocket.accept()

        # Get token from query params
        token = websocket.query_params.get("token")

        # Authenticate employee from token
        employee = await _get_hq_employee_from_ws_token(token, db)

        if not employee:
            await websocket.send_json({
                "type": "error",
                "data": {"message": "Authentication failed", "code": "auth_failed"}
            })
            await websocket.close(code=1008, reason="Authentication failed")
            return

        # Register with the HQ WebSocket manager
        await hq_manager.connect(websocket, employee)

        # Send welcome message
        await websocket.send_json({
            "type": "system_message",
            "data": {
                "message": "Connected to HQ real-time updates",
                "employee_id": str(employee.id),
                "employee_name": f"{employee.first_name} {employee.last_name}",
            }
        })

        # Broadcast presence update
        await hq_manager.broadcast_to_all({
            "type": "presence_update",
            "data": {
                "employeeId": str(employee.id),
                "employeeName": f"{employee.first_name} {employee.last_name}",
                "status": "online",
                "lastSeen": None,
            }
        })

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "subscribe_channel":
                channel_id = data.get("data", {}).get("channel_id")
                if channel_id:
                    await hq_manager.subscribe_to_channel(str(employee.id), channel_id)
                    await websocket.send_json({
                        "type": "subscription_ack",
                        "data": {"channel_id": channel_id, "status": "subscribed"}
                    })

            elif msg_type == "unsubscribe_channel":
                channel_id = data.get("data", {}).get("channel_id")
                if channel_id:
                    await hq_manager.unsubscribe_from_channel(str(employee.id), channel_id)
                    await websocket.send_json({
                        "type": "subscription_ack",
                        "data": {"channel_id": channel_id, "status": "unsubscribed"}
                    })

            elif msg_type == "chat_message":
                # Handle chat message - broadcast to channel subscribers
                msg_data = data.get("data", {})
                channel_id = msg_data.get("channel_id")
                content = msg_data.get("content")

                if channel_id and content:
                    # Broadcast message to all subscribers of this channel
                    await hq_manager.broadcast_to_channel({
                        "type": "chat_message",
                        "data": {
                            "channelId": channel_id,
                            "authorId": str(employee.id),
                            "authorName": f"{employee.first_name} {employee.last_name}",
                            "content": content,
                            "isAiResponse": False,
                        }
                    }, channel_id)

            elif msg_type == "typing":
                # Broadcast typing indicator
                channel_id = data.get("data", {}).get("channel_id")
                if channel_id:
                    await hq_manager.broadcast_to_channel({
                        "type": "typing",
                        "data": {
                            "channelId": channel_id,
                            "employeeId": str(employee.id),
                            "employeeName": f"{employee.first_name} {employee.last_name}",
                        }
                    }, channel_id)

            elif msg_type == "get_messages":
                # Client requesting message history via WebSocket
                channel_id = data.get("data", {}).get("channel_id")
                limit = data.get("data", {}).get("limit", 100)

                if channel_id:
                    try:
                        service = HQChatService(db)
                        messages = await service.list_messages(channel_id, limit)
                        await websocket.send_json({
                            "type": "message_history",
                            "data": {
                                "channel_id": channel_id,
                                "messages": [msg.model_dump() for msg in messages]
                            }
                        })
                    except Exception as e:
                        logger.error(f"Failed to fetch messages: {e}")

            else:
                logger.warning(f"Unknown HQ WebSocket message type from employee {employee.email}: {msg_type}")

    except WebSocketDisconnect:
        logger.info(f"HQ WebSocket disconnected normally - Employee: {employee.email if employee else 'Unknown'}")
        if employee:
            await hq_manager.disconnect(websocket, employee)
            # Broadcast offline presence
            await hq_manager.broadcast_to_all({
                "type": "presence_update",
                "data": {
                    "employeeId": str(employee.id),
                    "employeeName": f"{employee.first_name} {employee.last_name}",
                    "status": "offline",
                    "lastSeen": None,
                }
            })

    except Exception as e:
        logger.error(f"HQ WebSocket error - Employee: {employee.email if employee else 'Unknown'}: {e}", exc_info=True)
        if employee:
            await hq_manager.disconnect(websocket, employee)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass


# Helper function to broadcast chat messages from REST endpoints
async def broadcast_hq_chat_message(channel_id: str, message_data: dict) -> None:
    """Broadcast a chat message to all WebSocket subscribers of a channel."""
    await hq_manager.broadcast_to_channel({
        "type": "message_received",
        "data": message_data
    }, channel_id)


# ============================================================================
# HQ Check Payroll Proxy Endpoints
# ============================================================================

from app.services.check import CheckService


async def _get_hq_check_service(
    db: AsyncSession = Depends(get_db),
) -> CheckService:
    """Get Check service for HQ (company-level Check integration)."""
    from app.core.config import get_settings
    settings = get_settings()
    # HQ uses its own Check company ID configured in settings
    return CheckService(company_check_id=settings.check_hq_company_id)


# ==================== Check Company Endpoints ====================


@router.get("/check/company", summary="Get HQ Check company")
async def get_hq_check_company(
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Get the Check company for HQ."""
    try:
        return await service.get_company()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/check/company", status_code=status.HTTP_201_CREATED, summary="Create HQ Check company")
async def create_hq_check_company(
    payload: dict,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Create Check company for HQ."""
    try:
        return await service.create_company(payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ==================== Check Employee Endpoints ====================


@router.get("/check/employees", summary="List Check employees")
async def list_hq_check_employees(
    page: int = 1,
    per_page: int = 50,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> List[dict]:
    """List all Check employees."""
    try:
        return await service.list_employees(page=page, per_page=per_page)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/check/employees/{employee_id}", summary="Get Check employee")
async def get_hq_check_employee(
    employee_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Get a Check employee."""
    try:
        return await service.get_employee(employee_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/check/employees", status_code=status.HTTP_201_CREATED, summary="Create Check employee")
async def create_hq_check_employee(
    payload: dict,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Create a Check employee."""
    try:
        return await service.create_employee(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.patch("/check/employees/{employee_id}", summary="Update Check employee")
async def update_hq_check_employee(
    employee_id: str,
    payload: dict,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Update a Check employee."""
    try:
        return await service.update_employee(employee_id, payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ==================== Check Payroll Endpoints ====================


@router.get("/check/payrolls", summary="List Check payrolls")
async def list_hq_check_payrolls(
    page: int = 1,
    per_page: int = 50,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> List[dict]:
    """List Check payroll runs."""
    try:
        return await service.list_payrolls(page=page, per_page=per_page)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/check/payrolls/{payroll_id}", summary="Get Check payroll")
async def get_hq_check_payroll(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Get a Check payroll run."""
    try:
        return await service.get_payroll(payroll_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/check/payrolls", status_code=status.HTTP_201_CREATED, summary="Create Check payroll")
async def create_hq_check_payroll(
    payload: dict,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Create a Check payroll run."""
    try:
        return await service.create_payroll(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/check/payrolls/{payroll_id}/preview", summary="Preview Check payroll")
async def preview_hq_check_payroll(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Preview a Check payroll."""
    try:
        return await service.preview_payroll(payroll_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/check/payrolls/{payroll_id}/approve", summary="Approve Check payroll")
async def approve_hq_check_payroll(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Approve a Check payroll."""
    try:
        return await service.approve_payroll(payroll_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/check/payrolls/{payroll_id}/cancel", summary="Cancel Check payroll")
async def cancel_hq_check_payroll(
    payroll_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Cancel a Check payroll."""
    try:
        return await service.cancel_payroll(payroll_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ==================== Check Benefits Endpoints ====================


@router.get("/check/benefits", summary="List Check benefits")
async def list_hq_check_benefits(
    employee: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> List[dict]:
    """List Check benefits."""
    try:
        return await service.list_benefits(employee_id=employee)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/check/benefits", status_code=status.HTTP_201_CREATED, summary="Create Check benefit")
async def create_hq_check_benefit(
    payload: dict,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Create a Check benefit."""
    try:
        return await service.create_benefit(payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.patch("/check/benefits/{benefit_id}", summary="Update Check benefit")
async def update_hq_check_benefit(
    benefit_id: str,
    payload: dict,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Update a Check benefit."""
    try:
        return await service.update_benefit(benefit_id, payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.delete("/check/benefits/{benefit_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary="Delete Check benefit")
async def delete_hq_check_benefit(
    benefit_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
):
    """Delete a Check benefit."""
    try:
        await service.delete_benefit(benefit_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ==================== Check Company Benefits Endpoints ====================


@router.get("/check/company-benefits", summary="List Check company benefits")
async def list_hq_check_company_benefits(
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> List[dict]:
    """List Check company benefits."""
    try:
        return await service.list_company_benefits()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/check/company-benefits", status_code=status.HTTP_201_CREATED, summary="Create Check company benefit")
async def create_hq_check_company_benefit(
    payload: dict,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Create a Check company benefit."""
    try:
        return await service.create_company_benefit(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.patch("/check/company-benefits/{benefit_id}", summary="Update Check company benefit")
async def update_hq_check_company_benefit(
    benefit_id: str,
    payload: dict,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Update a Check company benefit."""
    try:
        return await service.update_company_benefit(benefit_id, payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.delete("/check/company-benefits/{benefit_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary="Delete Check company benefit")
async def delete_hq_check_company_benefit(
    benefit_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
):
    """Delete a Check company benefit."""
    try:
        await service.delete_company_benefit(benefit_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ==================== Check Contractors Endpoints ====================


@router.get("/check/contractors", summary="List Check contractors")
async def list_hq_check_contractors(
    page: int = 1,
    per_page: int = 50,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> List[dict]:
    """List Check contractors."""
    try:
        return await service.list_contractors(page=page, per_page=per_page)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/check/contractors", status_code=status.HTTP_201_CREATED, summary="Create Check contractor")
async def create_hq_check_contractor(
    payload: dict,
    _: HQEmployee = Depends(get_current_hq_employee),
    service: CheckService = Depends(_get_hq_check_service),
) -> dict:
    """Create a Check contractor."""
    try:
        return await service.create_contractor(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ============================================================================
# Contractor Settlements Endpoints (1099 Payments)
# ============================================================================

from app.schemas.hq import (
    HQContractorSettlementCreate,
    HQContractorSettlementUpdate,
    HQContractorSettlementResponse,
    HQContractorSettlementApproval,
    HQContractorSettlementPayment,
)
from app.models.hq_contractor_settlement import HQContractorSettlement, SettlementStatus
from decimal import Decimal


@router.get("/contractor-settlements", response_model=List[HQContractorSettlementResponse])
async def list_contractor_settlements(
    contractor_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_async_session),
):
    """List contractor settlements."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    query = select(HQContractorSettlement).options(selectinload(HQContractorSettlement.contractor))

    if contractor_id:
        query = query.where(HQContractorSettlement.contractor_id == contractor_id)
    if status_filter:
        query = query.where(HQContractorSettlement.status == SettlementStatus(status_filter))

    query = query.order_by(HQContractorSettlement.created_at.desc())
    result = await db.execute(query)
    settlements = result.scalars().all()

    return [HQContractorSettlementResponse.from_orm_model(s) for s in settlements]


@router.get("/contractor-settlements/{settlement_id}", response_model=HQContractorSettlementResponse)
async def get_contractor_settlement(
    settlement_id: str,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_async_session),
):
    """Get a contractor settlement by ID."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    query = select(HQContractorSettlement).options(
        selectinload(HQContractorSettlement.contractor)
    ).where(HQContractorSettlement.id == settlement_id)
    result = await db.execute(query)
    settlement = result.scalar_one_or_none()

    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    return HQContractorSettlementResponse.from_orm_model(settlement)


@router.post("/contractor-settlements", response_model=HQContractorSettlementResponse, status_code=201)
async def create_contractor_settlement(
    data: HQContractorSettlementCreate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a new contractor settlement."""
    import uuid
    from datetime import datetime
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload

    # Generate settlement number
    year = datetime.now().year
    count_query = select(func.count()).select_from(HQContractorSettlement).where(
        HQContractorSettlement.settlement_number.like(f"SET-{year}-%")
    )
    result = await db.execute(count_query)
    count = result.scalar() or 0
    settlement_number = f"SET-{year}-{count + 1:04d}"

    # Calculate totals from items
    total_commission = Decimal("0")
    total_bonus = Decimal("0")
    total_reimbursements = Decimal("0")
    total_deductions = Decimal("0")

    items_list = []
    for item in data.items:
        item_dict = item.model_dump()
        items_list.append(item_dict)
        amount = Decimal(str(item.amount))
        if item.type == "commission":
            total_commission += amount
        elif item.type == "bonus":
            total_bonus += amount
        elif item.type == "reimbursement":
            total_reimbursements += amount
        elif item.type == "deduction":
            total_deductions += amount

    net_payment = total_commission + total_bonus + total_reimbursements - total_deductions

    settlement = HQContractorSettlement(
        id=str(uuid.uuid4()),
        contractor_id=data.contractor_id,
        period_start=data.period_start,
        period_end=data.period_end,
        payment_date=data.payment_date,
        settlement_number=settlement_number,
        status=SettlementStatus.DRAFT,
        items=items_list,
        total_commission=total_commission,
        total_bonus=total_bonus,
        total_reimbursements=total_reimbursements,
        total_deductions=total_deductions,
        net_payment=net_payment,
        notes=data.notes,
        created_by_id=current_employee.id,
    )

    db.add(settlement)
    await db.commit()
    await db.refresh(settlement)

    # Load contractor relationship
    query = select(HQContractorSettlement).options(
        selectinload(HQContractorSettlement.contractor)
    ).where(HQContractorSettlement.id == settlement.id)
    result = await db.execute(query)
    settlement = result.scalar_one()

    return HQContractorSettlementResponse.from_orm_model(settlement)


@router.put("/contractor-settlements/{settlement_id}", response_model=HQContractorSettlementResponse)
async def update_contractor_settlement(
    settlement_id: str,
    data: HQContractorSettlementUpdate,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_async_session),
):
    """Update a contractor settlement (only draft status)."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    query = select(HQContractorSettlement).options(
        selectinload(HQContractorSettlement.contractor)
    ).where(HQContractorSettlement.id == settlement_id)
    result = await db.execute(query)
    settlement = result.scalar_one_or_none()

    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    if settlement.status != SettlementStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Can only update draft settlements")

    if data.payment_date:
        settlement.payment_date = data.payment_date
    if data.notes is not None:
        settlement.notes = data.notes
    if data.items is not None:
        # Recalculate totals
        total_commission = Decimal("0")
        total_bonus = Decimal("0")
        total_reimbursements = Decimal("0")
        total_deductions = Decimal("0")

        items_list = []
        for item in data.items:
            item_dict = item.model_dump()
            items_list.append(item_dict)
            amount = Decimal(str(item.amount))
            if item.type == "commission":
                total_commission += amount
            elif item.type == "bonus":
                total_bonus += amount
            elif item.type == "reimbursement":
                total_reimbursements += amount
            elif item.type == "deduction":
                total_deductions += amount

        settlement.items = items_list
        settlement.total_commission = total_commission
        settlement.total_bonus = total_bonus
        settlement.total_reimbursements = total_reimbursements
        settlement.total_deductions = total_deductions
        settlement.net_payment = total_commission + total_bonus + total_reimbursements - total_deductions

    await db.commit()
    await db.refresh(settlement)

    return HQContractorSettlementResponse.from_orm_model(settlement)


@router.post("/contractor-settlements/{settlement_id}/submit", response_model=HQContractorSettlementResponse)
async def submit_contractor_settlement(
    settlement_id: str,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_async_session),
):
    """Submit a settlement for approval."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    query = select(HQContractorSettlement).options(
        selectinload(HQContractorSettlement.contractor)
    ).where(HQContractorSettlement.id == settlement_id)
    result = await db.execute(query)
    settlement = result.scalar_one_or_none()

    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    if settlement.status != SettlementStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Can only submit draft settlements")

    settlement.status = SettlementStatus.PENDING_APPROVAL
    await db.commit()
    await db.refresh(settlement)

    return HQContractorSettlementResponse.from_orm_model(settlement)


@router.post("/contractor-settlements/{settlement_id}/approve", response_model=HQContractorSettlementResponse)
async def approve_contractor_settlement(
    settlement_id: str,
    data: HQContractorSettlementApproval,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_async_session),
):
    """Approve a contractor settlement."""
    from datetime import datetime
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    query = select(HQContractorSettlement).options(
        selectinload(HQContractorSettlement.contractor)
    ).where(HQContractorSettlement.id == settlement_id)
    result = await db.execute(query)
    settlement = result.scalar_one_or_none()

    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    if settlement.status != SettlementStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=400, detail="Can only approve pending settlements")

    settlement.status = SettlementStatus.APPROVED
    settlement.approved_by_id = current_employee.id
    settlement.approved_at = datetime.now()
    if data.notes:
        settlement.notes = (settlement.notes or "") + f"\n[Approval note]: {data.notes}"

    await db.commit()
    await db.refresh(settlement)

    return HQContractorSettlementResponse.from_orm_model(settlement)


@router.post("/contractor-settlements/{settlement_id}/pay", response_model=HQContractorSettlementResponse)
async def pay_contractor_settlement(
    settlement_id: str,
    data: HQContractorSettlementPayment,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_async_session),
):
    """Mark a contractor settlement as paid."""
    from datetime import datetime
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    query = select(HQContractorSettlement).options(
        selectinload(HQContractorSettlement.contractor)
    ).where(HQContractorSettlement.id == settlement_id)
    result = await db.execute(query)
    settlement = result.scalar_one_or_none()

    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    if settlement.status != SettlementStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Can only pay approved settlements")

    settlement.status = SettlementStatus.PAID
    settlement.paid_at = datetime.now()
    settlement.payment_reference = data.payment_reference
    settlement.payment_method = data.payment_method
    if data.notes:
        settlement.notes = (settlement.notes or "") + f"\n[Payment note]: {data.notes}"

    await db.commit()
    await db.refresh(settlement)

    return HQContractorSettlementResponse.from_orm_model(settlement)


@router.delete("/contractor-settlements/{settlement_id}", status_code=204)
async def delete_contractor_settlement(
    settlement_id: str,
    current_employee: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a draft contractor settlement."""
    from sqlalchemy import select

    query = select(HQContractorSettlement).where(HQContractorSettlement.id == settlement_id)
    result = await db.execute(query)
    settlement = result.scalar_one_or_none()

    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    if settlement.status != SettlementStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Can only delete draft settlements")

    await db.delete(settlement)
    await db.commit()


# ============================================================================
# IT Operations Endpoints
# ============================================================================

from app.schemas.hq_it_operations import (
    FeatureFlagCreate,
    FeatureFlagUpdate,
    FeatureFlagResponse,
    ServiceHealthCreate,
    ServiceHealthUpdate,
    ServiceHealthResponse,
    ServiceHealthCheckResult,
    DeploymentCreate,
    DeploymentResponse,
    BackgroundJobResponse,
    ITOperationsDashboard,
)
from app.services.hq_it_operations import (
    HQFeatureFlagService,
    HQServiceHealthService,
    HQDeploymentService,
    HQBackgroundJobService,
    HQITOperationsService,
)


@router.get("/it-ops/dashboard", response_model=ITOperationsDashboard)
async def get_it_operations_dashboard(
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Get IT Operations dashboard summary."""
    service = HQITOperationsService(db)
    return await service.get_dashboard()


# Feature Flags
@router.get("/it-ops/feature-flags", response_model=List[FeatureFlagResponse])
async def list_feature_flags(
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List all feature flags."""
    service = HQFeatureFlagService(db)
    flags = await service.list_flags()
    return [FeatureFlagResponse.model_validate(f, from_attributes=True) for f in flags]


@router.post("/it-ops/feature-flags", response_model=FeatureFlagResponse, status_code=status.HTTP_201_CREATED)
async def create_feature_flag(
    data: FeatureFlagCreate,
    current_employee: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new feature flag."""
    service = HQFeatureFlagService(db)

    # Check if key already exists
    existing = await service.get_flag_by_key(data.key)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Feature flag key already exists")

    flag = await service.create_flag(
        data,
        created_by_id=current_employee.id,
        created_by_name=f"{current_employee.first_name} {current_employee.last_name}",
    )
    return FeatureFlagResponse.model_validate(flag, from_attributes=True)


@router.put("/it-ops/feature-flags/{flag_id}", response_model=FeatureFlagResponse)
async def update_feature_flag(
    flag_id: str,
    data: FeatureFlagUpdate,
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Update a feature flag."""
    service = HQFeatureFlagService(db)
    flag = await service.update_flag(flag_id, data)
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature flag not found")
    return FeatureFlagResponse.model_validate(flag, from_attributes=True)


@router.post("/it-ops/feature-flags/{flag_id}/toggle", response_model=FeatureFlagResponse)
async def toggle_feature_flag(
    flag_id: str,
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Toggle a feature flag on/off."""
    service = HQFeatureFlagService(db)
    flag = await service.toggle_flag(flag_id)
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature flag not found")
    return FeatureFlagResponse.model_validate(flag, from_attributes=True)


@router.delete("/it-ops/feature-flags/{flag_id}")
async def delete_feature_flag(
    flag_id: str,
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Delete a feature flag."""
    service = HQFeatureFlagService(db)
    deleted = await service.delete_flag(flag_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feature flag not found")
    return {"status": "deleted"}


# Service Health
@router.get("/it-ops/services", response_model=List[ServiceHealthResponse])
async def list_services(
    include_inactive: bool = False,
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List all monitored services."""
    service = HQServiceHealthService(db)
    services = await service.list_services(include_inactive=include_inactive)
    return [ServiceHealthResponse.model_validate(s, from_attributes=True) for s in services]


@router.post("/it-ops/services", response_model=ServiceHealthResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    data: ServiceHealthCreate,
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Add a new service to monitor."""
    service = HQServiceHealthService(db)
    new_service = await service.create_service(data)
    return ServiceHealthResponse.model_validate(new_service, from_attributes=True)


@router.post("/it-ops/services/check-all", response_model=List[ServiceHealthCheckResult])
async def check_all_services(
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Perform health check on all active services."""
    service = HQServiceHealthService(db)
    return await service.check_all_services()


@router.post("/it-ops/services/{service_id}/check", response_model=ServiceHealthCheckResult)
async def check_service(
    service_id: str,
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Perform health check on a specific service."""
    health_service = HQServiceHealthService(db)
    service = await health_service.get_service(service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return await health_service.check_service_health(service)


@router.post("/it-ops/services/seed")
async def seed_default_services(
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Seed default services (Core API, database, etc.)."""
    service = HQServiceHealthService(db)
    await service.seed_default_services()
    return {"status": "seeded"}


# Deployments
@router.get("/it-ops/deployments", response_model=List[DeploymentResponse])
async def list_deployments(
    environment: Optional[str] = None,
    limit: int = 50,
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """List deployment history."""
    service = HQDeploymentService(db)
    deployments = await service.list_deployments(environment=environment, limit=limit)
    return [DeploymentResponse.model_validate(d, from_attributes=True) for d in deployments]


@router.post("/it-ops/deployments", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    data: DeploymentCreate,
    current_employee: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Record a new deployment."""
    service = HQDeploymentService(db)
    deployment = await service.create_deployment(
        data,
        deployed_by_id=current_employee.id,
        deployed_by_name=f"{current_employee.first_name} {current_employee.last_name}",
    )
    return DeploymentResponse.model_validate(deployment, from_attributes=True)


@router.post("/it-ops/deployments/{deployment_id}/complete", response_model=DeploymentResponse)
async def complete_deployment(
    deployment_id: str,
    success: bool = True,
    error_message: Optional[str] = None,
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Mark a deployment as completed."""
    service = HQDeploymentService(db)
    deployment = await service.complete_deployment(deployment_id, success, error_message)
    if not deployment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    return DeploymentResponse.model_validate(deployment, from_attributes=True)


@router.post("/it-ops/deployments/{deployment_id}/rollback", response_model=DeploymentResponse)
async def rollback_deployment(
    deployment_id: str,
    current_employee: HQEmployee = Depends(require_hq_permission("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a rollback to a previous deployment."""
    service = HQDeploymentService(db)
    deployment = await service.rollback_deployment(
        deployment_id,
        rolled_back_by_id=current_employee.id,
        rolled_back_by_name=f"{current_employee.first_name} {current_employee.last_name}",
    )
    if not deployment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    return DeploymentResponse.model_validate(deployment, from_attributes=True)


# Background Jobs
@router.get("/it-ops/jobs", response_model=List[BackgroundJobResponse])
async def list_background_jobs(
    _: HQEmployee = Depends(require_hq_permission("system_admin")),
):
    """List background jobs from the scheduler."""
    return HQBackgroundJobService.get_jobs()

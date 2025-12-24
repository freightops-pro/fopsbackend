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
    from app.models.hq_tenant import HQTenant

    result = await db.execute(
        select(HQTenant)
        .order_by(HQTenant.created_at.desc())
        .limit(5)
    )
    tenants = result.scalars().all()
    return [HQTenantResponse.model_validate(t, from_attributes=True) for t in tenants]


@router.get("/dashboard/expiring-contracts", response_model=List[HQContractResponse])
async def get_expiring_contracts(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQContractResponse]:
    """Get contracts expiring within 30 days."""
    from sqlalchemy import select, and_
    from datetime import datetime, timedelta
    from app.models.hq_contract import HQContract, ContractStatus

    thirty_days = datetime.utcnow() + timedelta(days=30)
    result = await db.execute(
        select(HQContract)
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
    return [HQContractResponse.model_validate(c, from_attributes=True) for c in contracts]


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
# Tenant Endpoints
# ============================================================================

def _build_tenant_response(tenant) -> HQTenantResponse:
    """Build HQTenantResponse from tenant with company data."""
    from app.schemas.hq import AddressResponse
    company = tenant.company
    users = company.users if company else []
    total_users = len(users)
    active_users = sum(1 for u in users if getattr(u, "is_active", True))

    # Build address if company has address fields
    address = None
    if company and (company.address_line1 or company.city):
        address = AddressResponse(
            street=company.address_line1,
            city=company.city,
            state=company.state,
            zip=company.zip_code,
        )

    return HQTenantResponse(
        id=tenant.id,
        company_name=company.name if company else "Unknown",
        legal_name=company.legal_name if company else None,
        tax_id=company.tax_id if company else None,
        dot_number=company.dotNumber if company else None,
        mc_number=company.mcNumber if company else None,
        status=tenant.status.value if hasattr(tenant.status, "value") else tenant.status,
        subscription_tier=tenant.subscription_tier.value if hasattr(tenant.subscription_tier, "value") else tenant.subscription_tier,
        subscription_start_date=tenant.subscription_started_at,
        subscription_end_date=tenant.current_period_ends_at,
        monthly_fee=tenant.monthly_rate or 0,
        setup_fee=getattr(tenant, "setup_fee", None) or 0,
        primary_contact_name=company.primaryContactName if company else None,
        primary_contact_email=company.email if company else None,
        primary_contact_phone=company.phone if company else None,
        billing_email=tenant.billing_email,
        address=address,
        total_users=total_users,
        active_users=active_users,
        stripe_customer_id=tenant.stripe_customer_id,
        stripe_subscription_id=tenant.stripe_subscription_id,
        notes=tenant.notes,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


@router.get("/tenants", response_model=List[HQTenantResponse])
async def list_tenants(
    status_filter: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQTenantResponse]:
    """List all tenants."""
    service = HQTenantService(db)
    tenants = await service.list_tenants(status=status_filter)
    return [_build_tenant_response(t) for t in tenants]


@router.post("/tenants", response_model=HQTenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: HQTenantCreate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQTenantResponse:
    """Create a new tenant with company."""
    service = HQTenantService(db)
    try:
        tenant = await service.create_tenant(payload)
        return _build_tenant_response(tenant)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/tenants/{tenant_id}", response_model=HQTenantResponse)
async def get_tenant(
    tenant_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQTenantResponse:
    """Get tenant by ID."""
    service = HQTenantService(db)
    tenant = await service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return _build_tenant_response(tenant)


@router.patch("/tenants/{tenant_id}", response_model=HQTenantResponse)
async def update_tenant(
    tenant_id: str,
    payload: HQTenantUpdate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQTenantResponse:
    """Update a tenant."""
    service = HQTenantService(db)
    try:
        tenant = await service.update_tenant(tenant_id, payload)
        # Reload with relationships for response
        tenant = await service.get_tenant(tenant_id)
        return _build_tenant_response(tenant)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/tenants/{tenant_id}/suspend", response_model=HQTenantResponse)
async def suspend_tenant(
    tenant_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQTenantResponse:
    """Suspend a tenant."""
    service = HQTenantService(db)
    try:
        await service.suspend_tenant(tenant_id)
        tenant = await service.get_tenant(tenant_id)
        return _build_tenant_response(tenant)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/tenants/{tenant_id}/activate", response_model=HQTenantResponse)
async def activate_tenant(
    tenant_id: str,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQTenantResponse:
    """Activate a tenant."""
    service = HQTenantService(db)
    try:
        await service.activate_tenant(tenant_id)
        tenant = await service.get_tenant(tenant_id)
        return _build_tenant_response(tenant)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/tenants/sync", response_model=dict)
async def sync_tenants_from_companies(
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Create HQ tenant records for all companies that don't have one.
    This is a one-time sync to populate the hq_tenant table from existing companies.
    """
    import uuid
    from sqlalchemy import select
    from app.models.company import Company
    from app.models.hq_tenant import HQTenant, TenantStatus, SubscriptionTier

    # Find companies without hq_tenant records
    result = await db.execute(
        select(Company).outerjoin(HQTenant, Company.id == HQTenant.company_id)
        .where(HQTenant.id == None)
    )
    orphan_companies = result.scalars().all()

    created = 0
    for company in orphan_companies:
        tenant = HQTenant(
            id=str(uuid.uuid4()),
            company_id=company.id,
            status=TenantStatus.ACTIVE if company.isActive else TenantStatus.SUSPENDED,
            subscription_tier=SubscriptionTier.PROFESSIONAL,
            monthly_rate=299,  # Default rate
            billing_email=company.email,
        )
        db.add(tenant)
        created += 1

    await db.commit()

    return {"synced": created, "message": f"Created {created} tenant records from existing companies"}


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

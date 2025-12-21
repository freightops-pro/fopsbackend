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


def set_hq_auth_cookie(response: Response, token: str) -> None:
    """Set HQ authentication cookie."""
    response.set_cookie(
        key=HQ_AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
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

@router.get("/tenants", response_model=List[HQTenantResponse])
async def list_tenants(
    status_filter: Optional[str] = None,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> List[HQTenantResponse]:
    """List all tenants."""
    service = HQTenantService(db)
    tenants = await service.list_tenants(status=status_filter)
    result = []
    for t in tenants:
        data = HQTenantResponse.model_validate(t, from_attributes=True)
        if t.company:
            data.company_name = t.company.name
            data.company_email = t.company.email
        result.append(data)
    return result


@router.post("/tenants", response_model=HQTenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: HQTenantCreate,
    _: HQEmployee = Depends(get_current_hq_employee),
    db: AsyncSession = Depends(get_db)
) -> HQTenantResponse:
    """Create a new tenant."""
    service = HQTenantService(db)
    try:
        tenant = await service.create_tenant(payload)
        return HQTenantResponse.model_validate(tenant, from_attributes=True)
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
    data = HQTenantResponse.model_validate(tenant, from_attributes=True)
    if tenant.company:
        data.company_name = tenant.company.name
        data.company_email = tenant.company.email
    return data


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
        return HQTenantResponse.model_validate(tenant, from_attributes=True)
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
        tenant = await service.suspend_tenant(tenant_id)
        return HQTenantResponse.model_validate(tenant, from_attributes=True)
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
        tenant = await service.activate_tenant(tenant_id)
        return HQTenantResponse.model_validate(tenant, from_attributes=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


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

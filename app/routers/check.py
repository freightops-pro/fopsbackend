"""Check Payroll API Router.

Provides proxy endpoints to Check's payroll API.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.models.integration import CompanyIntegration
from app.services.check import CheckService

router = APIRouter()


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    """Extract company_id from authenticated user."""
    return current_user.company_id


async def _get_check_service(
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> CheckService:
    """Get Check service with company's Check ID."""
    # Look up the company's Check integration to get their Check company ID
    result = await db.execute(
        select(CompanyIntegration).where(
            CompanyIntegration.company_id == company_id,
            CompanyIntegration.status == "active",
        ).join(
            CompanyIntegration.integration
        ).where(
            CompanyIntegration.integration.has(integration_key="check")
        )
    )
    integration = result.scalar_one_or_none()

    # Get Check company ID from integration credentials
    check_company_id = None
    if integration and integration.credentials:
        check_company_id = integration.credentials.get("check_company_id")

    return CheckService(company_check_id=check_company_id)


# ==================== Company Endpoints ====================


@router.get("/company", summary="Get Check company")
async def get_company(
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Get the Check company for this tenant."""
    try:
        return await service.get_company()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/company", status_code=status.HTTP_201_CREATED, summary="Create Check company")
async def create_company(
    payload: dict,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Create a new Check company."""
    try:
        return await service.create_company(payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ==================== Employee Endpoints ====================


@router.get("/employees", summary="List employees")
async def list_employees(
    page: int = 1,
    per_page: int = 50,
    service: CheckService = Depends(_get_check_service),
) -> List[dict]:
    """List all employees for the company."""
    try:
        return await service.list_employees(page=page, per_page=per_page)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/employees/{employee_id}", summary="Get employee")
async def get_employee(
    employee_id: str,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Get a specific employee."""
    try:
        return await service.get_employee(employee_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/employees", status_code=status.HTTP_201_CREATED, summary="Create employee")
async def create_employee(
    payload: dict,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Create a new employee in Check."""
    try:
        return await service.create_employee(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.patch("/employees/{employee_id}", summary="Update employee")
async def update_employee(
    employee_id: str,
    payload: dict,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Update an employee in Check."""
    try:
        return await service.update_employee(employee_id, payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary="Delete employee")
async def delete_employee(
    employee_id: str,
    service: CheckService = Depends(_get_check_service),
):
    """Delete an employee from Check."""
    try:
        await service.delete_employee(employee_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ==================== Payroll Endpoints ====================


@router.get("/payrolls", summary="List payrolls")
async def list_payrolls(
    page: int = 1,
    per_page: int = 50,
    service: CheckService = Depends(_get_check_service),
) -> List[dict]:
    """List all payroll runs for the company."""
    try:
        return await service.list_payrolls(page=page, per_page=per_page)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/payrolls/{payroll_id}", summary="Get payroll")
async def get_payroll(
    payroll_id: str,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Get a specific payroll run."""
    try:
        return await service.get_payroll(payroll_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/payrolls", status_code=status.HTTP_201_CREATED, summary="Create payroll")
async def create_payroll(
    payload: dict,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Create a new payroll run."""
    try:
        return await service.create_payroll(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/payrolls/{payroll_id}/preview", summary="Preview payroll")
async def preview_payroll(
    payroll_id: str,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Preview a payroll before approval."""
    try:
        return await service.preview_payroll(payroll_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/payrolls/{payroll_id}/approve", summary="Approve payroll")
async def approve_payroll(
    payroll_id: str,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Approve a payroll for processing."""
    try:
        return await service.approve_payroll(payroll_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/payrolls/{payroll_id}/cancel", summary="Cancel payroll")
async def cancel_payroll(
    payroll_id: str,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Cancel a payroll."""
    try:
        return await service.cancel_payroll(payroll_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ==================== Benefits Endpoints ====================


@router.get("/benefits", summary="List employee benefits")
async def list_benefits(
    employee: Optional[str] = None,
    service: CheckService = Depends(_get_check_service),
) -> List[dict]:
    """List benefits, optionally filtered by employee."""
    try:
        return await service.list_benefits(employee_id=employee)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/benefits", status_code=status.HTTP_201_CREATED, summary="Create benefit")
async def create_benefit(
    payload: dict,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Create a new benefit for an employee."""
    try:
        return await service.create_benefit(payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.patch("/benefits/{benefit_id}", summary="Update benefit")
async def update_benefit(
    benefit_id: str,
    payload: dict,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Update a benefit."""
    try:
        return await service.update_benefit(benefit_id, payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.delete("/benefits/{benefit_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary="Delete benefit")
async def delete_benefit(
    benefit_id: str,
    service: CheckService = Depends(_get_check_service),
):
    """Delete a benefit."""
    try:
        await service.delete_benefit(benefit_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ==================== Company Benefits Endpoints ====================


@router.get("/company-benefits", summary="List company benefits")
async def list_company_benefits(
    service: CheckService = Depends(_get_check_service),
) -> List[dict]:
    """List company-level benefit plans."""
    try:
        return await service.list_company_benefits()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/company-benefits", status_code=status.HTTP_201_CREATED, summary="Create company benefit")
async def create_company_benefit(
    payload: dict,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Create a new company-level benefit."""
    try:
        return await service.create_company_benefit(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.patch("/company-benefits/{benefit_id}", summary="Update company benefit")
async def update_company_benefit(
    benefit_id: str,
    payload: dict,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Update a company benefit."""
    try:
        return await service.update_company_benefit(benefit_id, payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.delete("/company-benefits/{benefit_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary="Delete company benefit")
async def delete_company_benefit(
    benefit_id: str,
    service: CheckService = Depends(_get_check_service),
):
    """Delete a company benefit."""
    try:
        await service.delete_company_benefit(benefit_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ==================== Contractors Endpoints ====================


@router.get("/contractors", summary="List contractors")
async def list_contractors(
    page: int = 1,
    per_page: int = 50,
    service: CheckService = Depends(_get_check_service),
) -> List[dict]:
    """List all contractors for the company."""
    try:
        return await service.list_contractors(page=page, per_page=per_page)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/contractors", status_code=status.HTTP_201_CREATED, summary="Create contractor")
async def create_contractor(
    payload: dict,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Create a new contractor in Check."""
    try:
        return await service.create_contractor(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ==================== Workplaces Endpoints ====================


@router.get("/workplaces", summary="List workplaces")
async def list_workplaces(
    service: CheckService = Depends(_get_check_service),
) -> List[dict]:
    """List all workplaces for the company."""
    try:
        return await service.list_workplaces()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/workplaces", status_code=status.HTTP_201_CREATED, summary="Create workplace")
async def create_workplace(
    payload: dict,
    service: CheckService = Depends(_get_check_service),
) -> dict:
    """Create a new workplace."""
    try:
        return await service.create_workplace(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

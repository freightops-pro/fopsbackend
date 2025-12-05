"""Payroll and worker management endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.worker import (
    DeductionCreate,
    DeductionResponse,
    PayRuleCreate,
    PayRuleResponse,
    PayrollPreviewRequest,
    PayrollPreviewResponse,
    PayrollRunCreate,
    PayrollRunResponse,
    SettlementResponse,
    WorkerCreate,
    WorkerDocumentCreate,
    WorkerDocumentResponse,
    WorkerProfileResponse,
    WorkerResponse,
    WorkerUpdate,
)
from app.services.payroll import PayrollService
from app.services.worker import WorkerService

router = APIRouter()


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


async def _user_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.id


async def _worker_service(db: AsyncSession = Depends(get_db)) -> WorkerService:
    return WorkerService(db)


async def _payroll_service(db: AsyncSession = Depends(get_db)) -> PayrollService:
    return PayrollService(db)


# Worker endpoints
@router.get("/workers", response_model=List[WorkerResponse])
async def list_workers(
    company_id: str = Depends(_company_id),
    worker_type: str | None = None,
    role: str | None = None,
    status: str | None = None,
    service: WorkerService = Depends(_worker_service),
) -> List[WorkerResponse]:
    """List all workers with optional filters."""
    return await service.list_workers(company_id, worker_type, role, status)


@router.post("/workers", response_model=WorkerResponse, status_code=status.HTTP_201_CREATED)
async def create_worker(
    payload: WorkerCreate,
    company_id: str = Depends(_company_id),
    service: WorkerService = Depends(_worker_service),
) -> WorkerResponse:
    """Create a new worker (employee or contractor)."""
    try:
        return await service.create_worker(company_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# Backfill endpoint - must be before {worker_id} routes
@router.post("/workers/backfill-drivers")
async def backfill_workers_for_drivers(
    company_id: str = Depends(_company_id),
    service: WorkerService = Depends(_worker_service),
) -> dict:
    """Create Worker records for existing drivers who don't have them."""
    return await service.backfill_workers_for_drivers(company_id)


@router.get("/workers/{worker_id}", response_model=WorkerResponse)
async def get_worker(
    worker_id: str,
    company_id: str = Depends(_company_id),
    service: WorkerService = Depends(_worker_service),
) -> WorkerResponse:
    """Get worker by ID."""
    worker = await service.get_worker(company_id, worker_id)
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return worker


@router.get("/workers/{worker_id}/profile", response_model=WorkerProfileResponse)
async def get_worker_profile(
    worker_id: str,
    company_id: str = Depends(_company_id),
    service: WorkerService = Depends(_worker_service),
) -> WorkerProfileResponse:
    """Get detailed worker profile with documents, pay rules, and settlements."""
    profile = await service.get_worker_profile(company_id, worker_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return profile


@router.put("/workers/{worker_id}", response_model=WorkerResponse)
async def update_worker(
    worker_id: str,
    payload: WorkerUpdate,
    company_id: str = Depends(_company_id),
    service: WorkerService = Depends(_worker_service),
) -> WorkerResponse:
    """Update worker details."""
    worker = await service.update_worker(company_id, worker_id, payload)
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return worker


# Worker documents
@router.post("/workers/{worker_id}/documents", response_model=WorkerDocumentResponse, status_code=status.HTTP_201_CREATED)
async def add_worker_document(
    worker_id: str,
    payload: WorkerDocumentCreate,
    company_id: str = Depends(_company_id),
    user_id: str = Depends(_user_id),
    service: WorkerService = Depends(_worker_service),
) -> WorkerDocumentResponse:
    """Upload document for worker."""
    try:
        return await service.add_document(company_id, worker_id, payload, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# Pay rules
@router.get("/workers/{worker_id}/pay-rules", response_model=List[PayRuleResponse])
async def get_worker_pay_rules(
    worker_id: str,
    company_id: str = Depends(_company_id),
    service: WorkerService = Depends(_worker_service),
) -> List[PayRuleResponse]:
    """Get pay rules for worker."""
    try:
        return await service.get_pay_rules(company_id, worker_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/workers/{worker_id}/pay-rules", response_model=PayRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_worker_pay_rule(
    worker_id: str,
    payload: PayRuleCreate,
    company_id: str = Depends(_company_id),
    service: WorkerService = Depends(_worker_service),
) -> PayRuleResponse:
    """Create pay rule for worker."""
    try:
        return await service.create_pay_rule(company_id, worker_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# Deductions
@router.get("/workers/{worker_id}/deductions", response_model=List[DeductionResponse])
async def get_worker_deductions(
    worker_id: str,
    company_id: str = Depends(_company_id),
    service: WorkerService = Depends(_worker_service),
) -> List[DeductionResponse]:
    """Get deductions for worker."""
    try:
        return await service.get_deductions(company_id, worker_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/workers/{worker_id}/deductions", response_model=DeductionResponse, status_code=status.HTTP_201_CREATED)
async def create_worker_deduction(
    worker_id: str,
    payload: DeductionCreate,
    company_id: str = Depends(_company_id),
    service: WorkerService = Depends(_worker_service),
) -> DeductionResponse:
    """Create deduction for worker."""
    try:
        return await service.create_deduction(company_id, worker_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# Payroll endpoints
@router.post("/payrolls/preview", response_model=PayrollPreviewResponse)
async def preview_payroll(
    payload: PayrollPreviewRequest,
    company_id: str = Depends(_company_id),
    service: PayrollService = Depends(_payroll_service),
) -> PayrollPreviewResponse:
    """
    Generate payroll preview for a pay period.
    Calculates gross, deductions, and net for each worker without creating a payroll run.
    """
    return await service.preview_payroll(company_id, payload)


@router.post("/payrolls", response_model=PayrollRunResponse, status_code=status.HTTP_201_CREATED)
async def create_payroll_run(
    payload: PayrollRunCreate,
    company_id: str = Depends(_company_id),
    user_id: str = Depends(_user_id),
    service: PayrollService = Depends(_payroll_service),
) -> PayrollRunResponse:
    """Create a new payroll run in draft status."""
    try:
        return await service.create_payroll_run(company_id, user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/payrolls/{payroll_id}/approve", response_model=PayrollRunResponse)
async def approve_payroll(
    payroll_id: str,
    user_id: str = Depends(_user_id),
    service: PayrollService = Depends(_payroll_service),
) -> PayrollRunResponse:
    """Approve a payroll run."""
    try:
        return await service.approve_payroll(payroll_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

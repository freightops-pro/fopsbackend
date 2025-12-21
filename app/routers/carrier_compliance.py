"""API router for carrier-level compliance endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.carrier_compliance import (
    CarrierComplianceDashboardResponse,
    CarrierCredentialCreate,
    CarrierCredentialResponse,
    CarrierCredentialUpdate,
    CarrierSAFERDataResponse,
    CompanyInsuranceCreate,
    CompanyInsuranceResponse,
    CompanyInsuranceUpdate,
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
from app.services.carrier_compliance import CarrierComplianceService

router = APIRouter()


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


async def _service(db: AsyncSession = Depends(get_db)) -> CarrierComplianceService:
    return CarrierComplianceService(db)


# ==================== DASHBOARD ====================


@router.get("/dashboard", response_model=CarrierComplianceDashboardResponse)
async def get_compliance_dashboard(
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> CarrierComplianceDashboardResponse:
    """Get the full carrier compliance dashboard."""
    return await service.get_dashboard(company_id)


# ==================== SAFER DATA ====================


@router.get("/safer", response_model=CarrierSAFERDataResponse)
async def get_safer_data(
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> CarrierSAFERDataResponse:
    """Get SAFER/SMS data from FMCSA."""
    data = await service.get_safer_data(company_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SAFER data available for this company",
        )
    return data


# ==================== COMPANY INSURANCE ====================


@router.get("/insurance", response_model=List[CompanyInsuranceResponse])
async def list_insurance(
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> List[CompanyInsuranceResponse]:
    """List all insurance policies."""
    return await service.list_insurance(company_id)


@router.post(
    "/insurance",
    response_model=CompanyInsuranceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_insurance(
    payload: CompanyInsuranceCreate,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> CompanyInsuranceResponse:
    """Create a new insurance policy."""
    return await service.create_insurance(company_id, payload)


@router.patch("/insurance/{insurance_id}", response_model=CompanyInsuranceResponse)
async def update_insurance(
    insurance_id: str,
    payload: CompanyInsuranceUpdate,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> CompanyInsuranceResponse:
    """Update an insurance policy."""
    try:
        return await service.update_insurance(company_id, insurance_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/insurance/{insurance_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_insurance(
    insurance_id: str,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> None:
    """Delete an insurance policy."""
    try:
        await service.delete_insurance(company_id, insurance_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ==================== CARRIER CREDENTIALS ====================


@router.get("/credentials", response_model=List[CarrierCredentialResponse])
async def list_credentials(
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> List[CarrierCredentialResponse]:
    """List all carrier credentials."""
    return await service.list_credentials(company_id)


@router.post(
    "/credentials",
    response_model=CarrierCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_credential(
    payload: CarrierCredentialCreate,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> CarrierCredentialResponse:
    """Create a new carrier credential."""
    return await service.create_credential(company_id, payload)


@router.patch("/credentials/{credential_id}", response_model=CarrierCredentialResponse)
async def update_credential(
    credential_id: str,
    payload: CarrierCredentialUpdate,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> CarrierCredentialResponse:
    """Update a carrier credential."""
    try:
        return await service.update_credential(company_id, credential_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_credential(
    credential_id: str,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> None:
    """Delete a carrier credential."""
    try:
        await service.delete_credential(company_id, credential_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ==================== VEHICLE REGISTRATIONS ====================


@router.get("/registrations", response_model=List[VehicleRegistrationResponse])
async def list_registrations(
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> List[VehicleRegistrationResponse]:
    """List all vehicle registrations."""
    return await service.list_registrations(company_id)


@router.post(
    "/registrations",
    response_model=VehicleRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_registration(
    payload: VehicleRegistrationCreate,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> VehicleRegistrationResponse:
    """Create a new vehicle registration."""
    return await service.create_registration(company_id, payload)


@router.patch("/registrations/{registration_id}", response_model=VehicleRegistrationResponse)
async def update_registration(
    registration_id: str,
    payload: VehicleRegistrationUpdate,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> VehicleRegistrationResponse:
    """Update a vehicle registration."""
    try:
        return await service.update_registration(company_id, registration_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/registrations/{registration_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_registration(
    registration_id: str,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> None:
    """Delete a vehicle registration."""
    try:
        await service.delete_registration(company_id, registration_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ==================== ELD AUDIT ITEMS ====================


@router.get("/eld-audit", response_model=ELDAuditSummaryResponse)
async def get_eld_audit_summary(
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> ELDAuditSummaryResponse:
    """Get ELD audit summary."""
    return await service.get_audit_summary(company_id)


@router.get("/eld-audit/items", response_model=List[ELDAuditItemResponse])
async def list_eld_audit_items(
    status_filter: Optional[str] = None,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> List[ELDAuditItemResponse]:
    """List ELD audit items."""
    return await service.list_audit_items(company_id, status=status_filter)


@router.post(
    "/eld-audit/items",
    response_model=ELDAuditItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_eld_audit_item(
    payload: ELDAuditItemCreate,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> ELDAuditItemResponse:
    """Create a new ELD audit item."""
    return await service.create_audit_item(company_id, payload)


@router.patch("/eld-audit/items/{item_id}", response_model=ELDAuditItemResponse)
async def update_eld_audit_item(
    item_id: str,
    payload: ELDAuditItemUpdate,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> ELDAuditItemResponse:
    """Update an ELD audit item."""
    try:
        return await service.update_audit_item(company_id, item_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/eld-audit/items/{item_id}/resolve", response_model=ELDAuditItemResponse)
async def resolve_eld_audit_item(
    item_id: str,
    payload: ELDAuditItemResolve,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> ELDAuditItemResponse:
    """Resolve an ELD audit item."""
    try:
        return await service.resolve_audit_item(company_id, item_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ==================== CSA SCORES ====================


@router.get("/csa-scores", response_model=List[CSAScoreResponse])
async def list_csa_scores(
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> List[CSAScoreResponse]:
    """List CSA BASIC scores."""
    return await service.list_csa_scores(company_id)


@router.put("/csa-scores", response_model=CSAScoreResponse)
async def upsert_csa_score(
    payload: CSAScoreCreate,
    company_id: str = Depends(_company_id),
    service: CarrierComplianceService = Depends(_service),
) -> CSAScoreResponse:
    """Create or update a CSA BASIC score."""
    return await service.upsert_csa_score(company_id, payload)

"""Background Checks API routes."""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.db import get_db_sync
from app.schemas.onboarding import (
    BackgroundCheckRequest,
    BackgroundCheckResponse,
    BackgroundCheckBatchRequest,
    BackgroundCheckBatchResponse,
    BackgroundCheckCostEstimate,
    BackgroundCheckProvidersResponse,
)
from app.services.background_checks import BackgroundCheckService

router = APIRouter()


def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    """Extract company ID from current user."""
    return current_user.company_id


@router.get("/costs", response_model=List[BackgroundCheckCostEstimate])
def get_cost_estimates() -> List[BackgroundCheckCostEstimate]:
    """
    Get cost estimates for all background check types.

    Returns pricing and turnaround times for:
    - MVR (Motor Vehicle Record)
    - PSP (Pre-Employment Screening Program)
    - CDL Verification
    - Clearinghouse
    - Criminal Background
    - Employment Verification
    """
    return BackgroundCheckService.get_cost_estimates()


@router.get("/providers", response_model=BackgroundCheckProvidersResponse)
def get_providers_info() -> BackgroundCheckProvidersResponse:
    """
    Get information about background check providers and pricing.

    Includes DOT driver package cost estimate.
    """
    estimates = BackgroundCheckService.get_cost_estimates()
    dot_cost = BackgroundCheckService.calculate_dot_driver_cost()

    return BackgroundCheckProvidersResponse(
        providers=[
            {
                "name": "Foley Services / StateServ",
                "checks": ["mvr", "cdl_verification"],
                "website": "https://foleyservices.com"
            },
            {
                "name": "FMCSA",
                "checks": ["psp", "clearinghouse"],
                "website": "https://portal.fmcsa.dot.gov"
            },
            {
                "name": "Checkr / HireRight",
                "checks": ["criminal_background"],
                "website": "https://checkr.com"
            }
        ],
        cost_estimates=estimates,
        total_estimated_cost_for_dot_driver=dot_cost
    )


@router.post("", response_model=BackgroundCheckResponse, status_code=status.HTTP_201_CREATED)
async def request_background_check(
    payload: BackgroundCheckRequest,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> BackgroundCheckResponse:
    """
    Request a single background check.

    Creates a background check request and initiates the check with the provider.
    Cost is automatically billed to the company.
    """
    try:
        check = await BackgroundCheckService.request_background_check(
            db=db,
            company_id=company_id,
            request=payload
        )

        return BackgroundCheckResponse.model_validate(check)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/batch", response_model=BackgroundCheckBatchResponse, status_code=status.HTTP_201_CREATED)
async def request_batch_background_checks(
    payload: BackgroundCheckBatchRequest,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> BackgroundCheckBatchResponse:
    """
    Request multiple background checks in batch.

    Useful for DOT driver onboarding (MVR + PSP + CDL + Clearinghouse).
    All costs automatically billed to the company.
    """
    try:
        result = await BackgroundCheckService.batch_request_checks(
            db=db,
            company_id=company_id,
            onboarding_id=payload.onboarding_id,
            driver_id=payload.driver_id,
            check_types=payload.check_types,
            subject_name=payload.subject_name,
            subject_cdl_number=payload.subject_cdl_number,
            subject_cdl_state=payload.subject_cdl_state,
            subject_dob=payload.subject_dob
        )

        return BackgroundCheckBatchResponse(
            onboarding_id=result.get("onboarding_id"),
            driver_id=result.get("driver_id"),
            checks_requested=result["checks_requested"],
            checks_initiated=[BackgroundCheckResponse.model_validate(c) for c in result["checks_initiated"]],
            total_estimated_cost=result["total_cost"],
            billing_company_id=company_id
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to request background checks: {str(e)}"
        )


@router.get("/{check_id}", response_model=BackgroundCheckResponse)
def get_background_check(
    check_id: str,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> BackgroundCheckResponse:
    """Get a specific background check by ID."""
    from app.models.onboarding import BackgroundCheck

    check = db.query(BackgroundCheck).filter(
        BackgroundCheck.id == check_id,
        BackgroundCheck.company_id == company_id
    ).first()

    if not check:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Background check not found: {check_id}"
        )

    return BackgroundCheckResponse.model_validate(check)


@router.get("", response_model=List[BackgroundCheckResponse])
def list_background_checks(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    check_type: Optional[str] = Query(None, description="Filter by check type"),
    onboarding_id: Optional[str] = Query(None, description="Filter by onboarding workflow"),
    driver_id: Optional[str] = Query(None, description="Filter by driver"),
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> List[BackgroundCheckResponse]:
    """
    List all background checks for the company.

    Optional filters:
    - status: pending, in_progress, completed, failed, error
    - check_type: mvr, psp, cdl_verification, clearinghouse, etc.
    - onboarding_id: Filter by specific onboarding workflow
    - driver_id: Filter by specific driver
    """
    from app.models.onboarding import BackgroundCheck

    query = db.query(BackgroundCheck).filter(
        BackgroundCheck.company_id == company_id
    )

    if status_filter:
        query = query.filter(BackgroundCheck.status == status_filter)

    if check_type:
        query = query.filter(BackgroundCheck.check_type == check_type)

    if onboarding_id:
        query = query.filter(BackgroundCheck.onboarding_id == onboarding_id)

    if driver_id:
        query = query.filter(BackgroundCheck.driver_id == driver_id)

    checks = query.order_by(BackgroundCheck.requested_at.desc()).all()

    return [BackgroundCheckResponse.model_validate(c) for c in checks]


@router.get("/drivers/{driver_id}/checks", response_model=List[BackgroundCheckResponse])
def get_driver_background_checks(
    driver_id: str,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> List[BackgroundCheckResponse]:
    """
    Get all background checks for a specific driver.

    Useful for viewing driver's background check history and compliance status.
    """
    checks = BackgroundCheckService.get_driver_checks(db=db, driver_id=driver_id)

    # Verify all checks belong to the company
    for check in checks:
        if check.company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

    return [BackgroundCheckResponse.model_validate(c) for c in checks]


@router.get("/billing/summary")
def get_billing_summary(
    start_date: Optional[datetime] = Query(None, description="Start date for billing period"),
    end_date: Optional[datetime] = Query(None, description="End date for billing period"),
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
):
    """
    Get billing summary for background checks.

    Shows total cost, breakdown by check type, and billing status.
    Defaults to current month if no dates provided.
    """
    summary = BackgroundCheckService.calculate_billing(
        db=db,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date
    )

    return summary

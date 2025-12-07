"""Onboarding API routes."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.db import get_db_sync
from app.schemas.onboarding import (
    OnboardingWorkflowCreate,
    OnboardingWorkflowUpdate,
    OnboardingWorkflowResponse,
    OnboardingLinkResponse,
    OnboardingCompleteRequest,
    OnboardingCompleteResponse,
    BackgroundCheckBatchRequest,
    BackgroundCheckBatchResponse,
)
from app.services.onboarding import OnboardingService

router = APIRouter()


def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    """Extract company ID from current user."""
    return current_user.company_id


def _user_id(current_user=Depends(deps.get_current_user)) -> str:
    """Extract user ID from current user."""
    return current_user.id


@router.post("/workflows", response_model=OnboardingWorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_onboarding_workflow(
    payload: OnboardingWorkflowCreate,
    company_id: str = Depends(_company_id),
    user_id: str = Depends(_user_id),
    db: Session = Depends(get_db_sync),
) -> OnboardingWorkflowResponse:
    """
    Create a new onboarding workflow.

    Creates an onboarding workflow for a new worker (employee, contractor, or driver).
    Optionally sends onboarding link immediately.
    """
    try:
        workflow = OnboardingService.create_onboarding_workflow(
            db=db,
            company_id=company_id,
            created_by=user_id,
            request=payload
        )

        # Generate and send onboarding link if requested
        if payload.send_onboarding_link:
            OnboardingService.generate_onboarding_link(
                db=db,
                workflow_id=workflow.id,
                expires_in_days=30
            )
            db.refresh(workflow)

        return OnboardingWorkflowResponse.model_validate(workflow)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create onboarding workflow: {str(e)}"
        )


@router.get("/workflows", response_model=List[OnboardingWorkflowResponse])
def list_onboarding_workflows(
    status_filter: Optional[str] = None,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> List[OnboardingWorkflowResponse]:
    """
    List all onboarding workflows for the company.

    Optional status filter: pending, in_progress, completed, cancelled
    """
    workflows = OnboardingService.get_company_workflows(
        db=db,
        company_id=company_id,
        status=status_filter
    )

    return [OnboardingWorkflowResponse.model_validate(w) for w in workflows]


@router.get("/workflows/{workflow_id}", response_model=OnboardingWorkflowResponse)
def get_onboarding_workflow(
    workflow_id: str,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> OnboardingWorkflowResponse:
    """Get a specific onboarding workflow by ID."""
    from app.models.onboarding import OnboardingWorkflow

    workflow = db.query(OnboardingWorkflow).filter(
        OnboardingWorkflow.id == workflow_id,
        OnboardingWorkflow.company_id == company_id
    ).first()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onboarding workflow not found: {workflow_id}"
        )

    return OnboardingWorkflowResponse.model_validate(workflow)


@router.patch("/workflows/{workflow_id}", response_model=OnboardingWorkflowResponse)
def update_onboarding_progress(
    workflow_id: str,
    payload: OnboardingWorkflowUpdate,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> OnboardingWorkflowResponse:
    """
    Update onboarding workflow progress.

    Used to track step completion, update status, etc.
    """
    try:
        workflow = OnboardingService.update_progress(
            db=db,
            workflow_id=workflow_id,
            update=payload
        )

        # Verify workflow belongs to company
        if workflow.company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        return OnboardingWorkflowResponse.model_validate(workflow)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/workflows/{workflow_id}/link", response_model=OnboardingLinkResponse)
def generate_onboarding_link(
    workflow_id: str,
    expires_in_days: int = 30,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> OnboardingLinkResponse:
    """
    Generate (or regenerate) an onboarding link for a workflow.

    Default expiration: 30 days
    """
    try:
        # Verify workflow belongs to company
        from app.models.onboarding import OnboardingWorkflow
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == workflow_id,
            OnboardingWorkflow.company_id == company_id
        ).first()

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Onboarding workflow not found: {workflow_id}"
            )

        link = OnboardingService.generate_onboarding_link(
            db=db,
            workflow_id=workflow_id,
            expires_in_days=expires_in_days
        )

        return link

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/workflows/{workflow_id}/background-checks", response_model=BackgroundCheckBatchResponse)
async def request_dot_background_checks(
    workflow_id: str,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> BackgroundCheckBatchResponse:
    """
    Request all required DOT background checks for a driver.

    Requests: MVR, PSP, CDL Verification, Clearinghouse Limited Query
    Total cost: ~$36.25
    """
    try:
        # Verify workflow belongs to company
        from app.models.onboarding import OnboardingWorkflow
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == workflow_id,
            OnboardingWorkflow.company_id == company_id
        ).first()

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Onboarding workflow not found: {workflow_id}"
            )

        if not workflow.is_dot_driver:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Background checks only applicable for DOT drivers"
            )

        result = await OnboardingService.request_dot_background_checks(
            db=db,
            workflow_id=workflow_id
        )

        return BackgroundCheckBatchResponse(
            onboarding_id=result.get("onboarding_id"),
            driver_id=result.get("driver_id"),
            checks_requested=result["checks_requested"],
            checks_initiated=[],  # TODO: Convert to response objects
            total_estimated_cost=result["total_cost"],
            billing_company_id=company_id
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/workflows/{workflow_id}/complete", response_model=OnboardingCompleteResponse)
def complete_onboarding(
    workflow_id: str,
    payload: OnboardingCompleteRequest,
    company_id: str = Depends(_company_id),
    db: Session = Depends(get_db_sync),
) -> OnboardingCompleteResponse:
    """
    Complete onboarding and create Worker/Driver records.

    This finalizes the onboarding process and creates the actual worker/driver records
    in the system. Optionally creates a user account for app access.
    """
    try:
        # Verify workflow belongs to company
        from app.models.onboarding import OnboardingWorkflow
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == workflow_id,
            OnboardingWorkflow.company_id == company_id
        ).first()

        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Onboarding workflow not found: {workflow_id}"
            )

        result = OnboardingService.complete_onboarding(
            db=db,
            workflow_id=workflow_id,
            request=payload
        )

        return OnboardingCompleteResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Public endpoint - does not require authentication
@router.get("/token/{token}", response_model=OnboardingWorkflowResponse)
def get_workflow_by_token(
    token: str,
    db: Session = Depends(get_db_sync),
) -> OnboardingWorkflowResponse:
    """
    Get onboarding workflow by token (public endpoint).

    This is used by the self-service onboarding portal.
    No authentication required, but token must be valid and not expired.
    """
    workflow = OnboardingService.get_workflow_by_token(db=db, token=token)

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired onboarding link"
        )

    return OnboardingWorkflowResponse.model_validate(workflow)

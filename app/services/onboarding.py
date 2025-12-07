"""
Onboarding Service
Manages worker and driver onboarding workflows with DOT compliance.
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session

from app.models.onboarding import OnboardingWorkflow, OnboardingStatus, DQFDocument
from app.models.worker import Worker
from app.models.driver import Driver
from app.schemas.onboarding import (
    OnboardingWorkflowCreate,
    OnboardingWorkflowUpdate,
    OnboardingLinkResponse,
    OnboardingCompleteRequest
)
from app.services.background_checks import BackgroundCheckService
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OnboardingService:
    """Service for managing worker and driver onboarding."""

    @staticmethod
    def create_onboarding_workflow(
        db: Session,
        company_id: str,
        created_by: Optional[str],
        request: OnboardingWorkflowCreate
    ) -> OnboardingWorkflow:
        """
        Create a new onboarding workflow.

        Args:
            db: Database session
            company_id: Company ID
            created_by: User ID creating the workflow
            request: Onboarding workflow creation request

        Returns:
            OnboardingWorkflow: Created onboarding workflow
        """
        workflow = OnboardingWorkflow(
            id=str(uuid.uuid4()),
            company_id=company_id,
            worker_type=request.worker_type,
            role_type=request.role_type,
            is_dot_driver=request.is_dot_driver,
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            phone=request.phone,
            status=OnboardingStatus.PENDING,
            created_by=created_by,
            completed_steps=[],
            background_checks_status={} if request.is_dot_driver else None,
            background_checks_cost=0 if request.is_dot_driver else None
        )

        db.add(workflow)
        db.commit()
        db.refresh(workflow)

        logger.info(
            f"Onboarding workflow created: {workflow.id}",
            extra={
                "workflow_id": workflow.id,
                "company_id": company_id,
                "worker_type": request.worker_type,
                "is_dot_driver": request.is_dot_driver
            }
        )

        return workflow

    @staticmethod
    def generate_onboarding_link(
        db: Session,
        workflow_id: str,
        expires_in_days: int = 30
    ) -> OnboardingLinkResponse:
        """
        Generate an onboarding link for a workflow.

        Args:
            db: Database session
            workflow_id: Onboarding workflow ID
            expires_in_days: Number of days until link expires

        Returns:
            OnboardingLinkResponse: Onboarding link details
        """
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == workflow_id
        ).first()

        if not workflow:
            raise ValueError(f"Onboarding workflow not found: {workflow_id}")

        # Generate secure token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Create onboarding URL
        # In production, this would use the actual frontend URL from settings
        base_url = getattr(settings, "frontend_url", "https://app.freightops.com")
        onboarding_url = f"{base_url}/onboarding/{token}"

        # Update workflow with token
        workflow.onboarding_token = token
        workflow.token_expires_at = expires_at
        workflow.onboarding_url = onboarding_url

        db.commit()

        logger.info(
            f"Onboarding link generated for workflow: {workflow_id}",
            extra={
                "workflow_id": workflow_id,
                "token": token[:8] + "...",  # Log truncated token
                "expires_at": expires_at.isoformat()
            }
        )

        # TODO: Send onboarding email with link
        email_sent = False
        if workflow.email:
            # In production, send email with onboarding link
            logger.info(f"Would send onboarding email to: {workflow.email}")
            email_sent = True

        return OnboardingLinkResponse(
            onboarding_id=workflow.id,
            onboarding_url=onboarding_url,
            token=token,
            expires_at=expires_at,
            email_sent=email_sent
        )

    @staticmethod
    def update_progress(
        db: Session,
        workflow_id: str,
        update: OnboardingWorkflowUpdate
    ) -> OnboardingWorkflow:
        """
        Update onboarding workflow progress.

        Args:
            db: Database session
            workflow_id: Workflow ID
            update: Progress update

        Returns:
            OnboardingWorkflow: Updated workflow
        """
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == workflow_id
        ).first()

        if not workflow:
            raise ValueError(f"Onboarding workflow not found: {workflow_id}")

        if update.current_step is not None:
            workflow.current_step = update.current_step

        if update.completed_steps is not None:
            workflow.completed_steps = update.completed_steps

        if update.status is not None:
            workflow.status = update.status  # type: ignore

            if update.status == "in_progress" and not workflow.started_at:
                workflow.started_at = datetime.utcnow()
            elif update.status == "completed" and not workflow.completed_at:
                workflow.completed_at = datetime.utcnow()

        if update.background_checks_status is not None:
            workflow.background_checks_status = update.background_checks_status

        db.commit()
        db.refresh(workflow)

        return workflow

    @staticmethod
    async def request_dot_background_checks(
        db: Session,
        workflow_id: str
    ) -> Dict[str, Any]:
        """
        Request all required DOT background checks for a driver.

        Standard DOT checks:
        - MVR (Motor Vehicle Record)
        - PSP (Pre-Employment Screening Program)
        - CDL Verification
        - Clearinghouse Limited Query

        Args:
            db: Database session
            workflow_id: Onboarding workflow ID

        Returns:
            Dict with batch check results
        """
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == workflow_id
        ).first()

        if not workflow:
            raise ValueError(f"Onboarding workflow not found: {workflow_id}")

        if not workflow.is_dot_driver:
            raise ValueError("Background checks only applicable for DOT drivers")

        # Request all standard DOT checks
        result = await BackgroundCheckService.batch_request_checks(
            db=db,
            company_id=workflow.company_id,
            onboarding_id=workflow.id,
            driver_id=workflow.driver_id,
            check_types=["mvr", "psp", "cdl_verification", "clearinghouse"],
            subject_name=f"{workflow.first_name} {workflow.last_name}",
            subject_cdl_number=None,  # Will be provided by applicant
            subject_cdl_state=None,
            subject_dob=None
        )

        # Update workflow with check status and cost
        workflow.background_checks_cost = result["total_cost"]
        workflow.background_checks_status = {
            "checks_requested": result["checks_requested"],
            "checks_initiated": [c.id for c in result["checks_initiated"]],
            "total_cost": result["total_cost"],
            "requested_at": datetime.utcnow().isoformat()
        }

        db.commit()

        return result

    @staticmethod
    def complete_onboarding(
        db: Session,
        workflow_id: str,
        request: OnboardingCompleteRequest
    ) -> Dict[str, Any]:
        """
        Complete onboarding and create worker/driver records.

        Args:
            db: Database session
            workflow_id: Workflow ID
            request: Completion request with worker/driver data

        Returns:
            Dict with created IDs and credentials
        """
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.id == workflow_id
        ).first()

        if not workflow:
            raise ValueError(f"Onboarding workflow not found: {workflow_id}")

        if workflow.status == OnboardingStatus.COMPLETED:
            raise ValueError("Onboarding already completed")

        # Create Worker record
        worker_id = str(uuid.uuid4())
        worker = Worker(
            id=worker_id,
            company_id=workflow.company_id,
            type=workflow.worker_type,  # type: ignore
            role=workflow.role_type,  # type: ignore
            first_name=workflow.first_name,
            last_name=workflow.last_name,
            email=workflow.email,
            phone=workflow.phone
        )
        db.add(worker)

        # Create Driver record if DOT driver
        driver_id = None
        if workflow.is_dot_driver:
            driver_id = str(uuid.uuid4())
            driver = Driver(
                id=driver_id,
                company_id=workflow.company_id,
                worker_id=worker_id,
                first_name=workflow.first_name,
                last_name=workflow.last_name,
                email=workflow.email,
                phone=workflow.phone
            )
            db.add(driver)
            workflow.driver_id = driver_id

        # Update workflow
        workflow.worker_id = worker_id
        workflow.status = OnboardingStatus.COMPLETED
        workflow.completed_at = datetime.utcnow()

        db.commit()

        logger.info(
            f"Onboarding completed: {workflow_id}",
            extra={
                "workflow_id": workflow_id,
                "worker_id": worker_id,
                "driver_id": driver_id
            }
        )

        return {
            "onboarding_id": workflow_id,
            "worker_id": worker_id,
            "driver_id": driver_id,
            "user_id": None,  # TODO: Create user account if requested
            "temporary_password": None,
            "message": "Onboarding completed successfully"
        }

    @staticmethod
    def get_workflow_by_token(db: Session, token: str) -> Optional[OnboardingWorkflow]:
        """Get onboarding workflow by token."""
        workflow = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.onboarding_token == token
        ).first()

        if workflow and workflow.token_expires_at:
            if datetime.utcnow() > workflow.token_expires_at:
                logger.warning(f"Expired onboarding token used: {token[:8]}...")
                return None

        return workflow

    @staticmethod
    def get_company_workflows(
        db: Session,
        company_id: str,
        status: Optional[str] = None
    ) -> List[OnboardingWorkflow]:
        """Get all onboarding workflows for a company."""
        query = db.query(OnboardingWorkflow).filter(
            OnboardingWorkflow.company_id == company_id
        )

        if status:
            query = query.filter(OnboardingWorkflow.status == status)

        return query.order_by(OnboardingWorkflow.created_at.desc()).all()

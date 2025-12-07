"""
Background Check Service
Integrates with MVR, PSP, CDL verification, and FMCSA Clearinghouse providers.

Providers:
- MVR (Motor Vehicle Records): State DMV APIs or third-party aggregators
- PSP (Pre-Employment Screening Program): FMCSA PSP system
- CDL Verification: CDLIS (Commercial Driver's License Information System)
- Clearinghouse: FMCSA Drug & Alcohol Clearinghouse
- Criminal Background: HireRight, Checkr, etc.

Pricing (typical):
- MVR: $10-25 per report
- PSP: $10 (FMCSA fee)
- CDL Verification: $5-15
- Clearinghouse Limited Query: $1.25
- Clearinghouse Full Query: $2.50
- Criminal Background: $25-50
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session

from app.models.onboarding import BackgroundCheck, BackgroundCheckType, BackgroundCheckStatus, BackgroundCheckResult
from app.schemas.onboarding import BackgroundCheckRequest, BackgroundCheckResponse, BackgroundCheckCostEstimate

logger = logging.getLogger(__name__)


# Pricing configuration (in USD)
BACKGROUND_CHECK_PRICING = {
    "mvr": {
        "cost": Decimal("15.00"),
        "turnaround_days": 2,
        "provider": "Foley Services / StateServ"
    },
    "psp": {
        "cost": Decimal("10.00"),
        "turnaround_days": 1,
        "provider": "FMCSA PSP"
    },
    "cdl_verification": {
        "cost": Decimal("10.00"),
        "turnaround_days": 1,
        "provider": "CDLIS"
    },
    "clearinghouse": {
        "cost": Decimal("1.25"),  # Limited query
        "turnaround_days": 1,
        "provider": "FMCSA Clearinghouse"
    },
    "criminal_background": {
        "cost": Decimal("35.00"),
        "turnaround_days": 3,
        "provider": "Checkr / HireRight"
    },
    "employment_verification": {
        "cost": Decimal("25.00"),
        "turnaround_days": 5,
        "provider": "Manual Verification"
    }
}


class BackgroundCheckService:
    """Service for managing background checks."""

    @staticmethod
    def get_cost_estimates() -> List[BackgroundCheckCostEstimate]:
        """Get cost estimates for all background check types."""
        estimates = []
        for check_type, info in BACKGROUND_CHECK_PRICING.items():
            estimates.append(
                BackgroundCheckCostEstimate(
                    check_type=check_type,  # type: ignore
                    provider=info["provider"],
                    estimated_cost=float(info["cost"]),
                    estimated_turnaround_days=info["turnaround_days"]
                )
            )
        return estimates

    @staticmethod
    def calculate_dot_driver_cost() -> float:
        """Calculate total cost for standard DOT driver checks (MVR + PSP + CDL + Clearinghouse)."""
        total = (
            BACKGROUND_CHECK_PRICING["mvr"]["cost"] +
            BACKGROUND_CHECK_PRICING["psp"]["cost"] +
            BACKGROUND_CHECK_PRICING["cdl_verification"]["cost"] +
            BACKGROUND_CHECK_PRICING["clearinghouse"]["cost"]
        )
        return float(total)

    @staticmethod
    async def request_background_check(
        db: Session,
        company_id: str,
        request: BackgroundCheckRequest
    ) -> BackgroundCheck:
        """
        Request a background check.

        This creates a pending background check record and would initiate the check
        with the appropriate provider in a production system.

        Args:
            db: Database session
            company_id: Company ID requesting the check
            request: Background check request details

        Returns:
            BackgroundCheck: Created background check record
        """
        # Get pricing info
        pricing = BACKGROUND_CHECK_PRICING.get(request.check_type)
        if not pricing:
            raise ValueError(f"Unknown background check type: {request.check_type}")

        # Create background check record
        check = BackgroundCheck(
            id=str(uuid.uuid4()),
            company_id=company_id,
            onboarding_id=request.onboarding_id,
            driver_id=request.driver_id,
            check_type=request.check_type,
            provider=pricing["provider"],
            provider_reference_id=f"REF-{secrets.token_hex(8).upper()}",  # Mock reference ID
            subject_name=request.subject_name,
            subject_cdl_number=request.subject_cdl_number,
            subject_cdl_state=request.subject_cdl_state,
            subject_dob=request.subject_dob,
            status=BackgroundCheckStatus.PENDING,
            cost=pricing["cost"],
            billed_to_company=True,
            billing_status="pending",
            requested_at=datetime.utcnow()
        )

        db.add(check)
        db.commit()
        db.refresh(check)

        logger.info(
            f"Background check requested: {request.check_type} for {request.subject_name}",
            extra={
                "check_id": check.id,
                "check_type": request.check_type,
                "company_id": company_id,
                "cost": float(pricing["cost"])
            }
        )

        # In production, this would initiate the actual background check with the provider
        # For now, we'll simulate the check process
        # asyncio.create_task(BackgroundCheckService._process_check(check.id, db))

        return check

    @staticmethod
    async def batch_request_checks(
        db: Session,
        company_id: str,
        onboarding_id: Optional[str],
        driver_id: Optional[str],
        check_types: List[str],
        subject_name: str,
        subject_cdl_number: Optional[str] = None,
        subject_cdl_state: Optional[str] = None,
        subject_dob: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Request multiple background checks in batch (e.g., for DOT driver onboarding).

        Args:
            db: Database session
            company_id: Company ID
            onboarding_id: Optional onboarding workflow ID
            driver_id: Optional driver ID
            check_types: List of check types to request
            subject_name: Subject's full name
            subject_cdl_number: CDL number
            subject_cdl_state: CDL state
            subject_dob: Date of birth

        Returns:
            Dict with batch results and total cost
        """
        checks = []
        total_cost = Decimal("0.00")

        for check_type in check_types:
            try:
                request = BackgroundCheckRequest(
                    onboarding_id=onboarding_id,
                    driver_id=driver_id,
                    check_type=check_type,  # type: ignore
                    subject_name=subject_name,
                    subject_cdl_number=subject_cdl_number,
                    subject_cdl_state=subject_cdl_state,
                    subject_dob=subject_dob
                )
                check = await BackgroundCheckService.request_background_check(
                    db=db,
                    company_id=company_id,
                    request=request
                )
                checks.append(check)
                if check.cost:
                    total_cost += check.cost
            except Exception as e:
                logger.error(
                    f"Failed to request {check_type} check: {str(e)}",
                    extra={"check_type": check_type, "company_id": company_id}
                )

        return {
            "checks_requested": len(check_types),
            "checks_initiated": checks,
            "total_cost": float(total_cost),
            "company_id": company_id,
            "onboarding_id": onboarding_id,
            "driver_id": driver_id
        }

    @staticmethod
    async def _process_check(check_id: str, db: Session):
        """
        Simulate processing a background check.
        In production, this would call the actual provider APIs.

        For demo purposes, this will mark the check as completed after a delay.
        """
        # This would be replaced with actual provider API calls
        # Example providers:
        # - MVR: Foley Services, StateServ, DriverReach
        # - PSP: FMCSA API
        # - CDL: CDLIS via state DMV APIs
        # - Clearinghouse: FMCSA Clearinghouse API
        # - Criminal: Checkr, HireRight, Accurate Background

        logger.info(f"Processing background check: {check_id}")

        # Simulated check processing would go here
        # For now, we'll just log that it would be processed
        pass

    @staticmethod
    def get_check_status(db: Session, check_id: str) -> Optional[BackgroundCheck]:
        """Get status of a background check."""
        return db.query(BackgroundCheck).filter(BackgroundCheck.id == check_id).first()

    @staticmethod
    def get_company_checks(
        db: Session,
        company_id: str,
        status: Optional[str] = None,
        check_type: Optional[str] = None
    ) -> List[BackgroundCheck]:
        """Get all background checks for a company."""
        query = db.query(BackgroundCheck).filter(BackgroundCheck.company_id == company_id)

        if status:
            query = query.filter(BackgroundCheck.status == status)
        if check_type:
            query = query.filter(BackgroundCheck.check_type == check_type)

        return query.order_by(BackgroundCheck.requested_at.desc()).all()

    @staticmethod
    def get_driver_checks(db: Session, driver_id: str) -> List[BackgroundCheck]:
        """Get all background checks for a specific driver."""
        return (
            db.query(BackgroundCheck)
            .filter(BackgroundCheck.driver_id == driver_id)
            .order_by(BackgroundCheck.requested_at.desc())
            .all()
        )

    @staticmethod
    def calculate_billing(
        db: Session,
        company_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate billing for background checks in a date range.

        Args:
            db: Database session
            company_id: Company ID
            start_date: Start date (default: beginning of current month)
            end_date: End date (default: now)

        Returns:
            Dict with billing summary
        """
        if not start_date:
            start_date = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not end_date:
            end_date = datetime.utcnow()

        checks = (
            db.query(BackgroundCheck)
            .filter(
                BackgroundCheck.company_id == company_id,
                BackgroundCheck.billed_to_company == True,
                BackgroundCheck.requested_at >= start_date,
                BackgroundCheck.requested_at <= end_date
            )
            .all()
        )

        total_cost = sum(float(check.cost or 0) for check in checks)
        checks_by_type = {}

        for check in checks:
            if check.check_type not in checks_by_type:
                checks_by_type[check.check_type] = {
                    "count": 0,
                    "total_cost": 0,
                    "provider": check.provider
                }
            checks_by_type[check.check_type]["count"] += 1
            checks_by_type[check.check_type]["total_cost"] += float(check.cost or 0)

        return {
            "company_id": company_id,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_checks": len(checks),
            "total_cost": total_cost,
            "checks_by_type": checks_by_type,
            "pending_billing": sum(1 for c in checks if c.billing_status == "pending"),
            "invoiced": sum(1 for c in checks if c.billing_status == "invoiced"),
            "paid": sum(1 for c in checks if c.billing_status == "paid")
        }


# Mock provider implementations (to be replaced with actual integrations)

class MVRProvider:
    """MVR (Motor Vehicle Record) provider integration."""

    @staticmethod
    async def request_mvr(
        cdl_number: str,
        cdl_state: str,
        driver_name: str,
        dob: date
    ) -> Dict[str, Any]:
        """Request MVR from state DMV or aggregator."""
        # In production, integrate with Foley Services, StateServ, or state DMV APIs
        logger.info(f"MVR requested for {driver_name} (CDL: {cdl_number}, State: {cdl_state})")
        return {
            "status": "pending",
            "reference_id": f"MVR-{secrets.token_hex(8).upper()}",
            "estimated_completion": datetime.utcnow() + timedelta(days=2)
        }


class PSPProvider:
    """PSP (Pre-Employment Screening Program) provider integration."""

    @staticmethod
    async def request_psp(cdl_number: str, cdl_state: str) -> Dict[str, Any]:
        """Request PSP from FMCSA."""
        # In production, integrate with FMCSA PSP API
        logger.info(f"PSP requested for CDL: {cdl_number}, State: {cdl_state}")
        return {
            "status": "pending",
            "reference_id": f"PSP-{secrets.token_hex(8).upper()}",
            "estimated_completion": datetime.utcnow() + timedelta(days=1)
        }


class CDLVerificationProvider:
    """CDL verification via CDLIS."""

    @staticmethod
    async def verify_cdl(cdl_number: str, cdl_state: str) -> Dict[str, Any]:
        """Verify CDL via CDLIS."""
        # In production, integrate with CDLIS via state DMV APIs
        logger.info(f"CDL verification for: {cdl_number}, State: {cdl_state}")
        return {
            "status": "pending",
            "reference_id": f"CDL-{secrets.token_hex(8).upper()}",
            "estimated_completion": datetime.utcnow() + timedelta(days=1)
        }


class ClearinghouseProvider:
    """FMCSA Drug & Alcohol Clearinghouse integration."""

    @staticmethod
    async def limited_query(cdl_number: str, cdl_state: str) -> Dict[str, Any]:
        """Perform limited query on Clearinghouse."""
        # In production, integrate with FMCSA Clearinghouse API
        logger.info(f"Clearinghouse limited query for CDL: {cdl_number}, State: {cdl_state}")
        return {
            "status": "pending",
            "reference_id": f"CLR-{secrets.token_hex(8).upper()}",
            "query_type": "limited",
            "cost": 1.25,
            "estimated_completion": datetime.utcnow() + timedelta(hours=24)
        }

    @staticmethod
    async def full_query(cdl_number: str, cdl_state: str, consent_obtained: bool = True) -> Dict[str, Any]:
        """Perform full query on Clearinghouse (requires driver consent)."""
        if not consent_obtained:
            raise ValueError("Driver consent required for full Clearinghouse query")

        # In production, integrate with FMCSA Clearinghouse API
        logger.info(f"Clearinghouse full query for CDL: {cdl_number}, State: {cdl_state}")
        return {
            "status": "pending",
            "reference_id": f"CLR-F-{secrets.token_hex(8).upper()}",
            "query_type": "full",
            "cost": 2.50,
            "estimated_completion": datetime.utcnow() + timedelta(hours=24)
        }

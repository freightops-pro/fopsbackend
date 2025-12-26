"""Router for driver settlements API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.models.driver import Driver
from app.services.settlements import SettlementsService
from app.schemas.settlements import (
    CurrentWeekSettlementResponse,
    SettlementHistoryResponse,
    PayStubListResponse,
    WeekSummaryResponse,
)
from sqlalchemy import select

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_driver_for_user(
    user: User, db: AsyncSession, driver_id: Optional[str] = None
) -> Driver:
    """Get the driver record for a user, or verify access to specified driver_id."""
    # If driver_id is provided, verify access
    if driver_id:
        query = select(Driver).where(
            Driver.id == driver_id,
            Driver.company_id == user.company_id,
        )
        result = await db.execute(query)
        driver = result.scalar_one_or_none()

        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")

        # If user is linked to a driver, they can only access their own data
        if user.id != driver.user_id:
            # Check if user has admin/dispatcher role
            user_is_admin = user.role and user.role.upper() in ["ADMIN", "OWNER", "DISPATCHER", "TENANT_ADMIN"]
            if not user_is_admin:
                raise HTTPException(status_code=403, detail="Not authorized to access this driver's data")

        return driver

    # If no driver_id provided, get driver linked to user
    query = select(Driver).where(Driver.user_id == user.id)
    result = await db.execute(query)
    driver = result.scalar_one_or_none()

    if not driver:
        raise HTTPException(
            status_code=404,
            detail="No driver profile linked to this user account"
        )

    return driver


@router.get("/driver/{driver_id}/current", response_model=CurrentWeekSettlementResponse)
async def get_current_week_settlement(
    driver_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current week's settlement progress for a driver.

    Returns earnings, deductions, and load statistics for the current week.
    """
    driver = await get_driver_for_user(current_user, db, driver_id)

    service = SettlementsService(db)
    return await service.get_current_week_settlement(
        driver_id=driver.id,
        company_id=driver.company_id,
    )


@router.get("/driver/{driver_id}/history", response_model=SettlementHistoryResponse)
async def get_settlement_history(
    driver_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get historical settlements for a driver.

    Returns paginated list of past settlements with earnings breakdown.
    """
    driver = await get_driver_for_user(current_user, db, driver_id)

    service = SettlementsService(db)
    settlements, total_count = await service.get_settlement_history(
        driver_id=driver.id,
        company_id=driver.company_id,
        limit=limit,
        offset=offset,
    )

    return SettlementHistoryResponse(
        settlements=settlements,
        total_count=total_count,
        page=(offset // limit) + 1,
        page_size=limit,
    )


@router.get("/driver/{driver_id}/paystubs", response_model=PayStubListResponse)
async def get_pay_stubs(
    driver_id: str,
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get pay stubs for a driver.

    Returns list of pay stubs with download URLs.
    """
    driver = await get_driver_for_user(current_user, db, driver_id)

    service = SettlementsService(db)
    pay_stubs = await service.get_pay_stubs(
        driver_id=driver.id,
        company_id=driver.company_id,
        limit=limit,
    )

    return PayStubListResponse(
        pay_stubs=pay_stubs,
        total_count=len(pay_stubs),
    )


@router.get("/driver/{driver_id}/week-summary", response_model=WeekSummaryResponse)
async def get_week_summary(
    driver_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get weekly summary for driver dashboard.

    Returns current earnings, projections, and comparison with last week.
    """
    driver = await get_driver_for_user(current_user, db, driver_id)

    service = SettlementsService(db)
    return await service.get_week_summary(
        driver_id=driver.id,
        company_id=driver.company_id,
    )


@router.get("/paystubs/{settlement_id}/download")
async def download_pay_stub(
    settlement_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download a pay stub as PDF.

    Returns the pay stub document for the specified settlement.
    """
    # Get the driver linked to current user
    driver = await get_driver_for_user(current_user, db)

    service = SettlementsService(db)
    pdf_bytes = await service.generate_pay_stub_pdf(
        settlement_id=settlement_id,
        driver_id=driver.id,
        company_id=driver.company_id,
    )

    if pdf_bytes is None:
        raise HTTPException(
            status_code=404,
            detail="Pay stub not found or PDF generation not available"
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=paystub_{settlement_id}.pdf"
        },
    )

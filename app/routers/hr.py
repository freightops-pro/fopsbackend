from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.accounting import PayrollSummary
from app.services.hr import HRService

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> HRService:
    return HRService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


@router.get("/payroll/summary", response_model=PayrollSummary)
async def get_payroll_summary(
    company_id: str = Depends(_company_id),
    service: HRService = Depends(_service),
) -> PayrollSummary:
    summary = await service.payroll_summary(company_id)
    return PayrollSummary(**summary)


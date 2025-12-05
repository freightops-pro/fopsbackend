from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.reporting import DashboardMetrics
from app.services.reporting import ReportingService

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> ReportingService:
    return ReportingService(db)


@router.get("/dashboard", response_model=DashboardMetrics)
async def dashboard_metrics(
    current_user=Depends(deps.get_current_user),
    service: ReportingService = Depends(_service),
) -> DashboardMetrics:
    return await service.dashboard(current_user.company_id)


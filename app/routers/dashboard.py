from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.dashboard import DashboardMetrics
from app.services.reporting import ReportingService

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> ReportingService:
    return ReportingService(db)


@router.get("/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    current_user=Depends(deps.get_current_user),
    service: ReportingService = Depends(_service),
) -> DashboardMetrics:
    try:
        return await service.dashboard_metrics(current_user.company_id)
    except Exception as e:
        from fastapi import HTTPException
        import traceback
        print(f"Error in dashboard_metrics: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to fetch dashboard metrics: {str(e)}")


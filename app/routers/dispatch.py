from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.dispatch import DispatchCalendarResponse, DispatchFiltersResponse
from app.schemas.matching import MatchingResponse
from app.services.dispatch import DispatchService
from app.services.matching import MatchingService

router = APIRouter()


async def _dispatch_service(db: AsyncSession = Depends(get_db)) -> DispatchService:
    return DispatchService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


@router.get("/calendar", response_model=DispatchCalendarResponse)
async def get_calendar(
    company_id: str = Depends(_company_id), service: DispatchService = Depends(_dispatch_service)
) -> DispatchCalendarResponse:
    return await service.calendar(company_id)


@router.get("/filters", response_model=DispatchFiltersResponse)
async def get_filters(
    company_id: str = Depends(_company_id), service: DispatchService = Depends(_dispatch_service)
) -> DispatchFiltersResponse:
    return await service.filters(company_id)


@router.get("/loads/{load_id}/matching", response_model=MatchingResponse)
async def match_load(
    load_id: str,
    company_id: str = Depends(_company_id),
    db: AsyncSession = Depends(get_db),
) -> MatchingResponse:
    service = MatchingService(db)
    try:
        return await service.suggest(company_id, load_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))



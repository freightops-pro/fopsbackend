from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.usage_ledger import UsageLedgerEntry
from app.services.usage_ledger import UsageLedgerService

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> UsageLedgerService:
    return UsageLedgerService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


@router.get("/preview", response_model=List[UsageLedgerEntry])
async def get_usage_preview(
    limit: int = Query(default=20, ge=1, le=100),
    company_id: str = Depends(_company_id),
    service: UsageLedgerService = Depends(_service),
) -> List[UsageLedgerEntry]:
    entries = await service.preview(company_id, limit)
    return entries


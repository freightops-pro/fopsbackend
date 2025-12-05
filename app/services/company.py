from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company


class CompanyService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_active(self) -> List[Company]:
        result = await self.db.execute(select(Company).where(Company.isActive.is_(True)))
        return list(result.scalars().all())


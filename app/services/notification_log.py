from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import NotificationLog


class NotificationLogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_logs(
        self,
        company_id: str,
        rule_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[NotificationLog]:
        query = (
            select(NotificationLog)
            .where(NotificationLog.company_id == company_id)
            .order_by(NotificationLog.created_at.desc())
            .limit(limit)
        )
        if rule_id:
            query = query.where(NotificationLog.rule_id == rule_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())


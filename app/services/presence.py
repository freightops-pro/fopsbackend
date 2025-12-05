from __future__ import annotations

import uuid
from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collaboration import Presence
from app.schemas.presence import PresenceState


class PresenceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def set_presence(self, channel_id: str, user_id: str, status: str) -> PresenceState:
        result = await self.db.execute(
            select(Presence).where(Presence.channel_id == channel_id, Presence.user_id == user_id)
        )
        record = result.scalar_one_or_none()
        if record:
            record.status = status
        else:
            record = Presence(
                id=str(uuid.uuid4()),
                channel_id=channel_id,
                user_id=user_id,
                status=status,
            )
            self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return PresenceState(
            user_id=record.user_id,
            status=record.status,
            last_seen_at=record.last_seen_at,
        )

    async def current_presence(self, channel_id: str) -> List[PresenceState]:
        result = await self.db.execute(select(Presence).where(Presence.channel_id == channel_id))
        return [
            PresenceState(user_id=record.user_id, status=record.status, last_seen_at=record.last_seen_at)
            for record in result.scalars().all()
        ]


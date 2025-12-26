"""HQ Employee Presence Service.

Tracks online/away/offline status for HQ portal employees
with support for away messages and automatic status detection.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hq_presence import HQPresence
from app.models.hq_employee import HQEmployee
from app.schemas.presence import PresenceState, PresenceStatus

# Auto-away thresholds
AUTO_AWAY_MINUTES = 5
AUTO_OFFLINE_MINUTES = 30


class HQPresenceService:
    """Service for HQ employee presence operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_employee_name(self, employee_id: str) -> Optional[str]:
        """Resolve employee name from employee_id."""
        result = await self.db.execute(select(HQEmployee).where(HQEmployee.id == employee_id))
        employee = result.scalar_one_or_none()
        if employee:
            return f"{employee.first_name} {employee.last_name}".strip() or employee.email
        return None

    async def set_presence(
        self,
        employee_id: str,
        status: PresenceStatus,
        away_message: Optional[str] = None,
        manual: bool = False,
    ) -> PresenceState:
        """Set employee presence status.

        Args:
            employee_id: The employee ID
            status: The presence status (online, away, offline)
            away_message: Optional away message
            manual: If True, status was set manually and won't auto-change
        """
        now = datetime.utcnow()
        result = await self.db.execute(
            select(HQPresence).where(HQPresence.employee_id == employee_id)
        )
        record = result.scalar_one_or_none()

        if record:
            record.status = status
            record.away_message = away_message
            record.status_set_manually = manual
            if status == "online":
                record.last_activity_at = now
        else:
            record = HQPresence(
                id=str(uuid.uuid4()),
                employee_id=employee_id,
                status=status,
                away_message=away_message,
                status_set_manually=manual,
                last_activity_at=now if status == "online" else None,
            )
            self.db.add(record)

        await self.db.commit()
        await self.db.refresh(record)

        employee_name = await self._get_employee_name(employee_id)
        return PresenceState(
            user_id=record.employee_id,
            user_name=employee_name,
            status=record.status,
            away_message=record.away_message,
            last_seen_at=record.updated_at,
            last_activity_at=record.last_activity_at,
        )

    async def update_activity(self, employee_id: str) -> Optional[PresenceState]:
        """Update last activity timestamp (heartbeat).

        Called periodically by clients to indicate activity.
        Also restores user to online if they were auto-away.
        """
        now = datetime.utcnow()
        result = await self.db.execute(
            select(HQPresence).where(HQPresence.employee_id == employee_id)
        )
        record = result.scalar_one_or_none()

        if not record:
            # Create presence record if doesn't exist
            return await self.set_presence(employee_id, "online")

        record.last_activity_at = now

        # If user was auto-away (not manually set), restore to online
        if record.status == "away" and not record.status_set_manually:
            record.status = "online"

        await self.db.commit()
        await self.db.refresh(record)

        employee_name = await self._get_employee_name(employee_id)
        return PresenceState(
            user_id=record.employee_id,
            user_name=employee_name,
            status=record.status,
            away_message=record.away_message,
            last_seen_at=record.updated_at,
            last_activity_at=record.last_activity_at,
        )

    async def set_away_message(
        self, employee_id: str, away_message: Optional[str]
    ) -> Optional[PresenceState]:
        """Set or clear away message for an employee."""
        result = await self.db.execute(
            select(HQPresence).where(HQPresence.employee_id == employee_id)
        )
        record = result.scalar_one_or_none()

        if not record:
            return None

        record.away_message = away_message
        await self.db.commit()
        await self.db.refresh(record)

        employee_name = await self._get_employee_name(employee_id)
        return PresenceState(
            user_id=record.employee_id,
            user_name=employee_name,
            status=record.status,
            away_message=record.away_message,
            last_seen_at=record.updated_at,
            last_activity_at=record.last_activity_at,
        )

    async def mark_employee_offline(self, employee_id: str) -> Optional[PresenceState]:
        """Mark employee as offline (e.g., on disconnect)."""
        result = await self.db.execute(
            select(HQPresence).where(HQPresence.employee_id == employee_id)
        )
        record = result.scalar_one_or_none()

        if not record:
            return None

        record.status = "offline"
        record.status_set_manually = False
        await self.db.commit()
        await self.db.refresh(record)

        employee_name = await self._get_employee_name(employee_id)
        return PresenceState(
            user_id=record.employee_id,
            user_name=employee_name,
            status=record.status,
            away_message=record.away_message,
            last_seen_at=record.updated_at,
            last_activity_at=record.last_activity_at,
        )

    async def check_idle_employees(self) -> List[PresenceState]:
        """Check for idle employees and update their status.

        Returns list of employees whose status changed.
        Called by scheduler job.
        """
        now = datetime.utcnow()
        away_threshold = now - timedelta(minutes=AUTO_AWAY_MINUTES)
        offline_threshold = now - timedelta(minutes=AUTO_OFFLINE_MINUTES)

        # Get all online/away employees who haven't set status manually
        result = await self.db.execute(
            select(HQPresence).where(
                and_(
                    HQPresence.status.in_(["online", "away"]),
                    HQPresence.status_set_manually == False,
                )
            )
        )
        records = result.scalars().all()

        changed: List[PresenceState] = []
        for record in records:
            if not record.last_activity_at:
                continue

            new_status = None
            if record.last_activity_at < offline_threshold:
                new_status = "offline"
            elif record.last_activity_at < away_threshold and record.status == "online":
                new_status = "away"

            if new_status and new_status != record.status:
                record.status = new_status
                employee_name = await self._get_employee_name(record.employee_id)
                changed.append(PresenceState(
                    user_id=record.employee_id,
                    user_name=employee_name,
                    status=record.status,
                    away_message=record.away_message,
                    last_seen_at=record.updated_at,
                    last_activity_at=record.last_activity_at,
                ))

        if changed:
            await self.db.commit()

        return changed

    async def get_all_presence(self) -> List[PresenceState]:
        """Get presence for all HQ employees."""
        result = await self.db.execute(select(HQPresence))

        states = []
        for record in result.scalars().all():
            employee_name = await self._get_employee_name(record.employee_id)
            states.append(PresenceState(
                user_id=record.employee_id,
                user_name=employee_name,
                status=record.status,
                away_message=record.away_message,
                last_seen_at=record.updated_at,
                last_activity_at=record.last_activity_at,
            ))
        return states

    async def get_employee_presence(self, employee_id: str) -> Optional[PresenceState]:
        """Get presence for a specific employee."""
        result = await self.db.execute(
            select(HQPresence).where(HQPresence.employee_id == employee_id)
        )
        record = result.scalar_one_or_none()

        if not record:
            return None

        employee_name = await self._get_employee_name(employee_id)
        return PresenceState(
            user_id=record.employee_id,
            user_name=employee_name,
            status=record.status,
            away_message=record.away_message,
            last_seen_at=record.updated_at,
            last_activity_at=record.last_activity_at,
        )

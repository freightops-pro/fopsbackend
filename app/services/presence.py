from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collaboration import Presence
from app.models.user import User
from app.schemas.presence import PresenceState, PresenceStatus

# Auto-away thresholds
AUTO_AWAY_MINUTES = 5
AUTO_OFFLINE_MINUTES = 30


class PresenceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_user_name(self, user_id: str) -> Optional[str]:
        """Resolve user name from user_id."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            return f"{user.first_name} {user.last_name}".strip() or user.email
        return None

    async def set_presence(
        self,
        channel_id: str,
        user_id: str,
        status: PresenceStatus,
        away_message: Optional[str] = None,
        manual: bool = False,
    ) -> PresenceState:
        """Set user presence status in a channel.

        Args:
            channel_id: The channel ID
            user_id: The user ID
            status: The presence status (online, away, offline)
            away_message: Optional away message
            manual: If True, status was set manually and won't auto-change
        """
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Presence).where(Presence.channel_id == channel_id, Presence.user_id == user_id)
        )
        record = result.scalar_one_or_none()

        if record:
            record.status = status
            record.away_message = away_message
            record.status_set_manually = manual
            if status == "online":
                record.last_activity_at = now
        else:
            record = Presence(
                id=str(uuid.uuid4()),
                channel_id=channel_id,
                user_id=user_id,
                status=status,
                away_message=away_message,
                status_set_manually=manual,
                last_activity_at=now if status == "online" else None,
            )
            self.db.add(record)

        await self.db.commit()
        await self.db.refresh(record)

        user_name = await self._get_user_name(user_id)
        return PresenceState(
            user_id=record.user_id,
            user_name=user_name,
            status=record.status,
            away_message=record.away_message,
            last_seen_at=record.last_seen_at,
            last_activity_at=record.last_activity_at,
        )

    async def update_activity(self, channel_id: str, user_id: str) -> Optional[PresenceState]:
        """Update last activity timestamp (heartbeat).

        Called periodically by clients to indicate activity.
        Also restores user to online if they were auto-away.
        """
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Presence).where(Presence.channel_id == channel_id, Presence.user_id == user_id)
        )
        record = result.scalar_one_or_none()

        if not record:
            # Create presence record if doesn't exist
            return await self.set_presence(channel_id, user_id, "online")

        record.last_activity_at = now

        # If user was auto-away (not manually set), restore to online
        if record.status == "away" and not record.status_set_manually:
            record.status = "online"

        await self.db.commit()
        await self.db.refresh(record)

        user_name = await self._get_user_name(user_id)
        return PresenceState(
            user_id=record.user_id,
            user_name=user_name,
            status=record.status,
            away_message=record.away_message,
            last_seen_at=record.last_seen_at,
            last_activity_at=record.last_activity_at,
        )

    async def set_away_message(
        self, channel_id: str, user_id: str, away_message: Optional[str]
    ) -> Optional[PresenceState]:
        """Set or clear away message for a user."""
        result = await self.db.execute(
            select(Presence).where(Presence.channel_id == channel_id, Presence.user_id == user_id)
        )
        record = result.scalar_one_or_none()

        if not record:
            return None

        record.away_message = away_message
        await self.db.commit()
        await self.db.refresh(record)

        user_name = await self._get_user_name(user_id)
        return PresenceState(
            user_id=record.user_id,
            user_name=user_name,
            status=record.status,
            away_message=record.away_message,
            last_seen_at=record.last_seen_at,
            last_activity_at=record.last_activity_at,
        )

    async def mark_user_offline(self, channel_id: str, user_id: str) -> Optional[PresenceState]:
        """Mark user as offline (e.g., on disconnect)."""
        result = await self.db.execute(
            select(Presence).where(Presence.channel_id == channel_id, Presence.user_id == user_id)
        )
        record = result.scalar_one_or_none()

        if not record:
            return None

        record.status = "offline"
        record.status_set_manually = False
        await self.db.commit()
        await self.db.refresh(record)

        user_name = await self._get_user_name(user_id)
        return PresenceState(
            user_id=record.user_id,
            user_name=user_name,
            status=record.status,
            away_message=record.away_message,
            last_seen_at=record.last_seen_at,
            last_activity_at=record.last_activity_at,
        )

    async def check_idle_users(self, channel_id: str) -> List[PresenceState]:
        """Check for idle users and update their status.

        Returns list of users whose status changed.
        Called by scheduler job.
        """
        import logging
        logger = logging.getLogger(__name__)

        now = datetime.utcnow()
        away_threshold = now - timedelta(minutes=AUTO_AWAY_MINUTES)
        offline_threshold = now - timedelta(minutes=AUTO_OFFLINE_MINUTES)

        # Get all online/away users who haven't set status manually
        result = await self.db.execute(
            select(Presence).where(
                and_(
                    Presence.channel_id == channel_id,
                    Presence.status.in_(["online", "away"]),
                    Presence.status_set_manually == False,
                )
            )
        )
        records = result.scalars().all()

        changed: List[PresenceState] = []
        for record in records:
            try:
                if not record.last_activity_at:
                    continue

                new_status = None
                if record.last_activity_at < offline_threshold:
                    new_status = "offline"
                elif record.last_activity_at < away_threshold and record.status == "online":
                    new_status = "away"

                if new_status and new_status != record.status:
                    record.status = new_status

                    # Safely get user name - handle case where user may be deleted
                    try:
                        user_name = await self._get_user_name(record.user_id)
                    except Exception as exc:
                        logger.warning(
                            f"Failed to get user name for presence check: user_id={record.user_id}",
                            extra={"error": str(exc), "user_id": record.user_id, "channel_id": channel_id}
                        )
                        user_name = None

                    changed.append(PresenceState(
                        user_id=record.user_id,
                        user_name=user_name,
                        status=record.status,
                        away_message=record.away_message,
                        last_seen_at=record.last_seen_at,
                        last_activity_at=record.last_activity_at,
                    ))
            except Exception as exc:
                # Log but don't fail entire check due to one bad record
                logger.warning(
                    f"Failed to process presence record during idle check: {exc}",
                    extra={"error": str(exc), "presence_id": record.id, "channel_id": channel_id}
                )
                continue

        if changed:
            try:
                await self.db.commit()
            except Exception as exc:
                logger.error(
                    f"Failed to commit presence changes: {exc}",
                    extra={"error": str(exc), "channel_id": channel_id, "changed_count": len(changed)}
                )
                await self.db.rollback()
                raise

        return changed

    async def cleanup_orphaned_records(self) -> int:
        """Remove presence records for deleted users or channels.

        Returns count of records removed.
        Called periodically by scheduler to prevent stale data.
        """
        import logging
        logger = logging.getLogger(__name__)

        # Find presence records where the user no longer exists
        from app.models.user import User
        from app.models.collaboration import Channel

        orphaned_count = 0

        # Clean up records for deleted users
        try:
            user_cleanup = await self.db.execute(
                select(Presence).where(
                    ~Presence.user_id.in_(
                        select(User.id)
                    )
                )
            )
            orphaned_users = user_cleanup.scalars().all()

            for record in orphaned_users:
                await self.db.delete(record)
                orphaned_count += 1

            if orphaned_users:
                logger.info(
                    f"Cleaned up {len(orphaned_users)} presence records for deleted users",
                    extra={"orphaned_user_count": len(orphaned_users)}
                )
        except Exception as exc:
            logger.warning(f"Failed to cleanup orphaned user presence records: {exc}")

        # Clean up records for deleted channels
        try:
            channel_cleanup = await self.db.execute(
                select(Presence).where(
                    ~Presence.channel_id.in_(
                        select(Channel.id)
                    )
                )
            )
            orphaned_channels = channel_cleanup.scalars().all()

            for record in orphaned_channels:
                await self.db.delete(record)
                orphaned_count += 1

            if orphaned_channels:
                logger.info(
                    f"Cleaned up {len(orphaned_channels)} presence records for deleted channels",
                    extra={"orphaned_channel_count": len(orphaned_channels)}
                )
        except Exception as exc:
            logger.warning(f"Failed to cleanup orphaned channel presence records: {exc}")

        # Commit if we made changes
        if orphaned_count > 0:
            try:
                await self.db.commit()
                logger.info(
                    f"Presence cleanup complete: removed {orphaned_count} orphaned records",
                    extra={"total_removed": orphaned_count}
                )
            except Exception as exc:
                logger.error(f"Failed to commit presence cleanup: {exc}")
                await self.db.rollback()
                raise

        return orphaned_count

    async def current_presence(self, channel_id: str) -> List[PresenceState]:
        """Get current presence for all users in a channel."""
        result = await self.db.execute(select(Presence).where(Presence.channel_id == channel_id))

        states = []
        for record in result.scalars().all():
            user_name = await self._get_user_name(record.user_id)
            states.append(PresenceState(
                user_id=record.user_id,
                user_name=user_name,
                status=record.status,
                away_message=record.away_message,
                last_seen_at=record.last_seen_at,
                last_activity_at=record.last_activity_at,
            ))
        return states

    async def get_user_presence(self, user_id: str) -> List[PresenceState]:
        """Get presence for a specific user across all channels."""
        result = await self.db.execute(select(Presence).where(Presence.user_id == user_id))

        user_name = await self._get_user_name(user_id)
        return [
            PresenceState(
                user_id=record.user_id,
                user_name=user_name,
                status=record.status,
                away_message=record.away_message,
                last_seen_at=record.last_seen_at,
                last_activity_at=record.last_activity_at,
            )
            for record in result.scalars().all()
        ]


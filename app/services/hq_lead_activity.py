"""HQ Lead Activity service for notes, follow-ups, and activity timeline."""

import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hq_lead import HQLead
from app.models.hq_lead_activity import (
    HQLeadActivity, ActivityType, FollowUpStatus
)

logger = logging.getLogger(__name__)


class HQLeadActivityService:
    """
    Service for managing lead activities - notes, follow-ups, calls, etc.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Activity CRUD
    # =========================================================================

    async def get_activities(
        self,
        lead_id: str,
        activity_types: Optional[List[ActivityType]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[HQLeadActivity]:
        """Get activities for a lead."""
        query = select(HQLeadActivity).where(HQLeadActivity.lead_id == lead_id)

        if activity_types:
            query = query.where(HQLeadActivity.activity_type.in_(activity_types))

        query = query.order_by(
            HQLeadActivity.is_pinned.desc(),
            HQLeadActivity.created_at.desc()
        ).offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_activity(self, activity_id: str) -> Optional[HQLeadActivity]:
        """Get a specific activity."""
        result = await self.db.execute(
            select(HQLeadActivity).where(HQLeadActivity.id == activity_id)
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Notes
    # =========================================================================

    async def add_note(
        self,
        lead_id: str,
        content: str,
        created_by_id: str,
        is_pinned: bool = False,
    ) -> HQLeadActivity:
        """Add a note to a lead."""
        activity = HQLeadActivity(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            activity_type=ActivityType.NOTE,
            content=content,
            created_by_id=created_by_id,
            is_pinned=is_pinned,
        )

        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(activity)

        logger.info(f"Note added to lead {lead_id}", extra={"activity_id": activity.id})
        return activity

    async def update_note(
        self,
        activity_id: str,
        content: Optional[str] = None,
        is_pinned: Optional[bool] = None,
    ) -> Optional[HQLeadActivity]:
        """Update a note."""
        activity = await self.get_activity(activity_id)
        if not activity or activity.activity_type != ActivityType.NOTE:
            return None

        if content is not None:
            activity.content = content
        if is_pinned is not None:
            activity.is_pinned = is_pinned

        await self.db.commit()
        await self.db.refresh(activity)
        return activity

    async def delete_activity(self, activity_id: str) -> bool:
        """Delete an activity."""
        activity = await self.get_activity(activity_id)
        if not activity:
            return False

        await self.db.delete(activity)
        await self.db.commit()
        return True

    # =========================================================================
    # Follow-ups
    # =========================================================================

    async def create_follow_up(
        self,
        lead_id: str,
        follow_up_date: datetime,
        content: str,
        created_by_id: str,
        subject: Optional[str] = None,
    ) -> HQLeadActivity:
        """Create a follow-up reminder for a lead."""
        activity = HQLeadActivity(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            activity_type=ActivityType.FOLLOW_UP,
            subject=subject or "Follow-up reminder",
            content=content,
            follow_up_date=follow_up_date,
            follow_up_status=FollowUpStatus.PENDING,
            created_by_id=created_by_id,
        )

        self.db.add(activity)

        # Also update the lead's next_follow_up_date
        result = await self.db.execute(
            select(HQLead).where(HQLead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        if lead:
            # Update if this is sooner than existing follow-up
            if not lead.next_follow_up_date or follow_up_date < lead.next_follow_up_date:
                lead.next_follow_up_date = follow_up_date

        await self.db.commit()
        await self.db.refresh(activity)

        logger.info(f"Follow-up created for lead {lead_id}", extra={"date": follow_up_date.isoformat()})
        return activity

    async def complete_follow_up(
        self,
        activity_id: str,
        notes: Optional[str] = None,
    ) -> Optional[HQLeadActivity]:
        """Mark a follow-up as completed."""
        activity = await self.get_activity(activity_id)
        if not activity or activity.activity_type != ActivityType.FOLLOW_UP:
            return None

        activity.follow_up_status = FollowUpStatus.COMPLETED
        activity.follow_up_completed_at = datetime.utcnow()

        if notes:
            activity.content = f"{activity.content}\n\n--- Completion Notes ---\n{notes}"

        # Update lead's next follow-up date
        await self._update_lead_next_follow_up(activity.lead_id)

        await self.db.commit()
        await self.db.refresh(activity)
        return activity

    async def snooze_follow_up(
        self,
        activity_id: str,
        new_date: datetime,
    ) -> Optional[HQLeadActivity]:
        """Snooze a follow-up to a new date."""
        activity = await self.get_activity(activity_id)
        if not activity or activity.activity_type != ActivityType.FOLLOW_UP:
            return None

        activity.follow_up_status = FollowUpStatus.PENDING
        activity.follow_up_date = new_date

        # Update lead's next follow-up date
        await self._update_lead_next_follow_up(activity.lead_id)

        await self.db.commit()
        await self.db.refresh(activity)
        return activity

    async def get_due_follow_ups(
        self,
        sales_rep_id: Optional[str] = None,
        include_overdue: bool = True,
    ) -> List[HQLeadActivity]:
        """Get follow-ups that are due now or overdue."""
        now = datetime.utcnow()

        query = select(HQLeadActivity).where(
            and_(
                HQLeadActivity.activity_type == ActivityType.FOLLOW_UP,
                HQLeadActivity.follow_up_status == FollowUpStatus.PENDING,
                HQLeadActivity.follow_up_date <= now if include_overdue else HQLeadActivity.follow_up_date == now.date(),
            )
        )

        if sales_rep_id:
            # Join with lead to filter by assigned sales rep
            query = query.join(HQLead).where(HQLead.assigned_sales_rep_id == sales_rep_id)

        query = query.order_by(HQLeadActivity.follow_up_date.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_upcoming_follow_ups(
        self,
        sales_rep_id: Optional[str] = None,
        days_ahead: int = 7,
    ) -> List[HQLeadActivity]:
        """Get follow-ups coming up in the next N days."""
        now = datetime.utcnow()
        end_date = now + timedelta(days=days_ahead)

        query = select(HQLeadActivity).where(
            and_(
                HQLeadActivity.activity_type == ActivityType.FOLLOW_UP,
                HQLeadActivity.follow_up_status == FollowUpStatus.PENDING,
                HQLeadActivity.follow_up_date > now,
                HQLeadActivity.follow_up_date <= end_date,
            )
        )

        if sales_rep_id:
            query = query.join(HQLead).where(HQLead.assigned_sales_rep_id == sales_rep_id)

        query = query.order_by(HQLeadActivity.follow_up_date.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _update_lead_next_follow_up(self, lead_id: str):
        """Update the lead's next_follow_up_date based on pending follow-ups."""
        result = await self.db.execute(
            select(HQLeadActivity).where(
                and_(
                    HQLeadActivity.lead_id == lead_id,
                    HQLeadActivity.activity_type == ActivityType.FOLLOW_UP,
                    HQLeadActivity.follow_up_status == FollowUpStatus.PENDING,
                )
            ).order_by(HQLeadActivity.follow_up_date.asc()).limit(1)
        )
        next_follow_up = result.scalar_one_or_none()

        lead_result = await self.db.execute(
            select(HQLead).where(HQLead.id == lead_id)
        )
        lead = lead_result.scalar_one_or_none()

        if lead:
            lead.next_follow_up_date = next_follow_up.follow_up_date if next_follow_up else None

    # =========================================================================
    # Call Logging
    # =========================================================================

    async def log_call(
        self,
        lead_id: str,
        created_by_id: str,
        outcome: str,
        notes: Optional[str] = None,
        duration_seconds: Optional[int] = None,
    ) -> HQLeadActivity:
        """Log a phone call with a lead."""
        activity = HQLeadActivity(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            activity_type=ActivityType.CALL,
            subject=f"Phone call - {outcome}",
            content=notes,
            call_duration_seconds=str(duration_seconds) if duration_seconds else None,
            call_outcome=outcome,
            created_by_id=created_by_id,
        )

        self.db.add(activity)

        # Update lead's last_contacted_at
        result = await self.db.execute(
            select(HQLead).where(HQLead.id == lead_id)
        )
        lead = result.scalar_one_or_none()
        if lead:
            lead.last_contacted_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(activity)

        logger.info(f"Call logged for lead {lead_id}", extra={"outcome": outcome})
        return activity

    # =========================================================================
    # Status Change Logging
    # =========================================================================

    async def log_status_change(
        self,
        lead_id: str,
        old_status: str,
        new_status: str,
        changed_by_id: str,
        reason: Optional[str] = None,
    ) -> HQLeadActivity:
        """Log a lead status change."""
        activity = HQLeadActivity(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            activity_type=ActivityType.STATUS_CHANGE,
            subject=f"Status changed: {old_status} → {new_status}",
            content=reason,
            created_by_id=changed_by_id,
            extra_data={
                "old_status": old_status,
                "new_status": new_status,
            }
        )

        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(activity)

        return activity

    # =========================================================================
    # AI Action Logging
    # =========================================================================

    async def log_ai_action(
        self,
        lead_id: str,
        action_type: str,
        description: str,
        ai_reasoning: Optional[str] = None,
        was_auto_executed: bool = False,
    ) -> HQLeadActivity:
        """Log an AI action on a lead."""
        activity = HQLeadActivity(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            activity_type=ActivityType.AI_ACTION,
            subject=f"AI: {action_type}",
            content=description,
            extra_data={
                "action_type": action_type,
                "ai_reasoning": ai_reasoning,
                "was_auto_executed": was_auto_executed,
            }
        )

        self.db.add(activity)
        await self.db.commit()
        await self.db.refresh(activity)

        return activity

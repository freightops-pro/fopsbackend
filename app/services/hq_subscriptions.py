"""HQ Subscriptions service for managing tenant subscriptions."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hq_subscription import (
    HQSubscription, HQSubscriptionRateChange,
    HQSubscriptionStatus, HQBillingInterval
)
from app.models.hq_tenant import HQTenant
from app.models.hq_deal import HQDeal, DealStage


class HQSubscriptionsService:
    """Service for managing tenant subscriptions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _generate_subscription_number(self) -> str:
        """Generate unique subscription number like SUB-000001."""
        result = await self.db.execute(
            select(func.count(HQSubscription.id))
        )
        count = result.scalar() or 0
        return f"SUB-{count + 1:06d}"

    async def get_subscriptions(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all subscriptions with optional filtering."""
        query = select(HQSubscription).options(
            selectinload(HQSubscription.tenant).selectinload(HQTenant.company)
        )

        if status:
            query = query.where(HQSubscription.status == status)

        query = query.order_by(HQSubscription.created_at.desc()).offset(offset).limit(limit)

        result = await self.db.execute(query)
        subscriptions = result.scalars().all()

        return [self._to_response(sub) for sub in subscriptions]

    async def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get a single subscription by ID."""
        result = await self.db.execute(
            select(HQSubscription)
            .options(selectinload(HQSubscription.tenant).selectinload(HQTenant.company))
            .where(HQSubscription.id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            return None
        return self._to_response(subscription)

    async def get_subscription_by_tenant(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get subscription for a tenant."""
        result = await self.db.execute(
            select(HQSubscription)
            .options(selectinload(HQSubscription.tenant).selectinload(HQTenant.company))
            .where(HQSubscription.tenant_id == tenant_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            return None
        return self._to_response(subscription)

    async def create_subscription(
        self,
        data: Dict[str, Any],
        created_by_id: str
    ) -> Dict[str, Any]:
        """Create a new subscription."""
        subscription_number = await self._generate_subscription_number()

        # Parse billing interval
        billing_interval = HQBillingInterval.MONTHLY
        if data.get("billing_interval"):
            try:
                billing_interval = HQBillingInterval(data["billing_interval"])
            except ValueError:
                billing_interval = HQBillingInterval.MONTHLY

        # Calculate current MRR
        monthly_rate = Decimal(str(data.get("monthly_rate", 0)))
        current_mrr = monthly_rate

        subscription = HQSubscription(
            id=str(uuid.uuid4()),
            subscription_number=subscription_number,
            tenant_id=data["tenant_id"],
            deal_id=data.get("deal_id"),
            status=HQSubscriptionStatus.ACTIVE,
            billing_interval=billing_interval,
            monthly_rate=monthly_rate,
            annual_rate=Decimal(str(data.get("annual_rate", 0))) if data.get("annual_rate") else None,
            current_mrr=current_mrr,
            setup_fee=Decimal(str(data.get("setup_fee", 0))) if data.get("setup_fee") else None,
            setup_fee_paid=data.get("setup_fee_paid", False),
            trial_ends_at=data.get("trial_ends_at"),
            started_at=data.get("started_at") or datetime.utcnow(),
            next_billing_date=data.get("next_billing_date"),
            truck_limit=data.get("truck_limit"),
            user_limit=data.get("user_limit"),
            notes=data.get("notes"),
            created_by_id=created_by_id,
        )

        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)

        return await self.get_subscription(subscription.id)

    async def create_subscription_from_deal(
        self,
        deal_id: str,
        data: Dict[str, Any],
        created_by_id: str
    ) -> Optional[Dict[str, Any]]:
        """Create a subscription from a won deal."""
        # Get the deal
        result = await self.db.execute(
            select(HQDeal).where(HQDeal.id == deal_id)
        )
        deal = result.scalar_one_or_none()
        if not deal:
            return None

        # Deal must be won
        if deal.stage != DealStage.WON:
            raise ValueError("Deal must be in 'won' stage to create subscription")

        # Need a tenant_id
        if not data.get("tenant_id"):
            raise ValueError("tenant_id is required to create subscription")

        subscription_number = await self._generate_subscription_number()

        # Use deal values as defaults
        monthly_rate = Decimal(str(data.get("monthly_rate") or deal.estimated_mrr or 0))
        setup_fee = Decimal(str(data.get("setup_fee") or deal.estimated_setup_fee or 0))

        subscription = HQSubscription(
            id=str(uuid.uuid4()),
            subscription_number=subscription_number,
            tenant_id=data["tenant_id"],
            deal_id=deal_id,
            status=HQSubscriptionStatus.ACTIVE,
            billing_interval=HQBillingInterval(data.get("billing_interval", "monthly")),
            monthly_rate=monthly_rate,
            annual_rate=Decimal(str(data.get("annual_rate", 0))) if data.get("annual_rate") else None,
            current_mrr=monthly_rate,
            setup_fee=setup_fee,
            setup_fee_paid=data.get("setup_fee_paid", False),
            started_at=datetime.utcnow(),
            truck_limit=deal.estimated_trucks,
            notes=data.get("notes"),
            created_by_id=created_by_id,
        )

        self.db.add(subscription)

        # Link subscription to deal
        deal.subscription_id = subscription.id

        await self.db.commit()
        await self.db.refresh(subscription)

        return await self.get_subscription(subscription.id)

    async def update_subscription(
        self,
        subscription_id: str,
        data: Dict[str, Any],
        updated_by_id: str
    ) -> Optional[Dict[str, Any]]:
        """Update an existing subscription."""
        result = await self.db.execute(
            select(HQSubscription).where(HQSubscription.id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            return None

        # Track rate changes
        old_mrr = subscription.current_mrr
        new_mrr = None

        # Update fields
        for field in ["notes", "truck_limit", "user_limit", "next_billing_date"]:
            if field in data:
                setattr(subscription, field, data[field])

        # Handle status
        if "status" in data:
            new_status = HQSubscriptionStatus(data["status"])
            subscription.status = new_status

            if new_status == HQSubscriptionStatus.PAUSED:
                subscription.paused_at = datetime.utcnow()
            elif new_status == HQSubscriptionStatus.CANCELLED:
                subscription.cancelled_at = datetime.utcnow()
                subscription.cancellation_reason = data.get("cancellation_reason")

        # Handle billing interval
        if "billing_interval" in data:
            subscription.billing_interval = HQBillingInterval(data["billing_interval"])

        # Handle rates
        if "monthly_rate" in data:
            subscription.monthly_rate = Decimal(str(data["monthly_rate"]))
            new_mrr = subscription.monthly_rate
            subscription.current_mrr = new_mrr

        if "annual_rate" in data:
            subscription.annual_rate = Decimal(str(data["annual_rate"])) if data["annual_rate"] else None

        if "setup_fee_paid" in data:
            subscription.setup_fee_paid = data["setup_fee_paid"]

        # Log rate change if MRR changed
        if new_mrr is not None and new_mrr != old_mrr:
            rate_change = HQSubscriptionRateChange(
                id=str(uuid.uuid4()),
                subscription_id=subscription_id,
                previous_mrr=old_mrr,
                new_mrr=new_mrr,
                reason=data.get("rate_change_reason"),
                effective_date=datetime.utcnow(),
                changed_by_id=updated_by_id
            )
            self.db.add(rate_change)

        await self.db.commit()
        return await self.get_subscription(subscription_id)

    async def pause_subscription(
        self,
        subscription_id: str,
        reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Pause a subscription."""
        result = await self.db.execute(
            select(HQSubscription).where(HQSubscription.id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            return None

        subscription.status = HQSubscriptionStatus.PAUSED
        subscription.paused_at = datetime.utcnow()
        if reason:
            subscription.notes = f"{subscription.notes or ''}\n\nPaused: {reason}".strip()

        await self.db.commit()
        return await self.get_subscription(subscription_id)

    async def resume_subscription(
        self,
        subscription_id: str
    ) -> Optional[Dict[str, Any]]:
        """Resume a paused subscription."""
        result = await self.db.execute(
            select(HQSubscription).where(HQSubscription.id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            return None

        subscription.status = HQSubscriptionStatus.ACTIVE
        subscription.paused_at = None

        await self.db.commit()
        return await self.get_subscription(subscription_id)

    async def cancel_subscription(
        self,
        subscription_id: str,
        reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Cancel a subscription."""
        result = await self.db.execute(
            select(HQSubscription).where(HQSubscription.id == subscription_id)
        )
        subscription = result.scalar_one_or_none()
        if not subscription:
            return None

        subscription.status = HQSubscriptionStatus.CANCELLED
        subscription.cancelled_at = datetime.utcnow()
        subscription.cancellation_reason = reason

        await self.db.commit()
        return await self.get_subscription(subscription_id)

    async def get_mrr_summary(self) -> Dict[str, Any]:
        """Get MRR summary statistics."""
        # Total active MRR
        active_result = await self.db.execute(
            select(func.coalesce(func.sum(HQSubscription.current_mrr), 0))
            .where(HQSubscription.status == HQSubscriptionStatus.ACTIVE)
        )
        active_mrr = float(active_result.scalar() or 0)

        # Count by status
        status_counts = {}
        for status in HQSubscriptionStatus:
            count_result = await self.db.execute(
                select(func.count(HQSubscription.id))
                .where(HQSubscription.status == status)
            )
            status_counts[status.value] = count_result.scalar() or 0

        # Total subscriptions
        total_result = await self.db.execute(
            select(func.count(HQSubscription.id))
        )
        total_subscriptions = total_result.scalar() or 0

        return {
            "activeMrr": active_mrr,
            "totalSubscriptions": total_subscriptions,
            "statusCounts": status_counts
        }

    async def get_rate_changes(
        self,
        subscription_id: str
    ) -> List[Dict[str, Any]]:
        """Get rate change history for a subscription."""
        result = await self.db.execute(
            select(HQSubscriptionRateChange)
            .options(selectinload(HQSubscriptionRateChange.changed_by))
            .where(HQSubscriptionRateChange.subscription_id == subscription_id)
            .order_by(HQSubscriptionRateChange.created_at.desc())
        )
        changes = result.scalars().all()

        return [
            {
                "id": c.id,
                "previousMrr": float(c.previous_mrr) if c.previous_mrr else 0,
                "newMrr": float(c.new_mrr) if c.new_mrr else 0,
                "reason": c.reason,
                "effectiveDate": c.effective_date.isoformat() if c.effective_date else None,
                "changedById": c.changed_by_id,
                "changedByName": f"{c.changed_by.first_name} {c.changed_by.last_name}" if c.changed_by else None,
                "createdAt": c.created_at.isoformat() if c.created_at else None
            }
            for c in changes
        ]

    def _to_response(self, subscription: HQSubscription) -> Dict[str, Any]:
        """Convert subscription model to response dict."""
        tenant_name = None
        if subscription.tenant and subscription.tenant.company:
            tenant_name = subscription.tenant.company.name

        return {
            "id": subscription.id,
            "subscriptionNumber": subscription.subscription_number,
            "tenantId": subscription.tenant_id,
            "tenantName": tenant_name,
            "dealId": subscription.deal_id,
            "status": subscription.status.value if subscription.status else "active",
            "billingInterval": subscription.billing_interval.value if subscription.billing_interval else "monthly",
            "monthlyRate": float(subscription.monthly_rate) if subscription.monthly_rate else 0,
            "annualRate": float(subscription.annual_rate) if subscription.annual_rate else None,
            "currentMrr": float(subscription.current_mrr) if subscription.current_mrr else 0,
            "setupFee": float(subscription.setup_fee) if subscription.setup_fee else 0,
            "setupFeePaid": subscription.setup_fee_paid,
            "trialEndsAt": subscription.trial_ends_at.isoformat() if subscription.trial_ends_at else None,
            "startedAt": subscription.started_at.isoformat() if subscription.started_at else None,
            "pausedAt": subscription.paused_at.isoformat() if subscription.paused_at else None,
            "cancelledAt": subscription.cancelled_at.isoformat() if subscription.cancelled_at else None,
            "cancellationReason": subscription.cancellation_reason,
            "nextBillingDate": subscription.next_billing_date.isoformat() if subscription.next_billing_date else None,
            "truckLimit": subscription.truck_limit,
            "userLimit": subscription.user_limit,
            "notes": subscription.notes,
            "createdById": subscription.created_by_id,
            "createdAt": subscription.created_at.isoformat() if subscription.created_at else None,
            "updatedAt": subscription.updated_at.isoformat() if subscription.updated_at else None,
        }

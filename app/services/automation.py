from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation import AutomationRule as AutomationRuleModel
from app.models.company import Company
from app.schemas.automation import AutomationRuleCreate, AutomationRuleUpdate


class AutomationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_rules(self, company_id: str) -> List[AutomationRuleModel]:
        result = await self.db.execute(
            select(AutomationRuleModel)
            .where(AutomationRuleModel.company_id == company_id)
            .order_by(AutomationRuleModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_rule(
        self,
        company_id: str,
        payload: AutomationRuleCreate,
        plan_hint: Optional[str] = None,
    ) -> AutomationRuleModel:
        await self._enforce_plan_limit(company_id, plan_hint)

        rule = AutomationRuleModel(
            id=str(uuid.uuid4()),
            company_id=company_id,
            name=payload.name.strip(),
            trigger=payload.trigger,
            channels=list(payload.channels),
            recipients=self._normalize(payload.recipients),
            lead_time_days=payload.lead_time_days,
            threshold_value=payload.threshold_value,
            escalation_days=payload.escalation_days,
            is_active=True,
        )
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def update_rule(
        self,
        company_id: str,
        rule_id: str,
        payload: AutomationRuleUpdate,
    ) -> AutomationRuleModel:
        rule = await self._get_rule(company_id, rule_id)
        if payload.name is not None:
            rule.name = payload.name.strip()
        if payload.trigger is not None:
            rule.trigger = payload.trigger
        if payload.channels is not None:
            if not payload.channels:
                raise ValueError("Channels cannot be empty")
            rule.channels = list(payload.channels)
        if payload.recipients is not None:
            recipients = self._normalize(payload.recipients)
            if not recipients:
                raise ValueError("Recipients cannot be empty")
            rule.recipients = recipients
        if payload.lead_time_days is not None:
            rule.lead_time_days = payload.lead_time_days
        if payload.threshold_value is not None or payload.threshold_value == 0:
            rule.threshold_value = payload.threshold_value
        if payload.escalation_days is not None:
            rule.escalation_days = payload.escalation_days
        if payload.is_active is not None:
            rule.is_active = payload.is_active

        await self.db.commit()
        await self.db.refresh(rule)
        return rule

    async def delete_rule(self, company_id: str, rule_id: str) -> None:
        rule = await self._get_rule(company_id, rule_id)
        await self.db.delete(rule)
        await self.db.commit()

    async def _get_rule(self, company_id: str, rule_id: str) -> AutomationRuleModel:
        result = await self.db.execute(
            select(AutomationRuleModel).where(
                AutomationRuleModel.company_id == company_id,
                AutomationRuleModel.id == rule_id,
            )
        )
        rule = result.scalar_one_or_none()
        if not rule:
            raise ValueError("Automation rule not found")
        return rule

    async def _enforce_plan_limit(self, company_id: str, plan_hint: Optional[str]) -> None:
        plan = plan_hint or await self._fetch_subscription_plan(company_id)
        limit = self._plan_limit(plan)
        if limit is None:
            return
        result = await self.db.execute(
            select(AutomationRuleModel)
            .where(AutomationRuleModel.company_id == company_id)
            .limit(limit + 1)
        )
        count = len(result.scalars().all())
        if count >= limit:
            raise ValueError("Automation limit reached for subscription plan")

    async def _fetch_subscription_plan(self, company_id: str) -> Optional[str]:
        result = await self.db.execute(select(Company.subscriptionPlan).where(Company.id == company_id))
        return result.scalar_one_or_none()

    def _plan_limit(self, plan: Optional[str]) -> Optional[int]:
        normalized = (plan or "").lower()
        if normalized in {"enterprise", "enterprise_plus"}:
            return None
        if normalized in {"starter", "core"}:
            return 3
        if normalized in {"professional", "pro"}:
            return 10
        return 5

    def _normalize(self, recipients: List[str]) -> List[str]:
        return [recipient.strip() for recipient in recipients if recipient and recipient.strip()]


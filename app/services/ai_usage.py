from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_usage import AIUsageLog, AIUsageQuota


OperationType = Literal["ocr", "chat", "audit", "email_parse"]


class AIUsageService:
    """Service for tracking and limiting AI feature usage."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_quota(self, company_id: str) -> AIUsageQuota:
        """Get or create usage quota for a company."""
        result = await self.db.execute(
            select(AIUsageQuota).where(AIUsageQuota.company_id == company_id)
        )
        quota = result.scalar_one_or_none()

        if not quota:
            # Create default free tier quota
            quota = AIUsageQuota(
                id=str(uuid.uuid4()),
                company_id=company_id,
                current_month=datetime.utcnow().strftime("%Y-%m"),
                monthly_ocr_limit=25,  # Increased: regex fallback doesn't work well
                monthly_chat_limit=100,
                monthly_audit_limit=200,
                current_ocr_usage=0,
                current_chat_usage=0,
                current_audit_usage=0,
                plan_tier="free",
                is_unlimited="false",
            )
            self.db.add(quota)
            await self.db.commit()
            await self.db.refresh(quota)

        return quota

    async def check_and_update_quota(
        self,
        company_id: str,
        operation_type: OperationType,
    ) -> tuple[bool, str]:
        """
        Check if operation is allowed and update usage.

        Returns:
            (allowed: bool, message: str)
        """
        quota = await self.get_or_create_quota(company_id)
        current_month = datetime.utcnow().strftime("%Y-%m")

        # Reset usage if new month
        if quota.current_month != current_month:
            quota.current_month = current_month
            quota.current_ocr_usage = 0
            quota.current_chat_usage = 0
            quota.current_audit_usage = 0
            await self.db.commit()
            await self.db.refresh(quota)

        # Check if unlimited
        if quota.is_unlimited == "true":
            return True, "Unlimited plan"

        # Check limits based on operation type
        if operation_type == "ocr":
            if quota.current_ocr_usage >= quota.monthly_ocr_limit:
                return False, f"Monthly AI OCR limit reached ({quota.monthly_ocr_limit} documents). Manual entry required or upgrade for unlimited AI extraction."
            quota.current_ocr_usage += 1

        elif operation_type == "chat":
            if quota.current_chat_usage >= quota.monthly_chat_limit:
                return False, f"Monthly chat limit reached ({quota.monthly_chat_limit} messages). Upgrade plan for more."
            quota.current_chat_usage += 1

        elif operation_type == "audit":
            if quota.current_audit_usage >= quota.monthly_audit_limit:
                return False, f"Monthly audit limit reached ({quota.monthly_audit_limit} audits). Upgrade plan for more."
            quota.current_audit_usage += 1

        await self.db.commit()
        return True, "OK"

    async def log_usage(
        self,
        company_id: str,
        operation_type: OperationType,
        status: str = "success",
        tokens_used: int | None = None,
        cost_usd: float | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        user_id: str | None = None,
        error_message: str | None = None,
    ) -> AIUsageLog:
        """Log an AI usage event."""
        log = AIUsageLog(
            id=str(uuid.uuid4()),
            company_id=company_id,
            user_id=user_id,
            operation_type=operation_type,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            error_message=error_message,
        )
        self.db.add(log)
        await self.db.commit()
        return log

    async def get_usage_stats(self, company_id: str) -> dict:
        """Get current usage statistics for a company."""
        quota = await self.get_or_create_quota(company_id)

        return {
            "plan_tier": quota.plan_tier,
            "is_unlimited": quota.is_unlimited == "true",
            "current_month": quota.current_month,
            "ocr": {
                "used": quota.current_ocr_usage,
                "limit": quota.monthly_ocr_limit,
                "remaining": max(0, quota.monthly_ocr_limit - quota.current_ocr_usage),
            },
            "chat": {
                "used": quota.current_chat_usage,
                "limit": quota.monthly_chat_limit,
                "remaining": max(0, quota.monthly_chat_limit - quota.current_chat_usage),
            },
            "audit": {
                "used": quota.current_audit_usage,
                "limit": quota.monthly_audit_limit,
                "remaining": max(0, quota.monthly_audit_limit - quota.current_audit_usage),
            },
        }

    async def upgrade_plan(
        self,
        company_id: str,
        plan_tier: str,
        ocr_limit: int | None = None,
        chat_limit: int | None = None,
        audit_limit: int | None = None,
        is_unlimited: bool = False,
    ) -> AIUsageQuota:
        """Upgrade a company's AI usage plan."""
        quota = await self.get_or_create_quota(company_id)

        quota.plan_tier = plan_tier
        quota.is_unlimited = "true" if is_unlimited else "false"

        if ocr_limit is not None:
            quota.monthly_ocr_limit = ocr_limit
        if chat_limit is not None:
            quota.monthly_chat_limit = chat_limit
        if audit_limit is not None:
            quota.monthly_audit_limit = audit_limit

        await self.db.commit()
        await self.db.refresh(quota)
        return quota

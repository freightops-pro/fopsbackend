from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.services.ai_usage import AIUsageService

router = APIRouter()


async def _service(db: AsyncSession = Depends(get_db)) -> AIUsageService:
    return AIUsageService(db)


async def _company_id(current_user=Depends(deps.get_current_user)) -> str:
    return current_user.company_id


@router.get("/usage/stats")
async def get_usage_stats(
    company_id: str = Depends(_company_id),
    service: AIUsageService = Depends(_service),
) -> dict:
    """Get current AI usage statistics for the company."""
    return await service.get_usage_stats(company_id)


@router.get("/usage/quota")
async def get_quota(
    company_id: str = Depends(_company_id),
    service: AIUsageService = Depends(_service),
) -> dict:
    """Get current usage quota details."""
    quota = await service.get_or_create_quota(company_id)
    return {
        "plan_tier": quota.plan_tier,
        "is_unlimited": quota.is_unlimited == "true",
        "current_month": quota.current_month,
        "ocr": {
            "limit": quota.monthly_ocr_limit,
            "used": quota.current_ocr_usage,
            "remaining": max(0, quota.monthly_ocr_limit - quota.current_ocr_usage),
        },
        "chat": {
            "limit": quota.monthly_chat_limit,
            "used": quota.current_chat_usage,
            "remaining": max(0, quota.monthly_chat_limit - quota.current_chat_usage),
        },
        "audit": {
            "limit": quota.monthly_audit_limit,
            "used": quota.current_audit_usage,
            "remaining": max(0, quota.monthly_audit_limit - quota.current_audit_usage),
        },
    }

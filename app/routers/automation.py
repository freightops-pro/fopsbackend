from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.schemas.automation import (
    AutomationRuleCreate,
    AutomationRuleResponse,
    AutomationRuleUpdate,
    NotificationLogResponse,
)
from app.services.automation import AutomationService
from app.services.automation_evaluator import AutomationEvaluator
from app.services.notifications import build_channel_registry
from app.services.notification_log import NotificationLogService

router = APIRouter()


async def _company_context(current_user=Depends(deps.get_current_user)) -> tuple[str, str | None]:
    company_id = current_user.company_id
    plan = getattr(current_user.company, "subscriptionPlan", None) if hasattr(current_user, "company") else None
    return company_id, plan


@router.get("/rules", response_model=List[AutomationRuleResponse])
async def list_rules(
    ctx: tuple[str, str | None] = Depends(_company_context),
    db: AsyncSession = Depends(get_db),
) -> List[AutomationRuleResponse]:
    company_id, _ = ctx
    service = AutomationService(db)
    rules = await service.list_rules(company_id)
    return [AutomationRuleResponse.model_validate(rule) for rule in rules]


@router.post("/rules", response_model=AutomationRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: AutomationRuleCreate,
    ctx: tuple[str, str | None] = Depends(_company_context),
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleResponse:
    company_id, plan = ctx
    service = AutomationService(db)
    try:
        rule = await service.create_rule(company_id, payload, plan)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return AutomationRuleResponse.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=AutomationRuleResponse)
async def update_rule(
    rule_id: str,
    payload: AutomationRuleUpdate,
    ctx: tuple[str, str | None] = Depends(_company_context),
    db: AsyncSession = Depends(get_db),
) -> AutomationRuleResponse:
    company_id, _ = ctx
    service = AutomationService(db)
    try:
        rule = await service.update_rule(company_id, rule_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return AutomationRuleResponse.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_rule(
    rule_id: str,
    ctx: tuple[str, str | None] = Depends(_company_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    company_id, _ = ctx
    service = AutomationService(db)
    try:
        await service.delete_rule(company_id, rule_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/run", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def run_automation_evaluation(
    ctx: tuple[str, str | None] = Depends(_company_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    company_id, _ = ctx
    evaluator = AutomationEvaluator(db, build_channel_registry())
    result = await evaluator.evaluate_company(company_id)
    return {"sent": len(result.sent), "skipped": len(result.skipped), "failed": len(result.failed)}


@router.get("/logs", response_model=List[NotificationLogResponse])
async def list_notification_logs(
    rule_id: str | None = None,
    limit: int = 50,
    ctx: tuple[str, str | None] = Depends(_company_context),
    db: AsyncSession = Depends(get_db),
) -> List[NotificationLogResponse]:
    if limit <= 0 or limit > 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Limit must be between 1 and 200")
    company_id, _ = ctx
    log_service = NotificationLogService(db)
    logs = await log_service.list_logs(company_id, rule_id=rule_id, limit=limit)
    return [NotificationLogResponse.model_validate(log) for log in logs]


"""AI Task Management API Endpoints."""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.db import get_db
from app.models.ai_task import AITask
from app.services.annie_ai import AnnieAI
from app.services.atlas_ai import AtlasAI
from app.services.alex_ai import AlexAI


router = APIRouter()


# === Request/Response Schemas ===

class CreateAITaskRequest(BaseModel):
    """Request to create a new AI task."""
    agent_type: str  # annie, atlas, alex
    task_description: str
    input_data: Optional[dict] = None
    priority: str = "normal"  # low, normal, high, urgent


class AITaskResponse(BaseModel):
    """AI task response."""
    id: str
    agent_type: str
    task_description: str
    status: str
    progress_percent: int
    result: Optional[dict]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# === Endpoints ===

@router.post("/tasks", response_model=AITaskResponse)
async def create_ai_task(
    request: CreateAITaskRequest,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AITaskResponse:
    """
    Create and execute an AI task.

    The AI agent will autonomously plan and execute the task.
    """
    # Validate agent type
    if request.agent_type not in ["annie", "atlas", "alex"]:
        raise HTTPException(status_code=400, detail="Invalid agent_type. Must be: annie, atlas, or alex")

    # Create the task
    task = AITask(
        id=str(uuid.uuid4()),
        company_id=current_user.company_id,
        user_id=current_user.id,
        agent_type=request.agent_type,
        task_type="user_request",  # General user request
        task_description=request.task_description,
        input_data=request.input_data,
        priority=request.priority,
        status="queued",
        progress_percent=0,
        created_at=datetime.utcnow(),
    )

    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Execute the task based on agent type
    if request.agent_type == "annie":
        agent = AnnieAI(db)
        await agent.register_tools()

        # Execute in background (in production, use a task queue like Celery/Dramatiq)
        success, error = await agent.execute_task(
            task=task,
            company_id=current_user.company_id,
            user_id=current_user.id
        )

    elif request.agent_type == "atlas":
        agent = AtlasAI(db)
        await agent.register_tools()

        success, error = await agent.execute_task(
            task=task,
            company_id=current_user.company_id,
            user_id=current_user.id
        )

    elif request.agent_type == "alex":
        agent = AlexAI(db)
        await agent.register_tools()

        success, error = await agent.execute_task(
            task=task,
            company_id=current_user.company_id,
            user_id=current_user.id
        )

    # Refresh task to get updated status
    await db.refresh(task)

    return AITaskResponse.model_validate(task)


@router.get("/tasks/{task_id}", response_model=AITaskResponse)
async def get_ai_task(
    task_id: str,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AITaskResponse:
    """Get AI task status and results."""
    result = await db.execute(
        select(AITask).where(
            AITask.id == task_id,
            AITask.company_id == current_user.company_id
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return AITaskResponse.model_validate(task)


@router.get("/tasks", response_model=list[AITaskResponse])
async def list_ai_tasks(
    agent_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AITaskResponse]:
    """List AI tasks for the current company."""
    query = select(AITask).where(AITask.company_id == current_user.company_id)

    if agent_type:
        query = query.where(AITask.agent_type == agent_type)

    if status:
        query = query.where(AITask.status == status)

    query = query.order_by(AITask.created_at.desc()).limit(limit)

    result = await db.execute(query)
    tasks = result.scalars().all()

    return [AITaskResponse.model_validate(task) for task in tasks]


@router.post("/tasks/{task_id}/cancel")
async def cancel_ai_task(
    task_id: str,
    current_user=Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running AI task."""
    result = await db.execute(
        select(AITask).where(
            AITask.id == task_id,
            AITask.company_id == current_user.company_id
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel task with status: {task.status}")

    task.status = "cancelled"
    task.completed_at = datetime.utcnow()
    await db.commit()

    return {"status": "cancelled", "task_id": task_id}

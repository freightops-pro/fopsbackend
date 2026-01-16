"""HQ AI Task Manager API endpoints."""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.hq_ai_task import HQAITask, HQAITaskEvent, HQAITaskStatus, HQAIAgentType, HQAITaskEventType
from app.schemas.hq_ai_task import (
    AITaskCreate,
    AITaskResponse,
    AITaskUpdate,
    AITaskEventCreate,
    AITaskEventResponse,
)
from app.api.deps import get_current_hq_employee
from app.models.hq_employee import HQEmployee

router = APIRouter()


@router.get("/tasks", response_model=List[AITaskResponse])
def list_ai_tasks(
    status: Optional[str] = Query(None, description="Comma-separated list of statuses"),
    agent_type: Optional[HQAIAgentType] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: HQEmployee = Depends(get_current_hq_employee),
) -> List[AITaskResponse]:
    """List AI tasks with optional filtering."""
    query = db.query(HQAITask)

    # Filter by status
    if status:
        statuses = [s.strip() for s in status.split(",")]
        valid_statuses = []
        for s in statuses:
            try:
                valid_statuses.append(HQAITaskStatus(s))
            except ValueError:
                pass
        if valid_statuses:
            query = query.filter(HQAITask.status.in_(valid_statuses))

    # Filter by agent type
    if agent_type:
        query = query.filter(HQAITask.agent_type == agent_type)

    # Order by created_at desc
    query = query.order_by(HQAITask.created_at.desc())

    # Limit
    tasks = query.limit(limit).all()

    return [AITaskResponse.from_orm_model(t) for t in tasks]


@router.post("/tasks", response_model=AITaskResponse)
def create_ai_task(
    task_data: AITaskCreate,
    db: Session = Depends(get_db),
    current_user: HQEmployee = Depends(get_current_hq_employee),
) -> AITaskResponse:
    """Create a new AI task."""
    task = HQAITask(
        agent_type=task_data.agent_type,
        description=task_data.task_description,
        priority=task_data.priority,
        context_data=task_data.context_data,
        created_by_id=current_user.id,
        status=HQAITaskStatus.QUEUED,
        progress_percent=0,
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    # Add initial event
    event = HQAITaskEvent(
        task_id=task.id,
        event_type=HQAITaskEventType.THINKING,
        content=f"Task queued for {task_data.agent_type.value.title()} agent. Analyzing request...",
    )
    db.add(event)
    db.commit()

    return AITaskResponse.from_orm_model(task)


@router.get("/tasks/{task_id}", response_model=AITaskResponse)
def get_ai_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: HQEmployee = Depends(get_current_hq_employee),
) -> AITaskResponse:
    """Get a specific AI task."""
    task = db.query(HQAITask).filter(HQAITask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return AITaskResponse.from_orm_model(task)


@router.patch("/tasks/{task_id}", response_model=AITaskResponse)
def update_ai_task(
    task_id: str,
    task_update: AITaskUpdate,
    db: Session = Depends(get_db),
    current_user: HQEmployee = Depends(get_current_hq_employee),
) -> AITaskResponse:
    """Update an AI task (typically by the background worker)."""
    task = db.query(HQAITask).filter(HQAITask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Update fields
    if task_update.status is not None:
        task.status = task_update.status
        if task_update.status == HQAITaskStatus.IN_PROGRESS and not task.started_at:
            task.started_at = datetime.utcnow()
        elif task_update.status in [HQAITaskStatus.COMPLETED, HQAITaskStatus.FAILED]:
            task.completed_at = datetime.utcnow()

    if task_update.progress_percent is not None:
        task.progress_percent = task_update.progress_percent

    if task_update.result is not None:
        task.result = task_update.result

    if task_update.error is not None:
        task.error = task_update.error

    db.commit()
    db.refresh(task)

    return AITaskResponse.from_orm_model(task)


@router.delete("/tasks/{task_id}")
def delete_ai_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: HQEmployee = Depends(get_current_hq_employee),
):
    """Delete an AI task."""
    task = db.query(HQAITask).filter(HQAITask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()

    return {"message": "Task deleted"}


# ============ Task Events ============

@router.get("/tasks/{task_id}/events", response_model=List[AITaskEventResponse])
def list_task_events(
    task_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: HQEmployee = Depends(get_current_hq_employee),
) -> List[AITaskEventResponse]:
    """Get events for a specific task."""
    # Verify task exists
    task = db.query(HQAITask).filter(HQAITask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    events = (
        db.query(HQAITaskEvent)
        .filter(HQAITaskEvent.task_id == task_id)
        .order_by(HQAITaskEvent.timestamp.asc())
        .limit(limit)
        .all()
    )

    return [AITaskEventResponse.from_orm_model(e) for e in events]


@router.post("/tasks/{task_id}/events", response_model=AITaskEventResponse)
def create_task_event(
    task_id: str,
    event_data: AITaskEventCreate,
    db: Session = Depends(get_db),
    current_user: HQEmployee = Depends(get_current_hq_employee),
) -> AITaskEventResponse:
    """Add an event to a task (typically by the background worker)."""
    # Verify task exists
    task = db.query(HQAITask).filter(HQAITask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    event = HQAITaskEvent(
        task_id=task_id,
        event_type=event_data.event_type,
        content=event_data.content,
        metadata=event_data.metadata,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return AITaskEventResponse.from_orm_model(event)

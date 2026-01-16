"""Pydantic schemas for HQ AI Task Manager."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.models.hq_ai_task import HQAIAgentType, HQAITaskStatus, HQAITaskPriority, HQAITaskEventType


# ============ Task Schemas ============

class AITaskCreate(BaseModel):
    """Create a new AI task."""
    agent_type: HQAIAgentType
    task_description: str = Field(..., min_length=1, max_length=2000)
    priority: HQAITaskPriority = HQAITaskPriority.NORMAL
    context_data: Optional[dict] = None


class AITaskResponse(BaseModel):
    """AI task response."""
    id: str
    agentType: HQAIAgentType
    description: str
    status: HQAITaskStatus
    priority: HQAITaskPriority
    progressPercent: int
    result: Optional[str] = None
    error: Optional[str] = None
    createdAt: datetime
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    createdById: Optional[str] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_model(cls, task) -> "AITaskResponse":
        """Convert from SQLAlchemy model."""
        return cls(
            id=task.id,
            agentType=task.agent_type,
            description=task.description,
            status=task.status,
            priority=task.priority,
            progressPercent=task.progress_percent or 0,
            result=task.result,
            error=task.error,
            createdAt=task.created_at,
            startedAt=task.started_at,
            completedAt=task.completed_at,
            createdById=task.created_by_id,
        )


class AITaskUpdate(BaseModel):
    """Update an AI task."""
    status: Optional[HQAITaskStatus] = None
    progress_percent: Optional[int] = Field(None, ge=0, le=100)
    result: Optional[str] = None
    error: Optional[str] = None


# ============ Task Event Schemas ============

class AITaskEventCreate(BaseModel):
    """Create a task event."""
    event_type: HQAITaskEventType
    content: str
    metadata: Optional[dict] = None


class AITaskEventResponse(BaseModel):
    """Task event response."""
    id: str
    taskId: str
    eventType: HQAITaskEventType
    content: str
    timestamp: datetime
    metadata: Optional[dict] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_model(cls, event) -> "AITaskEventResponse":
        """Convert from SQLAlchemy model."""
        return cls(
            id=event.id,
            taskId=event.task_id,
            eventType=event.event_type,
            content=event.content,
            timestamp=event.timestamp,
            metadata=event.metadata,
        )


# ============ List Response ============

class AITaskListResponse(BaseModel):
    """List of AI tasks."""
    tasks: List[AITaskResponse]
    total: int


class AITaskEventListResponse(BaseModel):
    """List of task events."""
    events: List[AITaskEventResponse]

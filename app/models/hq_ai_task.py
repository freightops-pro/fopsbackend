"""HQ AI Task Manager models for background AI task processing."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Column, String, Text, DateTime, Enum, ForeignKey, Integer, JSON
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class HQAIAgentType(str, PyEnum):
    """AI Agent types."""
    ORACLE = "oracle"  # Strategic Insights
    SENTINEL = "sentinel"  # Security & Compliance
    NEXUS = "nexus"  # Operations Hub


class HQAITaskStatus(str, PyEnum):
    """Task status."""
    QUEUED = "queued"  # Waiting to be processed
    PLANNING = "planning"  # Agent is planning approach
    IN_PROGRESS = "in_progress"  # Agent is working on task
    COMPLETED = "completed"  # Task finished successfully
    FAILED = "failed"  # Task encountered an error


class HQAITaskPriority(str, PyEnum):
    """Task priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class HQAITask(Base):
    """
    Background AI task assigned by HQ employees.

    Tasks are processed asynchronously by AI agents (Oracle, Sentinel, Nexus).
    """
    __tablename__ = "hq_ai_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Agent and task details
    agent_type = Column(Enum(HQAIAgentType), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(Enum(HQAITaskPriority), nullable=False, default=HQAITaskPriority.NORMAL)
    status = Column(Enum(HQAITaskStatus), nullable=False, default=HQAITaskStatus.QUEUED)

    # Progress tracking
    progress_percent = Column(Integer, default=0)

    # Result data
    result = Column(Text, nullable=True)  # Final result/output from agent
    error = Column(Text, nullable=True)  # Error message if failed

    # Task context/metadata
    context_data = Column(JSON, nullable=True)  # Additional context for the agent

    # Who created this task
    created_by_id = Column(String(36), ForeignKey("hq_employee.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    created_by = relationship("HQEmployee", backref="created_ai_tasks")
    events = relationship("HQAITaskEvent", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<HQAITask {self.id} - {self.agent_type.value} - {self.status.value}>"


class HQAITaskEventType(str, PyEnum):
    """Task event types."""
    THINKING = "thinking"  # Agent is analyzing/planning
    ACTION = "action"  # Agent is executing an operation
    RESULT = "result"  # Agent produced output
    ERROR = "error"  # Agent encountered an issue


class HQAITaskEvent(Base):
    """
    Activity log entry for an AI task.

    Shows the agent's "thought process" as it works on a task.
    """
    __tablename__ = "hq_ai_task_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Link to task
    task_id = Column(String(36), ForeignKey("hq_ai_tasks.id", ondelete="CASCADE"), nullable=False)

    # Event details
    event_type = Column(Enum(HQAITaskEventType), nullable=False)
    content = Column(Text, nullable=False)  # What the agent is doing/thinking

    # Optional event data
    event_metadata = Column(JSON, nullable=True)  # Additional event-specific data

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    task = relationship("HQAITask", back_populates="events")

    def __repr__(self):
        return f"<HQAITaskEvent {self.id} - {self.event_type.value}>"

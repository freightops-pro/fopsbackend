"""AI Task and Execution Models."""
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, Index

from app.models.base import Base


class AITask(Base):
    """
    Autonomous AI task execution tracking.

    Each task represents a goal assigned to an AI agent (Annie, Atlas, or Alex).
    The AI agent autonomously plans steps, executes them, and reports completion.
    """
    __tablename__ = "ai_tasks"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)  # Who assigned the task

    # AI agent assigned to this task
    agent_type = Column(String, nullable=False)  # annie | atlas | alex

    # Task definition
    task_type = Column(String, nullable=False, index=True)  # load_creation | driver_assignment | monitoring | forecast | etc.
    task_description = Column(Text, nullable=False)  # Natural language description
    input_data = Column(JSON, nullable=True)  # Input parameters (file paths, IDs, etc.)

    # Task planning and execution
    planned_steps = Column(JSON, nullable=True)  # Array of steps the AI plans to execute
    current_step_index = Column(Integer, default=0)  # Current step being executed
    executed_steps = Column(JSON, nullable=True)  # Steps completed with results

    # Task status
    status = Column(String, default="queued", index=True)  # queued | planning | in_progress | completed | failed | cancelled
    priority = Column(String, default="normal")  # low | normal | high | urgent
    progress_percent = Column(Integer, default=0)  # 0-100

    # Results and errors
    result = Column(JSON, nullable=True)  # Final result/output
    error_message = Column(Text, nullable=True)  # Error if failed
    error_step = Column(Integer, nullable=True)  # Which step failed

    # Execution metadata
    ai_model = Column(String, nullable=True)  # gemini-2.5-flash, claude-3.5-sonnet, etc.
    total_tokens_used = Column(Integer, default=0)  # Total tokens across all AI calls
    total_cost_usd = Column(String, default="0.00")  # Total cost for this task
    tools_used = Column(JSON, nullable=True)  # List of tools/APIs called
    execution_time_seconds = Column(Integer, nullable=True)  # How long it took

    # Human review
    requires_review = Column(String, default="false")  # Does this need human approval before executing?
    reviewed_by = Column(String, nullable=True)  # User ID who reviewed
    review_decision = Column(String, nullable=True)  # approved | rejected | modified
    review_notes = Column(Text, nullable=True)

    # Scheduling
    scheduled_for = Column(DateTime, nullable=True)  # For future/recurring tasks
    deadline = Column(DateTime, nullable=True)  # When task must be completed by
    recurring = Column(String, default="false")  # Is this a recurring task?
    recurrence_rule = Column(String, nullable=True)  # Cron-like rule

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)  # When AI started working
    completed_at = Column(DateTime, nullable=True)  # When finished

    __table_args__ = (
        Index("idx_ai_tasks_company_status", "company_id", "status"),
        Index("idx_ai_tasks_agent_status", "agent_type", "status"),
        Index("idx_ai_tasks_priority", "priority", "status"),
        Index("idx_ai_tasks_scheduled", "scheduled_for"),
    )


class AIToolExecution(Base):
    """
    Individual tool/function calls made by AI agents.

    Tracks each tool execution for debugging, auditing, and learning.
    """
    __tablename__ = "ai_tool_executions"

    id = Column(String, primary_key=True)
    task_id = Column(String, nullable=False, index=True)  # Parent task
    company_id = Column(String, nullable=False, index=True)

    # Tool info
    tool_name = Column(String, nullable=False, index=True)  # create_load, send_email, etc.
    tool_category = Column(String, nullable=True)  # api | database | notification | calculation

    # Execution
    input_parameters = Column(JSON, nullable=False)  # What was passed to the tool
    output_result = Column(JSON, nullable=True)  # What the tool returned
    status = Column(String, nullable=False)  # success | failed | skipped
    error_message = Column(Text, nullable=True)

    # Performance
    execution_time_ms = Column(Integer, nullable=True)  # How long the tool took
    retry_count = Column(Integer, default=0)  # How many times we retried

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_ai_tool_executions_task", "task_id", "created_at"),
        Index("idx_ai_tool_executions_tool_status", "tool_name", "status"),
    )


class AILearning(Base):
    """
    AI learning and feedback loop.

    Tracks outcomes to improve AI decision-making over time.
    """
    __tablename__ = "ai_learning"

    id = Column(String, primary_key=True)
    company_id = Column(String, nullable=False, index=True)
    agent_type = Column(String, nullable=False, index=True)

    # What was learned
    learning_type = Column(String, nullable=False)  # driver_match | rate_prediction | exception_pattern | etc.
    context = Column(JSON, nullable=False)  # Situation/context
    ai_decision = Column(JSON, nullable=False)  # What AI decided/suggested
    actual_outcome = Column(JSON, nullable=False)  # What actually happened
    feedback_score = Column(Integer, nullable=True)  # -10 to +10 (negative = bad, positive = good)

    # Human feedback
    human_modified = Column(String, default="false")  # Did human change the AI's decision?
    modifications = Column(JSON, nullable=True)  # What they changed
    feedback_comment = Column(Text, nullable=True)  # Optional human explanation

    # Analysis
    accuracy_metric = Column(String, nullable=True)  # Specific metric for this learning type
    accuracy_value = Column(String, nullable=True)  # How accurate the AI was

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_ai_learning_agent_type", "agent_type", "learning_type"),
        Index("idx_ai_learning_company", "company_id", "created_at"),
    )

"""
Pydantic schemas for AI Insights
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class AISource(str, Enum):
    ANNIE = "annie"
    ALEX = "alex"
    ATLAS = "atlas"

class InsightType(str, Enum):
    SUGGESTION = "suggestion"
    ALERT = "alert"
    REPORT = "report"
    PREDICTION = "prediction"
    ANALYSIS = "analysis"
    REMINDER = "reminder"

class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class InsightStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"

class AIInsightBase(BaseModel):
    ai_source: AISource
    function_category: str
    insight_type: InsightType
    priority: Priority
    title: str
    description: str
    data: Optional[Dict[str, Any]] = None
    target_users: Optional[List[str]] = None

class AIInsightCreate(AIInsightBase):
    subscriber_id: str

class AIInsightUpdate(BaseModel):
    status: Optional[InsightStatus] = None
    dismissed_by: Optional[str] = None

class AIInsightResponse(AIInsightBase):
    id: str
    subscriber_id: str
    status: InsightStatus
    created_at: datetime
    dismissed_at: Optional[datetime] = None
    dismissed_by: Optional[str] = None

    class Config:
        from_attributes = True

class AIInsightSummary(BaseModel):
    """Summary of insights for dashboard"""
    total_insights: int
    pending_insights: int
    critical_insights: int
    insights_by_category: Dict[str, int]
    recent_insights: List[AIInsightResponse]

class AnnieChatMessage(BaseModel):
    content: str
    sender_type: str  # "user" or "ai"
    timestamp: datetime

class AnnieChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class AnnieChatResponse(BaseModel):
    conversation_id: str
    user_message: AnnieChatMessage
    annie_response: AnnieChatMessage

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Import enums from the model
from app.models.chat import (
    MessageType
)

# Request/Response Models for API

class ConversationCreateRequest(BaseModel):
    """Request model for creating a new 1-on-1 conversation"""
    other_participant_id: str = Field(..., description="ID of the participant to start a conversation with")
    other_participant_type: str = Field(..., description="Type of participant ('user' or 'driver')")

    @validator('other_participant_id')
    def validate_other_participant_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Other participant ID is required')
        return v.strip()
    
    @validator('other_participant_type')
    def validate_other_participant_type(cls, v):
        if v not in ['user', 'driver']:
            raise ValueError('Participant type must be "user" or "driver"')
        return v

class ConversationResponse(BaseModel):
    """Response model for conversation details"""
    id: str
    company_id: str
    participant1_id: str
    participant2_id: str
    participant1_type: str
    participant2_type: str
    last_message_at: Optional[datetime] = None
    message_count: int
    created_at: datetime
    updated_at: datetime
    created_by: str
    created_by_type: str
    is_active: bool

    class Config:
        from_attributes = True

class ConversationListResponse(BaseModel):
    """Response model for conversation list"""
    id: str
    other_participant_id: str
    other_participant_type: str
    other_participant_name: Optional[str] = None
    last_message_content: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int

class MessageCreateRequest(BaseModel):
    """Request model for creating a new message"""
    conversation_id: str
    content: str = Field(..., min_length=1, max_length=5000)
    message_type: MessageType = MessageType.TEXT
    reply_to_message_id: Optional[str] = None

    @validator('content')
    def validate_content(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Message content cannot be empty')
        return v.strip()

class MessageResponse(BaseModel):
    """Response model for message details"""
    id: str
    conversation_id: str
    sender_id: str
    sender_type: str
    company_id: str
    content: str
    message_type: MessageType
    reply_to_message_id: Optional[str] = None
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MessageWithDetailsResponse(MessageResponse):
    """Response model for message with additional details"""
    sender: Optional[Dict[str, Any]] = None  # Basic sender info
    reply_to_message: Optional[MessageResponse] = None
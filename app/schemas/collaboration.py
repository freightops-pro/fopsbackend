from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ChannelTypeEnum(str, Enum):
    DM = "dm"
    GROUP = "group"
    DRIVER = "driver"


class ParticipantResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    driver_id: Optional[str] = None
    display_name: str
    added_at: datetime

    model_config = {"from_attributes": True}


class ChannelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class GroupChatCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    participant_ids: List[str] = Field(..., min_length=1, description="List of user IDs to add to group")


class ChannelResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    channel_type: Optional[str] = "dm"
    participants: List[ParticipantResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    body: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    id: str
    channel_id: str
    author_id: str
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChannelDetailResponse(ChannelResponse):
    messages: List[MessageResponse]

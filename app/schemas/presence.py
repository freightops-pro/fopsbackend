from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


PresenceStatus = Literal["online", "away", "offline"]


class PresenceUpdate(BaseModel):
    """Update presence status."""
    status: PresenceStatus = "online"
    away_message: Optional[str] = Field(None, max_length=200)


class PresenceState(BaseModel):
    """Current presence state for a user."""
    user_id: str
    user_name: Optional[str] = None
    status: PresenceStatus
    away_message: Optional[str] = None
    last_seen_at: datetime
    last_activity_at: Optional[datetime] = None


class PresenceHeartbeat(BaseModel):
    """Activity heartbeat to update last_activity_at."""
    pass  # No fields needed, just confirms user is active


class SetAwayMessage(BaseModel):
    """Set or clear away message."""
    away_message: Optional[str] = Field(None, max_length=200)


from datetime import datetime

from pydantic import BaseModel


class PresenceUpdate(BaseModel):
    status: str = "online"


class PresenceState(BaseModel):
    user_id: str
    status: str
    last_seen_at: datetime


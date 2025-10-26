from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class RecordType(str, Enum):
    LOAD = "load"
    INVOICE = "invoice"
    SETTLEMENT = "settlement"
    CUSTOMER = "customer"
    DRIVER = "driver"
    VEHICLE = "vehicle"


class LockStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    RELEASED = "released"
    FORCE_TAKEN = "force_taken"


class RequestStatus(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    CANCELLED = "cancelled"


class ChangeType(str, Enum):
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    RESTORE = "restore"


# Write Lock Schemas

class WriteLockResponse(BaseModel):
    id: int
    record_type: RecordType
    record_id: str
    current_editor_id: int
    current_editor_name: Optional[str] = None
    current_editor_avatar: Optional[str] = None
    acquired_at: datetime
    last_activity_at: datetime
    is_active: bool
    lock_type: str
    
    class Config:
        from_attributes = True


class WriteLockRequestCreate(BaseModel):
    record_type: RecordType
    record_id: str
    message: Optional[str] = None


class WriteLockRequestResponse(BaseModel):
    id: int
    lock_id: int
    requester_id: int
    requester_name: Optional[str] = None
    requester_avatar: Optional[str] = None
    requested_at: datetime
    status: RequestStatus
    responded_at: Optional[datetime] = None
    response_by_id: Optional[int] = None
    message: Optional[str] = None
    
    class Config:
        from_attributes = True


class GrantAccessRequest(BaseModel):
    request_id: int
    grant: bool = True
    message: Optional[str] = None


# Record Viewer Schemas

class RecordViewerResponse(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    user_role: Optional[str] = None
    joined_at: datetime
    last_seen_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True


# Version History Schemas

class RecordVersionResponse(BaseModel):
    id: int
    version_number: int
    changes: Dict[str, Any]
    full_snapshot: Optional[Dict[str, Any]] = None
    changed_by_id: int
    changed_by_name: Optional[str] = None
    changed_at: datetime
    change_summary: Optional[str] = None
    change_type: ChangeType
    
    class Config:
        from_attributes = True


class CreateVersionRequest(BaseModel):
    record_type: RecordType
    record_id: str
    changes: Dict[str, Any]
    full_snapshot: Optional[Dict[str, Any]] = None
    change_summary: Optional[str] = None
    change_type: ChangeType = ChangeType.EDIT


class RollbackVersionRequest(BaseModel):
    version_id: int
    restore_fields: Optional[List[str]] = None  # Specific fields to restore


# Collaboration Message Schemas

class CollaborationMessageCreate(BaseModel):
    record_type: RecordType
    record_id: str
    message: str = Field(..., min_length=1, max_length=1000)
    mentions: Optional[List[int]] = None
    attachments: Optional[List[Dict[str, str]]] = None


class CollaborationMessageResponse(BaseModel):
    id: int
    sender_id: int
    sender_name: Optional[str] = None
    sender_avatar: Optional[str] = None
    message: str
    sent_at: datetime
    mentions: Optional[List[int]] = None
    attachments: Optional[List[Dict[str, str]]] = None
    is_system_message: bool = False
    
    class Config:
        from_attributes = True


# Real-time Event Schemas

class CollaborationEvent(BaseModel):
    event_type: str  # lock_acquired, lock_released, access_requested, etc.
    record_type: RecordType
    record_id: str
    user_id: int
    user_name: Optional[str] = None
    timestamp: datetime
    data: Optional[Dict[str, Any]] = None


class PresenceUpdate(BaseModel):
    record_type: RecordType
    record_id: str
    user_id: int
    user_name: str
    user_avatar: Optional[str] = None
    action: str  # joined, left, typing, stopped_typing


# Lock Management Schemas

class ForceTakeLockRequest(BaseModel):
    record_type: RecordType
    record_id: str
    reason: Optional[str] = None


class LockTransferRequest(BaseModel):
    target_user_id: int
    message: Optional[str] = None


# Analytics Schemas

class CollaborationMetrics(BaseModel):
    total_locks_acquired: int
    average_lock_duration_minutes: float
    most_contended_records: List[Dict[str, Any]]
    access_request_grant_rate: float
    active_collaborators: int
    period_start: datetime
    period_end: datetime


class RecordCollaborationSummary(BaseModel):
    record_type: RecordType
    record_id: str
    total_editors: int
    total_viewers: int
    total_versions: int
    last_modified: datetime
    current_lock_holder: Optional[str] = None
    active_viewers: List[str] = []

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import logging

from app.config.db import get_db
from app.routes.user import get_current_user
from app.models.userModels import Users as User
from app.schema.collaboration import (
    WriteLockResponse,
    WriteLockRequestCreate,
    WriteLockRequestResponse,
    GrantAccessRequest,
    RecordViewerResponse,
    RecordVersionResponse,
    CreateVersionRequest,
    RollbackVersionRequest,
    CollaborationMessageCreate,
    CollaborationMessageResponse,
    ForceTakeLockRequest,
    CollaborationMetrics,
    RecordCollaborationSummary
)
from app.services.collaboration_service import CollaborationService
from app.websocket.connection_manager import ConnectionManager

router = APIRouter(prefix="/api/collaboration", tags=["collaboration"])

def get_current_company_id(current_user: User = Depends(get_current_user)) -> int:
    """Get current user's company ID"""
    return current_user.company_id
logger = logging.getLogger(__name__)

# WebSocket connection manager
manager = ConnectionManager()

@router.get("/locks/{record_type}/{record_id}", response_model=WriteLockResponse)
async def get_lock_status(
    record_type: str,
    record_id: str,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get current write lock status for a record"""
    
    service = CollaborationService(db)
    lock = await service.get_write_lock_status(record_type, record_id, company_id)
    
    if not lock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active lock found"
        )
    
    return lock

@router.post("/locks/{record_type}/{record_id}")
async def acquire_write_lock(
    record_type: str,
    record_id: str,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Acquire write lock for a record"""
    
    service = CollaborationService(db)
    
    try:
        lock = await service.acquire_write_lock(
            record_type=record_type,
            record_id=record_id,
            user_id=current_user.id,
            company_id=company_id
        )
        
        # Notify other users about lock acquisition
        await manager.broadcast_to_record(
            record_type=record_type,
            record_id=record_id,
            message={
                "type": "lock_acquired",
                "data": {
                    "record_type": record_type,
                    "record_id": record_id,
                    "locked_by": {
                        "user_id": current_user.id,
                        "user_name": current_user.full_name,
                        "avatar": current_user.avatar_url
                    },
                    "acquired_at": lock.acquired_at.isoformat()
                }
            }
        )
        
        return lock
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )

@router.delete("/locks/{record_type}/{record_id}")
async def release_write_lock(
    record_type: str,
    record_id: str,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Release write lock for a record"""
    
    service = CollaborationService(db)
    success = await service.release_write_lock(
        record_type=record_type,
        record_id=record_id,
        user_id=current_user.id,
        company_id=company_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active lock found for this user"
        )
    
    # Notify other users about lock release
    await manager.broadcast_to_record(
        record_type=record_type,
        record_id=record_id,
        message={
            "type": "lock_released",
            "data": {
                "record_type": record_type,
                "record_id": record_id,
                "released_by": {
                    "user_id": current_user.id,
                    "user_name": current_user.full_name
                }
            }
        }
    )
    
    return {"message": "Lock released successfully"}

@router.post("/locks/{record_type}/{record_id}/request")
async def request_write_access(
    record_type: str,
    record_id: str,
    request_data: WriteLockRequestCreate,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Request write access to a locked record"""
    
    service = CollaborationService(db)
    
    try:
        request = await service.request_write_access(
            record_type=record_type,
            record_id=record_id,
            requester_id=current_user.id,
            company_id=company_id
        )
        
        # Notify current lock holder about the request
        lock = await service.get_write_lock_status(record_type, record_id, company_id)
        if lock:
            await manager.send_to_user(
                user_id=lock.current_editor_id,
                message={
                    "type": "access_requested",
                    "data": {
                        "request_id": request.id,
                        "record_type": record_type,
                        "record_id": record_id,
                        "requester": {
                            "user_id": current_user.id,
                            "user_name": current_user.full_name,
                            "avatar": current_user.avatar_url
                        },
                        "message": request_data.message,
                        "requested_at": request.requested_at.isoformat()
                    }
                }
            )
        
        return request
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/requests/{request_id}/respond")
async def respond_to_access_request(
    request_id: int,
    response_data: GrantAccessRequest,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Grant or deny write access request"""
    
    service = CollaborationService(db)
    
    try:
        if response_data.grant:
            lock = await service.grant_write_access(
                request_id=request_id,
                granter_id=current_user.id,
                company_id=company_id
            )
            
            # Notify requester about grant
            request = await service.get_request_by_id(request_id, company_id)
            if request:
                await manager.send_to_user(
                    user_id=request.requester_id,
                    message={
                        "type": "access_granted",
                        "data": {
                            "record_type": lock.record_type,
                            "record_id": lock.record_id,
                            "granted_by": {
                                "user_id": current_user.id,
                                "user_name": current_user.full_name
                            },
                            "message": response_data.message
                        }
                    }
                )
            
            return lock
            
        else:
            success = await service.deny_write_access(
                request_id=request_id,
                denier_id=current_user.id,
                company_id=company_id
            )
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Request not found"
                )
            
            # Notify requester about denial
            request = await service.get_request_by_id(request_id, company_id)
            if request:
                await manager.send_to_user(
                    user_id=request.requester_id,
                    message={
                        "type": "access_denied",
                        "data": {
                            "record_type": request.lock.record_type,
                            "record_id": request.lock.record_id,
                            "denied_by": {
                                "user_id": current_user.id,
                                "user_name": current_user.full_name
                            },
                            "message": response_data.message
                        }
                    }
                )
            
            return {"message": "Access request denied"}
            
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/locks/{record_type}/{record_id}/force-take")
async def force_take_lock(
    record_type: str,
    record_id: str,
    force_data: ForceTakeLockRequest,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Force take write lock (managers/admins only)"""
    
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to force take lock"
        )
    
    service = CollaborationService(db)
    
    try:
        lock = await service.force_take_lock(
            record_type=record_type,
            record_id=record_id,
            user_id=current_user.id,
            company_id=company_id,
            user_role=current_user.role
        )
        
        # Notify previous lock holder
        previous_lock = await service.get_previous_lock_holder(
            record_type=record_type,
            record_id=record_id,
            company_id=company_id
        )
        
        if previous_lock:
            await manager.send_to_user(
                user_id=previous_lock,
                message={
                    "type": "lock_force_taken",
                    "data": {
                        "record_type": record_type,
                        "record_id": record_id,
                        "taken_by": {
                            "user_id": current_user.id,
                            "user_name": current_user.full_name,
                            "role": current_user.role
                        },
                        "reason": force_data.reason
                    }
                }
            )
        
        # Broadcast to all viewers
        await manager.broadcast_to_record(
            record_type=record_type,
            record_id=record_id,
            message={
                "type": "lock_force_taken",
                "data": {
                    "record_type": record_type,
                    "record_id": record_id,
                    "taken_by": {
                        "user_id": current_user.id,
                        "user_name": current_user.full_name,
                        "role": current_user.role
                    }
                }
            }
        )
        
        return lock
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Record Viewer Endpoints

@router.post("/viewers/{record_type}/{record_id}")
async def register_viewer(
    record_type: str,
    record_id: str,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Register as a viewer of a record"""
    
    service = CollaborationService(db)
    viewer = await service.register_viewer(
        record_type=record_type,
        record_id=record_id,
        user_id=current_user.id,
        company_id=company_id
    )
    
    # Notify other viewers about new viewer
    await manager.broadcast_to_record(
        record_type=record_type,
        record_id=record_id,
        message={
            "type": "viewer_joined",
            "data": {
                "user_id": current_user.id,
                "user_name": current_user.full_name,
                "avatar": current_user.avatar_url,
                "joined_at": viewer.joined_at.isoformat()
            }
        }
    )
    
    return viewer

@router.delete("/viewers/{record_type}/{record_id}")
async def unregister_viewer(
    record_type: str,
    record_id: str,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Unregister as a viewer of a record"""
    
    service = CollaborationService(db)
    success = await service.unregister_viewer(
        record_type=record_type,
        record_id=record_id,
        user_id=current_user.id,
        company_id=company_id
    )
    
    if success:
        # Notify other viewers about viewer leaving
        await manager.broadcast_to_record(
            record_type=record_type,
            record_id=record_id,
            message={
                "type": "viewer_left",
                "data": {
                    "user_id": current_user.id,
                    "user_name": current_user.full_name
                }
            }
        )
    
    return {"message": "Viewer unregistered successfully"}

@router.get("/viewers/{record_type}/{record_id}", response_model=List[RecordViewerResponse])
async def get_active_viewers(
    record_type: str,
    record_id: str,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get all active viewers for a record"""
    
    service = CollaborationService(db)
    viewers = await service.get_active_viewers(
        record_type=record_type,
        record_id=record_id,
        company_id=company_id
    )
    
    return viewers

# Version History Endpoints

@router.post("/versions")
async def create_version(
    version_data: CreateVersionRequest,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Create a new version entry for record changes"""
    
    service = CollaborationService(db)
    version = await service.create_version(
        record_type=version_data.record_type,
        record_id=version_data.record_id,
        user_id=current_user.id,
        company_id=company_id,
        changes=version_data.changes,
        full_snapshot=version_data.full_snapshot,
        change_summary=version_data.change_summary
    )
    
    return version

@router.get("/versions/{record_type}/{record_id}", response_model=List[RecordVersionResponse])
async def get_version_history(
    record_type: str,
    record_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get version history for a record"""
    
    service = CollaborationService(db)
    versions = await service.get_version_history(
        record_type=record_type,
        record_id=record_id,
        company_id=company_id,
        limit=limit
    )
    
    return versions

# Collaboration Messages Endpoints

@router.post("/messages")
async def send_message(
    message_data: CollaborationMessageCreate,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Send a collaboration message"""
    
    service = CollaborationService(db)
    message = await service.send_message(
        record_type=message_data.record_type,
        record_id=message_data.record_id,
        sender_id=current_user.id,
        company_id=company_id,
        message=message_data.message,
        mentions=message_data.mentions,
        attachments=message_data.attachments
    )
    
    # Broadcast message to all viewers
    await manager.broadcast_to_record(
        record_type=message_data.record_type,
        record_id=message_data.record_id,
        message={
            "type": "new_message",
            "data": {
                "message_id": message.id,
                "sender": {
                    "user_id": current_user.id,
                    "user_name": current_user.full_name,
                    "avatar": current_user.avatar_url
                },
                "message": message.message,
                "sent_at": message.sent_at.isoformat(),
                "mentions": message.mentions,
                "attachments": message.attachments
            }
        }
    )
    
    return message

@router.get("/messages/{record_type}/{record_id}", response_model=List[CollaborationMessageResponse])
async def get_messages(
    record_type: str,
    record_id: str,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get collaboration messages for a record"""
    
    service = CollaborationService(db)
    messages = await service.get_messages(
        record_type=record_type,
        record_id=record_id,
        company_id=company_id,
        limit=limit
    )
    
    return messages

# WebSocket endpoint for real-time collaboration

@router.websocket("/ws/{record_type}/{record_id}")
async def websocket_collaboration(
    websocket: WebSocket,
    record_type: str,
    record_id: str,
    token: str
):
    """WebSocket endpoint for real-time collaboration"""
    
    # Authenticate user (simplified - in production, use proper JWT validation)
    # This is a placeholder - implement proper authentication
    user_id = 1  # Extract from JWT token
    
    await manager.connect(websocket, user_id, record_type, record_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle different message types
            if message_data["type"] == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            
            elif message_data["type"] == "typing_start":
                await manager.broadcast_to_record(
                    record_type=record_type,
                    record_id=record_id,
                    message={
                        "type": "user_typing",
                        "data": {
                            "user_id": user_id,
                            "typing": True
                        }
                    },
                    exclude_user=user_id
                )
            
            elif message_data["type"] == "typing_stop":
                await manager.broadcast_to_record(
                    record_type=record_type,
                    record_id=record_id,
                    message={
                        "type": "user_typing",
                        "data": {
                            "user_id": user_id,
                            "typing": False
                        }
                    },
                    exclude_user=user_id
                )
            
    except WebSocketDisconnect:
        await manager.disconnect(user_id, record_type, record_id)

# Analytics Endpoints

@router.get("/metrics", response_model=CollaborationMetrics)
async def get_collaboration_metrics(
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get collaboration metrics for the company"""
    
    service = CollaborationService(db)
    metrics = await service.get_collaboration_metrics(
        company_id=company_id
    )
    
    return metrics

@router.get("/summary/{record_type}/{record_id}", response_model=RecordCollaborationSummary)
async def get_record_collaboration_summary(
    record_type: str,
    record_id: str,
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Get collaboration summary for a specific record"""
    
    service = CollaborationService(db)
    summary = await service.get_record_collaboration_summary(
        record_type=record_type,
        record_id=record_id,
        company_id=company_id
    )
    
    return summary

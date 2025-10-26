from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import json

from app.models.collaboration import WriteLock, WriteLockRequest, RecordViewer, RecordVersion, CollaborationMessage
from app.models.userModels import Users
from app.schema.collaboration import (
    WriteLockResponse,
    WriteLockRequestCreate,
    RecordViewerResponse,
    RecordVersionResponse,
    CollaborationMessageCreate
)
import logging
logger = logging.getLogger(__name__)


class CollaborationService:
    """Service for managing real-time collaboration and write locks"""
    
    def __init__(self, db: Session):
        self.db = db
        self.IDLE_TIMEOUT_MINUTES = 10
        self.DISCONNECT_TIMEOUT_SECONDS = 30

    # Write Lock Management
    
    async def acquire_write_lock(
        self, 
        record_type: str, 
        record_id: str, 
        user_id: int, 
        company_id: int
    ) -> WriteLock:
        """Acquire write lock for a record"""
        
        # Clean up expired locks first
        await self._cleanup_expired_locks()
        
        # Check if lock already exists
        existing_lock = self.db.query(WriteLock).filter(
            and_(
                WriteLock.record_type == record_type,
                WriteLock.record_id == record_id,
                WriteLock.company_id == company_id,
                WriteLock.is_active == True
            )
        ).first()
        
        if existing_lock:
            # Check if same user
            if existing_lock.current_editor_id == user_id:
                # Refresh the lock
                existing_lock.last_activity_at = datetime.now(timezone.utc)
                self.db.commit()
                return existing_lock
            else:
                # Lock held by another user
                raise ValueError(f"Record is currently locked by user {existing_lock.current_editor_id}")
        
        # Create new lock
        lock = WriteLock(
            record_type=record_type,
            record_id=record_id,
            current_editor_id=user_id,
            company_id=company_id,
            is_active=True
        )
        
        self.db.add(lock)
        self.db.commit()
        self.db.refresh(lock)
        
        logger.info(f"Write lock acquired for {record_type}:{record_id} by user {user_id}")
        return lock

    async def release_write_lock(
        self, 
        record_type: str, 
        record_id: str, 
        user_id: int, 
        company_id: int
    ) -> bool:
        """Release write lock for a record"""
        
        lock = self.db.query(WriteLock).filter(
            and_(
                WriteLock.record_type == record_type,
                WriteLock.record_id == record_id,
                WriteLock.company_id == company_id,
                WriteLock.current_editor_id == user_id,
                WriteLock.is_active == True
            )
        ).first()
        
        if not lock:
            return False
        
        lock.is_active = False
        self.db.commit()
        
        logger.info(f"Write lock released for {record_type}:{record_id} by user {user_id}")
        return True

    async def get_write_lock_status(
        self, 
        record_type: str, 
        record_id: str, 
        company_id: int
    ) -> Optional[WriteLock]:
        """Get current write lock status for a record"""
        
        # Clean up expired locks first
        await self._cleanup_expired_locks()
        
        return self.db.query(WriteLock).filter(
            and_(
                WriteLock.record_type == record_type,
                WriteLock.record_id == record_id,
                WriteLock.company_id == company_id,
                WriteLock.is_active == True
            )
        ).first()

    async def request_write_access(
        self, 
        record_type: str, 
        record_id: str, 
        requester_id: int, 
        company_id: int
    ) -> WriteLockRequest:
        """Request write access to a locked record"""
        
        # Get current lock
        lock = await self.get_write_lock_status(record_type, record_id, company_id)
        
        if not lock:
            raise ValueError("No active lock found for this record")
        
        if lock.current_editor_id == requester_id:
            raise ValueError("You already have write access")
        
        # Check for existing pending request
        existing_request = self.db.query(WriteLockRequest).filter(
            and_(
                WriteLockRequest.lock_id == lock.id,
                WriteLockRequest.requester_id == requester_id,
                WriteLockRequest.status == "pending"
            )
        ).first()
        
        if existing_request:
            return existing_request
        
        # Create new request
        request = WriteLockRequest(
            lock_id=lock.id,
            requester_id=requester_id,
            company_id=company_id,
            status="pending"
        )
        
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        
        logger.info(f"Write access requested for {record_type}:{record_id} by user {requester_id}")
        return request

    async def grant_write_access(
        self, 
        request_id: int, 
        granter_id: int, 
        company_id: int
    ) -> WriteLock:
        """Grant write access request and transfer lock"""
        
        request = self.db.query(WriteLockRequest).filter(
            and_(
                WriteLockRequest.id == request_id,
                WriteLockRequest.company_id == company_id,
                WriteLockRequest.status == "pending"
            )
        ).first()
        
        if not request:
            raise ValueError("Request not found or already processed")
        
        lock = request.lock
        
        # Verify granter is current lock holder
        if lock.current_editor_id != granter_id:
            raise ValueError("Only the current lock holder can grant access")
        
        # Transfer lock
        old_editor_id = lock.current_editor_id
        lock.current_editor_id = request.requester_id
        lock.acquired_at = datetime.now(timezone.utc)
        lock.last_activity_at = datetime.now(timezone.utc)
        lock.lock_type = "edit"
        
        # Update request status
        request.status = "granted"
        request.responded_at = datetime.now(timezone.utc)
        request.response_by_id = granter_id
        
        self.db.commit()
        self.db.refresh(lock)
        
        logger.info(f"Write access granted: {old_editor_id} → {request.requester_id} for lock {lock.id}")
        return lock

    async def deny_write_access(
        self, 
        request_id: int, 
        denier_id: int, 
        company_id: int
    ) -> bool:
        """Deny write access request"""
        
        request = self.db.query(WriteLockRequest).filter(
            and_(
                WriteLockRequest.id == request_id,
                WriteLockRequest.company_id == company_id,
                WriteLockRequest.status == "pending"
            )
        ).first()
        
        if not request:
            return False
        
        lock = request.lock
        
        # Verify denier is current lock holder
        if lock.current_editor_id != denier_id:
            raise ValueError("Only the current lock holder can deny access")
        
        request.status = "denied"
        request.responded_at = datetime.now(timezone.utc)
        request.response_by_id = denier_id
        
        self.db.commit()
        
        logger.info(f"Write access denied for request {request_id}")
        return True

    async def force_take_lock(
        self, 
        record_type: str, 
        record_id: str, 
        user_id: int, 
        company_id: int,
        user_role: str
    ) -> WriteLock:
        """Force take write lock (managers/admins only)"""
        
        if user_role not in ["admin", "manager"]:
            raise ValueError("Insufficient permissions to force take lock")
        
        # Release existing lock
        existing_lock = await self.get_write_lock_status(record_type, record_id, company_id)
        
        if existing_lock:
            old_editor_id = existing_lock.current_editor_id
            existing_lock.is_active = False
            self.db.commit()
            
            logger.warning(f"Lock force-taken from user {old_editor_id} by {user_id}")
        
        # Acquire new lock
        lock = WriteLock(
            record_type=record_type,
            record_id=record_id,
            current_editor_id=user_id,
            company_id=company_id,
            is_active=True,
            lock_type="force_take"
        )
        
        self.db.add(lock)
        self.db.commit()
        self.db.refresh(lock)
        
        return lock

    async def _cleanup_expired_locks(self):
        """Clean up locks that have exceeded idle timeout"""
        
        timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=self.IDLE_TIMEOUT_MINUTES)
        
        expired_locks = self.db.query(WriteLock).filter(
            and_(
                WriteLock.is_active == True,
                WriteLock.last_activity_at < timeout_threshold
            )
        ).all()
        
        for lock in expired_locks:
            lock.is_active = False
            logger.info(f"Lock {lock.id} expired due to inactivity")
        
        if expired_locks:
            self.db.commit()

    # Record Viewer Management
    
    async def register_viewer(
        self, 
        record_type: str, 
        record_id: str, 
        user_id: int, 
        company_id: int
    ) -> RecordViewer:
        """Register a user as viewing a record"""
        
        # Check for existing viewer
        existing_viewer = self.db.query(RecordViewer).filter(
            and_(
                RecordViewer.record_type == record_type,
                RecordViewer.record_id == record_id,
                RecordViewer.user_id == user_id,
                RecordViewer.company_id == company_id,
                RecordViewer.is_active == True
            )
        ).first()
        
        if existing_viewer:
            existing_viewer.last_seen_at = datetime.now(timezone.utc)
            self.db.commit()
            return existing_viewer
        
        viewer = RecordViewer(
            record_type=record_type,
            record_id=record_id,
            user_id=user_id,
            company_id=company_id,
            is_active=True
        )
        
        self.db.add(viewer)
        self.db.commit()
        self.db.refresh(viewer)
        
        return viewer

    async def unregister_viewer(
        self, 
        record_type: str, 
        record_id: str, 
        user_id: int, 
        company_id: int
    ) -> bool:
        """Unregister a viewer from a record"""
        
        viewer = self.db.query(RecordViewer).filter(
            and_(
                RecordViewer.record_type == record_type,
                RecordViewer.record_id == record_id,
                RecordViewer.user_id == user_id,
                RecordViewer.company_id == company_id,
                RecordViewer.is_active == True
            )
        ).first()
        
        if viewer:
            viewer.is_active = False
            self.db.commit()
            return True
        
        return False

    async def get_active_viewers(
        self, 
        record_type: str, 
        record_id: str, 
        company_id: int
    ) -> List[RecordViewer]:
        """Get all active viewers for a record"""
        
        # Clean up stale viewers
        stale_threshold = datetime.now(timezone.utc) - timedelta(seconds=self.DISCONNECT_TIMEOUT_SECONDS)
        
        stale_viewers = self.db.query(RecordViewer).filter(
            and_(
                RecordViewer.record_type == record_type,
                RecordViewer.record_id == record_id,
                RecordViewer.company_id == company_id,
                RecordViewer.is_active == True,
                RecordViewer.last_seen_at < stale_threshold
            )
        ).all()
        
        for viewer in stale_viewers:
            viewer.is_active = False
        
        if stale_viewers:
            self.db.commit()
        
        # Return active viewers
        return self.db.query(RecordViewer).filter(
            and_(
                RecordViewer.record_type == record_type,
                RecordViewer.record_id == record_id,
                RecordViewer.company_id == company_id,
                RecordViewer.is_active == True
            )
        ).all()

    # Version History Management
    
    async def create_version(
        self, 
        record_type: str, 
        record_id: str, 
        user_id: int, 
        company_id: int,
        changes: Dict[str, Any],
        full_snapshot: Optional[Dict[str, Any]] = None,
        change_summary: Optional[str] = None
    ) -> RecordVersion:
        """Create a new version entry for record changes"""
        
        # Get current version number
        latest_version = self.db.query(RecordVersion).filter(
            and_(
                RecordVersion.record_type == record_type,
                RecordVersion.record_id == record_id,
                RecordVersion.company_id == company_id
            )
        ).order_by(RecordVersion.version_number.desc()).first()
        
        version_number = (latest_version.version_number + 1) if latest_version else 1
        
        version = RecordVersion(
            record_type=record_type,
            record_id=record_id,
            version_number=version_number,
            changes=changes,
            full_snapshot=full_snapshot,
            changed_by_id=user_id,
            change_summary=change_summary,
            company_id=company_id
        )
        
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        
        return version

    async def get_version_history(
        self, 
        record_type: str, 
        record_id: str, 
        company_id: int,
        limit: int = 50
    ) -> List[RecordVersion]:
        """Get version history for a record"""
        
        return self.db.query(RecordVersion).filter(
            and_(
                RecordVersion.record_type == record_type,
                RecordVersion.record_id == record_id,
                RecordVersion.company_id == company_id
            )
        ).order_by(RecordVersion.changed_at.desc()).limit(limit).all()

    # Collaboration Messages
    
    async def send_message(
        self, 
        record_type: str, 
        record_id: str, 
        sender_id: int, 
        company_id: int,
        message: str,
        mentions: Optional[List[int]] = None,
        attachments: Optional[List[Dict[str, str]]] = None
    ) -> CollaborationMessage:
        """Send a collaboration message"""
        
        msg = CollaborationMessage(
            record_type=record_type,
            record_id=record_id,
            sender_id=sender_id,
            message=message,
            mentions=mentions,
            attachments=attachments,
            company_id=company_id
        )
        
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        
        return msg

    async def get_messages(
        self, 
        record_type: str, 
        record_id: str, 
        company_id: int,
        limit: int = 100
    ) -> List[CollaborationMessage]:
        """Get collaboration messages for a record"""
        
        return self.db.query(CollaborationMessage).filter(
            and_(
                CollaborationMessage.record_type == record_type,
                CollaborationMessage.record_id == record_id,
                CollaborationMessage.company_id == company_id
            )
        ).order_by(CollaborationMessage.sent_at.desc()).limit(limit).all()


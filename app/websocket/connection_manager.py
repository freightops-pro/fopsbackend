from fastapi import WebSocket
from typing import Dict, List, Set, Optional
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time collaboration"""
    
    def __init__(self):
        # Active connections: {user_id: {record_type: {record_id: websocket}}}
        self.active_connections: Dict[int, Dict[str, Dict[str, WebSocket]]] = {}
        
        # Record viewers: {(record_type, record_id): Set[user_id]}
        self.record_viewers: Dict[tuple, Set[int]] = {}
        
        # User presence: {user_id: {"last_seen": datetime, "status": "online"}}
        self.user_presence: Dict[int, Dict] = {}

    async def connect(self, websocket: WebSocket, user_id: int, record_type: str, record_id: str):
        """Accept a new WebSocket connection and register the user"""
        
        await websocket.accept()
        
        # Initialize user connections if not exists
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
        
        if record_type not in self.active_connections[user_id]:
            self.active_connections[user_id][record_type] = {}
        
        # Store the connection
        self.active_connections[user_id][record_type][record_id] = websocket
        
        # Add to record viewers
        record_key = (record_type, record_id)
        if record_key not in self.record_viewers:
            self.record_viewers[record_key] = set()
        
        self.record_viewers[record_key].add(user_id)
        
        # Update user presence
        self.user_presence[user_id] = {
            "last_seen": datetime.now(timezone.utc),
            "status": "online"
        }
        
        logger.info(f"User {user_id} connected to {record_type}:{record_id}")
        
        # Notify other viewers about new connection
        await self.broadcast_to_record(
            record_type=record_type,
            record_id=record_id,
            message={
                "type": "user_joined",
                "data": {
                    "user_id": user_id,
                    "joined_at": datetime.now(timezone.utc).isoformat()
                }
            },
            exclude_user=user_id
        )

    async def disconnect(self, user_id: int, record_type: str, record_id: str):
        """Disconnect a user from a specific record"""
        
        record_key = (record_type, record_id)
        
        # Remove from active connections
        if (user_id in self.active_connections and 
            record_type in self.active_connections[user_id] and
            record_id in self.active_connections[user_id][record_type]):
            
            del self.active_connections[user_id][record_type][record_id]
            
            # Clean up empty record type
            if not self.active_connections[user_id][record_type]:
                del self.active_connections[user_id][record_type]
            
            # Clean up empty user
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        # Remove from record viewers
        if record_key in self.record_viewers:
            self.record_viewers[record_key].discard(user_id)
            
            # Clean up empty record viewers
            if not self.record_viewers[record_key]:
                del self.record_viewers[record_key]
        
        # Update user presence
        if user_id in self.user_presence:
            self.user_presence[user_id]["status"] = "offline"
            self.user_presence[user_id]["last_seen"] = datetime.now(timezone.utc)
        
        logger.info(f"User {user_id} disconnected from {record_type}:{record_id}")
        
        # Notify other viewers about disconnection
        await self.broadcast_to_record(
            record_type=record_type,
            record_id=record_id,
            message={
                "type": "user_left",
                "data": {
                    "user_id": user_id,
                    "left_at": datetime.now(timezone.utc).isoformat()
                }
            },
            exclude_user=user_id
        )

    async def disconnect_user(self, user_id: int):
        """Disconnect a user from all records"""
        
        if user_id not in self.active_connections:
            return
        
        # Get all records the user is viewing
        records_to_notify = []
        for record_type, records in self.active_connections[user_id].items():
            for record_id in records.keys():
                records_to_notify.append((record_type, record_id))
        
        # Disconnect from all records
        for record_type, record_id in records_to_notify:
            await self.disconnect(user_id, record_type, record_id)

    async def send_to_user(self, user_id: int, message: dict):
        """Send a message to a specific user (all their active connections)"""
        
        if user_id not in self.active_connections:
            return
        
        message_text = json.dumps(message)
        failed_connections = []
        
        for record_type, records in self.active_connections[user_id].items():
            for record_id, websocket in records.items():
                try:
                    await websocket.send_text(message_text)
                except Exception as e:
                    logger.error(f"Failed to send message to user {user_id}: {e}")
                    failed_connections.append((record_type, record_id))
        
        # Clean up failed connections
        for record_type, record_id in failed_connections:
            await self.disconnect(user_id, record_type, record_id)

    async def broadcast_to_record(
        self, 
        record_type: str, 
        record_id: str, 
        message: dict,
        exclude_user: Optional[int] = None
    ):
        """Broadcast a message to all users viewing a specific record"""
        
        record_key = (record_type, record_id)
        
        if record_key not in self.record_viewers:
            return
        
        message_text = json.dumps(message)
        failed_users = []
        
        for user_id in self.record_viewers[record_key]:
            if exclude_user and user_id == exclude_user:
                continue
            
            if (user_id in self.active_connections and
                record_type in self.active_connections[user_id] and
                record_id in self.active_connections[user_id][record_type]):
                
                websocket = self.active_connections[user_id][record_type][record_id]
                
                try:
                    await websocket.send_text(message_text)
                except Exception as e:
                    logger.error(f"Failed to broadcast to user {user_id}: {e}")
                    failed_users.append(user_id)
        
        # Clean up failed connections
        for user_id in failed_users:
            await self.disconnect(user_id, record_type, record_id)

    async def broadcast_to_company(self, company_id: int, message: dict):
        """Broadcast a message to all users in a company"""
        
        # This would require tracking company_id for each user
        # For now, broadcast to all active users
        message_text = json.dumps(message)
        failed_users = []
        
        for user_id in list(self.active_connections.keys()):
            try:
                await self.send_to_user(user_id, message)
            except Exception as e:
                logger.error(f"Failed to broadcast to company user {user_id}: {e}")
                failed_users.append(user_id)
        
        # Clean up failed connections
        for user_id in failed_users:
            await self.disconnect_user(user_id)

    def get_active_viewers(self, record_type: str, record_id: str) -> List[int]:
        """Get list of active viewers for a record"""
        
        record_key = (record_type, record_id)
        if record_key not in self.record_viewers:
            return []
        
        return list(self.record_viewers[record_key])

    def get_user_presence(self, user_id: int) -> Optional[dict]:
        """Get user presence information"""
        
        return self.user_presence.get(user_id)

    def get_online_users(self) -> List[int]:
        """Get list of currently online users"""
        
        return [
            user_id for user_id, presence in self.user_presence.items()
            if presence.get("status") == "online"
        ]

    async def ping_users(self):
        """Send ping to all connected users to check connection health"""
        
        ping_message = {"type": "ping", "timestamp": datetime.now(timezone.utc).isoformat()}
        failed_users = []
        
        for user_id in list(self.active_connections.keys()):
            try:
                await self.send_to_user(user_id, ping_message)
            except Exception as e:
                logger.error(f"Failed to ping user {user_id}: {e}")
                failed_users.append(user_id)
        
        # Clean up failed connections
        for user_id in failed_users:
            await self.disconnect_user(user_id)

    async def update_user_presence(self, user_id: int, status: str = "online"):
        """Update user presence status"""
        
        self.user_presence[user_id] = {
            "last_seen": datetime.now(timezone.utc),
            "status": status
        }

    def get_connection_stats(self) -> dict:
        """Get connection statistics"""
        
        total_users = len(self.active_connections)
        total_records = len(self.record_viewers)
        online_users = len(self.get_online_users())
        
        return {
            "total_users": total_users,
            "total_records": total_records,
            "online_users": online_users,
            "active_connections": sum(
                len(records) 
                for user_records in self.active_connections.values()
                for records in user_records.values()
            )
        }
